"""Live PDFBox differential parity for the engine colour-operator *state* +
colour-space resolution surface.

Complementary to ``test_set_color_operand_oracle.py`` (which projects only the
resulting :class:`PDColor`): this fuzz round also projects the graphics-state's
current stroking / non-stroking *colour space name* after each operator, so it
pins the implicit colour-space switch performed by the device operators
``g`` / ``G`` / ``rg`` / ``RG`` / ``k`` / ``K`` (upstream
``SetNonStrokingDeviceGrayColor`` &c. set the graphics-state colour space, then
the colour) as well as the ``cs`` / ``CS`` named-resource resolution path.

Fuzz angles (NOT already covered by ``SetColorOperandProbe``):

* device operators after a named colour space (implicit ``cs`` switch).
* ``cs`` / ``CS`` with a device name vs a named resource vs missing vs unknown.
* setting a colour before setting a colour space (initial DeviceGray).
* nested ``q`` / ``Q`` colour-state restore.
* ``scn`` for a Separation / DeviceN with a component-count mismatch.
* ``/DefaultGray`` substitution honoured by ``g`` via ``/Resources``.
* too-few operands to a device operator (colour space still switches,
  colour value unchanged — upstream throws ``MissingOperandException``
  from ``SetColor.process`` *after* the colour-space switch).

The probe captures state *during* processing (overriding ``processOperator``)
because upstream resets the graphics stack at the end of ``processPage``.

Canonical line grammar (must match
``oracle/probes/ColorOperatorFuzzProbe.java``)::

    stroke=comps[<c0>,...] pattern=<name|null> cs=<csname|null>
    nonstroke=comps[...] pattern=<...> cs=<...>
    stroke_cs=<name|null>
    nonstroke_cs=<name|null>

A real production bug was fixed in this wave (the device operators did not
switch the graphics-state colour space); the ``named_then_*`` / ``*_too_few`` /
``g_only`` (DefaultGray) cases below pin the corrected behaviour. See
CHANGES.md (wave 1560).
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_cmyk import (
    SetNonStrokingCMYK,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color import (
    SetNonStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color_n import (
    SetNonStrokingColorN,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color_space import (
    SetNonStrokingColorSpace,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_gray import (
    SetNonStrokingGray,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_rgb import (
    SetNonStrokingRGB,
)
from pypdfbox.contentstream.operator.color.set_stroking_cmyk import (
    SetStrokingCMYK,
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
from pypdfbox.contentstream.operator.color.set_stroking_gray import (
    SetStrokingGray,
)
from pypdfbox.contentstream.operator.color.set_stroking_rgb import (
    SetStrokingRGB,
)
from pypdfbox.contentstream.operator.state.restore import Restore
from pypdfbox.contentstream.operator.state.save import Save
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
    "g_only",
    "rg_only",
    "k_only",
    "G_RG_K",
    "named_then_g",
    "named_then_G",
    "named_then_rg",
    "g_then_named_then_k",
    "cs_device_name",
    "CS_device_name",
    "cs_missing_resource",
    "cs_unknown_inline",
    "cs_default_gray",
    "scn_before_cs",
    "sc_before_cs",
    "q_restore_device",
    "q_restore_named",
    "q_nested_restore",
    "sep_ok",
    "sep_too_few",
    "sep_extra",
    "devicen_ok",
    "devicen_too_few",
    "pattern_name_only",
    "pattern_uncolored",
    "pattern_no_name",
    "rg_out_of_range",
    "g_out_of_range",
    "stroke_rgb_nonstroke_gray",
    "rg_too_few",
    "k_too_few",
]

_CONTENT = {
    "g_only": b"0.5 g\n",
    "rg_only": b"0.1 0.2 0.3 rg\n",
    "k_only": b"0.1 0.2 0.3 0.4 k\n",
    "G_RG_K": b"0.5 G 0.1 0.2 0.3 RG 0.1 0.2 0.3 0.4 K\n",
    "named_then_g": b"/CSRGB cs 0.5 g\n",
    "named_then_G": b"/CSRGB CS 0.5 G\n",
    "named_then_rg": b"/CSCMYK cs 0.1 0.2 0.3 rg\n",
    "g_then_named_then_k": b"0.5 g /CSRGB cs 0.1 0.2 0.3 0.4 k\n",
    "cs_device_name": b"/DeviceRGB cs 0.1 0.2 0.3 scn\n",
    "CS_device_name": b"/DeviceCMYK CS 0.1 0.2 0.3 0.4 SCN\n",
    "cs_missing_resource": b"/NotThere cs 0.1 0.2 0.3 scn\n",
    "cs_unknown_inline": b"/Bogus cs 0.5 scn\n",
    "cs_default_gray": b"/DeviceGray cs 0.7 scn\n",
    "scn_before_cs": b"0.5 scn\n",
    "sc_before_cs": b"0.5 sc\n",
    "q_restore_device": b"0.1 0.2 0.3 rg q 0.9 g Q\n",
    "q_restore_named": (
        b"/CSRGB cs 0.1 0.2 0.3 scn q /CSCMYK cs 0.1 0.2 0.3 0.4 scn Q\n"
    ),
    "q_nested_restore": b"0.2 g q 0.4 g q 0.6 g Q Q\n",
    "sep_ok": b"/Sep cs 0.7 scn\n",
    "sep_too_few": b"/Sep cs scn\n",
    "sep_extra": b"/Sep cs 0.7 0.9 scn\n",
    "devicen_ok": b"/DevN cs 0.3 0.6 scn\n",
    "devicen_too_few": b"/DevN cs 0.3 scn\n",
    "pattern_name_only": b"/Pattern cs /P1 scn\n",
    "pattern_uncolored": b"/PatternU cs 0.5 /P1 scn\n",
    "pattern_no_name": b"/Pattern cs scn\n",
    "rg_out_of_range": b"1.5 -0.2 0.3 rg\n",
    "g_out_of_range": b"2.0 g\n",
    "stroke_rgb_nonstroke_gray": b"0.1 0.2 0.3 RG 0.5 g\n",
    "rg_too_few": b"0.1 0.2 rg\n",
    "k_too_few": b"0.1 0.2 0.3 k\n",
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


def _cs_name(cs: object | None) -> str:
    if cs is None:
        return "null"
    return cs.get_name()


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _type2_fn(n_out: int) -> COSDictionary:
    fn = COSDictionary()
    fn.set_int(_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSFloat(0))
    domain.add(COSFloat(1))
    fn.set_item(_name("Domain"), domain)
    c0 = COSArray()
    for _ in range(n_out):
        c0.add(COSFloat(0))
    c1 = COSArray()
    for _ in range(n_out):
        c1.add(COSFloat(1))
    fn.set_item(_name("C0"), c0)
    fn.set_item(_name("C1"), c1)
    fn.set_item(COSName.N, COSFloat(1))
    return fn


def _separation_cs() -> COSArray:
    sep = COSArray()
    sep.add(_name("Separation"))
    sep.add(_name("Spot"))
    sep.add(_name("DeviceCMYK"))
    sep.add(_type2_fn(4))
    return sep


def _device_n_cs() -> COSArray:
    names = COSArray()
    names.add(_name("SpotA"))
    names.add(_name("SpotB"))
    dn = COSArray()
    dn.add(_name("DeviceN"))
    dn.add(names)
    dn.add(_name("DeviceCMYK"))
    dn.add(_type2_fn(4))
    return dn


def _build_resources(doc: PDDocument) -> PDResources:
    res = PDResources()
    cs_dict = COSDictionary()
    cs_dict.set_item(_name("CSRGB"), _name("DeviceRGB"))
    cs_dict.set_item(_name("CSCMYK"), _name("DeviceCMYK"))
    cs_dict.set_item(_name("Sep"), _separation_cs())
    cs_dict.set_item(_name("DevN"), _device_n_cs())
    # /DefaultGray substitution: a Separation stands in for DeviceGray.
    cs_dict.set_item(_name("DefaultGray"), _separation_cs())
    pat_u = COSArray()
    pat_u.add(_name("Pattern"))
    pat_u.add(_name("DeviceGray"))
    cs_dict.set_item(_name("PatternU"), pat_u)
    res.get_cos_object().set_item(_name("ColorSpace"), cs_dict)

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
    """Engine with a real graphics stack that records colour + colour-space
    state after each operator (mirroring the probe's ``processOperator``
    override)."""

    def __init__(self) -> None:
        super().__init__()
        self.captured_stroke: PDColor | None = None
        self.captured_nonstroke: PDColor | None = None
        self.captured_stroke_cs: object | None = None
        self.captured_nonstroke_cs: object | None = None
        for processor in (
            SetStrokingColor(),
            SetNonStrokingColor(),
            SetStrokingColorN(),
            SetNonStrokingColorN(),
            SetStrokingColorSpace(),
            SetNonStrokingColorSpace(),
            SetStrokingRGB(),
            SetNonStrokingRGB(),
            SetStrokingGray(),
            SetNonStrokingGray(),
            SetStrokingCMYK(),
            SetNonStrokingCMYK(),
            Save(),
            Restore(),
        ):
            self.add_operator(processor)

    def init_page(self, page: PDPage) -> None:
        super().init_page(page)
        self._graphics_stack.append(PDGraphicsState(page.get_crop_box()))

    # Real q/Q graphics-state stack management.
    def save_graphics_state(self) -> None:
        self._graphics_stack.append(self.get_graphics_state().clone())

    def restore_graphics_state(self) -> None:
        self._graphics_stack.pop()

    # Colour hooks write into the current (top) graphics state.
    def set_stroking_color(self, color: PDColor) -> None:
        self.get_graphics_state().set_stroking_color(color)

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.get_graphics_state().set_non_stroking_color(color)

    def process_operator(
        self,
        operator: Operator | str,
        operands: list[COSBase] | None,
    ) -> None:
        super().process_operator(operator, operands)
        gs = self.get_graphics_state()
        self.captured_stroke = gs.get_stroking_color()
        self.captured_nonstroke = gs.get_non_stroking_color()
        self.captured_stroke_cs = gs.get_stroking_color_space()
        self.captured_nonstroke_cs = gs.get_non_stroking_color_space()


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
            f"stroke_cs={_cs_name(engine.captured_stroke_cs)}",
            f"nonstroke_cs={_cs_name(engine.captured_nonstroke_cs)}",
        ]
        return "\n".join(lines) + "\n"
    finally:
        doc.close()


# Expected values pinned from Apache PDFBox 3.0.7 via ColorOperatorFuzzProbe
# (run live by the @requires_oracle test below; mirrored here so the parity
# values are reviewable and the suite stays green without the oracle jar).
_EXPECTED = {
    "g_only": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.5] pattern=null cs=Separation\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Separation\n"
    ),
    "rg_only": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.1,0.2,0.3] pattern=null cs=DeviceRGB\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceRGB\n"
    ),
    "k_only": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.1,0.2,0.3,0.4] pattern=null cs=DeviceCMYK\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceCMYK\n"
    ),
    "G_RG_K": (
        "stroke=comps[0.1,0.2,0.3,0.4] pattern=null cs=DeviceCMYK\n"
        "nonstroke=comps[0] pattern=null cs=DeviceGray\n"
        "stroke_cs=DeviceCMYK\n"
        "nonstroke_cs=DeviceGray\n"
    ),
    "named_then_g": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.5] pattern=null cs=Separation\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Separation\n"
    ),
    "named_then_G": (
        "stroke=comps[0.5] pattern=null cs=Separation\n"
        "nonstroke=comps[0] pattern=null cs=DeviceGray\n"
        "stroke_cs=Separation\n"
        "nonstroke_cs=DeviceGray\n"
    ),
    "named_then_rg": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.1,0.2,0.3] pattern=null cs=DeviceRGB\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceRGB\n"
    ),
    "g_then_named_then_k": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.1,0.2,0.3,0.4] pattern=null cs=DeviceCMYK\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceCMYK\n"
    ),
    "cs_device_name": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.1,0.2,0.3] pattern=null cs=DeviceRGB\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceRGB\n"
    ),
    "CS_device_name": (
        "stroke=comps[0.1,0.2,0.3,0.4] pattern=null cs=DeviceCMYK\n"
        "nonstroke=comps[0] pattern=null cs=DeviceGray\n"
        "stroke_cs=DeviceCMYK\n"
        "nonstroke_cs=DeviceGray\n"
    ),
    "cs_missing_resource": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.1] pattern=null cs=DeviceGray\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceGray\n"
    ),
    "cs_unknown_inline": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.5] pattern=null cs=DeviceGray\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceGray\n"
    ),
    "cs_default_gray": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.7] pattern=null cs=Separation\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Separation\n"
    ),
    "scn_before_cs": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.5] pattern=null cs=DeviceGray\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceGray\n"
    ),
    "sc_before_cs": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.5] pattern=null cs=DeviceGray\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceGray\n"
    ),
    "q_restore_device": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.1,0.2,0.3] pattern=null cs=DeviceRGB\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceRGB\n"
    ),
    "q_restore_named": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.1,0.2,0.3] pattern=null cs=DeviceRGB\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceRGB\n"
    ),
    "q_nested_restore": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.2] pattern=null cs=Separation\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Separation\n"
    ),
    "sep_ok": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.7] pattern=null cs=Separation\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Separation\n"
    ),
    "sep_too_few": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[1] pattern=null cs=Separation\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Separation\n"
    ),
    "sep_extra": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.7] pattern=null cs=Separation\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Separation\n"
    ),
    "devicen_ok": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.3,0.6] pattern=null cs=DeviceN\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceN\n"
    ),
    "devicen_too_few": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[1,1] pattern=null cs=DeviceN\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceN\n"
    ),
    "pattern_name_only": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[] pattern=P1 cs=Pattern\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Pattern\n"
    ),
    "pattern_uncolored": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0.5] pattern=P1 cs=Pattern\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Pattern\n"
    ),
    "pattern_no_name": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[] pattern=null cs=Pattern\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Pattern\n"
    ),
    "rg_out_of_range": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[1.5,-0.2,0.3] pattern=null cs=DeviceRGB\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceRGB\n"
    ),
    "g_out_of_range": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[2] pattern=null cs=Separation\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=Separation\n"
    ),
    "stroke_rgb_nonstroke_gray": (
        "stroke=comps[0.1,0.2,0.3] pattern=null cs=DeviceRGB\n"
        "nonstroke=comps[0.5] pattern=null cs=Separation\n"
        "stroke_cs=DeviceRGB\n"
        "nonstroke_cs=Separation\n"
    ),
    "rg_too_few": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0] pattern=null cs=DeviceGray\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceRGB\n"
    ),
    "k_too_few": (
        "stroke=comps[0] pattern=null cs=DeviceGray\n"
        "nonstroke=comps[0] pattern=null cs=DeviceGray\n"
        "stroke_cs=DeviceGray\n"
        "nonstroke_cs=DeviceCMYK\n"
    ),
}


@pytest.mark.parametrize("case", CASES)
def test_color_operator_matches_expected(case: str) -> None:
    """Pin Python output against the PDFBox-3.0.7-derived expected values."""
    assert _emit(case) == _EXPECTED[case]


@requires_oracle
@pytest.mark.parametrize("case", CASES)
def test_color_operator_matches_pdfbox(case: str) -> None:
    """Live differential: Python vs the Java ColorOperatorFuzzProbe oracle."""
    java = run_probe_text("ColorOperatorFuzzProbe", case)
    py = _emit(case)
    assert py == java
