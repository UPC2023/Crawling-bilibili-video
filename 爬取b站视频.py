import requests
import json
import re
from pprint import pprint
import os


def move_files(name, target_dir):
    """将文件移动到指定目录"""
    target_path = os.path.join(target_dir, name)
    # 创建新文件夹
    if not os.path.exists(target_path):
        os.makedirs(target_path)

    # 获取当前目录下的所有文件
    files = os.listdir('.')

    # 移动以name开头的文件到新文件夹
    for file in files:
        if file.startswith(name) and os.path.isfile(file):
            new_file_path = os.path.join(target_path, file)
            os.rename(file, new_file_path)
            print(f"Moved {file} to {new_file_path}")  # 打印移动信息

def delete_files(target_dir):
    """删除指定目录下的 .mp3 和 .mp4 文件（除了 _out.mp4）"""
    # 注意：这里修改为删除 *指定目录* 下的文件
    for filename in os.listdir(target_dir):
        if (filename.endswith('.mp3') or filename.endswith('.mp4')) and not filename.endswith('_out.mp4'):
            filepath = os.path.join(target_dir, filename)
            if os.path.isfile(filepath):  # 确保是文件
                try:
                    os.remove(filepath)
                    print(f"Deleted file: {filepath}")
                except Exception as e:
                    print(f"Error deleting file {filepath}: {e}")


# 修改 download 函数，增加 target_dir 参数
def download(BV, name, i, target_dir="."):  # 默认保存在当前目录
    url = f'https://www.bilibili.com/video/{BV}?spm_id_from=333.788.videopod.episodes&vd_source=5582e4daba3923b421f451b7a651fb63&p={i}'

    # 设置请求头
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.76",
        "Referer": "https://www.bilibili.com/",  # 设置防盗链
    }

    resp = requests.get(url=url, headers=header)
    if resp.status_code != 200:
        print("Failed to retrieve the webpage.")
        exit()

    # 这个baseUrl就是视频的地址
    obj = re.compile(r'window.__playinfo__=(.*?)</script>', re.S)
    html_data = obj.findall(resp.text)[0]  # 从列表转换为字符串
    json_data = json.loads(html_data)

    # 获取视频和音频地址
    videos = json_data['data']['dash']['video']  # 这里得到的是一个列表
    audios = json_data['data']['dash']['audio']

    if not videos or not audios:
        print("Failed to find video or audio URLs.")
        exit()

    video_url = videos[0]['baseUrl']  # 视频地址
    audio_url = audios[0]['baseUrl']  # 音频地址

    # 构建完整文件路径
    video_filename = f'{name}{i}.mp4'
    audio_filename = f'{name}{i}.mp3'
    output_filename = f'{name}{i}_out.mp4'

    video_path = os.path.join(target_dir, video_filename)
    audio_path = os.path.join(target_dir, audio_filename)
    output_path = os.path.join(target_dir, output_filename)

    # 下载视频文件
    resp1 = requests.get(url=video_url, headers=header)
    with open(video_path, mode='wb') as f:  # 使用完整路径
        f.write(resp1.content)
    print(f"Downloaded video to: {video_path}")

    # 下载音频文件
    resp2 = requests.get(url=audio_url, headers=header)
    with open(audio_path, mode='wb') as f:  # 使用完整路径
        f.write(resp2.content)
    print(f"Downloaded audio to: {audio_path}")

    print("Download complete")

    # 现在需要将视频和音频合并 需要模块ffmpeg 可以在网上看教程
    # 注意：ffmpeg命令中的路径也需要是完整的路径
    command = f'ffmpeg -i "{video_path}" -i "{audio_path}" -acodec copy -vcodec copy "{output_path}"'
    os.system(command)

    print(f"Merge complete, output to: {output_path}")

def parse_selection(sel_str):
    """解析用户输入的下载选择，返回整数列表。
    支持格式：
    - 单个数字：'5' -> [5]
    - 范围：'1-3' -> [1,2,3]（包含两端）
    - 逗号分隔的多个项：'1,3,5-7' -> [1,3,5,6,7]
    """
    indices = []
    parts = sel_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            a, b = map(int, part.split('-'))
            indices.extend(range(a, b + 1))
        else:
            indices.append(int(part))
    return indices


# --- 主程序 ---
BV = input("BV: ")
name = input("name: ")
target_dir = input("请输入保存路径 (留空则保存在当前目录): ").strip() or "."
sel_input = input("请输入要下载的p数，支持单个数字(如1)、范围(如1-2)或用逗号分隔(如1,3,5): ")
indices = parse_selection(sel_input)

while BV != "0":
    # 确保目标目录存在
    os.makedirs(target_dir, exist_ok=True)

    for i in indices:
        download(BV, name, i, target_dir)  # 传递 target_dir 参数
    f = int(input("是否删除合并前文件，是1否0: "))
    if f == 1:
        # 注意：delete_files 现在会删除 target_dir 下的文件
        delete_files(target_dir)
    f2 = int(input("是否整合为文件夹，是1否0: "))
    if f2 == 1:
        # 注意：move_files 现在会将文件移动到 target_dir 下的子目录
        move_files(name, target_dir)
    BV = input("BV: ")
    name = input("name: ")
    target_dir = input("请输入保存路径 (留空则保存在当前目录): ").strip() or "."
    sel_input = input("请输入要下载的p数，支持单个数字(如1)、范围(如1-2)或用逗号分隔(如1,3,5): ")
    indices = parse_selection(sel_input)
