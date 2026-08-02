"""Resolve FigureSmith's Windows runtime dependency closure into committed locks.

Runtime V1 ships a pre-installed interpreter, so the dependency set must be a
property of the FigureSmith version rather than of the install date. This script
performs the *acquisition* half of that contract: it resolves an exact closure
and writes ``requirements-win-py312-<variant>.lock.json`` plus
``sources-<variant>.lock.json``.

Resolution runs with ``pip install --dry-run --report``, which returns every
resolved distribution with its URL and SHA-256 without downloading any wheel.
The multi-GB download and resulting ``wheelhouse-<variant>.manifest.json`` belong to
CI; this script only needs the network long enough to read metadata, plus the
small archives it must hash itself.

Assembly consumes the locks offline and never re-resolves.

Usage::

    python scripts/runtime/resolve_locks.py --variant cpu   --out locks
    python scripts/runtime/resolve_locks.py --variant cu128 --out locks
    python scripts/runtime/resolve_locks.py --sources-only  --out locks
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_VERSION = "3.12"
ABI = "cp312"
PLATFORM = "win_amd64"
LOCK_SCHEMA = 1
SUPPORTED_VARIANTS = ("cpu", "cu128")
# 26.2 is verified; 24.0 is verified broken. Anything between is untested, so
# the floor sits at the lowest version actually measured to work.
MIN_PIP_VERSION = (26, 2)

PYPI_INDEX = "https://pypi.org/simple"
TORCH_INDEX = "https://download.pytorch.org/whl/{variant}"

# The cu128 index lags PyPI. With an unbounded `torch>=2.1`, pip merges both
# indexes and prefers PyPI's newer build, which has no CUDA wheels — producing a
# pack labelled cu128 that is actually CPU-only. Measured: PyPI carried torch
# 2.13.0 while the cu128 index topped out at 2.11.0, and the two variants
# resolved to byte-identical closures.
#
# Pin the newest pair that actually exists on the cu128 index. Bumping these is
# a deliberate act: check the index first, then move both together.
VARIANT_CONSTRAINTS: Mapping[str, tuple[str, ...]] = {
    "cpu": (),
    "cu128": ("torch==2.11.0+cu128", "torchvision==0.26.0+cu128"),
}

# Direct inputs. These files are the reviewable declaration of intent; the lock
# is the resolved consequence. Editing a range here and re-running is the only
# supported way to move a pin.
DIRECT_REQUIREMENTS = (
    REPO_ROOT / "scripts" / "runtime" / "requirements-bootstrap.txt",
    REPO_ROOT / "scripts" / "runtime" / "requirements-models.txt",
)

# CPython embeddable: the interpreter the pack ships. Pinned by exact release.
CPYTHON = {
    "name": "cpython-embeddable",
    "kind": "archive",
    "version": "3.12.10",
    "url": (
        "https://www.python.org/ftp/python/3.12.10/"
        "python-3.12.10-embed-amd64.zip"
    ),
    "license": "PSF-2.0",
}

# cairosvg reaches outside its wheel for libcairo-2.dll through cairocffi, which
# dlopens a real DLL. No PyPI wheel supplies one, and pycairo's wheel links cairo
# statically into a .pyd that cairocffi cannot use. See
# research/cairosvg-decision.md for the measured 14-DLL / 8.3 MB closure.
MSYS2_BASE = "https://repo.msys2.org/mingw/mingw64/"
# Filenames are verified against the live index by --refresh-msys2 rather than
# hand-maintained; MSYS2 rebuilds packages often and stale pins 404.
MSYS2_PACKAGES = (
    ("cairo", "mingw-w64-x86_64-cairo-1.18.4-4-any.pkg.tar.zst", "LGPL-2.1-only OR MPL-1.1"),
    ("fontconfig", "mingw-w64-x86_64-fontconfig-2.18.2-1-any.pkg.tar.zst", "MIT"),
    ("freetype", "mingw-w64-x86_64-freetype-2.14.3-1-any.pkg.tar.zst", "FTL OR GPL-2.0-or-later"),
    ("pixman", "mingw-w64-x86_64-pixman-0.46.4-3-any.pkg.tar.zst", "MIT"),
    ("libpng", "mingw-w64-x86_64-libpng-1.6.58-1-any.pkg.tar.zst", "Libpng"),
    ("zlib", "mingw-w64-x86_64-zlib-1.3.2-2-any.pkg.tar.zst", "Zlib"),
    ("bzip2", "mingw-w64-x86_64-bzip2-1.0.8-3-any.pkg.tar.zst", "bzip2-1.0.6"),
    ("brotli", "mingw-w64-x86_64-brotli-1.2.0-1-any.pkg.tar.zst", "MIT"),
    ("expat", "mingw-w64-x86_64-expat-2.8.2-1-any.pkg.tar.zst", "MIT"),
    ("graphite2", "mingw-w64-x86_64-graphite2-1.3.15-1-any.pkg.tar.zst", "LGPL-2.1-or-later"),
    ("harfbuzz", "mingw-w64-x86_64-harfbuzz-14.2.1-1-any.pkg.tar.zst", "MIT"),
    ("gcc-libs", "mingw-w64-x86_64-gcc-libs-16.1.0-5-any.pkg.tar.zst", "GPL-3.0-or-later WITH GCC-exception-3.1"),
    ("gettext-runtime", "mingw-w64-x86_64-gettext-runtime-1.0-1-any.pkg.tar.zst", "LGPL-2.1-or-later"),
    ("glib2", "mingw-w64-x86_64-glib2-2.88.3-1-any.pkg.tar.zst", "LGPL-2.1-or-later"),
    ("libwinpthread", "mingw-w64-x86_64-libwinpthread-14.0.0.r220.gd999af622-1-any.pkg.tar.zst", "MIT"),
    ("libiconv", "mingw-w64-x86_64-libiconv-1.19-1-any.pkg.tar.zst", "LGPL-2.1-or-later"),
    ("pcre2", "mingw-w64-x86_64-pcre2-10.47-1-any.pkg.tar.zst", "BSD-3-Clause"),
)

# DLLs extracted from the packages above, in the measured closure order.
CAIRO_DLLS = (
    "libcairo-2.dll",
    "libfontconfig-1.dll",
    "libfreetype-6.dll",
    "libpixman-1-0.dll",
    "libpng16-16.dll",
    "zlib1.dll",
    "libbz2-1.dll",
    "libbrotlicommon.dll",
    "libbrotlidec.dll",
    "libexpat-1.dll",
    "libgraphite2.dll",
    "libharfbuzz-0.dll",
    "libgcc_s_seh-1.dll",
    "libstdc++-6.dll",
    "libglib-2.0-0.dll",
    "libintl-8.dll",
    "libwinpthread-1.dll",
    "libiconv-2.dll",
    "libpcre2-8-0.dll",
)

_WHEEL_RE = re.compile(
    r"^(?P<name>.+?)-(?P<version>[^-]+?)"
    r"(?:-(?P<build>\d[^-]*?))?"
    r"-(?P<python>[^-]+)-(?P<abi>[^-]+)-(?P<platform>[^-]+)\.whl$"
)
_MSYS2_VERSION_RE = re.compile(r"-(\d[0-9A-Za-z.+]*?)-(\d+)-any\.pkg\.tar\.zst$")


class ResolveError(RuntimeError):
    """Raised when a closure cannot be resolved into an exact, hashed lock."""


def _wheel_filename(url: str) -> str:
    """Return the decoded wheel basename from a resolver download URL."""
    return urllib.parse.unquote(url.rsplit("/", 1)[-1].split("#", 1)[0])


def _wheel_tags(filename: str) -> list[str]:
    match = _WHEEL_RE.match(filename)
    if not match:
        raise ResolveError(f"cannot parse wheel filename: {filename}")
    return [f"{match['python']}-{match['abi']}-{match['platform']}"]


def _license_of(metadata: Mapping[str, Any]) -> str:
    """Best-effort license extraction from PEP 566 metadata."""
    expression = metadata.get("license_expression")
    if isinstance(expression, str) and expression.strip():
        return expression.strip()
    declared = metadata.get("license")
    if isinstance(declared, str) and declared.strip():
        # Some projects dump the entire license text into this field.
        first = declared.strip().splitlines()[0].strip()
        if first and len(first) <= 80:
            return first
    for classifier in metadata.get("classifier", []) or []:
        if isinstance(classifier, str) and classifier.startswith("License ::"):
            return classifier.rsplit("::", 1)[-1].strip()
    return ""


def _assert_pip_is_new_enough(interpreter: Path) -> None:
    """Refuse to resolve with a pip that ignores PEP 658 metadata.

    The PyTorch index advertises ``data-core-metadata`` on every wheel, but old
    pip fetches the wheel body anyway. Measured on the cu128 index resolving
    torch + torchvision:

    - pip 24.0 — no report after 5 minutes, 1.8 GB pulled into the http cache
    - pip 26.2 — complete report in 3.45 seconds

    A resolve that downloads multi-GB wheels to read their dependencies is not
    viable in CI either, so this fails fast with an actionable message.
    """
    result = subprocess.run(
        [str(interpreter), "-m", "pip", "--version"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ResolveError(f"cannot determine pip version: {result.stderr.strip()}")
    match = re.search(r"pip (\d+)\.(\d+)", result.stdout)
    if not match:
        raise ResolveError(f"cannot parse pip version from: {result.stdout.strip()}")
    version = (int(match.group(1)), int(match.group(2)))
    if version < MIN_PIP_VERSION:
        wanted = ".".join(str(part) for part in MIN_PIP_VERSION)
        found = ".".join(str(part) for part in version)
        raise ResolveError(
            f"pip {found} is too old to resolve the PyTorch index efficiently; "
            f"pip >= {wanted} is required (it honours PEP 658 metadata instead "
            "of downloading whole wheels). Run: "
            f'"{interpreter}" -m pip install --upgrade pip'
        )


def _resolve_closure(variant: str, python: str) -> list[dict[str, Any]]:
    """Return the resolved closure without downloading any wheel."""
    for path in DIRECT_REQUIREMENTS:
        if not path.is_file():
            raise ResolveError(f"direct requirements file is missing: {path}")

    interpreter = Path(python).expanduser()
    if not interpreter.is_absolute():
        interpreter = (Path.cwd() / interpreter).resolve()
    if not interpreter.is_file():
        raise ResolveError(f"interpreter does not exist: {interpreter}")
    _assert_pip_is_new_enough(interpreter)

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "report.json"
        command = [
            str(interpreter), "-m", "pip", "install",
            "--dry-run", "--ignore-installed", "--quiet",
            "--report", str(report_path),
            "--only-binary", ":all:",
            "--python-version", PYTHON_VERSION,
            "--platform", PLATFORM,
            "--abi", ABI,
        ]
        if variant == "cu128":
            # The CUDA build of torch only exists on the PyTorch index. Keeping
            # PyPI as the extra index lets everything else resolve normally.
            command += [
                "--index-url", TORCH_INDEX.format(variant=variant),
                "--extra-index-url", PYPI_INDEX,
            ]
        for path in DIRECT_REQUIREMENTS:
            command += ["-r", str(path)]
        # Constraints come last so they win over the ranges in the direct files.
        command += list(VARIANT_CONSTRAINTS.get(variant, ()))

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise ResolveError(
                "pip could not resolve the closure:\n"
                + (result.stderr or result.stdout)[-4000:]
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))

    packages: list[dict[str, Any]] = []
    unlicensed: list[str] = []
    for item in report.get("install", []):
        metadata = item["metadata"]
        download = item.get("download_info") or {}
        url = download.get("url", "")
        digest = ((download.get("archive_info") or {}).get("hashes") or {}).get("sha256")
        name = metadata["name"]
        if not digest:
            raise ResolveError(f"{name} resolved without a SHA-256; refusing to lock")
        filename = _wheel_filename(url)
        if not filename.endswith(".whl"):
            raise ResolveError(
                f"{name} resolved to a non-wheel ({filename}); "
                "source builds are not allowed in the runtime closure"
            )
        license_name = _license_of(metadata)
        if not license_name:
            unlicensed.append(name)
            license_name = "UNKNOWN"
        packages.append(
            {
                "name": name,
                "version": metadata["version"],
                "wheel": filename,
                "url": url,
                "sha256": digest,
                "tags": _wheel_tags(filename),
                "license": license_name,
            }
        )

    if unlicensed:
        print(
            f"WARNING: {len(unlicensed)} distributions resolved without a "
            "detectable license and were recorded as UNKNOWN. Fill these in "
            "before release:\n  " + ", ".join(sorted(unlicensed)),
            file=sys.stderr,
        )
    packages.sort(key=lambda item: item["name"].lower())
    _assert_variant_is_real(variant, packages)
    return packages


def _assert_variant_is_real(variant: str, packages: list[dict[str, Any]]) -> None:
    """Refuse to write a CUDA lock that silently resolved to CPU wheels.

    pip merges ``--index-url`` and ``--extra-index-url`` and picks the highest
    version across both. When the cu128 index lags PyPI, an unbounded range
    resolves the PyPI build and the resulting pack is CPU-only while claiming
    CUDA. That failure is invisible in the lock unless it is asserted.
    """
    if variant == "cpu":
        stray = sorted(
            package["name"]
            for package in packages
            if "+cu" in package["version"] or "pytorch.org/whl/cu" in package["url"]
        )
        if stray:
            raise ResolveError(
                "cpu closure contains CUDA builds: " + ", ".join(stray)
            )
        return

    by_name = {package["name"].lower(): package for package in packages}
    for required in ("torch", "torchvision"):
        package = by_name.get(required)
        if package is None:
            raise ResolveError(f"{variant} closure is missing {required}")
        if f"+{variant}" not in package["version"]:
            raise ResolveError(
                f"{variant} closure resolved {required}=={package['version']} "
                f"without a +{variant} local version — pip preferred another "
                "index. Update VARIANT_CONSTRAINTS to a pair that exists on "
                f"{TORCH_INDEX.format(variant=variant)}."
            )
        if "pytorch.org" not in package["url"]:
            raise ResolveError(
                f"{variant} closure resolved {required} from "
                f"{package['url'].split('/')[2]}, not the PyTorch index"
            )


def _read_url(url: str, *, timeout: int = 180, retries: int = 4) -> bytes:
    """Read a small acquisition input with bounded transient-network retries."""
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "FigureSmith-Runtime-Acquirer/1"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return response.read()
        except (OSError, ssl.SSLError, urllib.error.URLError) as exc:
            if attempt == retries:
                raise ResolveError(
                    f"cannot fetch {url} after {retries} attempts: {exc}"
                ) from exc
            time.sleep(min(2**attempt, 10))
    raise AssertionError("unreachable")


def _hash_url(url: str) -> tuple[str, int]:
    """Read a pinned source and return its SHA-256 and byte length."""
    payload = _read_url(url, timeout=300)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _msys2_version(filename: str) -> str:
    match = _MSYS2_VERSION_RE.search(filename)
    if not match:
        raise ResolveError(f"cannot parse MSYS2 package version: {filename}")
    return f"{match.group(1)}-{match.group(2)}"


def _msys2_sort_key(filename: str) -> tuple[tuple[int, object], ...]:
    match = _MSYS2_VERSION_RE.search(filename)
    if not match:
        return ()
    # Natural-sort mixed versions such as 13.0.0.r124.g2717de84e.
    parts = re.findall(r"\d+|[A-Za-z]+", match.group(1))
    key: list[tuple[int, object]] = [
        (0, int(part)) if part.isdigit() else (1, part.lower()) for part in parts
    ]
    key.append((0, int(match.group(2))))
    return tuple(key)


def refresh_msys2_packages() -> tuple[tuple[str, str, str], ...]:
    """Return MSYS2_PACKAGES with filenames refreshed from the live index.

    MSYS2 rebuilds packages frequently and removes superseded files, so a
    hand-maintained pin goes stale and 404s. Licenses stay as declared here
    because the index does not carry them.
    """
    print(f"reading {MSYS2_BASE} ...", file=sys.stderr)
    index = _read_url(MSYS2_BASE).decode("utf-8", "ignore")

    refreshed: list[tuple[str, str, str]] = []
    for name, pinned, license_name in MSYS2_PACKAGES:
        matches = sorted(
            set(
                re.findall(
                    rf'(mingw-w64-x86_64-{re.escape(name)}-\d[^"<]*?-any\.pkg\.tar\.zst)',
                    index,
                )
            ),
            key=_msys2_sort_key,
        )
        if not matches:
            raise ResolveError(f"MSYS2 package not found in index: {name}")
        latest = matches[-1]
        if latest != pinned:
            print(f"  {name}: {pinned} -> {latest}", file=sys.stderr)
        refreshed.append((name, latest, license_name))
    return tuple(refreshed)


def _resolve_sources(*, refresh: bool = False) -> list[dict[str, Any]]:
    """Pin every non-wheel input by SHA-256."""
    sources: list[dict[str, Any]] = []

    print(f"  hashing {CPYTHON['url'].rsplit('/', 1)[-1]} ...", file=sys.stderr)
    digest, size = _hash_url(CPYTHON["url"])
    sources.append({**CPYTHON, "sha256": digest, "size_bytes": size})

    packages = refresh_msys2_packages() if refresh else MSYS2_PACKAGES
    for name, filename, license_name in packages:
        url = MSYS2_BASE + filename
        print(f"  hashing {filename} ...", file=sys.stderr)
        digest, size = _hash_url(url)
        sources.append(
            {
                "name": f"msys2-{name}",
                "kind": "archive",
                "version": _msys2_version(filename),
                "url": url,
                "sha256": digest,
                "license": license_name,
                "size_bytes": size,
            }
        )
    return sources


def _runtime_header(variant: str) -> dict[str, str]:
    return {"python": PYTHON_VERSION, "platform": PLATFORM, "cuda": variant}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {path}", file=sys.stderr)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", choices=("cpu", "cu128"), default=None)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "locks")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="interpreter whose pip performs resolution (needs pip >= 23.1)",
    )
    parser.add_argument(
        "--sources-only",
        action="store_true",
        help="only refresh variant-specific sources locks (CPython + native DLL chain)",
    )
    parser.add_argument(
        "--refresh-msys2",
        action="store_true",
        help="re-read the MSYS2 index and pin the newest package filenames",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.sources_only and args.variant is None:
        parser.error("--variant is required unless --sources-only is given")

    # CPython and the native DLL chain are identical for both variants, but the
    # lock schema stamps a variant on every file and validate_lock_bundle
    # requires all three to agree. Write one sources lock per variant so that
    # invariant holds without special-casing the validator.
    variants = (args.variant,) if args.variant else SUPPORTED_VARIANTS
    try:
        if not args.sources_only:
            variant = args.variant
            print(f"resolving {variant} closure (no wheels downloaded) ...", file=sys.stderr)
            packages = _resolve_closure(variant, args.python)
            _write_json(
                args.out / f"requirements-win-py312-{variant}.lock.json",
                {
                    "schema": LOCK_SCHEMA,
                    "product": "FigureSmith",
                    "runtime": _runtime_header(variant),
                    "packages": packages,
                },
            )
            print(f"  {len(packages)} packages pinned", file=sys.stderr)

        print("pinning non-wheel sources ...", file=sys.stderr)
        sources = _resolve_sources(refresh=args.refresh_msys2)
        for variant in variants:
            _write_json(
                args.out / f"sources-{variant}.lock.json",
                {
                    "schema": LOCK_SCHEMA,
                    "product": "FigureSmith",
                    "runtime": _runtime_header(variant),
                    "sources": sources,
                    "native_dlls": list(CAIRO_DLLS),
                },
            )
        print(f"  {len(sources)} sources pinned", file=sys.stderr)
    except ResolveError as exc:
        print(f"lock resolution failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
