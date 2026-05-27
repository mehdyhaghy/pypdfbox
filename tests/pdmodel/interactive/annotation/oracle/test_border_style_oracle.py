"""Live Apache PDFBox differential parity for annotation BORDER STYLING.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation``

* :class:`PDBorderStyleDictionary` (``/BS``) — ``get_width()`` / ``get_style()``
  (the ``S``/``D``/``B``/``I``/``U`` enum) / ``get_dash_style()`` dash array.
* The legacy ``/Border`` array ``[hradius vradius width [dash]]`` on
  :class:`PDAnnotation` — ``get_border()`` including the absent-array default
  ``[0 0 1]`` PDFBox/Adobe synthesise.
* :class:`PDBorderEffectDictionary` (``/BE``) — ``get_style()`` (cloudy ``C`` /
  solid ``S``) / ``get_intensity()``.
* ``/RD`` rectangle differences on :class:`PDAnnotationSquareCircle` —
  ``get_rect_differences()`` float array.

How it works
------------
The Java probe ``BorderStyleProbe`` runs in ``read`` mode: load a PDF and print,
per annotation, a canonical block with the ``/BS`` width/style/dash, the raw
legacy ``/Border`` array, the ``/BE`` style/intensity and the ``/RD`` array.
``/BS`` and ``/BE`` are read via the typed PDFBox wrappers off the annotation
COS dictionary so the probe is uniform across every subtype (matching
pypdfbox's per-subclass surface).

pypdfbox BUILDS the fixture (four annotations exercising every branch — a
dashed ``/BS`` + ``/D`` array, a legacy ``/Border [0 0 3 [3 2]]``, a square with
cloudy ``/BE`` + ``/RD``, and a bare annotation with no border dict), saves it
once, then loads it and emits the identical canonical block. The two blocks are
compared exactly, and the defaults for absent dicts are asserted explicitly.

Defaulting facts verified against the oracle
--------------------------------------------
* absent ``/BS`` -> ``getBorderStyle()`` is null (the probe emits ``BS none``);
  the typed accessor only synthesises width 1 / style S when constructed on a
  present-but-empty dict.
* absent legacy ``/Border`` -> ``getBorder()`` synthesises ``[0 0 1]`` (width 1).
* absent ``/BE`` -> ``getBorderEffect()`` is null (``BE none``).
* absent ``/RD`` -> ``getRectDifferences()`` is the empty array (``RD none``).
* a present ``/BS`` with style ``S``/``D`` etc. takes precedence over the legacy
  ``/Border`` array (both are emitted independently so precedence is visible).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationLink,
    PDAnnotationSquare,
    PDAnnotationText,
    PDBorderEffectDictionary,
    PDBorderStyleDictionary,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "BorderStyleProbe"

_BS: COSName = COSName.get_pdf_name("BS")
_BE: COSName = COSName.get_pdf_name("BE")
_RD: COSName = COSName.get_pdf_name("RD")
_BORDER: COSName = COSName.get_pdf_name("Border")


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors BorderStyleProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


# ---------------------------------------------------------------------------
# fixture builder — pypdfbox builds the PDF the probe reads back
# ---------------------------------------------------------------------------


def _build(path: Path) -> None:
    """Build a one-page PDF with four border-styling annotations.

    (a) link with a /BS style /D (dashed) + /D dash array [4 2] + width 2;
    (b) link with a legacy /Border [0 0 3 [3 2]] array (and no /BS);
    (c) square with /BE /S /C /I 2 cloudy effect + /RD [1 1 1 1];
    (d) text annotation with NO border dict (defaults).
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        # (a) /BS dashed, width 2, dash array [4 2]. Distinct rect so the
        # canonical sort key is unique.
        a = PDAnnotationLink()
        a.set_rectangle(PDRectangle(10, 700, 110, 720))
        bs = PDBorderStyleDictionary()
        bs.set_width(2)
        bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
        bs.set_dash_style([4, 2])
        a.set_border_style(bs)
        page.add_annotation(a)

        # (b) legacy /Border [0 0 3 [3 2]] array, no /BS.
        b = PDAnnotationLink()
        b.set_rectangle(PDRectangle(10, 600, 110, 620))
        border = COSArray(
            [
                COSInteger.get(0),
                COSInteger.get(0),
                COSInteger.get(3),
                COSArray([COSInteger.get(3), COSInteger.get(2)]),
            ]
        )
        b.set_border(border)
        page.add_annotation(b)

        # (c) square with cloudy /BE /I 2 + /RD [1 1 1 1].
        c = PDAnnotationSquare()
        c.set_rectangle(PDRectangle(10, 500, 110, 560))
        be = PDBorderEffectDictionary()
        be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
        be.set_intensity(2)
        c.set_border_effect(be)
        c.set_rect_differences(1.0, 1.0, 1.0, 1.0)
        page.add_annotation(c)

        # (d) text annotation, no border dict at all (defaults).
        d = PDAnnotationText()
        d.set_rectangle(PDRectangle(10, 400, 30, 420))
        page.add_annotation(d)

        doc.save(str(path))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# pypdfbox reader — mirrors BorderStyleProbe.read byte-for-byte
# ---------------------------------------------------------------------------


def _rect_str(annot) -> str:
    r = annot.get_rectangle()
    if r is None:
        return "none"
    return ",".join(
        _canon_float(v)
        for v in (
            r.get_lower_left_x(),
            r.get_lower_left_y(),
            r.get_upper_right_x(),
            r.get_upper_right_y(),
        )
    )


def _bs_line(annot) -> str:
    cos = annot.get_cos_object()
    bs_dict = cos.get_dictionary_object(_BS)
    if not isinstance(bs_dict, COSDictionary):
        return "BS none"
    bs = PDBorderStyleDictionary(bs_dict)
    parts = [f"BS w={_canon_float(bs.get_width())}", f"s={bs.get_style()}"]
    dash = bs.get_dash_style()
    if dash is None:
        parts.append("dash=none")
    else:
        arr = dash.get_dash_array()
        if not arr:
            parts.append("dash=none")
        else:
            parts.append("dash=" + ",".join(_canon_float(v) for v in arr))
    return " ".join(parts)


def _border_line(annot) -> str:
    cos = annot.get_cos_object()
    base = cos.get_dictionary_object(_BORDER)
    if not isinstance(base, COSArray):
        return "BORDER none"
    parts: list[str] = []
    for i in range(base.size()):
        e = base.get(i)
        if isinstance(e, COSArray):
            dash_parts = []
            for j in range(e.size()):
                de = e.get(j)
                val = getattr(de, "float_value", None)
                dash_parts.append(
                    _canon_float(val()) if callable(val) else "?"
                )
            parts.append("dash:" + ";".join(dash_parts))
        else:
            val = getattr(e, "float_value", None)
            parts.append(_canon_float(val()) if callable(val) else "?")
    return "BORDER " + ",".join(parts)


def _be_line(annot) -> str:
    cos = annot.get_cos_object()
    be_dict = cos.get_dictionary_object(_BE)
    if not isinstance(be_dict, COSDictionary):
        return "BE none"
    be = PDBorderEffectDictionary(be_dict)
    return f"BE s={be.get_style()} i={_canon_float(be.get_intensity())}"


def _rd_line(annot) -> str:
    cos = annot.get_cos_object()
    base = cos.get_dictionary_object(_RD)
    if not isinstance(base, COSArray):
        return "RD none"
    arr = base.to_float_array()
    if not arr:
        return "RD none"
    return "RD " + ",".join(_canon_float(v) for v in arr)


def _py_blocks(path: Path) -> str:
    out: list[str] = []
    doc = PDDocument.load(path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            blocks: list[str] = []
            for annot in page.get_annotations():
                subtype = annot.get_subtype() or "?"
                key = f"p{page_index} {subtype} {_rect_str(annot)}"
                block = (
                    f"ANNOT {subtype}\n"
                    f"KEY {key}\n"
                    f"{_bs_line(annot)}\n"
                    f"{_border_line(annot)}\n"
                    f"{_be_line(annot)}\n"
                    f"{_rd_line(annot)}\n"
                    "END\n"
                )
                blocks.append(block)
            blocks.sort()
            out.extend(blocks)
    finally:
        doc.close()
    return "".join(out)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_border_styling_blocks_match_pdfbox() -> None:
    """/BS width/style/dash, legacy /Border, /BE style/intensity and /RD match
    Apache PDFBox exactly across the built four-annotation fixture."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "border_style.pdf"
        _build(out)
        java = run_probe_text(_PROBE, "read", str(out))
        py = _py_blocks(out)
    assert py == java, (
        f"border-styling block mismatch:\n--- pypdfbox ---\n{py}\n"
        f"--- PDFBox ---\n{java}"
    )
    # Sanity: every branch is exercised in the built fixture.
    assert "BS w=2 s=D dash=4,2" in py  # dashed /BS + /D array + width 2
    assert "BORDER 0,0,3,dash:3;2" in py  # legacy /Border with nested dash
    assert "BE s=C i=2" in py  # cloudy /BE intensity 2
    assert "RD 1,1,1,1" in py  # /RD rectangle differences
    assert "BS none" in py  # the no-border annotation
    assert "BE none" in py
    assert "RD none" in py


@requires_oracle
def test_typed_wrapper_accessors_match_pdfbox() -> None:
    """The high-value accessor facts (the /BS style enum, the /BE cloudy
    style+intensity, the /RD float array, and the absent-dict defaults) match
    Apache PDFBox via the typed pypdfbox wrappers, not just the raw COS view."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "border_style.pdf"
        _build(out)
        java = run_probe_text(_PROBE, "read", str(out))

        doc = PDDocument.load(out)
        try:
            by_subtype: dict[tuple[str, str], object] = {}
            for page in doc.get_pages():
                for annot in page.get_annotations():
                    by_subtype[
                        (annot.get_subtype(), _rect_str(annot))
                    ] = annot

            # (a) dashed /BS link: width 2, style D, dash [4 2].
            link_bs = by_subtype[("Link", "10,700,110,720")]
            bs = link_bs.get_border_style()
            assert bs is not None
            assert bs.get_width() == 2.0
            assert bs.get_style() == PDBorderStyleDictionary.STYLE_DASHED
            assert bs.is_dashed()
            assert bs.get_dash_style().get_dash_array() == [4.0, 2.0]

            # (b) legacy /Border link: no /BS; getBorderStyle() is None; the
            # legacy array is parsed verbatim.
            link_border = by_subtype[("Link", "10,600,110,620")]
            assert link_border.get_border_style() is None
            legacy = link_border.get_border()
            assert legacy.to_float_array()[:3] == [0.0, 0.0, 3.0]

            # (c) square /BE cloudy + /RD.
            square = by_subtype[("Square", "10,500,110,560")]
            be = square.get_border_effect()
            assert be is not None
            assert be.get_style() == PDBorderEffectDictionary.STYLE_CLOUDY
            assert be.is_cloudy()
            assert be.get_intensity() == 2.0
            assert square.get_rect_differences() == [1.0, 1.0, 1.0, 1.0]

            # (d) text annotation, no border dict -> defaults.
            text = by_subtype[("Text", "10,400,30,420")]
            assert text.get_border_style() is None  # absent /BS
            # absent legacy /Border -> synthesised [0 0 1] (width 1).
            assert text.get_border().to_float_array() == [0.0, 0.0, 1.0]
        finally:
            doc.close()

    # Cross-check the defaults against the oracle's raw view.
    assert "BS none" in java
    assert "BORDER none" in java  # PDFBox does not persist a synthetic /Border
    assert "BE none" in java
    assert "RD none" in java
