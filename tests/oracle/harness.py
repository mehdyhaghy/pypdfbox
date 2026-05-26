"""Live Apache PDFBox differential oracle for behavioural-parity tests.

Compiles small Java "probe" programs (``oracle/probes/*.java``) against the
pinned PDFBox app jar and runs them so a test can compare Apache PDFBox's actual
output against pypdfbox's on the same input. This is the gold-standard parity
check: unlike value-based parity tests (which assert against expected values we
translated from upstream by hand), the oracle catches divergences we would
otherwise have reproduced in our own expectations.

The jar is downloaded by ``oracle/download_jars.sh`` and gitignored. On a
machine without Java or without the jar, the ``requires_oracle`` marker skips
the differential tests, so the suite stays green everywhere — the oracle is an
opt-in, developer-machine check, not a hard CI gate.

Usage in a test::

    from tests.oracle.harness import requires_oracle, run_probe_text

    @requires_oracle
    def test_text_extraction_matches_pdfbox():
        java = run_probe_text("TextExtractProbe", str(fixture))
        py = PDFTextStripper().get_text(PDDocument.load(fixture))
        assert py == java
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ORACLE = _REPO_ROOT / "oracle"
_JAR = _ORACLE / "jars" / "pdfbox-app-3.0.7.jar"
_PROBES = _ORACLE / "probes"
_BUILD = _ORACLE / "build"


def oracle_available() -> bool:
    """True when the live PDFBox oracle can run (jar present + JDK on PATH)."""
    return (
        _JAR.is_file()
        and shutil.which("java") is not None
        and shutil.which("javac") is not None
    )


requires_oracle = pytest.mark.skipif(
    not oracle_available(),
    reason="live PDFBox oracle unavailable — run oracle/download_jars.sh (needs java + javac)",
)


def _ensure_compiled(probe: str) -> None:
    src = _PROBES / f"{probe}.java"
    if not src.is_file():
        raise FileNotFoundError(f"no probe source: {src}")
    cls = _BUILD / f"{probe}.class"
    # Recompile when the class is missing or older than its source.
    if not cls.is_file() or cls.stat().st_mtime < src.stat().st_mtime:
        _BUILD.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["javac", "-cp", str(_JAR), "-d", str(_BUILD), str(src)],
            check=True,
            capture_output=True,
        )


def run_probe(probe: str, *args: str) -> bytes:
    """Compile (if needed) and run a probe; return its raw stdout bytes."""
    _ensure_compiled(probe)
    classpath = f"{_JAR}{os.pathsep}{_BUILD}"
    result = subprocess.run(
        ["java", "-cp", classpath, probe, *args],
        check=True,
        capture_output=True,
    )
    return result.stdout


def run_probe_text(probe: str, *args: str, encoding: str = "utf-8") -> str:
    """Compile (if needed) and run a probe; return its stdout decoded as text."""
    return run_probe(probe, *args).decode(encoding)
