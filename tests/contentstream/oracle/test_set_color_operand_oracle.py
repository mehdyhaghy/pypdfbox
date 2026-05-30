"""Live PDFBox differential parity for the ``sc``/``scn``/``SC``/``SCN``
colour-set operators' operand handling.

Drives the four colour-set operators through a minimal
:class:`~pypdfbox.contentstream.pdf_stream_engine.PDFStreamEngine` over content
streams that exercise each operand layout the operators must distinguish:

* DeviceRGB (3 components), DeviceCMYK (4), a Separation colorant (1).
* A Pattern colour space with a trailing ``/Name`` operand — both the
  colored form (``/P1 scn``) and the uncolored-tiling form
  (``c1 /P1 scn``).
* Edge cases: too few operands for the current colour space, a non-numeric
  operand in a non-Pattern colour space (PDFBOX-5851 invalid-color path), and
  extra operands beyond the component count.

The resulting current stroking / non-stroking :class:`PDColor` is emitted as a
canonical line and compared against Apache PDFBox via the
``SetColorOperandProbe`` Java oracle.

Canonical line grammar (must match ``oracle/probes/SetColorOperandProbe.java``)::

    stroke=comps[<c0>,<c1>,...] pattern=<name|null> cs=<csname|null>
    nonstroke=comps[...] pattern=<...> cs=<...>
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color import (
    SetNonStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color_n import (
    SetNonStrokingColorN,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color_space import (
    SetNonStrokingColorSpace,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_device_rgb_color import (
    SetNonStrokingDeviceRGBColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_color import (
    SetStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_color_n import (
    SetStrokingColorN,
)
from pypdfbox.contentstream.operator.color.set_stroking_color_space import (
    SetStrokingColorSpace,
)
from pypdfbox.contentstream.operator.color.set_stroking_device_rgb_color import (
    SetStrokingDeviceRGBColor,
)
from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSName,
)
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

CASES = [
    "rgb",
    "cmyk",
    "sep",
    "pattern_name_only",
    "pattern_with_comps",
    "too_few",
    "nonnumeric",
    "nonnumeric_sc",
    "device_nonnumeric",
    "extra",
]

_CONTENT = {
    "rgb": b"/CSRGB cs /CSRGB CS 0.1 0.2 0.3 scn 0.4 0.5 0.6 SCN\n",
    "cmyk": b"/CSCMYK cs 0.1 0.2 0.3 0.4 scn\n",
    "sep": b"/Sep cs /Sep CS 0.7 scn 0.3 SCN\n",
    "pattern_name_only": b"/Pattern cs /P1 scn\n",
    "pattern_with_comps": b"/PatternU cs 0.5 /P1 scn\n",
    "too_few": b"/CSRGB cs 0.1 0.2 scn\n",
    "nonnumeric": b"/CSRGB cs /Foo /Bar /Baz scn\n",
    "nonnumeric_sc": b"/CSRGB cs /CSRGB CS /Foo /Bar /Baz sc /Foo /Bar /Baz SC\n",
    "device_nonnumeric": b"/Foo /Bar /Baz rg\n",
    "extra": b"/CSRGB cs 0.1 0.2 0.3 0.9 scn\n",
}


def _fmt(value: float) -> str:
    """Canonical float rendering matching the probe's ``fmt``."""
    f = float(value)
    if f == int(f):
        return str(int(f))
    s = f"{f:.6f}".rstrip("0").rstrip(".")
    return s


def _describe(color: PDColor | None) -> str:
    if color is None:
        return "null"
    comps = ",".join(_fmt(v) for v in color.get_components())
    pattern = color.get_pattern_name()
    pattern_str = "null" if pattern is None else pattern.get_name()
    cs = color.get_color_space()
    cs_str = "null" if cs is None else cs.get_name()
    return f"comps[{comps}] pattern={pattern_str} cs={cs_str}"


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _separation_cs() -> COSArray:
    fn = COSDictionary()
    fn.set_int(_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSFloat(0))
    domain.add(COSFloat(1))
    fn.set_item(_name("Domain"), domain)
    c0 = COSArray()
    for _ in range(4):
        c0.add(COSFloat(0))
    c1 = COSArray()
    c1.add(COSFloat(0))
    c1.add(COSFloat(1))
    c1.add(COSFloat(0))
    c1.add(COSFloat(0))
    fn.set_item(_name("C0"), c0)
    fn.set_item(_name("C1"), c1)
    fn.set_item(COSName.N, COSFloat(1))
    sep = COSArray()
    sep.add(_name("Separation"))
    sep.add(_name("Spot"))
    sep.add(_name("DeviceCMYK"))
    sep.add(fn)
    return sep


def _build_resources(doc: PDDocument) -> PDResources:
    res = PDResources()
    cs_dict = COSDictionary()
    cs_dict.set_item(_name("CSRGB"), _name("DeviceRGB"))
    cs_dict.set_item(_name("CSCMYK"), _name("DeviceCMYK"))
    cs_dict.set_item(_name("Sep"), _separation_cs())
    pat_u = COSArray()
    pat_u.add(_name("Pattern"))
    pat_u.add(_name("DeviceGray"))
    cs_dict.set_item(_name("PatternU"), pat_u)
    res.get_cos_object().set_item(_name("ColorSpace"), cs_dict)

    # A type-1 tiling pattern resource named /P1.
    pat_dict = COSDictionary()
    tiling = doc.get_document().create_cos_stream()
    tiling.set_item(COSName.TYPE, _name("Pattern"))
    tiling.set_int(_name("PatternType"), 1)
    tiling.set_int(_name("PaintType"), 1)
    tiling.set_int(_name("TilingType"), 1)
    bbox = COSArray()
    bbox.add(COSFloat(0))
    bbox.add(COSFloat(0))
    bbox.add(COSFloat(1))
    bbox.add(COSFloat(1))
    tiling.set_item(_name("BBox"), bbox)
    tiling.set_float(_name("XStep"), 1)
    tiling.set_float(_name("YStep"), 1)
    pat_dict.set_item(_name("P1"), tiling)
    res.get_cos_object().set_item(_name("Pattern"), pat_dict)
    return res


class _CaptureEngine(PDFStreamEngine):
    """Engine that records the current colours after each operator."""

    def __init__(self) -> None:
        super().__init__()
        self.captured_stroke: PDColor | None = None
        self.captured_nonstroke: PDColor | None = None
        self.add_operator(SetStrokingColor())
        self.add_operator(SetNonStrokingColor())
        self.add_operator(SetStrokingColorN())
        self.add_operator(SetNonStrokingColorN())
        self.add_operator(SetStrokingColorSpace())
        self.add_operator(SetNonStrokingColorSpace())
        self.add_operator(SetStrokingDeviceRGBColor())
        self.add_operator(SetNonStrokingDeviceRGBColor())

    def init_page(self, page: PDPage) -> None:
        # Mirror upstream's base ``processPage`` which seeds the stack with
        # ``new PDGraphicsState(page.getCropBox())`` before dispatch.
        super().init_page(page)
        self._graphics_stack.append(PDGraphicsState(page.get_crop_box()))

    def process_operator(
        self,
        operator: Operator | str,
        operands: list[COSBase] | None,
    ) -> None:
        super().process_operator(operator, operands)
        gs = self.get_graphics_state()
        self.captured_stroke = gs.get_stroking_color()
        self.captured_nonstroke = gs.get_non_stroking_color()


def _emit(case: str) -> str:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        res = _build_resources(doc)
        stream = PDStream(doc)
        with stream.create_output_stream() as out:
            out.write(_CONTENT[case])
        page.set_contents(stream)
        page.set_resources(res)

        engine = _CaptureEngine()
        engine.process_page(page)
        lines = [
            f"stroke={_describe(engine.captured_stroke)}",
            f"nonstroke={_describe(engine.captured_nonstroke)}",
        ]
        return "\n".join(lines) + "\n"
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize("case", CASES)
def test_set_color_operand_matches_pdfbox(case: str) -> None:
    java = run_probe_text("SetColorOperandProbe", case)
    py = _emit(case)
    assert py == java
