"""Wave 1347 — coverage boost (Agent E).

Tests targeting the last uncovered branches in six modules:

* ``pypdfbox.xmpbox.xml.dom_helper`` (None-returns + qname helpers)
* ``pypdfbox.pdmodel.graphics.color.pd_tristimulus`` (`get_cos_object`,
  non-COSNumber read fallback, `set_y` / `set_z`)
* ``pypdfbox.pdmodel.graphics.shading.cubic_bezier_curve``
  (`to_string` / ``__repr__``)
* ``pypdfbox.tools.pdf_box`` (`run` + `main` defaulting to ``sys.argv``)
* ``pypdfbox.tools.pdf_merger`` (success return + ``__main__`` block)
* ``pypdfbox.fontbox.ttf.otf_parser`` (legacy underscore aliases +
  embedded ``_check_tables`` early-return + no-CFF lenient tail)
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from xml.dom.minidom import parseString

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.fontbox.ttf import OpenTypeFont, OTFParser
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.ttf_table import TTFTable
from pypdfbox.pdmodel.graphics.color.pd_tristimulus import PDTristimulus
from pypdfbox.pdmodel.graphics.shading.cubic_bezier_curve import CubicBezierCurve
from pypdfbox.tools.pdf_box import PDFBox
from pypdfbox.tools.pdf_merger import PDFMerger
from pypdfbox.xmpbox.xml.dom_helper import DomHelper

# ---------------------------------------------------------------------------
# DomHelper — covers lines 40, 49, 58, 63
# ---------------------------------------------------------------------------


def test_dom_helper_get_unique_element_child_returns_none_when_no_children() -> None:
    """Empty element → ``pos < 0`` arm returns ``None`` (line 40)."""
    doc = parseString("<root/>")
    assert DomHelper.get_unique_element_child(doc.documentElement) is None


def test_dom_helper_get_first_child_element_returns_none_when_no_children() -> None:
    """Text-only / empty element → first-child returns ``None`` (line 49)."""
    doc = parseString("<root>just text</root>")
    assert DomHelper.get_first_child_element(doc.documentElement) is None


def test_dom_helper_get_qname_returns_triple() -> None:
    """``get_qname`` returns ``(namespaceURI, localName, prefix)`` (line 58)."""
    doc = parseString('<x:foo xmlns:x="urn:x"/>')
    ns, local, prefix = DomHelper.get_qname(doc.documentElement)
    assert ns == "urn:x"
    assert local == "foo"
    assert prefix == "x"


def test_dom_helper_get_q_name_alias_delegates() -> None:
    """``get_q_name`` is a snake-case alias for ``get_qname`` (line 63)."""
    doc = parseString('<x:foo xmlns:x="urn:x"/>')
    assert DomHelper.get_q_name(doc.documentElement) == DomHelper.get_qname(
        doc.documentElement
    )


# ---------------------------------------------------------------------------
# PDTristimulus — covers lines 35, 41, 60, 68
# ---------------------------------------------------------------------------


def test_pd_tristimulus_get_cos_object_returns_backing_array() -> None:
    """``get_cos_object`` exposes the underlying ``COSArray`` (line 35)."""
    arr = COSArray()
    arr.add(COSFloat(0.1))
    arr.add(COSFloat(0.2))
    arr.add(COSFloat(0.3))
    t = PDTristimulus(arr)
    assert t.get_cos_object() is arr


def test_pd_tristimulus_read_non_number_returns_zero() -> None:
    """Non-``COSNumber`` entry → ``_read`` falls through to ``0.0`` (line 41).

    A ``COSName`` is not a ``COSNumber``, so reading the slot must return
    the documented zero fallback.
    """
    arr = COSArray()
    arr.add(COSName.get_pdf_name("not-a-number"))
    arr.add(COSFloat(1.0))
    arr.add(COSFloat(2.0))
    t = PDTristimulus(arr)
    assert t.get_x() == 0.0


def test_pd_tristimulus_set_y_and_set_z() -> None:
    """``set_y`` / ``set_z`` round-trip (lines 60, 68)."""
    t = PDTristimulus()
    t.set_y(1.5)
    t.set_z(2.5)
    assert t.get_y() == pytest.approx(1.5)
    assert t.get_z() == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# CubicBezierCurve — covers lines 57-60, 63
# ---------------------------------------------------------------------------


def test_cubic_bezier_curve_to_string_lists_all_control_points() -> None:
    """``to_string`` formats every control point as ``Point2D.Double``
    (lines 57-60)."""
    curve = CubicBezierCurve(
        [(0.0, 0.0), (1.0, 2.0), (3.0, 4.0), (5.0, 6.0)], 1
    )
    text = curve.to_string()
    assert text.startswith("Cubic Bezier curve{control points p0, p1, p2, p3:")
    assert "Point2D.Double[0.0, 0.0]" in text
    assert "Point2D.Double[1.0, 2.0]" in text
    assert "Point2D.Double[3.0, 4.0]" in text
    assert "Point2D.Double[5.0, 6.0]" in text


def test_cubic_bezier_curve_repr_matches_to_string() -> None:
    """``__repr__`` delegates to ``to_string`` (line 63)."""
    curve = CubicBezierCurve(
        [(0.0, 0.0), (1.0, 1.0), (2.0, 1.0), (3.0, 0.0)], 1
    )
    assert repr(curve) == curve.to_string()


# ---------------------------------------------------------------------------
# PDFBox dispatcher — covers lines 64, 69, 82
# ---------------------------------------------------------------------------


def test_pdf_box_run_raises_system_exit() -> None:
    """Bare ``run()`` raises ``SystemExit`` like upstream's
    ``ParameterException`` (line 64)."""
    with pytest.raises(SystemExit):
        PDFBox().run()


def test_pdf_box_main_defaults_to_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """``main(None)`` falls back to ``sys.argv[1:]`` (line 69)."""
    monkeypatch.setattr(sys, "argv", ["pdfbox", "version"])
    assert PDFBox.main(None) == 0


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_pdf_box_dunder_main_block_runs_via_runpy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executing the module as ``__main__`` exercises the
    ``if __name__ == "__main__":`` guard (line 82).

    We monkey-patch ``sys.argv`` so the dispatch resolves to ``version``
    (a no-arg subcommand that exits 0) before ``runpy`` re-imports the
    module under the ``__main__`` name.
    """
    monkeypatch.setattr(sys, "argv", ["pdfbox", "version"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("pypdfbox.tools.pdf_box", run_name="__main__")
    assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# PDFMerger — covers lines 51, 79-80
# ---------------------------------------------------------------------------


def _make_minimal_pdf(path: Path) -> None:
    """Drop a one-page PDF at ``path`` using pypdfbox's writer."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(path))
    finally:
        doc.close()


def test_pdf_merger_call_returns_zero_on_success(tmp_path: Path) -> None:
    """Happy-path merge: two real PDFs in, one PDF out, exit code 0
    (line 51)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "merged.pdf"
    _make_minimal_pdf(a)
    _make_minimal_pdf(b)
    m = PDFMerger()
    m.infiles = [a, b]
    m.outfile = out
    rc = m.call()
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_pdf_merger_dunder_main_block_runs_via_runpy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Run the module as ``__main__`` so the ``if __name__ == "__main__":``
    block executes (lines 79-80)."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pdf_merger",
            "-i",
            str(tmp_path / "missing-a.pdf"),
            "-o",
            str(tmp_path / "out.pdf"),
        ],
    )
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("pypdfbox.tools.pdf_merger", run_name="__main__")
    # Missing inputs → OSError → exit code 4 (mirrors upstream contract).
    assert excinfo.value.code == 4


# ---------------------------------------------------------------------------
# OTFParser legacy aliases + lenient _check_tables — covers 114, 117, 120,
# 154, 162
# ---------------------------------------------------------------------------


def test_otf_parser_legacy_underscore_aliases_forward() -> None:
    """The leading-underscore variants pre-date the public names and
    must continue to forward (lines 114, 117, 120)."""
    parser = OTFParser()
    # ``_allow_cff`` mirrors the public ``allow_cff``.
    assert parser._allow_cff() is True

    # ``_read_table`` dispatches the same way as ``read_table``.
    cff_table = parser._read_table("CFF ")
    assert isinstance(cff_table, TTFTable)
    assert cff_table.get_tag() == "CFF "
    otl_table = parser._read_table("GSUB")
    assert otl_table.get_tag() == "GSUB"

    # ``_new_font`` mirrors ``new_font`` — builds an ``OpenTypeFont``
    # from a real SFNT data stream. The OpenTypeFont constructor calls
    # fontTools, so the bytes must be a parseable font.
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "fontbox"
        / "ttf"
        / "LiberationSans-Regular.ttf"
    )
    if not fixture.exists():
        pytest.skip("TTF fixture not present")
    stream = MemoryTTFDataStream(fixture.read_bytes())
    font = parser._new_font(stream)
    assert isinstance(font, OpenTypeFont)


def test_otf_parser_check_tables_embedded_short_circuits() -> None:
    """When ``_is_embedded`` is true, the OTF table check returns early
    after delegating to super (line 154)."""
    parser = OTFParser(is_embedded=True)
    # Build the bare-minimum TTF/OS2/etc. required by the super check.
    # The simplest path is to parse a real font, then re-run _check_tables
    # under the embedded flag — the embedded short-circuit must skip the
    # OTF-specific CFF presence check.
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "fontbox"
        / "ttf"
        / "LiberationSans-Regular.ttf"
    )
    if not fixture.exists():
        pytest.skip("TTF fixture not present")
    font = parser.parse(fixture.read_bytes())
    # Re-run the check directly to exercise the embedded early-return.
    parser._check_tables(font)  # should not raise


def test_otf_parser_check_tables_lenient_when_unsupported_otf() -> None:
    """When the font is an ``OpenTypeFont`` whose flavour is
    *unsupported* (``OTTO`` magic + ``CFF2`` table without ``CFF ``
    fallback), the OTF check takes the lenient ``return`` arm
    (line 162) rather than raise.

    A real ``CFF2``-only OTF is not in the fixture set, so we drive the
    branch by flipping the two state predicates on a parsed font: set
    the post-script-tag flag and stub ``has_table`` so the
    ``is_supported_otf`` rule resolves to ``False``. The parser itself
    is exercised end-to-end up to the check call.
    """
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "fontbox"
        / "ttf"
        / "LiberationSans-Regular.ttf"
    )
    if not fixture.exists():
        pytest.skip("TTF fixture not present")
    parser = OTFParser(is_embedded=False)
    font = parser.parse(fixture.read_bytes())

    # Force ``is_supported_otf`` to return False — its rule rejects
    # OTTO + CFF2 without a CFF` fallback.
    font._has_post_script_tag = True
    original_has_table = font.has_table

    def fake_has_table(tag: str) -> bool:
        if tag == "CFF ":
            return False
        if tag == "CFF2":
            return True
        return original_has_table(tag)

    font.has_table = fake_has_table  # type: ignore[method-assign]
    assert font.is_supported_otf() is False

    # Lenient tail returns ``None`` instead of raising.
    assert parser._check_tables(font) is None
