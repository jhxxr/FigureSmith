"""API tests for Phase 3 model manager routes (TestClient, no vendor server)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # required by starlette TestClient
from fastapi.testclient import TestClient  # noqa: E402

from figuresmith.api.models_routes import create_models_app  # noqa: E402


def _make_rmbg_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text("{}", encoding="utf-8")
    (root / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    (root / "model.safetensors").write_bytes(b"api-rmbg")
    return root


@pytest.fixture()
def client(tmp_path: Path):
    app_data = tmp_path / "appdata"
    app_data.mkdir()
    app = create_models_app(app_data_dir=app_data)
    return TestClient(app), app_data, tmp_path


def test_list_and_paths(client) -> None:
    c, app_data, _ = client
    r = c.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    assert body["app_data_dir"] == str(app_data.resolve()) or Path(body["app_data_dir"]) == app_data.resolve()
    assert len(body["models"]) == 2

    r2 = c.get("/api/models/paths")
    assert r2.status_code == 200
    paths = r2.json()
    assert "sam3_checkpoint" in paths
    assert "rmbg_model_dir" in paths


def test_import_sam3_via_api(client) -> None:
    c, app_data, tmp_path = client
    src = tmp_path / "sam3.pt"
    src.write_bytes(b"api-sam3-weights")

    # Reject relative
    bad = c.post("/api/models/sam3/import", json={"source_path": "relative.pt", "min_bytes": 1})
    assert bad.status_code == 400

    # Reject missing
    missing = c.post(
        "/api/models/sam3/import",
        json={"source_path": str((tmp_path / "nope.pt").resolve()), "min_bytes": 1},
    )
    assert missing.status_code == 400

    ok = c.post(
        "/api/models/sam3/import",
        json={"source_path": str(src.resolve()), "min_bytes": 1},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert data["ok"] is True
    assert Path(data["checkpoint"]).is_file()

    verify = c.post("/api/models/sam3/verify")
    assert verify.status_code == 200
    assert verify.json()["verified"] is True

    listed = c.get("/api/models").json()
    sam3 = next(m for m in listed["models"] if m["id"] == "sam3")
    assert sam3["installed"] is True

    deleted = c.delete("/api/models/sam3")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_import_rmbg_via_api(client) -> None:
    c, app_data, tmp_path = client
    src = _make_rmbg_dir(tmp_path / "rmbg-src")
    resp = c.post(
        "/api/models/rmbg/import",
        json={"source_path": str(src.resolve()), "kind": "dir"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    # ZIP path
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(src).as_posix())
    zpath = tmp_path / "rmbg.zip"
    zpath.write_bytes(buf.getvalue())

    # delete first
    c.delete("/api/models/rmbg")
    resp2 = c.post(
        "/api/models/rmbg/import",
        json={"source_path": str(zpath.resolve()), "kind": "zip"},
    )
    assert resp2.status_code == 200, resp2.text

    verify = c.post("/api/models/rmbg/verify")
    assert verify.status_code == 200


def test_verify_missing_returns_404(client) -> None:
    c, _, _ = client
    r = c.post("/api/models/sam3/verify")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["code"] in {"MODEL_NOT_INSTALLED", "SAM3_MODEL_MISSING"}
