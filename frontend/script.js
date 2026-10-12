/**
 * CRASHGUARD ENGINEERING CONSOLE
 * Multi-page architecture, live psutil telemetry, canvas charts, checkpoint validation & recovery supervisor.
 */

// Simple Charting Utility using 2D Canvas for strict zero-dependency, high-density performance
class OsChart {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
    this.options = {
      maxPoints: 30,
      minY: 0,
      maxY: 100,
      unit: "%",
      color1: "#38bdf8",
      color2: "#22c55e",
      ...options,
    };
    this.series1 = [];
    this.series2 = [];
    this.labels = [];
    this._initCanvas();
  }

  _initCanvas() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    this.width = rect.width || 400;
    this.height = rect.height || 160;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    if (this.ctx) {
      this.ctx.scale(dpr, dpr);
    }
  }

  push(val1, val2 = null, label = "") {
    if (!this.ctx) return;
    this.series1.push(val1);
    if (this.series1.length > this.options.maxPoints) this.series1.shift();

    if (val2 !== null) {
      this.series2.push(val2);
      if (this.series2.length > this.options.maxPoints) this.series2.shift();
    }

    this.labels.push(label);
    if (this.labels.length > this.options.maxPoints) this.labels.shift();

    this.render();
  }

  setData(s1, s2 = [], labels = []) {
    this.series1 = [...s1];
    this.series2 = [...s2];
    this.labels = [...labels];
    this.render();
  }

  render() {
    if (!this.ctx) return;
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;
    const padding = { top: 15, right: 15, bottom: 25, left: 35 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    ctx.clearRect(0, 0, w, h);

    // Background & subtle grid
    ctx.fillStyle = "#0c1017";
    ctx.fillRect(padding.left, padding.top, chartW, chartH);

    ctx.strokeStyle = "#1b2330";
    ctx.lineWidth = 1;

    // Grid lines (3 horizontal levels)
    const levels = 3;
    ctx.font = "9.5px 'JetBrains Mono', Consolas, monospace";
    ctx.fillStyle = "#545d68";
    ctx.textAlign = "right";

    const computedMax = this.options.autoMax
      ? Math.max(1, ...this.series1, ...this.series2) * 1.15
      : this.options.maxY;
    const minVal = this.options.minY;

    for (let i = 0; i <= levels; i++) {
      const y = padding.top + (chartH / levels) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(w - padding.right, y);
      ctx.stroke();

      const labelVal = Math.round(computedMax - ((computedMax - minVal) / levels) * i);
      ctx.fillText(`${labelVal}${this.options.unit}`, padding.left - 4, y + 3);
    }

    // Draw series
    const drawLine = (data, color) => {
      if (!data || data.length < 2) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      data.forEach((val, idx) => {
        const x = padding.left + (chartW / (data.length - 1)) * idx;
        const norm = Math.min(1, Math.max(0, (val - minVal) / (computedMax - minVal || 1)));
        const y = padding.top + chartH * (1 - norm);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Point dots
      ctx.fillStyle = color;
      data.forEach((val, idx) => {
        const x = padding.left + (chartW / (data.length - 1)) * idx;
        const norm = Math.min(1, Math.max(0, (val - minVal) / (computedMax - minVal || 1)));
        const y = padding.top + chartH * (1 - norm);
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fill();
      });
    };

    drawLine(this.series1, this.options.color1);
    if (this.series2.length > 0) {
      drawLine(this.series2, this.options.color2);
    }
  }
}

// Global Application Controller
const App = {
  activePage: "overview",
  refreshInterval: null,
  cachedCheckpoints: [],
  selectedCheckpointId: null,
  charts: {},

  // Navigation Titles
  pageTitles: {
    overview: "COMMAND CENTER / OPERATIONAL OVERVIEW",
    analytics: "SYSTEM ANALYTICS & RECOVERY BENCHMARKS",
    visualizer: "RESOURCE TELEMETRY & SUBPROCESS VISUALIZER",
    checkpoints: "CHECKPOINT CATALOG & CRYPTOGRAPHIC VALIDATION",
    recovery: "FAULT-TOLERANCE SUPERVISOR & RECOVERY CENTER",
    "failure-lab": "ISOLATED PROCESS FAULT INJECTION LAB",
    events: "EVENT LOGS & RECOVERY AUDIT AUDIT TRAIL",
    configuration: "RUNTIME THRESHOLDS & ENGINE SETTINGS",
  },

  async init() {
    this.setupNavigation();
    this.setupCharts();
    this.bindEvents();

    // Read initial hash route if present
    const initialRoute = window.location.hash.replace("#", "") || "overview";
    this.navigate(initialRoute);

    // Initial load
    await this.refreshAll();

    // Start background polling (2.5s for operational responsiveness)
    this.refreshInterval = setInterval(() => this.refreshAll(), 2500);
  },

  setupNavigation() {
    window.addEventListener("hashchange", () => {
      const page = window.location.hash.replace("#", "") || "overview";
      this.navigate(page);
    });

    document.querySelectorAll(".nav-link").forEach((link) => {
      link.addEventListener("click", (e) => {
        const page = link.getAttribute("data-page");
        if (page) {
          this.navigate(page);
        }
      });
    });
  },

  navigate(pageId) {
    if (!this.pageTitles[pageId]) pageId = "overview";
    this.activePage = pageId;

    // Update active navigation link
    document.querySelectorAll(".nav-link").forEach((link) => {
      link.classList.toggle("active", link.getAttribute("data-page") === pageId);
    });

    // Update view panels
    document.querySelectorAll(".page-view").forEach((view) => {
      view.classList.toggle("active", view.id === `page-${pageId}`);
    });

    // Update Header
    const heading = document.getElementById("page-heading");
    if (heading) heading.textContent = this.pageTitles[pageId];

    // Trigger page-specific chart resize / refresh
    setTimeout(() => {
      if (pageId === "analytics") {
        if (this.charts.rto) this.charts.rto._initCanvas();
        if (this.charts.checkpoints) this.charts.checkpoints._initCanvas();
        this.refreshAnalytics();
      } else if (pageId === "visualizer") {
        if (this.charts.liveSystem) this.charts.liveSystem._initCanvas();
        if (this.charts.liveProcess) this.charts.liveProcess._initCanvas();
      } else if (pageId === "events") {
        this.refreshEventsPage();
      } else if (pageId === "configuration") {
        this.refreshConfigPage();
      }
    }, 50);
  },

  setupCharts() {
    this.charts.liveSystem = new OsChart("chart-live-system", {
      maxPoints: 25,
      maxY: 100,
      unit: "%",
      color1: "#38bdf8", // CPU
      color2: "#22c55e", // RAM
    });

    this.charts.liveProcess = new OsChart("chart-live-process", {
      maxPoints: 25,
      autoMax: true,
      unit: " MB",
      color1: "#38bdf8",
    });

    this.charts.rto = new OsChart("chart-rto", {
      maxPoints: 15,
      autoMax: true,
      unit: "s",
      color1: "#eab308",
    });

    this.charts.checkpoints = new OsChart("chart-checkpoints", {
      maxPoints: 15,
      autoMax: true,
      unit: " B",
      color1: "#a855f7",
    });
  },

  bindEvents() {
    // Manual sync button
    document.getElementById("btn-manual-sync")?.addEventListener("click", () => {
      this.refreshAll();
      this.toast("Telemetry synchronized with backend");
    });

    // Process Start/Stop Controls
    const startHandler = async () => {
      try {
        await this.api("/api/process/start", { method: "POST" });
        this.toast("Supervised worker process started");
        await this.refreshAll();
      } catch (err) {
        this.toast(`Error starting process: ${err.message}`);
      }
    };

    const stopHandler = async () => {
      try {
        await this.api("/api/process/stop", { method: "POST" });
        this.toast("Supervised worker process stopped");
        await this.refreshAll();
      } catch (err) {
        this.toast(`Error stopping process: ${err.message}`);
      }
    };

    document.getElementById("ov-btn-start")?.addEventListener("click", startHandler);
    document.getElementById("ov-btn-stop")?.addEventListener("click", stopHandler);
    document.getElementById("vis-btn-start")?.addEventListener("click", startHandler);
    document.getElementById("vis-btn-stop")?.addEventListener("click", stopHandler);

    // Create Checkpoint
    const cpHandler = async () => {
      try {
        const res = await this.api("/api/checkpoints/create", { method: "POST" });
        this.toast(`Checkpoint ${res.checkpoint_id} created (${res.checkpoint_type})`);
        await this.refreshAll();
      } catch (err) {
        this.toast(`Checkpoint creation failed: ${err.message}`);
      }
    };

    document.getElementById("ov-btn-create-cp")?.addEventListener("click", cpHandler);
    document.getElementById("vis-btn-checkpoint")?.addEventListener("click", cpHandler);
    document.getElementById("btn-create-checkpoint-page")?.addEventListener("click", cpHandler);

    // Checkpoint Search Filter
    document.getElementById("cp-search-input")?.addEventListener("input", (e) => {
      this.renderCheckpointsTable(e.target.value.toLowerCase());
    });

    // Policy Save
    document.getElementById("btn-save-policy")?.addEventListener("click", async () => {
      const policy = document.getElementById("rec-policy-select").value;
      try {
        await this.api("/api/recovery/policy", {
          method: "POST",
          body: JSON.stringify({ policy }),
        });
        this.toast(`Recovery policy updated to: ${policy}`);
        await this.refreshRecovery();
      } catch (err) {
        this.toast(`Failed to update policy: ${err.message}`);
      }
    });

    // Manual Recovery Trigger
    document.getElementById("btn-trigger-manual-recovery")?.addEventListener("click", async () => {
      const cpIdVal = document.getElementById("rec-manual-cp-id").value;
      const payload = cpIdVal ? { checkpoint_id: parseInt(cpIdVal, 10) } : {};
      try {
        const res = await this.api("/api/recovery/trigger", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (res.status === "SUCCESS") {
          this.toast(`Recovery completed | Checkpoint: ${res.checkpoint?.checkpoint_id || "default"} | Status: ${res.status}`);
        } else {
          this.toast(`Recovery completed with status: ${res.status}`);
        }
        await this.refreshAll();
      } catch (err) {
        this.toast(`Manual recovery error: ${err.message}`);
      }
    });

    // Failure Lab Triggers with Confirmation Dialog
    document.getElementById("lab-btn-crash")?.addEventListener("click", () => {
      this.confirmDialog(
        "Execute Process Crash",
        "This will terminate the demo subprocess immediately with os._exit(7). The supervisor will detect process disappearance and trigger recovery rollback. Proceed?",
        () => this.postFailure("/api/failure/crash", "Process Crash simulated")
      );
    });

    document.getElementById("lab-btn-hang")?.addEventListener("click", () => {
      this.confirmDialog(
        "Execute Process Hang",
        "This will command the demo process to stop its heartbeat loop. When the heartbeat threshold is breached, the supervisor flags a hang. Proceed?",
        () => this.postFailure("/api/failure/hang", "Process Hang simulated")
      );
    });

    document.getElementById("lab-btn-corrupt")?.addEventListener("click", () => {
      this.confirmDialog(
        "Corrupt Process State",
        "This will write corrupted data into the atomic state file. Failure detector Pydantic validation will identify invalid fields and trigger recovery. Proceed?",
        () => this.postFailure("/api/failure/corrupt", "State Corruption simulated")
      );
    });

    document.getElementById("lab-btn-memory")?.addEventListener("click", () => {
      this.postFailure("/api/failure/memory", "Allocated 60 MB memory pressure");
    });

    document.getElementById("lab-btn-random")?.addEventListener("click", () => {
      this.confirmDialog(
        "Trigger Random Chaos",
        "A randomly chosen fault condition (crash, hang, corruption, or memory spike) will be dispatched to the isolated worker. Proceed?",
        () => this.postFailure("/api/failure/random", "Random fault injection triggered")
      );
    });

    // Event Logs Controls
    document.getElementById("btn-refresh-logs")?.addEventListener("click", () => {
      this.refreshEventsPage();
    });

    document.getElementById("log-filter-level")?.addEventListener("change", () => {
      this.refreshEventsPage();
    });

    document.getElementById("log-search-input")?.addEventListener("keyup", (e) => {
      if (e.key === "Enter") this.refreshEventsPage();
    });

    document.getElementById("btn-export-csv")?.addEventListener("click", () => {
      window.location.href = "/api/events/export";
    });

    // Configuration Save
    document.getElementById("btn-save-configuration")?.addEventListener("click", async () => {
      const payload = {
        recovery_policy: document.getElementById("cfg-policy").value,
        monitor_interval_seconds: parseFloat(document.getElementById("cfg-monitor-interval").value),
        heartbeat_timeout_seconds: parseFloat(document.getElementById("cfg-heartbeat-timeout").value),
        cpu_threshold_percent: parseFloat(document.getElementById("cfg-cpu-threshold").value),
        memory_threshold_mb: parseFloat(document.getElementById("cfg-mem-threshold").value),
      };
      try {
        await this.api("/api/config", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        this.toast("Runtime configuration successfully updated & saved in SQLite");
        await this.refreshConfigPage();
      } catch (err) {
        this.toast(`Configuration error: ${err.message}`);
      }
    });

    // Modal Cancel
    document.getElementById("modal-btn-cancel")?.addEventListener("click", () => {
      document.getElementById("confirm-modal").classList.remove("open");
    });
  },

  async postFailure(endpoint, message) {
    try {
      await this.api(endpoint, { method: "POST" });
      this.toast(message);
      await this.refreshAll();
    } catch (err) {
      this.toast(`Failure simulation error: ${err.message}`);
    }
  },

  confirmDialog(title, message, onConfirm) {
    const modal = document.getElementById("confirm-modal");
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-message").textContent = message;
    const confirmBtn = document.getElementById("modal-btn-confirm");
    
    // Replace with clone to remove previous listeners
    const newBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);

    newBtn.addEventListener("click", () => {
      modal.classList.remove("open");
      onConfirm();
    });

    modal.classList.add("open");
  },

  async api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || response.statusText);
    }
    return response.json();
  },

  toast(message) {
    const bar = document.getElementById("toast-bar");
    if (!bar) return;
    bar.textContent = message;
    bar.style.display = "block";
    clearTimeout(this._toastTimeout);
    this._toastTimeout = setTimeout(() => {
      bar.style.display = "none";
    }, 4000);
  },

  async refreshAll() {
    try {
      const [status, metrics] = await Promise.all([
        this.api("/api/system/status"),
        this.api("/api/system/metrics"),
      ]);

      this.updateHeaderAndHealth(status);
      this.updateOverview(status, metrics);
      this.updateVisualizer(status, metrics);

      if (this.activePage === "checkpoints") {
        await this.refreshCheckpoints();
      } else if (this.activePage === "recovery") {
        await this.refreshRecovery();
      } else if (this.activePage === "analytics") {
        await this.refreshAnalytics();
      } else if (this.activePage === "events") {
        await this.refreshEventsPage();
      }
    } catch (err) {
      this.setDisconnectedState(err.message);
    }
  },

  setDisconnectedState(msg) {
    const dot = document.getElementById("system-health-dot");
    const txt = document.getElementById("system-health-text");
    if (dot) dot.className = "indicator-dot disconnected";
    if (txt) txt.textContent = "DISCONNECTED";
  },

  updateHeaderAndHealth(status) {
    const dot = document.getElementById("system-health-dot");
    const txt = document.getElementById("system-health-text");
    const syncTime = document.getElementById("sync-timestamp");

    const health = status.system_health || "UNKNOWN";
    if (txt) txt.textContent = health;
    if (dot) {
      dot.className = `indicator-dot ${health.toLowerCase()}`;
    }
    if (syncTime) {
      syncTime.textContent = new Date().toLocaleTimeString();
    }
  },

  updateOverview(status, metrics) {
    // Top metric cards
    document.getElementById("ov-cpu").textContent = `${Number(status.cpu || 0).toFixed(1)}%`;
    document.getElementById("ov-mem").textContent = `${Number(status.memory || 0).toFixed(1)}%`;
    document.getElementById("ov-mem-mb").textContent = `${metrics.ram_used_mb || 0} MB host allocated`;
    document.getElementById("ov-disk").textContent = `${Number(status.disk || 0).toFixed(1)}%`;
    document.getElementById("ov-checkpoints").textContent = status.checkpoint_count || 0;
    document.getElementById("ov-recoveries").textContent = status.recovery_count || 0;

    const lastCp = status.last_checkpoint;
    document.getElementById("ov-last-cp").textContent = lastCp
      ? `${lastCp.checkpoint_id} (${new Date(lastCp.timestamp).toLocaleTimeString()})`
      : "None saved";

    const lastRec = status.last_recovery;
    document.getElementById("ov-last-rec").textContent = lastRec
      ? `${lastRec.recovery_status} at ${new Date(lastRec.recovery_end).toLocaleTimeString()}`
      : "Idle";

    // Process Supervisor Card
    const proc = status.process || {};
    const state = proc.state || {};

    const statusTag = document.getElementById("ov-proc-status-tag");
    const procStatus = proc.status || "STOPPED";
    if (statusTag) {
      statusTag.textContent = procStatus;
      statusTag.className = `tag tag-${procStatus.toLowerCase()}`;
    }

    document.getElementById("ov-proc-pid").textContent = proc.pid || "--";
    document.getElementById("ov-proc-uptime").textContent = this.formatSeconds(proc.uptime);
    document.getElementById("ov-proc-task").textContent = state.current_task || "--";
    
    const progVal = state.progress !== undefined ? state.progress : 0;
    document.getElementById("ov-proc-prog-val").textContent = `${progVal}%`;
    const progFill = document.getElementById("ov-proc-prog-fill");
    if (progFill) progFill.style.width = `${progVal}%`;

    document.getElementById("ov-proc-counter").textContent = state.counter !== undefined ? state.counter : "--";
    document.getElementById("ov-proc-item").textContent = state.current_item !== undefined ? state.current_item : "--";
    
    const hb = state.heartbeat;
    document.getElementById("ov-proc-heartbeat").textContent = hb 
      ? `${(Date.now() / 1000 - hb).toFixed(1)}s ago`
      : "--";

    // Feed Recent Events into overview
    this.refreshOverviewEvents();
  },

  async refreshOverviewEvents() {
    try {
      const events = await this.api("/api/events?limit=8");
      const container = document.getElementById("ov-events-feed");
      if (!container) return;
      if (events.length === 0) {
        container.innerHTML = `<div style="padding: 14px; text-align: center; color: var(--text-dim);">No operational events recorded</div>`;
        return;
      }
      container.innerHTML = events.map((e) => `
        <div class="event-row">
          <span class="event-time">${new Date(e.timestamp).toLocaleTimeString()}</span>
          <span class="event-lvl ${e.level}">${e.level}</span>
          <span class="event-type">${e.event_type}</span>
          <span class="event-msg" title="${e.message}">${e.message}</span>
          <span class="event-status"><span class="tag tag-${(e.status || 'info').toLowerCase()}">${e.status || ''}</span></span>
        </div>
      `).join("");
    } catch (_) {}
  },

  updateVisualizer(status, metrics) {
    // Push live data to Canvas charts
    if (this.charts.liveSystem) {
      this.charts.liveSystem.push(metrics.cpu_percent || 0, metrics.ram_percent || 0);
    }
    if (this.charts.liveProcess) {
      this.charts.liveProcess.push(metrics.process_memory_mb || 0);
    }

    const proc = status.process || {};
    const state = proc.state || {};

    const rssEl = document.getElementById("vis-proc-rss");
    if (rssEl) rssEl.textContent = `${metrics.process_memory_mb || 0} MB`;
    
    const statusEl = document.getElementById("vis-proc-status");
    if (statusEl) statusEl.textContent = proc.status || "STOPPED";

    const pidEl = document.getElementById("vis-pid");
    if (pidEl) pidEl.textContent = proc.pid || "--";

    const taskEl = document.getElementById("vis-task");
    if (taskEl) taskEl.textContent = state.current_task || "--";

    const counterEl = document.getElementById("vis-counter");
    if (counterEl) counterEl.textContent = state.counter !== undefined ? state.counter : "--";

    const itemEl = document.getElementById("vis-item");
    if (itemEl) itemEl.textContent = state.current_item !== undefined ? state.current_item : "--";

    const wsEl = document.getElementById("vis-workset");
    if (wsEl) wsEl.textContent = JSON.stringify((state.memory_state && state.memory_state.working_set) || []);

    const hbDelayEl = document.getElementById("vis-heartbeat-delay");
    if (hbDelayEl) {
      const hb = state.heartbeat;
      hbDelayEl.textContent = hb ? `${(Date.now() / 1000 - hb).toFixed(1)}s` : "--";
    }
  },

  async refreshCheckpoints() {
    try {
      const rows = await this.api("/api/checkpoints");
      this.cachedCheckpoints = rows;
      this.renderCheckpointsTable();
    } catch (err) {
      this.toast(`Failed to load checkpoints: ${err.message}`);
    }
  },

  renderCheckpointsTable(filter = "") {
    const tbody = document.getElementById("checkpoints-table-body");
    if (!tbody) return;

    const filtered = this.cachedCheckpoints.filter((cp) => {
      if (!filter) return true;
      const str = `${cp.checkpoint_id} ${cp.checkpoint_type} ${cp.status} ${cp.checksum}`.toLowerCase();
      return str.includes(filter);
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 18px;">No checkpoints found matching query</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map((cp) => `
      <tr style="cursor: pointer;" onclick="App.inspectCheckpoint(${cp.id})">
        <td><strong>${cp.checkpoint_id}</strong></td>
        <td>${new Date(cp.timestamp).toLocaleTimeString()}</td>
        <td><span class="tag tag-${cp.checkpoint_type}">${cp.checkpoint_type}</span></td>
        <td>${cp.state_size} B</td>
        <td>${Number(cp.storage_savings || 0).toFixed(1)}%</td>
        <td>${cp.base_checkpoint_id ? '#' + cp.base_checkpoint_id : 'root'}</td>
        <td><span class="tag tag-${(cp.validation_reason === 'OK' ? 'healthy' : 'critical')}">${cp.validation_reason || 'OK'}</span></td>
        <td><span class="tag tag-${cp.status}">${cp.status}</span></td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="event.stopPropagation(); App.restoreCheckpoint(${cp.id})">Restore</button>
          <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); App.deleteCheckpoint(${cp.id})">Delete</button>
        </td>
      </tr>
    `).join("");
  },

  async inspectCheckpoint(id) {
    try {
      const cp = await this.api(`/api/checkpoints/${id}`);
      this.selectedCheckpointId = id;
      
      document.getElementById("cp-inspector-empty").style.display = "none";
      document.getElementById("cp-inspector-body").style.display = "block";
      document.getElementById("cp-detail-label").textContent = `ID #${cp.id} (${cp.checkpoint_id})`;

      document.getElementById("cp-insp-id").textContent = `${cp.checkpoint_id} (Internal DB #${cp.id})`;
      document.getElementById("cp-insp-time").textContent = cp.timestamp;
      document.getElementById("cp-insp-type").textContent = `${cp.checkpoint_type.toUpperCase()} snapshot`;
      document.getElementById("cp-insp-base").textContent = cp.base_checkpoint_id ? `Base ID #${cp.base_checkpoint_id}` : "None (Root Full Checkpoint)";
      document.getElementById("cp-insp-checksum").textContent = cp.checksum;
      
      const val = cp.validation || {};
      document.getElementById("cp-insp-val-status").innerHTML = val.valid
        ? `<span class="tag tag-healthy">VALID (Verified SHA-256)</span>`
        : `<span class="tag tag-critical">INVALID (${val.reason})</span>`;
      
      document.getElementById("cp-insp-path").textContent = cp.snapshot_path;

      // Fetch or show state payload
      try {
        const fullPayload = JSON.stringify(cp, null, 2);
        document.getElementById("cp-state-json").textContent = fullPayload;
      } catch (_) {
        document.getElementById("cp-state-json").textContent = "Unable to read snapshot payload";
      }
    } catch (err) {
      this.toast(`Inspection failed: ${err.message}`);
    }
  },

  async restoreCheckpoint(id) {
    this.confirmDialog(
      `Confirm Restore Checkpoint #${id}`,
      `Restoring will halt the current worker state, reconstruct full state lineage from base snapshots, and restart the process with checkpoint #${id}. Continue?`,
      async () => {
        try {
          const res = await this.api(`/api/checkpoints/${id}/restore`, { method: "POST" });
          this.toast(`Successfully restored checkpoint ${res.checkpoint.checkpoint_id}`);
          await this.refreshAll();
        } catch (err) {
          this.toast(`Restore failed: ${err.message}`);
        }
      }
    );
  },

  async deleteCheckpoint(id) {
    this.confirmDialog(
      `Delete Checkpoint #${id}`,
      `Are you sure you want to mark checkpoint #${id} as deleted? This action removes it from recovery candidates.`,
      async () => {
        try {
          await this.api(`/api/checkpoints/${id}`, { method: "DELETE" });
          this.toast(`Checkpoint #${id} deleted`);
          await this.refreshCheckpoints();
        } catch (err) {
          this.toast(`Deletion failed: ${err.message}`);
        }
      }
    );
  },

  async refreshRecovery() {
    try {
      const [status, history] = await Promise.all([
        this.api("/api/recovery/status"),
        this.api("/api/recovery/history"),
      ]);

      const policySelect = document.getElementById("rec-policy-select");
      if (policySelect) policySelect.value = status.policy || "latest";

      const policyVal = document.getElementById("rec-policy-val");
      if (policyVal) policyVal.textContent = status.policy || "latest";

      const statusTag = document.getElementById("rec-status-tag");
      const currentStatus = status.status || "IDLE";
      if (statusTag) {
        statusTag.textContent = currentStatus;
        statusTag.className = `tag tag-${currentStatus.toLowerCase()}`;
      }

      document.getElementById("rec-last-failure").textContent = status.last_failure || "None recorded";
      document.getElementById("rec-last-cp").textContent = status.checkpoint_used || "None";
      document.getElementById("rec-last-rto").textContent = status.rto !== undefined ? `${status.rto}s` : "--";

      // Populate history table
      const tbody = document.getElementById("rec-history-table");
      if (tbody) {
        if (history.length === 0) {
          tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 18px;">No recovery events recorded yet</td></tr>`;
        } else {
          tbody.innerHTML = history.map((h) => `
            <tr>
              <td>#${h.id}</td>
              <td>${h.failure_type}</td>
              <td>${new Date(h.detection_time).toLocaleTimeString()}</td>
              <td>${h.rto}s</td>
              <td>${h.checkpoint_used || 'None'}</td>
              <td><span class="tag tag-${h.recovery_status.toLowerCase()}">${h.recovery_status}</span></td>
            </tr>
          `).join("");
        }
      }
    } catch (err) {
      this.toast(`Error refreshing recovery: ${err.message}`);
    }
  },

  async refreshAnalytics() {
    try {
      const summary = await this.api("/api/analytics/summary");
      
      const rec = summary.recoveries || {};
      document.getElementById("an-success-rate").textContent = `${rec.success_rate || 0}%`;
      document.getElementById("an-success-sub").textContent = `${rec.success || 0} of ${rec.total || 0} successful`;
      document.getElementById("an-avg-rto").textContent = `${rec.avg_rto || 0}s`;
      document.getElementById("an-rto-bounds").textContent = `Min: ${rec.min_rto || 0}s | Max: ${rec.max_rto || 0}s`;

      const cp = summary.checkpoints || {};
      document.getElementById("an-avg-savings").textContent = `${cp.avg_savings_pct || 0}%`;
      
      const totalCp = cp.total || 0;
      const incRatio = totalCp > 0 ? ((cp.incremental / totalCp) * 100).toFixed(1) : 0;
      document.getElementById("an-cp-ratio").textContent = `${incRatio}%`;
      document.getElementById("an-cp-counts").textContent = `${cp.full || 0} full, ${cp.incremental || 0} inc`;

      // Render Charts
      if (this.charts.rto && summary.recent_rto_series) {
        const rtoValues = summary.recent_rto_series.map((s) => s.rto).reverse();
        if (rtoValues.length > 0) {
          this.charts.rto.setData(rtoValues);
        }
      }

      if (this.charts.checkpoints && summary.recent_cp_series) {
        const sizeValues = summary.recent_cp_series.map((s) => s.state_size).reverse();
        if (sizeValues.length > 0) {
          this.charts.checkpoints.setData(sizeValues);
        }
      }

      // Render Failure Breakdown table
      const failTbody = document.getElementById("an-failure-table");
      if (failTbody) {
        const fb = summary.failure_breakdown || [];
        if (fb.length === 0) {
          failTbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-dim);">No failures recorded</td></tr>`;
        } else {
          failTbody.innerHTML = fb.map((f) => `
            <tr>
              <td><strong>${f.failure_type}</strong></td>
              <td>${f.count} incidents</td>
              <td><span class="tag tag-warning">EVALUATED</span></td>
            </tr>
          `).join("");
        }
      }

      // Render Recent Rec Audits
      const recTbody = document.getElementById("an-recent-rec-table");
      if (recTbody) {
        const rts = summary.recent_rto_series || [];
        if (rts.length === 0) {
          recTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim);">No recoveries logged</td></tr>`;
        } else {
          recTbody.innerHTML = rts.map((r) => `
            <tr>
              <td>#${r.id}</td>
              <td>${r.failure_type}</td>
              <td>${r.recovery_status === 'SUCCESS' ? 'Restored' : 'None'}</td>
              <td>${r.rto}s</td>
              <td><span class="tag tag-${r.recovery_status.toLowerCase()}">${r.recovery_status}</span></td>
            </tr>
          `).join("");
        }
      }
    } catch (err) {
      this.toast(`Analytics error: ${err.message}`);
    }
  },

  async refreshEventsPage() {
    const level = document.getElementById("log-filter-level")?.value || "ALL";
    const search = document.getElementById("log-search-input")?.value || "";

    try {
      const params = new URLSearchParams({ limit: 120 });
      if (level !== "ALL") params.append("level", level);
      if (search.trim()) params.append("search", search.trim());

      const events = await this.api(`/api/events?${params.toString()}`);
      const container = document.getElementById("full-events-feed");
      if (!container) return;

      if (events.length === 0) {
        container.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-dim);">No event logs match the current query filter</div>`;
        return;
      }

      container.innerHTML = events.map((e) => `
        <div class="event-row">
          <span class="event-time">${new Date(e.timestamp).toLocaleTimeString()}</span>
          <span class="event-lvl ${e.level}">${e.level}</span>
          <span class="event-type">${e.event_type}</span>
          <span class="event-msg" title="${e.message}">${e.message}</span>
          <span class="event-status"><span class="tag tag-${(e.status || 'info').toLowerCase()}">${e.status || ''}</span></span>
        </div>
      `).join("");
    } catch (err) {
      this.toast(`Event query failed: ${err.message}`);
    }
  },

  async refreshConfigPage() {
    try {
      const conf = await this.api("/api/config");
      
      const policyEl = document.getElementById("cfg-policy");
      if (policyEl) policyEl.value = conf.recovery_policy;

      const intEl = document.getElementById("cfg-monitor-interval");
      if (intEl) intEl.value = conf.monitor_interval_seconds;

      const hbEl = document.getElementById("cfg-heartbeat-timeout");
      if (hbEl) hbEl.value = conf.heartbeat_timeout_seconds;

      const cpuEl = document.getElementById("cfg-cpu-threshold");
      if (cpuEl) cpuEl.value = conf.cpu_threshold_percent;

      const memEl = document.getElementById("cfg-mem-threshold");
      if (memEl) memEl.value = conf.memory_threshold_mb;

      // Diagnostics metadata
      const verEl = document.getElementById("cfg-version");
      if (verEl) verEl.textContent = conf.app_version;

      const paths = conf.storage_paths || {};
      const dbEl = document.getElementById("cfg-path-db");
      if (dbEl) dbEl.textContent = paths.database || "--";

      const snEl = document.getElementById("cfg-path-snapshots");
      if (snEl) snEl.textContent = paths.snapshots || "--";

      const lgEl = document.getElementById("cfg-path-logs");
      if (lgEl) lgEl.textContent = paths.logs || "--";
    } catch (err) {
      this.toast(`Failed to load configuration: ${err.message}`);
    }
  },

  formatSeconds(val) {
    const s = Math.floor(Number(val || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  },
};

// Launch application on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  App.init();
});
