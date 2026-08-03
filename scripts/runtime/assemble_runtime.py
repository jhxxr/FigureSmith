"""Assemble a self-contained FigureSmith runtime pack from committed locks.

This is the *assembly* half of the acquisition split. It runs offline: every
input is either already in the wheelhouse or pinned by SHA-256 in the sources
lock, and pip is invoked with ``--no-index`` so an unlocked fetch fails loudly
instead of silently pulling a fresh build.

The result is a tree that starts with no system Python, no pip, and no network::

    <pack>/
      python/                     CPython embeddable + python312._pth
        Lib/site-packages/        resolved packages, installed at build time
      app/backend/  app/vendor/  app/resources/
      native/                     libcairo and its DLL closure
      locks/                      the exact locks this pack was built from
      runtime-manifest.json       schema 2, full SHA-256 inventory

Usage::

    python scripts/runtime/assemble_runtime.py --variant cpu \
        --wheelhouse build/wheelhouse-cpu --out dist-runtime/pack-cpu
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from figuresmith.runtime.locks import (  # noqa: E402
    RuntimeLockError,
    render_pip_requirements,
    requirements_lock_name,
    sources_lock_name,
    validate_lock_bundle,
    validate_requirements_lock,
    validate_sources_lock,
    wheelhouse_manifest_name,
)
from figuresmith.runtime.manifest import (  # noqa: E402
    SITE_PACKAGES_DIR,
    verify_runtime_manifest,
    write_runtime_manifest,
)

SUPPORTED_VARIANTS = ("cpu", "cu128")

# The embeddable interpreter's isolation policy. Its mere presence disables
# user-site and registry lookups; `import site` is required so that
# site-packages is processed at all, which native extensions depend on.
PTH_CONTENT = """python312.zip
.
Lib\\site-packages
import site
"""

# Application trees copied into the pack, as (source, destination) pairs.
APPLICATION_TREES = (
    ("apps/backend", "app/backend"),
    ("vendor/autofigure_edit", "app/vendor/autofigure_edit"),
    ("vendor/svg_edit", "app/vendor/svg_edit"),
    ("resources", "app/resources"),
)
LEGAL_FILES = ("LICENSE", "NOTICE.md", "THIRD_PARTY_NOTICES.md", "VERSION")

_EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".staging",
    ".trash",
    ".venv",
    "venv",
    "node_modules",
    "outputs",
    "target",
    "uploads",
}
_WEIGHT_SUFFIXES = {
    ".pt", ".pth", ".onnx", ".safetensors", ".gguf", ".ckpt", ".h5", ".pb", ".bin"
}


class AssemblyError(RuntimeError):
    """Raised when a pack cannot be assembled from the committed locks."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_lock(path: Path) -> Mapping[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssemblyError(f"cannot read lock: {path}") from exc


def _source_cache_path(url: str, expected_sha256: str, cache: Path) -> Path:
    """Return the deterministic cache path for a pinned source archive."""
    filename = Path(urllib.parse.urlsplit(url).path).name
    if not filename:
        raise AssemblyError(f"source URL does not name an archive: {url}")
    return cache / f"{expected_sha256[:16]}-{filename}"


def _cached_source(url: str, expected_sha256: str, cache: Path) -> Path:
    """Return a verified source archive without performing network I/O.

    Source acquisition belongs to the network-enabled acquire phase. Assembly is
    deliberately cache-only so a missing input fails closed instead of silently
    making an allegedly offline build depend on network availability.
    """
    target = _source_cache_path(url, expected_sha256, cache)
    if not target.is_file():
        raise AssemblyError(
            f"pinned source archive is missing from the offline cache: {target}"
        )
    actual = _sha256_file(target)
    if actual != expected_sha256:
        raise AssemblyError(
            f"cached source digest mismatch: {target}\n"
            f"  expected {expected_sha256}\n  actual   {actual}"
        )
    return target


def fetch_sources(lock_root: Path, variant: str, cache: Path) -> list[Path]:
    """Acquire pinned non-wheel inputs for a later offline assembly."""
    sources_lock = _read_lock(lock_root / sources_lock_name(variant))
    try:
        checked = validate_sources_lock(sources_lock)
    except RuntimeLockError as exc:
        raise AssemblyError(f"committed sources lock is invalid: {exc}") from exc
    if checked["variant"] != variant:
        raise AssemblyError("sources lock variant does not match the requested variant")

    cache.mkdir(parents=True, exist_ok=True)
    acquired: list[Path] = []
    for source in checked["sources"]:
        target = _source_cache_path(source["url"], source["sha256"], cache)
        if target.is_file() and _sha256_file(target) == source["sha256"]:
            acquired.append(target)
            continue
        partial = target.with_suffix(target.suffix + ".part")
        partial.unlink(missing_ok=True)
        print(f"  fetching {target.name} ...", file=sys.stderr)
        try:
            with urllib.request.urlopen(source["url"], timeout=300) as response:  # noqa: S310
                with partial.open("wb") as handle:
                    shutil.copyfileobj(response, handle, length=1024 * 1024)
        except OSError as exc:
            partial.unlink(missing_ok=True)
            raise AssemblyError(f"source download failed: {source['url']}") from exc
        actual = _sha256_file(partial)
        if actual != source["sha256"]:
            partial.unlink(missing_ok=True)
            raise AssemblyError(
                f"source digest mismatch for {source['url']}\n"
                f"  expected {source['sha256']}\n  actual   {actual}"
            )
        partial.replace(target)
        acquired.append(target)
    return acquired


def _extract_cpython(archive: Path, python_dir: Path) -> None:
    python_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(python_dir)
    # The embeddable ships its own ._pth; replace it with our isolation policy.
    for stale in python_dir.glob("*._pth"):
        stale.unlink()
    (python_dir / "python312._pth").write_text(PTH_CONTENT, encoding="utf-8", newline="\n")
    if not (python_dir / "python.exe").is_file():
        raise AssemblyError(f"CPython archive did not yield python.exe: {archive}")


def _extract_native_dlls(
    packages: Iterable[tuple[Path, str]], wanted: set[str], native_dir: Path
) -> list[str]:
    """Extract the named DLLs from MSYS2 packages into native_dir."""
    try:
        import zstandard
    except ImportError as exc:  # pragma: no cover - environment guard
        raise AssemblyError(
            "the zstandard package is required to unpack MSYS2 archives; "
            "install it into the build environment"
        ) from exc

    native_dir.mkdir(parents=True, exist_ok=True)
    found: list[str] = []
    remaining = {name.lower() for name in wanted}
    for archive, name in packages:
        raw = zstandard.ZstdDecompressor().stream_reader(archive.open("rb")).read()
        with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
            for member in tar.getmembers():
                base = Path(member.name).name
                if base.lower() not in remaining or "/bin/" not in member.name:
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                (native_dir / base).write_bytes(handle.read())
                remaining.discard(base.lower())
                found.append(base)
    if remaining:
        raise AssemblyError(
            "native DLLs missing from the pinned MSYS2 packages: "
            + ", ".join(sorted(remaining))
        )
    return sorted(found)


def _copy_application(pack: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        skipped = {name for name in names if name.lower() in _EXCLUDED_DIRS}
        for name in names:
            if Path(name).suffix.lower() in _WEIGHT_SUFFIXES:
                skipped.add(name)
        return skipped

    for source_rel, dest_rel in APPLICATION_TREES:
        source = REPO_ROOT / source_rel
        if not source.is_dir():
            raise AssemblyError(f"application tree is missing: {source}")
        shutil.copytree(source, pack / dest_rel, ignore=ignore, dirs_exist_ok=True)

    # resources/models is weight staging and must never enter the pack.
    staged_models = pack / "app" / "resources" / "models"
    if staged_models.exists():
        shutil.rmtree(staged_models)

    for name in LEGAL_FILES:
        source = REPO_ROOT / name
        if source.is_file():
            shutil.copy2(source, pack / name)


def _install_packages(
    pack: Path, requirements: Path, wheelhouse: Path, builder_python: Path
) -> None:
    """Install the locked closure into the pack's site-packages, offline."""
    target = pack / SITE_PACKAGES_DIR
    target.mkdir(parents=True, exist_ok=True)
    command = [
        str(builder_python), "-m", "pip", "install",
        "--no-index",
        "--find-links", str(wheelhouse),
        "--require-hashes",
        "--no-deps",
        "--no-compile",
        "--only-binary", ":all:",
        "--python-version", "3.12",
        "--platform", "win_amd64",
        "--abi", "cp312",
        "--target", str(target),
        "--requirement", str(requirements),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssemblyError(
            "offline install failed:\n" + (result.stderr or result.stdout)[-4000:]
        )


def _assert_builder_python(builder_python: Path) -> None:
    """Require the build interpreter to match the locked CPython minor version."""
    probe = (
        "import platform, sys; "
        "print(platform.python_implementation()); "
        "print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    )
    try:
        result = subprocess.run(
            [str(builder_python), "-c", probe],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise AssemblyError(
            f"cannot execute the Runtime V1 builder Python: {builder_python}"
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AssemblyError(
            f"Runtime V1 builder Python failed its version probe: {builder_python}"
            + (f" ({detail[-500:]})" if detail else "")
        )
    identity = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if identity[:2] != ["CPython", "3.12"]:
        actual = " ".join(identity[:2]) if identity else "unknown"
        raise AssemblyError(
            "Runtime V1 assembly requires CPython 3.12 on the build machine; "
            f"got {actual} from {builder_python}"
        )


def _strip_non_runtime_install_artifacts(pack: Path) -> tuple[int, int]:
    """Remove pip-generated files whose bytes are deliberately non-deterministic.

    Windows console launchers in ``site-packages/bin`` embed an installer-chosen
    executable stub, and each corresponding ``dist-info/RECORD`` records that
    random launcher's digest. FigureSmith invokes modules through its own
    embedded interpreter and never uses those console scripts, so both are
    build artifacts rather than runtime inputs. Removing them makes two clean
    assemblies byte-identical without deleting importable package metadata.
    """
    site_packages = pack / SITE_PACKAGES_DIR
    launchers = site_packages / "bin"
    launcher_count = 0
    if launchers.is_dir():
        launcher_count = sum(1 for path in launchers.rglob("*") if path.is_file())
        shutil.rmtree(launchers)

    record_count = 0
    for record in site_packages.glob("*.dist-info/RECORD"):
        record.unlink()
        record_count += 1
    return launcher_count, record_count


def _strip_caches(pack: Path) -> int:
    """Remove __pycache__ trees; .pyc embeds absolute paths and mtimes."""
    removed = 0
    for cache in sorted(pack.rglob("__pycache__"), reverse=True):
        if cache.is_dir():
            shutil.rmtree(cache)
            removed += 1
    for stray in pack.rglob("*.pyc"):
        stray.unlink()
        removed += 1
    return removed


def assemble(
    *,
    variant: str,
    lock_root: Path,
    wheelhouse: Path,
    out: Path,
    cache: Path,
    version: str,
    builder_python: Path,
) -> Path:
    if variant not in SUPPORTED_VARIANTS:
        raise AssemblyError(f"unsupported variant: {variant}")

    requirements_lock = _read_lock(lock_root / requirements_lock_name(variant))
    sources_lock = _read_lock(lock_root / sources_lock_name(variant))
    try:
        checked_requirements = validate_requirements_lock(requirements_lock)
        checked_sources = validate_sources_lock(sources_lock)
    except RuntimeLockError as exc:
        raise AssemblyError(f"committed locks are invalid: {exc}") from exc
    if checked_requirements["variant"] != variant or checked_sources["variant"] != variant:
        raise AssemblyError("lock variant does not match the requested variant")
    try:
        validate_lock_bundle(lock_root, wheelhouse_root=wheelhouse, variant=variant)
    except RuntimeLockError as exc:
        raise AssemblyError(f"wheelhouse does not match the committed locks: {exc}") from exc
    _assert_builder_python(builder_python)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    print(f"assembling {variant} pack -> {out}", file=sys.stderr)

    sources_by_name = {item["name"]: item for item in checked_sources["sources"]}
    cpython = sources_by_name.get("cpython-embeddable")
    if cpython is None:
        raise AssemblyError("sources lock does not pin cpython-embeddable")
    archive = _cached_source(cpython["url"], cpython["sha256"], cache)
    _extract_cpython(archive, out / "python")
    print("  interpreter extracted", file=sys.stderr)

    msys_packages: list[tuple[Path, str]] = []
    for name, item in sorted(sources_by_name.items()):
        if not name.startswith("msys2-"):
            continue
        msys_packages.append((_cached_source(item["url"], item["sha256"], cache), name))
    wanted = set(sources_lock.get("native_dlls") or ())
    if wanted:
        extracted = _extract_native_dlls(msys_packages, wanted, out / "native")
        # Windows safe DLL search includes the executable directory. cairocffi
        # dlopens `libcairo-2.dll` by basename, so keeping the chain only in a
        # sibling native/ directory is not enough when PATH is scrubbed. Copy
        # the verified DLLs beside python.exe as well; manifest hashes both.
        for name in extracted:
            shutil.copy2(out / "native" / name, out / "python" / name)
        print(f"  {len(extracted)} native DLLs extracted", file=sys.stderr)

    _copy_application(out)
    print("  application copied", file=sys.stderr)

    requirements_txt = out / "locks" / f"requirements-{variant}.txt"
    requirements_txt.parent.mkdir(parents=True, exist_ok=True)
    requirements_txt.write_text(
        render_pip_requirements(requirements_lock), encoding="utf-8", newline="\n"
    )
    _install_packages(out, requirements_txt, wheelhouse, builder_python)
    print(f"  {checked_requirements['package_count']} packages installed", file=sys.stderr)

    lock_names = (
        requirements_lock_name(variant),
        sources_lock_name(variant),
        wheelhouse_manifest_name(variant),
    )
    for name in lock_names:
        shutil.copy2(lock_root / name, out / "locks" / name)

    launchers, records = _strip_non_runtime_install_artifacts(out)
    if launchers or records:
        print(
            f"  stripped {launchers} console launchers and {records} RECORD files",
            file=sys.stderr,
        )
    removed = _strip_caches(out)
    if removed:
        print(f"  stripped {removed} cache entries", file=sys.stderr)

    locks_digest = {
        "requirements": _sha256_bytes(
            (lock_root / requirements_lock_name(variant)).read_bytes()
        ),
        "sources": _sha256_bytes((lock_root / sources_lock_name(variant)).read_bytes()),
        "wheelhouse": _sha256_bytes(
            (lock_root / wheelhouse_manifest_name(variant)).read_bytes()
        ),
    }
    manifest_path = write_runtime_manifest(
        out,
        version=version,
        variant=variant,
        python_version=str(cpython["version"]),
        python_source_sha256=str(cpython["sha256"]),
        locks=locks_digest,
    )
    manifest = verify_runtime_manifest(manifest_path, out)
    print(
        f"  manifest verified: {manifest['file_count']} files, "
        f"python {manifest['python']['version']}",
        file=sys.stderr,
    )
    return out


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", choices=SUPPORTED_VARIANTS, required=True)
    parser.add_argument("--lock-root", type=Path, default=REPO_ROOT / "locks")
    parser.add_argument("--wheelhouse", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--cache", type=Path, default=REPO_ROOT / "build" / "source-cache")
    parser.add_argument("--version", default=None)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--fetch-sources",
        action="store_true",
        help="acquire pinned source archives into --cache, then exit",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.fetch_sources:
            acquired = fetch_sources(args.lock_root, args.variant, args.cache)
            print(f"acquired {len(acquired)} source archives -> {args.cache}", file=sys.stderr)
            return 0

        if args.wheelhouse is None or args.out is None:
            parser.error("--wheelhouse and --out are required for assembly")

        version = args.version
        if version is None:
            version_file = REPO_ROOT / "VERSION"
            version = (
                version_file.read_text(encoding="utf-8").strip()
                if version_file.is_file()
                else "0.0.0-dev"
            )

        assemble(
            variant=args.variant,
            lock_root=args.lock_root,
            wheelhouse=args.wheelhouse,
            out=args.out,
            cache=args.cache,
            version=version,
            builder_python=args.python,
        )
    except AssemblyError as exc:
        print(f"assembly failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
