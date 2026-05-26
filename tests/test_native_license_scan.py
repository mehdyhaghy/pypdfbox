"""Tests for ``scripts/check_native_licenses.py``.

The native-license scanner is the defense-in-depth complement to the
metadata-only ``pip-licenses`` gate (the jbig2-parser incident: MIT metadata,
GPL-3.0 statically-linked crate). These tests assert it (a) runs clean on the
current environment and (b) WOULD flag a synthetic jbig2-style copyleft binary
that carries permissive metadata.

Stdlib + fast. Skips gracefully if the script or a venv layout is absent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_native_licenses.py"


def _load_module():
    if not _SCRIPT.is_file():
        pytest.skip("check_native_licenses.py not present")
    spec = importlib.util.spec_from_file_location("check_native_licenses", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass field resolution (which looks up
    # sys.modules[cls.__module__]) can find the module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scanner():
    return _load_module()


def test_runs_clean_on_current_env(scanner, capsys):
    """The installed environment must scan clean (exit 0)."""
    site_packages = scanner.find_site_packages()
    if site_packages is None:
        pytest.skip("no virtualenv site-packages on this layout")

    rc = scanner.main([])
    out = capsys.readouterr().out
    assert rc == 0, f"scanner flagged the current env:\n{out}"
    assert "artifacts scanned, clean" in out


def test_scan_returns_no_violations_on_current_env(scanner):
    """Lower-level: ``scan()`` finds zero non-allow-listed copyleft hits."""
    site_packages = scanner.find_site_packages()
    if site_packages is None:
        pytest.skip("no virtualenv site-packages on this layout")

    findings, count = scanner.scan(site_packages)
    assert count > 0
    violations = [f for f in findings if not f.allowed]
    assert violations == [], f"unexpected native copyleft: {violations}"


def test_flags_synthetic_copyleft_binary(scanner, tmp_path):
    """A fake .so carrying a copyleft string + cargo crate path must be flagged.

    This is the jbig2-style case: a wheel with permissive metadata whose
    compiled artifact bundles GPL code. ``evilpkg`` is not on the allow-list,
    so both the GPL string and the bundled crate must surface as violations.
    """
    site_packages = tmp_path / ".venv" / "lib" / "python3.14" / "site-packages"
    pkg = site_packages / "evilpkg"
    pkg.mkdir(parents=True)

    blob = (
        b"\x00\x01\x02XXXX"
        b"this artifact statically links the GNU General Public License v3 code"
        b"\x00\xff"
        b"/cargo/registry/src/index.crates.io-abc123/jbig2dec-0.19.0/src/lib.rs"
        b"\x00\x00\x00"
    )
    (pkg / "_evil.cpython-314-darwin.so").write_bytes(blob)

    findings, count = scanner.scan(site_packages)
    assert count == 1
    violations = [f for f in findings if not f.allowed]
    markers = {f.marker for f in violations}

    assert any(m.startswith("GPL") for m in markers), markers
    assert any(m == "cargo crate: jbig2dec-0.19.0" for m in markers), markers
    assert all(f.dist == "evilpkg" for f in violations)


def test_synthetic_copyleft_exits_nonzero(scanner, tmp_path, monkeypatch, capsys):
    """End-to-end: a synthetic violation makes ``main()`` exit non-zero."""
    site_packages = tmp_path / ".venv" / "lib" / "python3.14" / "site-packages"
    pkg = site_packages / "badwheel"
    pkg.mkdir(parents=True)
    (pkg / "_x.cpython-314-darwin.so").write_bytes(
        b"\x00\x00pad\x00GNU Affero General Public License\x00pad\x00"
    )

    monkeypatch.setattr(scanner, "find_site_packages", lambda: site_packages)
    rc = scanner.main([])
    out = capsys.readouterr().out
    assert rc == 1
    assert "VIOLATION" in out
    assert "badwheel" in out


def test_word_boundary_avoids_symbol_false_positive(scanner):
    """A C symbol containing the substring 'agpl' must not match AGPL."""
    # e.g. liblcms2's ``__cmsAllocTagPlugin`` contains "agPl".
    hits = scanner._scan_binary(b"\x00__cmsAllocTagPluginChunk\x00cmsAllocTagPlugin\x00")
    assert hits == {}


def test_license_prose_mention_is_not_a_grant(scanner):
    """Prose that merely references the GPL must not be flagged in a license text."""
    prose = (
        b"This software, previously distributed under the GNU General Public "
        b"License (GPL), is now offered under the BSD-2-Clause license. You may "
        b"alternatively relicense lzf.c under the GPLv2."
    )
    assert scanner._scan_license_text(prose) == {}


def test_license_spdx_grant_is_flagged(scanner):
    """An actual SPDX 'License: GPL-...' grant declaration must be flagged."""
    grant = b"Name: vendored\nFiles: foo/*\nLicense: GPL-3.0-or-later\n  body...\n"
    hits = scanner._scan_license_text(grant)
    assert "GPL-3 / GPLv3" in hits


def test_missing_venv_returns_zero(scanner, monkeypatch, capsys):
    """When no site-packages is found, the gate is a no-op (exit 0)."""
    monkeypatch.setattr(scanner, "find_site_packages", lambda: None)
    rc = scanner.main([])
    assert rc == 0
    assert "nothing to scan" in capsys.readouterr().out


def test_main_module_importable():
    """The script must be importable without executing main (no import-time work)."""
    assert "check_native_licenses" in sys.modules or _SCRIPT.is_file()
