const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || response.statusText);
  }
  return response.json();
}

function pct(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function fmtSeconds(value) {
  const seconds = Number(value || 0);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.style.display = "block";
  setTimeout(() => (el.style.display = "none"), 3600);
}

function setBar(id, value) {
  $(id).style.width = `${Math.min(100, Math.max(0, Number(value || 0)))}%`;
}

async function refreshStatus() {
  const status = await api("/api/system/status");
  $("cpu").textContent = pct(status.cpu);
  $("memory").textContent = pct(status.memory);
  $("disk").textContent = pct(status.disk);
  $("checkpoint-count").textContent = status.checkpoint_count;
  $("recovery-count").textContent = status.recovery_count;
  $("cpu-small").textContent = pct(status.cpu);
  $("ram-small").textContent = pct(status.memory);
  $("disk-small").textContent = pct(status.disk);
  setBar("cpu-bar", status.cpu);
  setBar("ram-bar", status.memory);
  setBar("disk-bar", status.disk);
  $("health").textContent = status.system_health;
  $("health-dot").className = `dot ${status.system_health.toLowerCase()}`;

  const process = status.process || {};
  const state = process.state || {};
  $("process-name").textContent = process.name || "crashguard-demo";
  $("pid").textContent = process.pid || "--";
  $("process-status").textContent = process.status || "STOPPED";
  $("uptime").textContent = fmtSeconds(process.uptime);
  $("task").textContent = state.current_task || "--";
  $("progress").textContent = state.progress === undefined ? "--" : `${state.progress}%`;
  $("counter").textContent = state.counter === undefined ? "--" : state.counter;
}

async function refreshCheckpoints() {
  const rows = await api("/api/checkpoints");
  $("checkpoint-table").innerHTML = rows.map((cp) => `
    <tr>
      <td>${cp.checkpoint_id}</td>
      <td>${new Date(cp.timestamp).toLocaleTimeString()}</td>
      <td class="status-${cp.checkpoint_type}">${cp.checkpoint_type.toUpperCase()}</td>
      <td>${cp.state_size} B</td>
      <td>${Number(cp.storage_savings || 0).toFixed(1)}%</td>
      <td class="status-${cp.status}">${cp.status.toUpperCase()}</td>
      <td>
        <button data-restore="${cp.id}">Restore</button>
        <button data-delete="${cp.id}">Delete</button>
      </td>
    </tr>
  `).join("");
}

async function refreshRecovery() {
  const status = await api("/api/recovery/status");
  $("policy").value = status.policy || "latest";
  $("last-failure").textContent = status.last_failure || "--";
  $("checkpoint-used").textContent = status.checkpoint_used || "--";
  $("rto").textContent = status.rto === undefined ? "--" : `${status.rto}s`;
  $("recovery-status").textContent = status.status || "IDLE";

  const history = await api("/api/recovery/history");
  $("history-table").innerHTML = history.map((item) => `
    <tr>
      <td>#${String(item.id).padStart(3, "0")}</td>
      <td>${item.failure_type}</td>
      <td>${item.checkpoint_used || "--"}</td>
      <td>${item.rto}s</td>
      <td class="status-${String(item.recovery_status).toLowerCase()}">${item.recovery_status}</td>
    </tr>
  `).join("");
}

async function refreshEvents() {
  const events = await api("/api/events?limit=60");
  $("events").innerHTML = events.map((event) => `
    <div class="event-line">
      <span>${new Date(event.timestamp).toLocaleTimeString()}</span>
      <span>${event.level}</span>
      <span>${event.event_type}</span>
      <span>${event.message}</span>
      <span>${event.status || ""}</span>
    </div>
  `).join("");
}

async function refreshAll() {
  try {
    await Promise.all([refreshStatus(), refreshCheckpoints(), refreshRecovery(), refreshEvents()]);
  } catch (error) {
    toast(error.message);
  }
}

async function post(path, message) {
  await api(path, { method: "POST" });
  toast(message);
  await refreshAll();
}

document.body.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  try {
    const action = target.dataset.action;
    if (action === "startProcess") await post("/api/process/start", "Demo process started");
    if (action === "stopProcess") await post("/api/process/stop", "Demo process stopped");
    if (action === "createCheckpoint") await post("/api/checkpoints/create", "Checkpoint created");
    if (action === "crash") await post("/api/failure/crash", "Process crash triggered");
    if (action === "hang") await post("/api/failure/hang", "Process hang triggered");
    if (action === "corrupt") await post("/api/failure/corrupt", "State corruption triggered");
    if (action === "memory") await post("/api/failure/memory", "Memory stress triggered");
    if (action === "random") await post("/api/failure/random", "Random failure triggered");
    if (target.dataset.restore) await post(`/api/checkpoints/${target.dataset.restore}/restore`, "Checkpoint restored");
    if (target.dataset.delete) {
      await api(`/api/checkpoints/${target.dataset.delete}`, { method: "DELETE" });
      toast("Checkpoint deleted");
      await refreshAll();
    }
  } catch (error) {
    toast(error.message);
  }
});

$("policy").addEventListener("change", async (event) => {
  try {
    await api("/api/recovery/policy", {
      method: "POST",
      body: JSON.stringify({ policy: event.target.value }),
    });
    toast("Recovery policy updated");
    await refreshRecovery();
  } catch (error) {
    toast(error.message);
  }
});

refreshAll();
setInterval(refreshAll, 2500);
