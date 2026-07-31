"""Hostile and compatibility coverage for the shared SVG sanitizer."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from figuresmith.models.errors import UnsafeSvgContent
from figuresmith.security.svg import SvgLimits, sanitize_svg


SAFE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient></defs><rect width="10" height="10" fill="url(#g)"/><text x="1" y="9" style="font-size:4px;fill:#111">ok</text></svg>'


def test_safe_svg_round_trips_and_removes_comments() -> None:
    result = sanitize_svg(f"<!-- comment -->{SAFE}")
    assert result.data.startswith(b"<?xml")
    assert b"comment" not in result.data
    assert b"linearGradient" in result.data


@pytest.mark.parametrize(
    "payload",
    [
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><rect onclick="alert(1)"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><body>x</body></foreignObject></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><rect style="background:url(https://example.com/x)"/></svg>',
        '<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>',
    ],
)
def test_active_external_and_doctype_content_is_rejected(payload: str) -> None:
    with pytest.raises(UnsafeSvgContent) as exc_info:
        sanitize_svg(payload)
    assert exc_info.value.code == "UNSAFE_SVG_CONTENT"
    assert "<svg" not in str(exc_info.value)


@pytest.mark.parametrize(
    "payload",
    [
        "<svg><rect/></svg>",
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///tmp/x"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="javascript:alert(1)"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="//example.com/x"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill: \"red; stroke:black"/></svg>',
    ],
)
def test_hostile_url_and_namespace_variants_are_rejected(payload: str) -> None:
    with pytest.raises(UnsafeSvgContent):
        sanitize_svg(payload)


def test_local_reference_and_bounded_data_uri_are_allowed() -> None:
    encoded = base64.b64encode(b"png-bytes").decode("ascii")
    payload = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<defs><clipPath id="clip"><circle r="2"/></clipPath></defs>'
        f'<image href="data:image/png;base64,{encoded}" clip-path="url(#clip)" width="2" height="2"/>'
        "</svg>"
    )
    assert b"data:image/png;base64" in sanitize_svg(payload).data


def test_resource_limits_are_bounded() -> None:
    payload = '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'
    with pytest.raises(UnsafeSvgContent):
        sanitize_svg(payload, limits=SvgLimits(max_elements=1))


def test_depth_attribute_and_data_limits_are_bounded() -> None:
    nested = '<svg xmlns="http://www.w3.org/2000/svg">' + ("<g>" * 4) + "x" + ("</g>" * 4) + "</svg>"
    with pytest.raises(UnsafeSvgContent):
        sanitize_svg(nested, limits=SvgLimits(max_depth=2))

    encoded = base64.b64encode(b"0123456789").decode("ascii")
    data_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        f'<image href="data:image/png;base64,{encoded}"/>'
        "</svg>"
    )
    with pytest.raises(UnsafeSvgContent):
        sanitize_svg(data_svg, limits=SvgLimits(max_data_uri_bytes=4))


def test_legal_scientific_svg_features_survive() -> None:
    payload = """
    <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
         viewBox="0 0 100 100">
      <defs>
        <linearGradient id="grad"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>
        <clipPath id="clip"><rect width="90" height="90"/></clipPath>
        <marker id="arrow" markerWidth="4" markerHeight="4" refX="2" refY="2"><circle r="2"/></marker>
      </defs>
      <g clip-path="url(#clip)" transform="translate(2 2)" style="fill:url(#grad);stroke:#111">
        <path d="M0 0 L80 80" marker-end="url(#arrow)"/>
        <text x="4" y="20"><tspan>Figure 1</tspan></text>
        <use xlink:href="#arrow" x="20" y="20"/>
      </g>
    </svg>
    """
    safe = sanitize_svg(payload).data
    assert b"clipPath" in safe
    assert b"marker-end" in safe
    assert b"Figure 1" in safe


def test_vendor_artifact_egress_sanitizes_history_file(tmp_path, monkeypatch) -> None:
    from main import ensure_vendor_on_sys_path

    ensure_vendor_on_sys_path()
    import server

    output_root = tmp_path / "outputs"
    job_dir = output_root / "job-1"
    job_dir.mkdir(parents=True)
    (job_dir / "final.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "OUTPUTS_DIR", output_root)

    with TestClient(server.app) as client:
        response = client.get("/api/artifacts/job-1/final.svg")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSAFE_SVG_CONTENT"


def test_vendor_artifact_download_is_attachment_but_preview_is_inline(
    tmp_path, monkeypatch
) -> None:
    from main import ensure_vendor_on_sys_path

    ensure_vendor_on_sys_path()
    import server

    output_root = tmp_path / "outputs"
    job_dir = output_root / "job-1"
    job_dir.mkdir(parents=True)
    (job_dir / "final.svg").write_text(SAFE, encoding="utf-8")
    monkeypatch.setattr(server, "OUTPUTS_DIR", output_root)

    with TestClient(server.app) as client:
        preview = client.get("/api/artifacts/job-1/final.svg")
        download = client.get("/api/artifacts/job-1/final.svg?download=1")

    assert preview.status_code == 200
    assert "content-disposition" not in preview.headers
    assert download.status_code == 200
    assert download.headers["content-disposition"].startswith("attachment;")


def test_vendor_upload_egress_rejects_sibling_prefix_escape(tmp_path, monkeypatch) -> None:
    from main import ensure_vendor_on_sys_path

    ensure_vendor_on_sys_path()
    import server

    uploads = tmp_path / "uploads"
    sibling = tmp_path / "uploads-escape"
    uploads.mkdir()
    sibling.mkdir()
    (sibling / "secret.png").write_bytes(b"not-for-upload-route")
    monkeypatch.setattr(server, "UPLOADS_DIR", uploads)

    with pytest.raises(HTTPException) as exc_info:
        server.get_upload("../uploads-escape/secret.png")
    assert exc_info.value.status_code == 400


def test_uploaded_svg_uses_the_same_sanitized_egress(tmp_path, monkeypatch) -> None:
    from main import ensure_vendor_on_sys_path

    ensure_vendor_on_sys_path()
    import server

    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "unsafe.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "UPLOADS_DIR", uploads)

    with TestClient(server.app) as client:
        response = client.get("/api/uploads/unsafe.svg")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSAFE_SVG_CONTENT"


def test_vendor_upload_path_uses_app_data_root(tmp_path, monkeypatch) -> None:
    from main import ensure_vendor_on_sys_path

    ensure_vendor_on_sys_path()
    import server

    app_data = tmp_path / "app-data"
    uploads = app_data / "uploads"
    uploads.mkdir(parents=True)
    monkeypatch.setattr(server, "APP_DATA_DIR", app_data)
    monkeypatch.setattr(server, "UPLOADS_DIR", uploads)

    with TestClient(server.app) as client:
        response = client.post(
            "/api/upload",
            files={"file": ("reference.png", b"png", "image/png")},
        )

    assert response.status_code == 200
    payload = response.json()
    resolved = Path(server._resolve_client_path(payload["path"]))
    assert resolved.parent == uploads.resolve()
    assert resolved.is_file()
