"""Live PDFBox differential parity for ``PDShadingPattern`` MODEL accessors.

Companion to ``test_tiling_pattern_accessor_oracle.py`` (which pins the typed
accessor surface of a *tiling* pattern). This file pins the *model* accessor
surface of a shading pattern (``/PatternType 2``) as parsed back off a saved
PDF: ``get_pattern_type`` / ``get_shading().get_shading_type`` /
``get_extended_graphics_state`` presence / ``get_matrix`` — exactly the values
Apache PDFBox's ``PDShadingPattern`` reports through the same accessors.

``oracle/probes/ShadingPatternProbe.java`` walks each page's ``/Resources``
``/Pattern`` subdictionary, keeps the ``PDShadingPattern`` entries, and emits
one canonical block per pattern (sorted by resource name). pypdfbox reproduces
the identical block from its own accessors over the same reloaded fixture; the
two strings must be byte-for-byte equal.

The non-oracle assertions pin the same expected block independently, so the
test stays green on a machine without Java / the jar.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.graphics.pattern import PDShadingPattern
from tests.oracle.harness import requires_oracle, run_probe_text

_PATTERN = COSName.get_pdf_name("Pattern")
_PATTERN_TYPE = COSName.get_pdf_name("PatternType")
_SHADING = COSName.get_pdf_name("Shading")
_SHADING_TYPE = COSName.get_pdf_name("ShadingType")
_COLOR_SPACE = COSName.get_pdf_name("ColorSpace")
_MATRIX = COSName.get_pdf_name("Matrix")
_EXT_G_STATE = COSName.get_pdf_name("ExtGState")
_TYPE = COSName.get_pdf_name("Type")


def _canon_float(value: float) -> str:
    quant = Decimal(repr(float(value))).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_EVEN
    )
    quant = quant.normalize()
    s = format(quant, "f")
    if s in {"-0", ""}:
        s = "0"
    return s


def _shading_dict(shading_type: int) -> COSDictionary:
    """A minimal axial (type-2) shading dictionary, valid enough for
    ``PDShading.create`` / ``PDShadingType2``."""
    sh = COSDictionary()
    sh.set_int(_SHADING_TYPE, shading_type)
    sh.set_item(_COLOR_SPACE, COSName.get_pdf_name("DeviceRGB"))
    # /Coords for axial shading (x0 y0 x1 y1).
    coords = COSArray(
        [COSFloat(0.0), COSFloat(0.0), COSFloat(100.0), COSFloat(0.0)]
    )
    sh.set_item(COSName.get_pdf_name("Coords"), coords)
    return sh


def _build_shading_pattern_dict(*, with_matrix: bool, with_extgstate: bool):
    d = COSDictionary()
    d.set_item(_TYPE, _PATTERN)
    d.set_int(_PATTERN_TYPE, 2)
    d.set_item(_SHADING, _shading_dict(2))
    if with_matrix:
        d.set_item(
            _MATRIX,
            COSArray(
                [
                    COSFloat(2.0),
                    COSFloat(0.0),
                    COSFloat(0.0),
                    COSFloat(3.0),
                    COSFloat(10.0),
                    COSFloat(20.0),
                ]
            ),
        )
    if with_extgstate:
        egs = COSDictionary()
        egs.set_item(_TYPE, COSName.get_pdf_name("ExtGState"))
        egs.set_item(COSName.get_pdf_name("ca"), COSFloat(0.5))
        d.set_item(_EXT_G_STATE, egs)
    return d


def _make_fixture(tmp_path: Path) -> Path:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        res = page.get_resources()
        # full — matrix + extgstate present; bare — both absent.
        res.put(
            _PATTERN,
            COSName.get_pdf_name("P0full"),
            _build_shading_pattern_dict(with_matrix=True, with_extgstate=True),
        )
        res.put(
            _PATTERN,
            COSName.get_pdf_name("P1bare"),
            _build_shading_pattern_dict(with_matrix=False, with_extgstate=False),
        )
        page.set_resources(res)
        out = tmp_path / "shading_patterns.pdf"
        doc.save(str(out))
        return out
    finally:
        doc.close()


def _py_block(name: str, p: PDShadingPattern) -> str:
    shading = p.get_shading()
    shading_str = (
        "none" if shading is None else str(shading.get_shading_type())
    )
    egs = p.get_extended_graphics_state()
    matrix_str = ",".join(_canon_float(v) for v in p.get_matrix())
    return (
        f"PATTERN {name}\n"
        f"PATTERNTYPE {p.get_pattern_type()}\n"
        f"SHADINGTYPE {shading_str}\n"
        f"EXTGSTATE {'yes' if egs is not None else 'no'}\n"
        f"MATRIX {matrix_str}\n"
        "END\n"
    )


def _py_listing(pdf: Path) -> str:
    doc = PDDocument.load(str(pdf))
    try:
        blocks: list[str] = []
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_pattern_names():
                pattern = res.get_pattern(name)
                if isinstance(pattern, PDShadingPattern):
                    blocks.append(_py_block(name.get_name(), pattern))
        blocks.sort()
        return "".join(blocks)
    finally:
        doc.close()


# Expected canonical listing — pins the model surface independently of the
# oracle so this test passes without Java / the jar.
_EXPECTED = (
    "PATTERN P0full\n"
    "PATTERNTYPE 2\n"
    "SHADINGTYPE 2\n"
    "EXTGSTATE yes\n"
    "MATRIX 2,0,0,3,10,20\n"
    "END\n"
    "PATTERN P1bare\n"
    "PATTERNTYPE 2\n"
    "SHADINGTYPE 2\n"
    "EXTGSTATE no\n"
    "MATRIX 1,0,0,1,0,0\n"
    "END\n"
)


def test_shading_pattern_model_surface(tmp_path: Path) -> None:
    pdf = _make_fixture(tmp_path)
    assert _py_listing(pdf) == _EXPECTED


@requires_oracle
def test_shading_pattern_model_surface_matches_pdfbox(tmp_path: Path) -> None:
    pdf = _make_fixture(tmp_path)
    java = run_probe_text("ShadingPatternProbe", str(pdf))
    assert _py_listing(pdf) == java
