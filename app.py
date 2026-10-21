import json
import re
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=2)
tasks = {}
tasks_lock = threading.Lock()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/118.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def clean_filename(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip()
    return value[:100] or "bilibili_video"


def normalize_bv(value):
    match = re.search(r"(BV[a-zA-Z0-9]+)", value.strip())
    if not match:
        raise ValueError("请输入有效的 BV 号或 B 站视频链接")
    return match.group(1)


def parse_selection(value):
    result = set()
    if not value or not value.strip():
        raise ValueError("请输入要下载的分P，例如 1、1-3 或 1,3,5-7")
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            pieces = part.split("-")
            if len(pieces) != 2:
                raise ValueError(f"无法识别分P范围：{part}")
            start, end = (int(item.strip()) for item in pieces)
            if start < 1 or end < start or end - start > 200:
                raise ValueError(f"分P范围无效：{part}")
            result.update(range(start, end + 1))
        else:
            number = int(part)
            if number < 1:
                raise ValueError("分P编号必须从 1 开始")
            result.add(number)
    if not result:
        raise ValueError("没有可下载的分P")
    return sorted(result)


def fetch_playinfo(bv, part):
    response = requests.get(f"https://www.bilibili.com/video/{bv}?p={part}", headers=HEADERS, timeout=20)
    response.raise_for_status()
    match = re.search(r"window\.__playinfo__=(.*?)</script>", response.text, re.S)
    if not match:
        raise RuntimeError("没有找到视频播放信息，可能需要登录或 B 站页面结构已变化")
    try:
        data = json.loads(match.group(1))
        dash = data["data"]["dash"]
        videos, audios = dash["video"], dash["audio"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("B站返回的数据格式无法识别") from exc
    if not videos or not audios:
        raise RuntimeError("没有找到可用的视频或音频流")
    title_match = re.search(r"<title>(.*?)</title>", response.text, re.S)
    title = re.sub(r"\s+", " ", title_match.group(1)).replace("_哔哩哔哩_bilibili", "").strip() if title_match else bv
    return {
        "title": title or bv,
        "video_url": videos[0].get("baseUrl") or videos[0].get("base_url"),
        "audio_url": audios[0].get("baseUrl") or audios[0].get("base_url"),
    }


def update_task(task_id, **values):
    with tasks_lock:
        tasks[task_id].update(values)


def download_stream(url, destination, task_id, part, kind):
    response = requests.get(url, headers=HEADERS, stream=True, timeout=(20, 60))
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    received = 0
    with destination.open("wb") as output:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            output.write(chunk)
            received += len(chunk)
            progress = round(received / total * 100, 1) if total else 0
            update_task(task_id, current_part=part, stage=f"正在下载{kind}", part_progress=progress)


def run_download(task_id, payload):
    target_dir = Path(payload["target_dir"]).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        bv = normalize_bv(payload["bv"])
        parts = parse_selection(payload["parts"])
        name = clean_filename(payload.get("name") or bv)
        remove_temp = bool(payload.get("remove_temp"))
        results = []
        for part in parts:
            update_task(task_id, status="running", current_part=part, stage="正在解析视频", part_progress=0)
            info = fetch_playinfo(bv, part)
            prefix = f"{name}{part}"
            video_path, audio_path = target_dir / f"{prefix}.mp4", target_dir / f"{prefix}.mp3"
            output_path = target_dir / f"{prefix}_out.mp4"
            update_task(task_id, title=info["title"])
            download_stream(info["video_url"], video_path, task_id, part, "视频")
            download_stream(info["audio_url"], audio_path, task_id, part, "音频")
            update_task(task_id, stage="正在合并音视频", part_progress=100)
            completed = subprocess.run(
                ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
                 "-acodec", "copy", "-vcodec", "copy", str(output_path)],
                capture_output=True, check=False,
            )
            if completed.returncode != 0:
                stderr = completed.stderr.decode("utf-8", errors="replace") if completed.stderr else ""
                error = stderr.strip().splitlines()[-1] if stderr.strip() else "FFmpeg 合并失败"
                raise RuntimeError(error)
            if remove_temp:
                video_path.unlink(missing_ok=True)
                audio_path.unlink(missing_ok=True)
            results.append(str(output_path))
            update_task(task_id, completed_parts=len(results), total_parts=len(parts))
        update_task(task_id, status="completed", stage="全部下载完成", part_progress=100, files=results)
    except Exception as exc:
        update_task(task_id, status="failed", stage="下载失败", error=str(exc))


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/select-directory")
def select_directory():
    """Open a native Windows folder picker for this local-only application."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="选择视频保存目录")
        root.destroy()
        return jsonify({"path": selected})
    except Exception as exc:
        return jsonify({"error": f"无法打开文件夹选择器：{exc}"}), 500


@app.post("/api/parse")
def parse_video():
    body = request.get_json(silent=True) or {}
    try:
        bv = normalize_bv(body.get("bv", ""))
        info = fetch_playinfo(bv, 1)
        return jsonify({"bv": bv, "title": info["title"], "parts_hint": "已解析第 1 P，可输入范围下载"})
    except (ValueError, requests.RequestException, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/tasks")
def create_task():
    body = request.get_json(silent=True) or {}
    try:
        normalize_bv(body.get("bv", ""))
        parts = parse_selection(body.get("parts", ""))
        if not body.get("target_dir", "").strip():
            raise ValueError("请选择保存目录")
        task_id = uuid.uuid4().hex
        task = {
            "id": task_id, "status": "queued", "stage": "等待开始",
            "title": body.get("name") or body.get("bv"), "current_part": None,
            "part_progress": 0, "completed_parts": 0, "total_parts": len(parts), "files": [],
        }
        with tasks_lock:
            tasks[task_id] = task
        executor.submit(run_download, task_id, body)
        return jsonify(task), 202
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/api/tasks/<task_id>")
def get_task(task_id):
    with tasks_lock:
        task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task)


@app.get("/api/tasks/<task_id>/events")
def task_events(task_id):
    def stream():
        last = ""
        while True:
            with tasks_lock:
                task = tasks.get(task_id)
            if not task:
                yield "event: error\ndata: 任务不存在\n\n"
                return
            current = json.dumps(task, ensure_ascii=False)
            if current != last:
                yield f"data: {current}\n\n"
                last = current
            if task["status"] in {"completed", "failed"}:
                return
            threading.Event().wait(0.6)
    return Response(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
