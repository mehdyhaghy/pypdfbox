#!/usr/bin/env python3
"""Defense-in-depth scan for *bundled* copyleft native code.

The pre-push license gate (`pip-licenses --allow-only ...`) is **metadata
only**: it trusts each wheel's declared PyPI ``License`` field. That gate is
blind to copyleft code statically linked into a wheel's compiled artifacts.

Lesson (wave ~1426): ``jbig2-parser`` declared ``MIT`` in its Python metadata
— so ``pip-licenses`` passed — yet its compiled ``.so`` statically linked the
GPL-3.0 Rust ``jbig2dec`` crate. Metadata-only checking cannot see that. This
script complements the metadata gate by scanning the *bytes* of installed
native artifacts (and the SPDX grant lines of bundled license texts) for
copyleft signatures, so a new jbig2-style "permissive metadata, copyleft
binary" wheel cannot slip in silently.

Pure stdlib (no new deps). It walks the active virtualenv's ``site-packages``
and applies two tiers of detection:

  * **Compiled artifacts** (``*.so``, ``*.pyd``, ``*.dylib``, bundled
    ``*.so.*``): printable strings (an in-process ``strings`` equivalent) are
    matched against copyleft markers using *word boundaries* (so a symbol like
    ``__cmsAllocTagPlugin`` does not falsely match ``AGPL``), plus Rust
    cargo-registry crate paths (which reveal a statically-linked crate whose
    own license must then be confirmed — exactly how ``jbig2dec`` would show
    up).

  * **Bundled license texts** (``*.dist-info/licenses/**``): only a copyleft
    *SPDX grant declaration* (``License: GPL-3.0-...``, ``License: LGPL-...``,
    etc.) is treated as a hit. Free prose that merely *mentions* another
    license — "previously distributed under the GPL", dual-license "or the GNU
    ... General Public License", an optional-relicense clause, or a reproduced
    third-party notice — is intentionally ignored, because it is not evidence
    of bundled copyleft *code* in this wheel.

A small allow-list of ``(dist, marker)`` pairs suppresses hits the manual
audit confirmed benign (see ``ALLOW_LIST``). Anything else is a hard failure.

Usage::

    python scripts/check_native_licenses.py [--verbose]

Exit codes:
    0  every artifact scanned cleanly (or no venv found — nothing to scan).
    1  a non-allow-listed copyleft signature was found in a bundled artifact.
"""
from __future__ import annotations

import argparse
import re
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path

# --- copyleft markers for COMPILED BINARIES --------------------------------
# Matched with word boundaries against printable strings extracted from
# binaries. Word boundaries are essential: a C symbol like
# ``__cmsAllocTagPlugin`` contains the substring "agpl" but is not the AGPL.
BINARY_MARKERS: dict[str, re.Pattern[bytes]] = {
    "GPL (GNU General Public)": re.compile(
        rb"GNU\s+(?:Lesser\s+|Affero\s+)?General\s+Public", re.I
    ),
    "AGPL / Affero": re.compile(rb"\bAffero\b|\bAGPL\b", re.I),
    "GPL-3 / GPLv3": re.compile(rb"\bGPL-?3\b|\bGPLv3\b", re.I),
    "GPL-2 / GPLv2": re.compile(rb"\bGPL-?2\b|\bGPLv2\b", re.I),
    "LGPL": re.compile(rb"\bLGPL\b", re.I),
    "Mozilla Public License": re.compile(rb"Mozilla\s+Public\s+License", re.I),
    "Eclipse Public License": re.compile(rb"Eclipse\s+Public\s+License", re.I),
    "CDDL": re.compile(rb"Common\s+Development\s+and\s+Distribution", re.I),
    "Server Side Public License": re.compile(rb"Server\s+Side\s+Public\s+License", re.I),
    "Business Source License": re.compile(rb"Business\s+Source\s+License", re.I),
}

# Rust cargo-registry crate path, e.g. ".../cargo/registry/src/<index>/<crate>-<ver>/...".
# A crate path baked into a binary means a Rust crate was statically linked;
# its license must be confirmed permissive (this is exactly how the jbig2dec
# crate would have shown up). We capture "<crate>-<ver>" for the report.
CARGO_CRATE_RE = re.compile(
    rb"/cargo/registry/(?:src|cache)/[^/]+/([A-Za-z0-9_.+-]+?-\d[A-Za-z0-9_.+-]*)/"
)

# --- copyleft markers for LICENSE TEXTS ------------------------------------
# Only an SPDX-style *grant declaration* counts as a hit in a license text. A
# bundled, vendored copyleft component (the jbig2 risk) declares its own grant
# ("License: GPL-3.0-or-later" in an aggregated third-party LICENSE, or a
# standalone LICENSE file that *is* the GPL). Prose that names another license
# is not a grant and is ignored. Marker labels are reused from BINARY_MARKERS
# where they overlap so the allow-list keys stay consistent.
_LICENSE_GRANT_RE = re.compile(
    rb"License:\s*(?P<spdx>[A-Za-z0-9.+_-]*"
    rb"(?:GPL|LGPL|AGPL|MPL|EPL|CDDL|SSPL|BUSL)[A-Za-z0-9.+_ -]*)",
    re.I,
)
# A standalone file whose grant body itself is the GPL/AGPL (no "License:"
# header, just the license text) — e.g. a vendored crate's COPYING file.
_LICENSE_BODY_RE = re.compile(
    rb"is\s+free\s+software[^.]{0,80}under\s+the\s+terms\s+of\s+the\s+"
    rb"GNU\s+(?:Lesser\s+|Affero\s+)?General\s+Public\s+License",
    re.I,
)


def _grant_label(spdx: str) -> str:
    """Map a matched SPDX grant string to a stable marker label."""
    s = spdx.upper()
    if "AGPL" in s:
        return "AGPL / Affero"
    if "LGPL" in s:
        return "LGPL"
    if "GPL-3" in s or "GPLV3" in s:
        return "GPL-3 / GPLv3"
    if "GPL-2" in s or "GPLV2" in s:
        return "GPL-2 / GPLv2"
    if "GPL" in s:
        return "GPL (GNU General Public)"
    if "MPL" in s:
        return "Mozilla Public License"
    if "EPL" in s:
        return "Eclipse Public License"
    if "CDDL" in s:
        return "CDDL"
    if "SSPL" in s:
        return "Server Side Public License"
    if "BUSL" in s:
        return "Business Source License"
    return "copyleft grant"


# --- known-benign allow-list ----------------------------------------------
# Each entry is ((dist_name_lower_prefix, marker_label), justification). A hit
# is suppressed only when BOTH the distribution prefix and the marker label
# match — so a NEW copyleft binary in the same dist (different marker), or the
# same marker in a DIFFERENT dist, still fails. dist_name_lower is matched as a
# case-insensitive prefix of the dist-info / top-level package name.
#
# Two categories are present in the current clean env:
#
#  (1) numpy ships an aggregated third-party LICENSE.txt that declares the
#      grants of the gcc runtime libs it links. Both are bundled copyleft *with
#      a permissive escape*: libgfortran is GPL-3 WITH the GCC Runtime Library
#      Exception (no copyleft propagation), and libquadmath is LGPL-2.1 (a
#      permissive dynamic-link). (On this platform numpy 2.4.5 ships no
#      .dylibs, so only the text declarations are present.)
#
#  (2) the three textual false positives the audit called out. With the
#      grant-only license-text detector these no longer fire as hits (they are
#      prose, not "License:" grants), so they need no allow-list entry — they
#      are documented here for the record and kept defensive in case an
#      upstream re-spin reformats the prose into a grant-looking line.
ALLOW_LIST: dict[tuple[str, str], str] = {
    ("numpy", "GPL-3 / GPLv3"): (
        "numpy LICENSE.txt declares libgfortran as 'GPL-3.0-or-later WITH "
        "GCC-exception-3.1' — the GCC Runtime Library Exception removes "
        "copyleft propagation for normal use; permissive in effect."
    ),
    ("numpy", "LGPL"): (
        "numpy LICENSE.txt declares libquadmath as 'LGPL-2.1-or-later'; "
        "dynamically linked, LGPL imposes no copyleft on dependents."
    ),
}

# Artifact discovery.
_BINARY_SUFFIXES = (".so", ".pyd", ".dylib")
_BINARY_SO_VERSIONED = re.compile(r"\.so(\.\d+)+$")

# Cap per-file binary scan size so a giant artifact can't make the gate crawl.
# Copyleft markers / cargo paths live in .rodata / note sections present
# throughout; an 8 MiB window per file is ample and keeps the scan fast.
_MAX_BYTES_PER_FILE = 8 * 1024 * 1024


@dataclass(frozen=True)
class Finding:
    """A single copyleft signature located in an artifact."""

    dist: str
    artifact: Path
    marker: str
    sample: str
    allowed: bool
    reason: str = ""


def _is_binary_artifact(path: Path) -> bool:
    name = path.name
    if name.endswith(_BINARY_SUFFIXES):
        return True
    return bool(_BINARY_SO_VERSIONED.search(name))


def _dist_name_for(path: Path, site_packages: Path) -> str:
    """Best-effort distribution name for an artifact path.

    Uses the first path component under site-packages (the top-level package or
    the ``*.dist-info`` dir), lowercased with a trailing ``-<version>`` tail
    stripped. Used only for allow-list matching and reporting, so a coarse name
    (``imagecodecs``, ``pillow``, ``numpy``) is sufficient.
    """
    try:
        rel = path.relative_to(site_packages)
    except ValueError:
        return path.parent.name.lower()
    first = rel.parts[0] if rel.parts else path.name
    if first.endswith(".dist-info"):
        first = first[: -len(".dist-info")]
    first = re.sub(r"-\d[\w.+!]*$", "", first)
    return first.lower()


def _iter_printable_chunks(data: bytes, min_len: int = 6):
    """Yield runs of printable ASCII (a stdlib ``strings`` equivalent).

    Joining the whole blob would let a marker straddle non-printable bytes and
    create false matches; yielding printable runs mirrors ``strings`` and keeps
    matches anchored to real embedded text.
    """
    run = bytearray()
    for byte in data:
        if 0x20 <= byte < 0x7F or byte == 0x09:
            run.append(byte)
        else:
            if len(run) >= min_len:
                yield bytes(run)
            run.clear()
    if len(run) >= min_len:
        yield bytes(run)


def _scan_binary(data: bytes) -> dict[str, str]:
    """Return ``{marker_label: sample}`` for copyleft markers in a binary."""
    hits: dict[str, str] = {}
    for chunk in _iter_printable_chunks(data):
        for label, pattern in BINARY_MARKERS.items():
            if label not in hits and pattern.search(chunk):
                hits[label] = chunk.decode("ascii", "replace")[:160]
        for crate in CARGO_CRATE_RE.findall(chunk):
            label = f"cargo crate: {crate.decode('ascii', 'replace')}"
            hits.setdefault(label, chunk.decode("ascii", "replace")[:160])
    return hits


def _scan_license_text(data: bytes) -> dict[str, str]:
    """Return ``{marker_label: sample}`` for copyleft *grants* in a license text.

    Only SPDX-style ``License:`` grant declarations and standalone GPL grant
    bodies count — prose that merely references another license is ignored.
    """
    hits: dict[str, str] = {}
    for match in _LICENSE_GRANT_RE.finditer(data):
        spdx = match.group("spdx").decode("ascii", "replace").strip()
        label = _grant_label(spdx)
        hits.setdefault(label, f"License: {spdx}"[:160])
    if not any(lbl.startswith("GPL") or lbl == "AGPL / Affero" for lbl in hits):
        body = _LICENSE_BODY_RE.search(data)
        if body:
            text = body.group(0).decode("ascii", "replace")
            label = "AGPL / Affero" if re.search(r"Affero", text, re.I) else (
                "LGPL" if re.search(r"Lesser", text, re.I) else "GPL (GNU General Public)"
            )
            hits.setdefault(label, text[:160])
    return hits


def _read_capped(path: Path) -> bytes | None:
    try:
        with path.open("rb") as handle:
            return handle.read(_MAX_BYTES_PER_FILE)
    except OSError:
        return None


def _allow_reason(dist: str, marker: str) -> str | None:
    """Return the justification if ``(dist, marker)`` is allow-listed, else None."""
    for (allow_dist, allow_marker), reason in ALLOW_LIST.items():
        if marker == allow_marker and dist.startswith(allow_dist):
            return reason
    return None


def find_site_packages() -> Path | None:
    """Locate the active environment's ``site-packages``.

    Prefers the running interpreter's ``purelib`` (correct under ``uv run``
    inside ``.venv``); falls back to a ``.venv`` beside the repo.
    """
    purelib = sysconfig.get_paths().get("purelib")
    if purelib:
        candidate = Path(purelib)
        if candidate.is_dir():
            return candidate
    repo_root = Path(__file__).resolve().parent.parent
    for lib in sorted((repo_root / ".venv" / "lib").glob("python*")):
        candidate = lib / "site-packages"
        if candidate.is_dir():
            return candidate
    return None


def _is_license_text(path: Path) -> bool:
    parts = [p.lower() for p in path.parts]
    return "licenses" in parts and any(p.endswith(".dist-info") for p in path.parts)


def iter_artifacts(site_packages: Path):
    """Yield every native binary and bundled license text under site-packages."""
    for path in site_packages.rglob("*"):
        if not path.is_file():
            continue
        if _is_binary_artifact(path) or _is_license_text(path):
            yield path


def scan(site_packages: Path) -> tuple[list[Finding], int]:
    """Scan all artifacts. Return ``(findings, artifact_count)``."""
    findings: list[Finding] = []
    count = 0
    for artifact in iter_artifacts(site_packages):
        count += 1
        data = _read_capped(artifact)
        if data is None:
            continue
        dist = _dist_name_for(artifact, site_packages)
        hits = _scan_binary(data) if _is_binary_artifact(artifact) else _scan_license_text(data)
        for marker, sample in hits.items():
            reason = _allow_reason(dist, marker)
            findings.append(
                Finding(
                    dist=dist,
                    artifact=artifact,
                    marker=marker,
                    sample=sample,
                    allowed=reason is not None,
                    reason=reason or "",
                )
            )
    return findings, count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan installed native artifacts for bundled copyleft code."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Also print allow-listed (benign) hits."
    )
    args = parser.parse_args(argv)

    site_packages = find_site_packages()
    if site_packages is None:
        print("check_native_licenses: no virtualenv site-packages found; nothing to scan.")
        return 0

    findings, count = scan(site_packages)
    violations = [f for f in findings if not f.allowed]
    allowed = [f for f in findings if f.allowed]

    if args.verbose and allowed:
        print(f"Allow-listed (benign) hits: {len(allowed)}")
        for f in allowed:
            print(f"  OK  [{f.dist}] {f.marker}")
            print(f"      {f.artifact}")
            print(f"      reason: {f.reason}")
        print()

    if violations:
        print("NATIVE COPYLEFT VIOLATION(S) DETECTED")
        print("=" * 60)
        print(
            "A bundled native artifact contains a copyleft signature that is\n"
            "not on the known-benign allow-list. The metadata-only pip-licenses\n"
            "gate cannot see this (recall the jbig2-parser incident: MIT\n"
            "metadata, GPL-3.0 statically-linked crate). Investigate before\n"
            "shipping; if genuinely benign, add a justified ALLOW_LIST entry in\n"
            "scripts/check_native_licenses.py.\n"
        )
        for f in violations:
            print(f"  !!  [{f.dist}] {f.marker}")
            print(f"      {f.artifact}")
            print(f"      string: {f.sample!r}")
            print()
        print(f"{count} artifacts scanned, {len(violations)} violation(s).")
        return 1

    suffix = f" ({len(allowed)} allow-listed)" if allowed else ""
    print(f"check_native_licenses: {count} artifacts scanned, clean{suffix}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
