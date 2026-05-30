"""Live PDFBox differential parity for the linearization PARAMETER DICTIONARY
file-geometry values (PDF 32000-1 Annex F, Table F.1).

``test_linearized_oracle.py`` already pins the ``/Linearized`` marker, version,
``/N`` (page count) and ``/O`` (first-page object number). This module covers the
remaining uncovered parameters pypdfbox exposes through
``COSDocument.get_linearized_dictionary()`` →
``PDLinearizationDictionary``:

  * ``/L`` — total file length in bytes (``get_length_of_file``)
  * ``/T`` — byte offset of the first (trailing) xref entry
            (``get_offset_of_first_xref``)
  * ``/E`` — byte offset of the end of the first page (``get_end_of_first_page``)
  * ``/H`` — primary hint-stream offset + length, and optional overflow pair
            (``get_hint_table``)

These exercise the full integer/array decode of the parameter dict rather than
just marker detection. The :class:`LinearizationParamsProbe` Java oracle emits
the same five fields so pypdfbox is held to PDFBox 3.0.7 byte-for-byte.

Fixtures are the same ``qpdf --linearize`` outputs used by the sibling module
(qpdf is Apache-2.0, TEST-ONLY, never a runtime dependency).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.loader import Loader
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "pdfparser"

_LINEARIZED_FIXTURES = [
    _FIXTURES / "linearized_unencrypted.pdf",
    _FIXTURES / "linearized_PDFBOX-3110-poems-beads.pdf",
]

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


def _parse_probe(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in raw.split("\n"):
        if not line:
            continue
        key, _, value = line.partition("=")
        fields[key] = value
    return fields


def _qpdf_is_linearized(path: Path) -> bool:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return "File is linearized" in (proc.stdout or "")


def _py_hint_str(hint: object) -> str:
    """Render pypdfbox's ``get_hint_table`` tuple the way the probe emits ``/H``
    (``"int,int"`` / ``"int,int,int,int"``), or ``"absent"`` for ``None``."""
    if hint is None:
        return "absent"
    assert isinstance(hint, tuple)
    return ",".join(str(int(x)) for x in hint)


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _LINEARIZED_FIXTURES, ids=lambda p: p.stem)
def test_linearization_params_match_pdfbox(fixture: Path) -> None:
    """pypdfbox reads the same ``/L``, ``/T``, ``/E`` and ``/H`` values from a
    real linearized PDF as Apache PDFBox 3.0.7."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    assert _qpdf_is_linearized(fixture), f"fixture is not linearized: {fixture}"

    java = _parse_probe(run_probe_text("LinearizationParamsProbe", str(fixture)))
    assert java != {"PARSE_FAIL": ""}, "PDFBox failed to load the linearized fixture"
    assert java["linearized"] == "true", "PDFBox did not detect linearization"

    cos = Loader.load_pdf(fixture)
    try:
        lin = cos.get_linearized_dictionary()
        assert lin is not None, "pypdfbox failed to detect linearization"

        assert lin.get_length_of_file() == int(java["L"]), (
            f"/L mismatch: PDFBox={java['L']} pypdfbox={lin.get_length_of_file()}"
        )
        assert lin.get_offset_of_first_xref() == int(java["T"]), (
            f"/T mismatch: PDFBox={java['T']} "
            f"pypdfbox={lin.get_offset_of_first_xref()}"
        )
        assert lin.get_end_of_first_page() == int(java["E"]), (
            f"/E mismatch: PDFBox={java['E']} "
            f"pypdfbox={lin.get_end_of_first_page()}"
        )
        assert _py_hint_str(lin.get_hint_table()) == java["H"], (
            f"/H mismatch: PDFBox={java['H']} "
            f"pypdfbox={_py_hint_str(lin.get_hint_table())}"
        )
    finally:
        cos.close()
