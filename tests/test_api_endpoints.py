import pytest
from fastapi.testclient import TestClient
from backend.main import app, db, checkpoint_manager, process_manager, recovery_engine


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_system_status_and_metrics_endpoints(client):
    res_status = client.get("/api/system/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "cpu" in data
    assert "memory" in data
    assert "process" in data
    assert "system_health" in data

    res_metrics = client.get("/api/system/metrics")
    assert res_metrics.status_code == 200
    m_data = res_metrics.json()
    assert "cpu_percent" in m_data
    assert "ram_percent" in m_data
    assert "process_memory_mb" in m_data


def test_config_get_and_update(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    cfg = res.json()
    assert cfg["recovery_policy"] in {"latest", "safest", "manual", "automatic"}
    assert cfg["monitor_interval_seconds"] > 0

    # Test update
    update_res = client.post("/api/config", json={
        "recovery_policy": "safest",
        "monitor_interval_seconds": 3.0,
        "heartbeat_timeout_seconds": 8.0,
    })
    assert update_res.status_code == 200
    assert update_res.json()["updated"]["recovery_policy"] == "safest"

    # Reset back to latest
    client.post("/api/config", json={"recovery_policy": "latest", "monitor_interval_seconds": 2.0})


def test_analytics_summary_endpoint(client):
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    analytics = res.json()
    assert "recoveries" in analytics
    assert "checkpoints" in analytics
    assert "failure_breakdown" in analytics
    assert "recent_rto_series" in analytics


def test_events_filtering_and_export(client):
    res_all = client.get("/api/events?limit=10")
    assert res_all.status_code == 200
    assert isinstance(res_all.json(), list)

    res_info = client.get("/api/events?level=INFO")
    assert res_info.status_code == 200
    for e in res_info.json():
        assert e["level"] == "INFO"

    res_csv = client.get("/api/events/export")
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"].startswith("text/csv")
    assert "timestamp" in res_csv.text


def test_static_index_loads(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "CRASHGUARD" in res.text
    assert "page-overview" in res.text
    assert "page-analytics" in res.text
    assert "page-checkpoints" in res.text
    assert "page-recovery" in res.text
    assert "page-failure-lab" in res.text
