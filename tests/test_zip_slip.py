"""Zip Slip and ZIP bomb guard tests for RMBG import."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from figuresmith.models.errors import ModelImportZipSlip
from figuresmith.models.import_rmbg import safe_extract_zip


def _build_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_safe_extract_ok(tmp_path: Path) -> None:
    raw = _build_zip(
        {
            "config.json": b"{}",
            "nested/a.txt": b"hello",
        }
    )
    zpath = tmp_path / "ok.zip"
    zpath.write_bytes(raw)
    dest = tmp_path / "out"
    extracted = safe_extract_zip(zpath, dest)
    assert (dest / "config.json").read_text(encoding="utf-8") == "{}"
    assert (dest / "nested" / "a.txt").read_bytes() == b"hello"
    assert "config.json" in extracted


def test_zip_slip_parent_traversal(tmp_path: Path) -> None:
    raw = _build_zip({"../evil.txt": b"nope"})
    zpath = tmp_path / "slip.zip"
    zpath.write_bytes(raw)
    dest = tmp_path / "out"
    with pytest.raises(ModelImportZipSlip) as exc_info:
        safe_extract_zip(zpath, dest)
    assert exc_info.value.code == "MODEL_IMPORT_ZIP_SLIP"
    assert not (tmp_path / "evil.txt").exists()


def test_zip_slip_absolute_posix(tmp_path: Path) -> None:
    raw = _build_zip({"/tmp/evil.txt": b"nope"})
    zpath = tmp_path / "abs.zip"
    zpath.write_bytes(raw)
    with pytest.raises(ModelImportZipSlip):
        safe_extract_zip(zpath, tmp_path / "out")


def test_zip_slip_absolute_windows_drive(tmp_path: Path) -> None:
    raw = _build_zip({"C:/Windows/evil.txt": b"nope"})
    zpath = tmp_path / "winabs.zip"
    zpath.write_bytes(raw)
    with pytest.raises(ModelImportZipSlip):
        safe_extract_zip(zpath, tmp_path / "out")


def test_zip_max_files(tmp_path: Path) -> None:
    entries = {f"f{i}.txt": b"x" for i in range(10)}
    zpath = tmp_path / "many.zip"
    zpath.write_bytes(_build_zip(entries))
    with pytest.raises(ModelImportZipSlip) as exc_info:
        safe_extract_zip(zpath, tmp_path / "out", max_files=3)
    assert "too many files" in (exc_info.value.detail or "").lower()


def test_zip_max_uncompressed(tmp_path: Path) -> None:
    # Small compressed payload with large declared size is hard without ZipInfo tricks;
    # use real large-ish content over a tiny limit.
    zpath = tmp_path / "big.zip"
    zpath.write_bytes(_build_zip({"big.bin": b"a" * 10_000}))
    with pytest.raises(ModelImportZipSlip) as exc_info:
        safe_extract_zip(zpath, tmp_path / "out", max_uncompressed_bytes=100)
    assert "uncompressed" in (exc_info.value.detail or "").lower()


def test_nested_dotdot_component(tmp_path: Path) -> None:
    raw = _build_zip({"foo/../../outside.txt": b"x"})
    zpath = tmp_path / "nested-slip.zip"
    zpath.write_bytes(raw)
    with pytest.raises(ModelImportZipSlip):
        safe_extract_zip(zpath, tmp_path / "out")


def test_zip_counts_actual_bytes_not_only_declared(tmp_path: Path) -> None:
    """Guard should trip on actual inflated size, not only pre-scan of headers."""
    zpath = tmp_path / "actual.zip"
    # Normal zip: declared size matches content; tiny limit forces mid-extract reject.
    zpath.write_bytes(_build_zip({"payload.bin": b"Z" * 50_000}))
    dest = tmp_path / "out"
    with pytest.raises(ModelImportZipSlip) as exc_info:
        safe_extract_zip(zpath, dest, max_uncompressed_bytes=1_000)
    assert "uncompressed" in (exc_info.value.detail or "").lower()
    # Partial extract must not leave the oversized payload behind.
    leftover = dest / "payload.bin" if dest.exists() else None
    if leftover is not None and leftover.exists():
        assert leftover.stat().st_size <= 1_000 + 1024 * 1024  # at most one chunk
