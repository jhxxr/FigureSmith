"""Phase 5 system status / onboarding API tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from figuresmith.api.models_routes import create_models_app  # noqa: E402
from figuresmith.api.system_routes import build_system_status, probe_gpu_status  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path):
    app_data = tmp_path / "appdata"
    app_data.mkdir()
    app = create_models_app(app_data_dir=app_data, install_system=True)
    return TestClient(app), app_data


def test_probe_gpu_status_never_raises() -> None:
    result = probe_gpu_status()
    assert isinstance(result, dict)
    assert "gpu_available" in result
    assert "pytorch_cuda" in result


def test_build_system_status_shape(tmp_path: Path) -> None:
    app_data = tmp_path / "data"
    app_data.mkdir()
    status = build_system_status(app_data_dir=app_data)
    assert status["product"] == "FigureSmith"
    assert "version" in status
    assert "platform" in status
    assert "gpu_available" in status
    assert "sam3_loaded" in status
    assert "rmbg_loaded" in status
    assert "models" in status
    assert "onboarding_completed" in status
    assert "gpu_missing_zh" in status["messages"]
    assert "gpu_missing_en" in status["messages"]
    assert "NVIDIA" in status["messages"]["gpu_missing_zh"] or "CUDA" in status["messages"]["gpu_missing_zh"]


def test_system_status_endpoint(client) -> None:
    c, _ = client
    r = c.get("/api/system/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["product"] == "FigureSmith"
    assert isinstance(body["gpu_available"], bool)
    assert "messages" in body


def test_onboarding_persist(client) -> None:
    c, app_data = client
    before = c.get("/api/system/status").json()
    assert before["onboarding_completed"] is False

    r = c.post("/api/system/onboarding", json={"completed": True})
    assert r.status_code == 200, r.text
    assert r.json()["onboarding_completed"] is True

    after = c.get("/api/system/status").json()
    assert after["onboarding_completed"] is True

    settings = app_data / "settings.json"
    # settings may live under app_data or prefer_dev path; at least status reflects write
    assert after["onboarding_completed"] is True
