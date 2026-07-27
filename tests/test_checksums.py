"""Unit tests for SHA-256 helpers and staging promote/rollback."""

from __future__ import annotations

from pathlib import Path

import pytest

from figuresmith.models.checksums import (
    digests_equal,
    multi_file_digest,
    read_checksum_file,
    sha256_bytes,
    sha256_file,
    write_checksum_file,
)
from figuresmith.models.staging import (
    atomic_promote,
    cleanup_dir,
    create_staging_dir,
    prune_trash,
    stream_copy_file,
)


def test_sha256_file_and_bytes(tmp_path: Path) -> None:
    data = b"figuresmith-phase3"
    f = tmp_path / "sample.bin"
    f.write_bytes(data)
    assert sha256_file(f) == sha256_bytes(data)
    assert len(sha256_file(f)) == 64


def test_write_and_read_checksum_file(tmp_path: Path) -> None:
    digest = sha256_bytes(b"abc")
    path = write_checksum_file(tmp_path, digest, labeled_name="sam3.pt")
    assert path.is_file()
    assert read_checksum_file(path) == digest
    assert digests_equal(digest, digest.upper())
    assert not digests_equal(digest, "0" * 64)


def test_multi_file_digest_stable_order() -> None:
    a = multi_file_digest({"b": "11", "a": "22"})
    b = multi_file_digest({"a": "22", "b": "11"})
    assert a == b
    assert a != multi_file_digest({"a": " rep", "b": "11"})


def test_create_staging_and_cleanup(tmp_path: Path) -> None:
    staging = create_staging_dir("sam3", app_data_dir=tmp_path)
    assert staging.is_dir()
    assert staging.parent.name == ".staging"
    (staging / "x.txt").write_text("ok", encoding="utf-8")
    cleanup_dir(staging)
    assert not staging.exists()


def test_atomic_promote_fresh(tmp_path: Path) -> None:
    staging = create_staging_dir("sam3", app_data_dir=tmp_path)
    (staging / "sam3.pt").write_bytes(b"weights-v1")
    dest = tmp_path / "models" / "sam3"
    result = atomic_promote(staging, dest, app_data_dir=tmp_path, model_id="sam3")
    assert result.destination == dest.resolve() or result.destination == dest
    assert (dest / "sam3.pt").read_bytes() == b"weights-v1"
    assert not staging.exists()
    assert result.replaced_existing is False


def test_atomic_promote_replaces_and_keeps_trash(tmp_path: Path) -> None:
    dest = tmp_path / "models" / "sam3"
    dest.mkdir(parents=True)
    (dest / "sam3.pt").write_bytes(b"old-weights")

    staging = create_staging_dir("sam3", app_data_dir=tmp_path)
    (staging / "sam3.pt").write_bytes(b"new-weights")

    result = atomic_promote(
        staging, dest, app_data_dir=tmp_path, model_id="sam3", keep_trash=3
    )
    assert (dest / "sam3.pt").read_bytes() == b"new-weights"
    assert result.replaced_existing is True
    assert result.trash_path is not None
    assert result.trash_path.is_dir()
    assert (result.trash_path / "sam3.pt").read_bytes() == b"old-weights"


def test_atomic_promote_restore_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "models" / "rmbg-2.0"
    dest.mkdir(parents=True)
    (dest / "marker.txt").write_text("keep-me", encoding="utf-8")

    staging = create_staging_dir("rmbg-2.0", app_data_dir=tmp_path)
    (staging / "new.txt").write_text("new", encoding="utf-8")

    real_move = __import__("shutil").move
    staging_res = staging.resolve()
    dest_res = dest.resolve()

    def flaky_move(src: str, dst: str) -> str:
        # Allow dest→trash and trash→dest restore; fail only staging→dest promote.
        if Path(src).resolve() == staging_res and Path(dst).resolve() == dest_res:
            raise PermissionError("simulated lock")
        return real_move(src, dst)

    monkeypatch.setattr("figuresmith.models.staging.shutil.move", flaky_move)

    with pytest.raises(Exception):
        atomic_promote(staging, dest, app_data_dir=tmp_path, model_id="rmbg-2.0")

    # Previous model restored.
    assert dest.is_dir()
    assert (dest / "marker.txt").read_text(encoding="utf-8") == "keep-me"


def test_stream_copy_file(tmp_path: Path) -> None:
    src = tmp_path / "src.pt"
    src.write_bytes(b"x" * 10_000)
    dst = tmp_path / "nested" / "dst.pt"
    n = stream_copy_file(src, dst, chunk_size=1024)
    assert n == 10_000
    assert dst.read_bytes() == src.read_bytes()


def test_prune_trash(tmp_path: Path) -> None:
    trash = tmp_path / "models" / ".trash"
    trash.mkdir(parents=True)
    paths = []
    for i in range(5):
        p = trash / f"sam3-2026010{i}-aaaa"
        p.mkdir()
        (p / "f").write_text(str(i), encoding="utf-8")
        paths.append(p)
        # Ensure distinct mtimes
        import os
        import time

        os.utime(p, (time.time() + i, time.time() + i))
    removed = prune_trash(model_id="sam3", app_data_dir=tmp_path, keep=2)
    assert removed == 3
    remaining = list((tmp_path / "models" / ".trash").iterdir())
    assert len(remaining) == 2
