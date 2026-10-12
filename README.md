# CrashGuard: Intelligent System Failure Recovery & Checkpointing Framework

CrashGuard is an engineering-grade, user-space Operating Systems supervisory framework and observability console. It actively supervises an isolated demo process, creates full and incremental state checkpoints, validates cryptographic snapshot integrity, simulates realistic failure scenarios, and executes policy-driven state rollback while measuring Recovery Time Objective (RTO).

Designed specifically for operating systems engineering demonstrations, technical viva presentations, and portfolios, CrashGuard maintains safety: it never alters host OS boot configurations, registries, or external processes. All failure simulation is confined to the isolated `crashguard-demo` subprocess via atomic command structures.

---

## 1. Architectural Highlights

- **Multi-Page Operational Console**: 8 distinct functional pages with persistent sidebar navigation, live psutil telemetry, and zero-dependency 2D canvas charts.
- **Engineered Visual Design**: Dark charcoal and near-black surfaces (`#090b0e`, `#13171f`), cool precision cyan accents (`#38bdf8`), restrained status colors, crisp typography, and dense informational layouts.
- **Full & Incremental Checkpointing**: Root snapshots store full state; subsequent snapshots store key-level differential states, reducing storage footprint by 40–80%.
- **Cryptographic Snapshot Validation**: SHA-256 checksumming, JSON schema validation, and state-hash lineage reconstruction prevent restoring corrupted states.
- **Policy-Driven Recovery Engine**: Automated failure classification and recovery execution across four policies: `latest`, `safest`, `automatic`, and `manual`.
- **Auditable Observability**: Persistent recovery event logging, RTO benchmarking, live system metrics, event querying, and CSV log export.

```mermaid
flowchart TD
    subgraph UI ["Engineering Console (Multi-Page)"]
        Nav[Sidebar Navigation]
        P1[1. Command Center / Overview]
        P2[2. System Analytics]
        P3[3. Resource Visualizer]
        P4[4. Checkpoint Explorer]
        P5[5. Recovery Center]
        P6[6. Failure Lab]
        P7[7. Event Logs]
        P8[8. System Configuration]
    end

    subgraph Backend ["FastAPI Core Services"]
        API[REST Endpoints]
        PM[Process Manager]
        CM[Checkpoint Manager]
        FD[Failure Detector]
        FS[Failure Simulator]
        RE[Recovery Engine]
        SM[System Monitor Loop]
        MET[Metrics Service - psutil]
    end

    subgraph Storage ["Persistence Layer"]
        DB[(SQLite: crashguard.db)]
        Snap[checkpoints/snapshots/*.json]
        DiskState[data/demo_state.json]
    end

    subgraph Worker ["Isolated Subprocess"]
        Demo[demo_worker.py (PID)]
    end

    Nav --> P1 & P2 & P3 & P4 & P5 & P6 & P7 & P8
    UI <--> API
    API --> PM & CM & FS & RE & MET
    SM --> FD --> RE
    RE --> CM & PM
    PM <--> DiskState
    PM <--> Demo
    FS --> Demo
    CM --> Snap
    CM & RE & SM <--> DB
```

---

## 2. Multi-Page Application Layout

CrashGuard is structured into eight functional pages:

| Page | Section | Operational Scope & Capabilities |
| :--- | :--- | :--- |
| **1. Overview** | `MONITORING` | Operational command center displaying host CPU/RAM/Disk metrics, active subprocess state (PID, uptime, counter, task, progress), total checkpoints, recoveries, and live system event stream. |
| **2. System Analytics** | `MONITORING` | Recovery analytics workspace featuring RTO trends, recovery success rate, full vs. incremental storage savings, failure distribution breakdown, and historical audit tables. |
| **3. Resource Visualizer** | `MONITORING` | Real-time telemetry workspace rendering live host CPU & RAM curves via canvas charts, subprocess RSS memory growth, heartbeat timing, and atomic state data. |
| **4. Checkpoint Explorer** | `RELIABILITY` | Checkpoint catalog table with instant search and sort, full vs. incremental badges, SHA-256 checksum verification, base snapshot lineage, raw JSON state inspector, manual restore, and delete actions. |
| **5. Recovery Center** | `RELIABILITY` | Operational recovery workspace with policy switcher (`latest`, `safest`, `automatic`, `manual`), manual operator trigger, 5-step OS recovery workflow visualizer, and complete RTO history audit. |
| **6. Failure Lab** | `RELIABILITY` | Controlled fault injection sandbox with confirmation modals for Process Crash, Process Hang (heartbeat freeze), State Corruption, Memory Stress, and Chaos Injection. Targets isolated demo process only. |
| **7. Event Logs** | `SYSTEM` | Observability log viewer with severity level filtering (INFO, WARNING, ERROR), text search query, real-time reload, and full CSV audit export. |
| **8. System Configuration** | `SYSTEM` | Persistent runtime settings stored in SQLite: recovery policy, monitor polling interval, heartbeat timeout, host CPU threshold, and process memory limits, plus system environment metadata. |

---

## 3. Supported Failure Scenarios

| Scenario | Simulated Action | Detection Mechanism | Recovery Workflow |
| :--- | :--- | :--- | :--- |
| **Process Crash** | Sends `os._exit(7)` to subprocess | Supervisor detects process termination (`status == STOPPED` while supervised) | Rolls back to newest valid checkpoint, respawns process with checkpointed state, measures RTO. |
| **Process Hang** | Subprocess suspends heartbeat updates | Heartbeat timeout exceeded (`now - heartbeat > 6.0s`) | Terminates unresponsive process, restores validated state, respawns worker. |
| **State Corruption** | Injects invalid fields and bad hash into state | Pydantic schema validation failure or unreadable JSON | Detects schema failure, rolls back to safe checkpoint, restores valid state file. |
| **Memory Stress** | Subprocess allocates buffer memory (60 MB) | `psutil` RSS memory tracking breaches configured threshold | Logs warning event, records resource pressure, triggers recovery if configured. |
| **Random Chaos** | Dispatches a random failure scenario | Dynamic matching against crash, hang, corruption, or stress | Exercises fault-tolerance under unpredictable conditions. |

---

## 4. Local Setup & Execution Guide (Windows)

### Prerequisites
- Python 3.11+ installed and added to `PATH`
- PowerShell or Command Prompt

### Step 1: Open Terminal in Project Directory
```powershell
cd "c:\Users\Priyanshu\OneDrive\Desktop\OS project\crashguard-os-recovery-master"
```

### Step 2: Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Launch CrashGuard Backend & Console
```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

### Step 4: Access Console in Browser
Open your browser and navigate to:
```text
http://127.0.0.1:8000
```
API Documentation is available at:
```text
http://127.0.0.1:8000/docs
```

---

## 5. Automated Verification & Test Suite

CrashGuard includes an automated test suite covering checkpoint creation, incremental reconstruction, validation rejection, process failure detection, RTO calculation, and complete API endpoint contracts:

```powershell
python -m pytest -v
```

### Test Suite Results:
- `tests/test_api_endpoints.py::test_system_status_and_metrics_endpoints`: **PASSED**
- `tests/test_api_endpoints.py::test_config_get_and_update`: **PASSED**
- `tests/test_api_endpoints.py::test_analytics_summary_endpoint`: **PASSED**
- `tests/test_api_endpoints.py::test_events_filtering_and_export`: **PASSED**
- `tests/test_api_endpoints.py::test_static_index_loads`: **PASSED**
- `tests/test_crashguard_core.py::test_checkpoint_creation_and_incremental_restore`: **PASSED**
- `tests/test_crashguard_core.py::test_checkpoint_validation_rejects_corruption`: **PASSED**
- `tests/test_crashguard_core.py::test_invalid_checkpoint_restore_fails`: **PASSED**
- `tests/test_crashguard_core.py::test_failure_detection_for_stopped_process`: **PASSED**
- `tests/test_crashguard_core.py::test_recovery_records_rto_and_restarts_process`: **PASSED**
- `tests/test_crashguard_core.py::test_end_to_end_crash_restore_flow`: **PASSED**

**Status: 11 passed in 9.86s (100% test pass rate)**

---

## 6. Demonstration & Viva Walkthrough

1. **Start Subprocess**: Open the console at `http://127.0.0.1:8000`. Navigate to **Overview** and click **Start Process**. Observe the PID, counter, and task advance in real time.
2. **Create Baseline Snapshot**: Click **Create Checkpoint**. Notice Checkpoint `CP-001` created as `FULL`.
3. **Advance & Incremental Snapshot**: Wait 3–5 seconds so the state advances. Click **Create Checkpoint** again. Notice `CP-002` created as `INCREMENTAL` with storage savings displayed.
4. **Inspect in Checkpoint Explorer**: Click **Checkpoint Explorer** in the sidebar. Click `CP-002` to inspect its SHA-256 checksum, parent base checkpoint reference, and reconstructed JSON state payload.
5. **Inject Failure in Failure Lab**: Navigate to **Failure Lab**. Click **Simulate Process Crash** and confirm in the modal.
6. **Watch Real-Time Recovery**: The background supervisor detects process termination within 2 seconds, logs an event, restores `CP-002`, restarts the worker, and records the measured RTO.
7. **Audit in Recovery Center & Analytics**: Open **Recovery Center** to inspect the recovery record and RTO duration. Open **System Analytics** to see the updated RTO graph, success rate, and storage efficiency metrics.
8. **Export Observability Logs**: Open **Event Logs**, review the timestamped audit log, and click **Export CSV** to download `crashguard_events.csv`.

---

## 7. Viva Questions and Answers

**Q: Is CrashGuard performing kernel-level checkpointing?**  
A: No. CrashGuard is a user-space supervisory framework. It snapshots application-level state and process metadata safely, demonstrating OS fault-tolerance principles without requiring root kernel hooks or kernel memory dumps.

**Q: How does incremental checkpointing function?**  
A: The initial checkpoint captures full state. Subsequent checkpoints store differential key-value changes compared against the previous reconstructed state. Restoration dynamically traverses the base chain to rebuild the full snapshot before process restart.

**Q: How does CrashGuard differentiate between a normal stop and a crash?**  
A: The process manager tracks whether the subprocess is `supervised`. A user-requested stop sets `supervised = False`. If the subprocess terminates while `supervised == True`, the failure detector classifies the event as an abnormal `Process Crash`.

**Q: How is checkpoint corruption detected?**  
A: Checkpoints contain a cryptographic SHA-256 checksum calculated over snapshot contents and an independent full state hash. If a snapshot file is tampered with or corrupted on disk, validation fails immediately, marking the record `invalid` and preventing unsafe rollback.

**Q: What is Recovery Time Objective (RTO)?**  
A: RTO represents the elapsed time from failure detection through snapshot validation, state reconstruction, process restart, and health verification, measured with microsecond precision via monotonic timers.

---

## 8. Limitations & Scope

- **User-Space Demonstration**: Snapshots capture application variables, progress counters, and data sets; arbitrary open OS sockets and kernel thread registers are out of scope.
- **Process Target**: To ensure safety on student machines, failure simulation commands are strictly restricted to the isolated demo worker.
- **Diff Resolution**: State differences operate at key-level JSON structures rather than block-level copy-on-write storage blocks.
