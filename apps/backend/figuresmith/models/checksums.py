"""SHA-256 helpers for model import verification (Phase 3)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Mapping, Optional, Union

PathLike = Union[str, Path]

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def sha256_file(path: PathLike, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Compute lowercase hex SHA-256 of a file without loading it fully."""
    p = Path(path)
    digest = hashlib.sha256()
    with open(p, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """SHA-256 of an in-memory buffer (tests / small fixtures)."""
    return hashlib.sha256(data).hexdigest()


def sha256_paths(
    paths: Iterable[PathLike],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    relative_to: Optional[PathLike] = None,
) -> dict[str, str]:
    """Return mapping of path key → sha256 for each existing file.

    Keys are relative to ``relative_to`` when provided, otherwise the file name.
    """
    root = Path(relative_to).resolve() if relative_to is not None else None
    out: dict[str, str] = {}
    for raw in paths:
        p = Path(raw)
        if not p.is_file():
            continue
        if root is not None:
            try:
                key = str(p.resolve().relative_to(root)).replace("\\", "/")
            except ValueError:
                key = p.name
        else:
            key = p.name
        out[key] = sha256_file(p, chunk_size=chunk_size)
    return out


def write_checksum_file(
    destination: PathLike,
    digest: str,
    *,
    filename: str = "checksum.sha256",
    labeled_name: Optional[str] = None,
) -> Path:
    """Write a simple ``checksum.sha256`` file next to imported model content.

    Format (GNU coreutils style)::

        <hex>  <name>
    """
    dest_dir = Path(destination)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / filename
    name = labeled_name or "model"
    out.write_text(f"{digest.lower()}  {name}\n", encoding="utf-8")
    return out


def read_checksum_file(path: PathLike) -> Optional[str]:
    """Parse the first hex digest from a checksum file, if present."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    first = text.splitlines()[0].strip().split()
    if not first:
        return None
    digest = first[0].lower()
    if len(digest) == 64 and all(c in "0123456789abcdef" for c in digest):
        return digest
    return None


def digests_equal(a: Optional[str], b: Optional[str]) -> bool:
    """Constant-time-ish compare of hex digests (case-insensitive)."""
    if a is None or b is None:
        return False
    left = a.strip().lower()
    right = b.strip().lower()
    if len(left) != len(right):
        return False
    # Use hmac.compare_digest when available for timing safety.
    import hmac

    return hmac.compare_digest(left, right)


def multi_file_digest(
    file_digests: Mapping[str, str],
    *,
    algorithm: str = "sha256",
) -> str:
    """Stable combined digest over a sorted map of relative path → file digest."""
    h = hashlib.new(algorithm)
    for key in sorted(file_digests.keys()):
        h.update(key.encode("utf-8"))
        h.update(b"\0")
        h.update(str(file_digests[key]).lower().encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()
