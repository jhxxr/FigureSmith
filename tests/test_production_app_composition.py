"""Regression tests for the production outer-app/vendor composition."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import create_production_app
from figuresmith.models.errors import DataDirNotWritable


def _vendor_app() -> FastAPI:
    app = FastAPI()

    @app.get("/vendor-only")
    def vendor_only() -> dict[str, str]:
        return {"application": "vendor"}

    @app.get("/healthz")
    def vendor_health() -> dict[str, str]:
        return {"application": "vendor"}

    return app


def test_outer_routes_precede_vendor_mount(monkeypatch) -> None:
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "1")
    monkeypatch.delenv("FIGURESMITH_SESSION_TOKEN", raising=False)

    app = create_production_app(_vendor_app(), install_auth=True)
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {
            "status": "ok",
            "application": "figuresmith",
        }
        assert client.get("/vendor-only").json() == {"application": "vendor"}
        assert client.get("/api/desktop/ready").json()["ready"] is True
        bridge = client.get("/figuresmith-bridge.js")
        assert bridge.status_code == 200
        assert "FigureSmith" in bridge.text


def test_production_factory_exposes_one_canonical_data_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "1")
    monkeypatch.delenv("FIGURESMITH_SESSION_TOKEN", raising=False)

    app = create_production_app(_vendor_app(), app_data_dir=tmp_path, install_auth=False)
    with TestClient(app) as client:
        ready = client.get("/api/desktop/ready")
        assert ready.status_code == 200
        assert Path(ready.json()["app_data_dir"]) == tmp_path.resolve()
        assert Path(ready.json()["models_dir"]) == (tmp_path / "models").resolve()
        models = client.get("/api/models")
        assert models.status_code == 200
        assert Path(models.json()["app_data_dir"]) == tmp_path.resolve()


def test_production_factory_rejects_mutable_paths_outside_root(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "1")
    monkeypatch.setenv("FIGURESMITH_OUTPUTS_DIR", str(tmp_path / "outside-outputs"))
    with pytest.raises(DataDirNotWritable) as exc_info:
        create_production_app(app_data_dir=tmp_path / "data", install_auth=False)
    assert exc_info.value.code == "DATA_DIR_NOT_WRITABLE"


def test_production_factory_smokes_real_vendor_routes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "1")
    monkeypatch.delenv("FIGURESMITH_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("FIGURESMITH_DATA_DIR", str(tmp_path))

    app = create_production_app(install_auth=False)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/config").status_code == 200
        assert client.get("/api/models").status_code == 200

    import server

    assert Path(server.APP_DATA_DIR) == tmp_path.resolve()
    assert Path(server.JOBS_DIR) == (tmp_path / "jobs").resolve()
    assert Path(server.TEMP_DIR) == (tmp_path / "temp").resolve()
    assert Path(server.LOGS_DIR) == (tmp_path / "logs").resolve()
    assert Path(server.SVG_CACHE_DIR) == (tmp_path / "cache" / "svg-v1").resolve()
    assert Path(server.OUTPUTS_DIR) == (tmp_path / "outputs").resolve()
    assert Path(server.UPLOADS_DIR) == (tmp_path / "uploads").resolve()


def test_production_factory_exposes_system_routes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "1")
    monkeypatch.delenv("FIGURESMITH_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("FIGURESMITH_DATA_DIR", str(tmp_path))

    app = create_production_app(install_auth=False)
    with TestClient(app) as client:
        status = client.get("/api/system/status")

    assert status.status_code == 200
    assert status.json()["product"] == "FigureSmith"


def test_authenticated_ready_probe_requires_bearer_token(monkeypatch) -> None:
    token = "composition-test-token"
    monkeypatch.delenv("FIGURESMITH_DISABLE_AUTH", raising=False)
    monkeypatch.setenv("FIGURESMITH_SESSION_TOKEN", token)

    app = create_production_app(_vendor_app(), install_auth=True)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/desktop/ready").status_code == 401
        ready = client.get(
            "/api/desktop/ready",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ready.status_code == 200
        assert ready.json()["application"] == "figuresmith"
