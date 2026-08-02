"""Download the wheelhouse for a committed FigureSmith runtime lock.

The lock is the source of truth: every wheel is fetched from the exact URL it
pins and verified against its pinned SHA-256. pip is never asked to resolve
anything here, so the wheelhouse cannot drift from the lock.

Writes a variant-specific manifest (for example
``wheelhouse-cpu.manifest.json``) into the lock root, which
``figuresmith.runtime.locks`` then validates as part of the lock bundle.

Usage::

    python scripts/runtime/fetch_wheelhouse.py --variant cpu \
        --out build/wheelhouse-cpu
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend"))

from figuresmith.runtime.locks import (  # noqa: E402
    LOCK_SCHEMA,
    RuntimeLockError,
    requirements_lock_name,
    validate_requirements_lock,
    validate_wheelhouse_manifest,
    wheelhouse_manifest_name,
)

SUPPORTED_VARIANTS = ("cpu", "cu128")


class FetchError(RuntimeError):
    """Raised when a wheel cannot be fetched or fails its pinned digest."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, target: Path, expected: str, *, retries: int = 4) -> int:
    """Download url to target and verify it against its pinned digest.

    Wheel downloads are resumable. A transient TLS EOF after 100 MiB must not
    restart a 2.56 GiB torch wheel from byte zero; the next attempt requests the
    remaining range and hashes the complete partial before publication.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")

    for attempt in range(1, retries + 1):
        offset = partial.stat().st_size if partial.is_file() else 0
        headers = {"User-Agent": "FigureSmith-Runtime-Acquirer/1"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310
                # A server that ignores Range returns 200; starting at offset in
                # that case would append a second full wheel and fail the digest.
                resumed = offset > 0 and response.status == 206
                mode = "ab" if resumed else "wb"
                if offset and not resumed:
                    offset = 0
                with partial.open(mode) as handle:
                    while chunk := response.read(1024 * 512):
                        handle.write(chunk)
            actual = _sha256_file(partial)
            if actual != expected:
                partial.unlink(missing_ok=True)
                raise FetchError(
                    f"digest mismatch for {url}\n"
                    f"  expected {expected}\n  actual   {actual}"
                )
            size = partial.stat().st_size
            partial.replace(target)
            return size
        except FetchError:
            raise
        except (OSError, ssl.SSLError, urllib.error.URLError) as exc:
            if attempt == retries:
                raise FetchError(
                    f"download failed after {retries} attempts: {url} ({exc})"
                ) from exc
            have = partial.stat().st_size if partial.is_file() else 0
            print(
                f"    transient download error ({type(exc).__name__}); "
                f"retry {attempt}/{retries - 1} from {have / 1024 / 1024:.1f} MiB",
                file=sys.stderr,
            )
            time.sleep(min(2**attempt, 10))

    raise AssertionError("unreachable")


def fetch(variant: str, lock_root: Path, out: Path) -> Mapping[str, Any]:
    lock_path = lock_root / requirements_lock_name(variant)
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        checked = validate_requirements_lock(lock)
    except (OSError, json.JSONDecodeError) as exc:
        raise FetchError(f"cannot read lock: {lock_path}") from exc
    except RuntimeLockError as exc:
        raise FetchError(f"committed lock is invalid: {exc}") from exc

    out.mkdir(parents=True, exist_ok=True)
    packages = checked["packages"]
    files: list[dict[str, Any]] = []
    total = 0
    for index, package in enumerate(packages, start=1):
        target = out / package["wheel"]
        label = f"[{index}/{len(packages)}] {package['name']}=={package['version']}"
        if target.is_file() and _sha256_file(target) == package["sha256"]:
            size = target.stat().st_size
            print(f"  {label} (cached)", file=sys.stderr)
        else:
            print(f"  {label}", file=sys.stderr)
            size = _download(package["url"], target, package["sha256"])
        total += size
        files.append(
            {"path": package["wheel"], "size_bytes": size, "sha256": package["sha256"]}
        )

    manifest = {
        "schema": LOCK_SCHEMA,
        "product": "FigureSmith",
        "runtime": {"python": "3.12", "platform": "win_amd64", "cuda": variant},
        "file_count": len(files),
        "files": sorted(files, key=lambda item: item["path"].lower()),
    }
    validate_wheelhouse_manifest(manifest)
    manifest_path = lock_root / wheelhouse_manifest_name(variant)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"{len(files)} wheels, {total / 1024 / 1024:.0f} MiB -> {out}",
        file=sys.stderr,
    )
    print(f"wrote {manifest_path}", file=sys.stderr)
    return manifest


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", choices=SUPPORTED_VARIANTS, required=True)
    parser.add_argument("--lock-root", type=Path, default=REPO_ROOT / "locks")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        fetch(args.variant, args.lock_root, args.out)
    except FetchError as exc:
        print(f"wheelhouse fetch failed: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("wheelhouse fetch interrupted; partial files are kept for resume", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
