const $ = id => document.getElementById(id);
let eventSource;
function showMessage(text, error = false) { $("message").textContent = text; $("message").style.color = error ? "#c03957" : "var(--deep)"; }
async function parseVideo() {
  const bv = $("bv").value.trim();
  if (!bv) return showMessage("请先输入 BV 号", true);
  $("parseBtn").disabled = true; showMessage("正在解析视频...");
  try {
    const response = await fetch("/api/parse", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({bv})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || "解析失败");
    $("bv").value = data.bv; $("videoInfo").textContent = `已识别：${data.title} · ${data.parts_hint}`;
    $("videoInfo").classList.remove("hidden"); showMessage("解析成功，可以开始下载");
  } catch (error) { showMessage(error.message, true); } finally { $("parseBtn").disabled = false; }
}
async function browseDirectory() {
  $("browseBtn").disabled = true;
  showMessage("正在打开文件夹选择器...");
  try {
    const response = await fetch("/api/select-directory", {method:"POST"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "无法选择保存目录");
    if (data.path) {
      $("targetDir").value = data.path;
      showMessage("已选择保存目录");
    } else {
      showMessage("已取消选择目录");
    }
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    $("browseBtn").disabled = false;
  }
}
async function startDownload() {
  const body = {bv:$("bv").value.trim(),target_dir:$("targetDir").value.trim(),parts:$("parts").value.trim(),name:$("name").value.trim(),remove_temp:$("removeTemp").checked};
  if (!body.bv || !body.target_dir || !body.parts) return showMessage("请填写 BV 号、保存目录和下载分P", true);
  $("startBtn").disabled = true; showMessage("正在创建下载任务...");
  try {
    const response = await fetch("/api/tasks",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || "创建任务失败");
    $("taskCard").classList.remove("hidden"); connectTask(data.id); showMessage("任务已加入队列");
  } catch (error) { showMessage(error.message, true); $("startBtn").disabled = false; }
}
function connectTask(id) {
  if (eventSource) eventSource.close(); eventSource = new EventSource(`/api/tasks/${id}/events`);
  eventSource.onmessage = event => {
    const task = JSON.parse(event.data), done = Number(task.completed_parts || 0), total = Number(task.total_parts || 0), part = Number(task.part_progress || 0);
    const overall = total ? Math.min(100, ((done + part / 100) / total) * 100) : 0;
    $("stage").textContent = task.stage || "等待开始"; $("count").textContent = `${done} / ${total}`; $("progressBar").style.width = `${overall}%`;
    $("taskStatus").textContent = task.status === "completed" ? "已完成" : task.status === "failed" ? "失败" : "进行中";
    if (task.error) { $("taskError").textContent = task.error; $("taskError").classList.remove("hidden"); }
    if (task.files?.length) $("files").innerHTML = task.files.map(file => `<div>✓ ${file}</div>`).join("");
    if (["completed","failed"].includes(task.status)) { eventSource.close(); $("startBtn").disabled = false; }
  };
  eventSource.onerror = () => { if (!$("taskError").textContent) showMessage("任务连接中断，请刷新查看状态", true); };
}
$("parseBtn").addEventListener("click", parseVideo);
$("browseBtn").addEventListener("click", browseDirectory);
$("startBtn").addEventListener("click", startDownload);
