"""Fuzz / parity round-out for the device + general colour content-stream
operators — wave 1571.

Surface under test:

* ``RG`` / ``rg`` (DeviceRGB, 3 components),
* ``G`` / ``g`` (DeviceGray, 1 component),
* ``K`` / ``k`` (DeviceCMYK, 4 components),
* ``CS`` / ``cs`` (set colour space from ``/Resources /ColorSpace``),
* ``SC`` / ``sc`` and ``SCN`` / ``scn`` (set colour, with trailing
  ``/PatternName`` for the Pattern colour space).

The device operators (``RG`` / ``rg`` / ``G`` / ``g`` / ``K`` / ``k``) share
``pypdfbox.contentstream.operator.color._device_color.set_device_color``. The
canonical behaviour these tests pin against Apache PDFBox 3.0.7 (see the
``SetColorOperandProbe`` / ``DevColorProbe`` oracles) is:

* well-formed operands → a valid :class:`PDColor` over the device space, stored
  on the graphics-state colour slot *and* forwarded to the engine notification;
* a non-numeric operand in the first ``n`` (device, non-Pattern) → an invalid
  ``PDColor([], None)`` (PDFBOX-5851), **not** a silent skip — wave 1571 fixed
  ``set_device_color`` which previously left the colour untouched;
* a too-short operand list → upstream's inherited ``SetColor.process`` raises
  ``MissingOperandException`` (caught + logged by the engine) so the colour is
  left at its previous value;
* extra trailing operands beyond the component count are tolerated — only the
  first ``n`` become components.

``cs`` resolves the named colour space through ``/Resources /ColorSpace`` and
installs it (plus the space's initial colour); ``sc`` / ``scn`` then interpret
bare operands against that current space, and ``scn`` additionally accepts a
trailing pattern name.
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
from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color import (
    PDColor,
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resources import PDResources

# ---------------------------------------------------------------------------
# Content-stream-level driver (the most faithful exercise of the operators —
# it runs them through the real tokenizer + dispatch + graphics state).
# ---------------------------------------------------------------------------


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _separation_cs() -> COSArray:
    """``[ /Separation /Spot /DeviceCMYK <type-2 fn> ]`` (1 component)."""
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
    cs_dict.set_item(_name("CSGray"), _name("DeviceGray"))
    cs_dict.set_item(_name("CSCMYK"), _name("DeviceCMYK"))
    cs_dict.set_item(_name("Sep"), _separation_cs())
    # Uncolored tiling pattern colour space: [ /Pattern <baseCS> ].
    pat_u = COSArray()
    pat_u.add(_name("Pattern"))
    pat_u.add(_name("DeviceGray"))
    cs_dict.set_item(_name("PatternU"), pat_u)
    res.get_cos_object().set_item(_name("ColorSpace"), cs_dict)

    # A type-1 tiling pattern named /P1 so a pattern name resolves.
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
    """Registers the real colour operators and records the current colours."""

    def __init__(self) -> None:
        super().__init__()
        self.captured_stroke: PDColor | None = None
        self.captured_nonstroke: PDColor | None = None
        for op in (
            SetStrokingColor(),
            SetNonStrokingColor(),
            SetStrokingColorN(),
            SetNonStrokingColorN(),
            SetStrokingColorSpace(),
            SetNonStrokingColorSpace(),
            SetStrokingGray(),
            SetNonStrokingGray(),
            SetStrokingRGB(),
            SetNonStrokingRGB(),
            SetStrokingCMYK(),
            SetNonStrokingCMYK(),
        ):
            self.add_operator(op)

    def init_page(self, page: PDPage) -> None:
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


def _run(content: bytes) -> tuple[PDColor, PDColor]:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        res = _build_resources(doc)
        stream = PDStream(doc)
        with stream.create_output_stream() as out:
            out.write(content)
        page.set_contents(stream)
        page.set_resources(res)
        engine = _CaptureEngine()
        engine.process_page(page)
        assert engine.captured_stroke is not None
        assert engine.captured_nonstroke is not None
        return engine.captured_stroke, engine.captured_nonstroke
    finally:
        doc.close()


def _cs_name(color: PDColor) -> str | None:
    cs = color.get_color_space()
    return None if cs is None else cs.get_name()


def _approx(values: list[float], expected: list[float]) -> None:
    assert len(values) == len(expected)
    for got, want in zip(values, expected, strict=True):
        assert got == pytest.approx(want, abs=1e-6)


# ---------------------------------------------------------------------------
# Device operators: well-formed colour, full arity.
# ---------------------------------------------------------------------------


def test_rg_nonstroking_sets_device_rgb() -> None:
    _, ns = _run(b"0.1 0.2 0.3 rg\n")
    _approx(ns.get_components(), [0.1, 0.2, 0.3])
    assert _cs_name(ns) == "DeviceRGB"
    assert ns.get_pattern_name() is None


def test_uppercase_rg_sets_stroking_only() -> None:
    stroke, ns = _run(b"0.4 0.5 0.6 RG\n")
    _approx(stroke.get_components(), [0.4, 0.5, 0.6])
    assert _cs_name(stroke) == "DeviceRGB"
    # Non-stroking stays at its initial DeviceGray colour.
    assert _cs_name(ns) == "DeviceGray"


def test_g_sets_device_gray() -> None:
    _, ns = _run(b"0.5 g\n")
    _approx(ns.get_components(), [0.5])
    assert _cs_name(ns) == "DeviceGray"


def test_uppercase_g_sets_stroking_gray() -> None:
    stroke, _ = _run(b"0.75 G\n")
    _approx(stroke.get_components(), [0.75])
    assert _cs_name(stroke) == "DeviceGray"


def test_k_sets_device_cmyk() -> None:
    _, ns = _run(b"0.1 0.2 0.3 0.4 k\n")
    _approx(ns.get_components(), [0.1, 0.2, 0.3, 0.4])
    assert _cs_name(ns) == "DeviceCMYK"


def test_uppercase_k_sets_stroking_cmyk() -> None:
    stroke, _ = _run(b"0.9 0.8 0.7 0.6 K\n")
    _approx(stroke.get_components(), [0.9, 0.8, 0.7, 0.6])
    assert _cs_name(stroke) == "DeviceCMYK"


def test_rg_does_not_clamp_out_of_range_components() -> None:
    # Upstream PDColor keeps raw components; clamping happens only at toRGB.
    _, ns = _run(b"-0.5 2.0 0.3 rg\n")
    _approx(ns.get_components(), [-0.5, 2.0, 0.3])
    assert _cs_name(ns) == "DeviceRGB"


# ---------------------------------------------------------------------------
# Device operators: malformed operands (the wave-1571 fixed paths).
# ---------------------------------------------------------------------------


def test_rg_non_numeric_first_sets_invalid_color() -> None:
    _, ns = _run(b"/Foo /Bar /Baz rg\n")
    assert ns.get_components() == []
    assert ns.get_color_space() is None
    assert ns.get_pattern_name() is None


def test_rg_non_numeric_middle_sets_invalid_color() -> None:
    _, ns = _run(b"0.1 /Bad 0.3 rg\n")
    assert ns.get_components() == []
    assert ns.get_color_space() is None


def test_g_non_numeric_sets_invalid_color() -> None:
    _, ns = _run(b"/Foo g\n")
    assert ns.get_components() == []
    assert ns.get_color_space() is None


def test_k_non_numeric_sets_invalid_color() -> None:
    _, ns = _run(b"0.1 0.2 /Bad 0.4 k\n")
    assert ns.get_components() == []
    assert ns.get_color_space() is None


def test_stroking_rg_non_numeric_sets_invalid_color() -> None:
    stroke, _ = _run(b"/A /B /C RG\n")
    assert stroke.get_components() == []
    assert stroke.get_color_space() is None


def test_rg_too_few_operands_leaves_colour_unchanged() -> None:
    # MissingOperandException upstream -> colour stays at initial gray.
    _, ns = _run(b"0.1 0.2 rg\n")
    _approx(ns.get_components(), [0.0])
    assert _cs_name(ns) == "DeviceGray"


def test_k_too_few_operands_leaves_colour_unchanged() -> None:
    _, ns = _run(b"0.1 0.2 0.3 k\n")
    _approx(ns.get_components(), [0.0])
    assert _cs_name(ns) == "DeviceGray"


def test_g_empty_operands_leaves_colour_unchanged() -> None:
    _, ns = _run(b"g\n")
    _approx(ns.get_components(), [0.0])
    assert _cs_name(ns) == "DeviceGray"


def test_rg_extra_operands_uses_first_three() -> None:
    _, ns = _run(b"0.1 0.2 0.3 0.9 rg\n")
    _approx(ns.get_components(), [0.1, 0.2, 0.3])
    assert _cs_name(ns) == "DeviceRGB"


def test_k_extra_operands_uses_first_four() -> None:
    _, ns = _run(b"0.1 0.2 0.3 0.4 0.5 k\n")
    _approx(ns.get_components(), [0.1, 0.2, 0.3, 0.4])
    assert _cs_name(ns) == "DeviceCMYK"


# ---------------------------------------------------------------------------
# cs / CS + sc / scn / SC / SCN against the resolved colour space.
# ---------------------------------------------------------------------------


def test_cs_then_scn_device_rgb() -> None:
    _, ns = _run(b"/CSRGB cs 0.1 0.2 0.3 scn\n")
    _approx(ns.get_components(), [0.1, 0.2, 0.3])
    assert _cs_name(ns) == "DeviceRGB"


def test_uppercase_cs_then_scn_stroking() -> None:
    stroke, _ = _run(b"/CSRGB CS 0.4 0.5 0.6 SCN\n")
    _approx(stroke.get_components(), [0.4, 0.5, 0.6])
    assert _cs_name(stroke) == "DeviceRGB"


def test_cs_then_sc_device_cmyk() -> None:
    _, ns = _run(b"/CSCMYK cs 0.1 0.2 0.3 0.4 sc\n")
    _approx(ns.get_components(), [0.1, 0.2, 0.3, 0.4])
    assert _cs_name(ns) == "DeviceCMYK"


def test_cs_named_gray_then_sc() -> None:
    _, ns = _run(b"/CSGray cs 0.6 sc\n")
    _approx(ns.get_components(), [0.6])
    assert _cs_name(ns) == "DeviceGray"


def test_cs_initial_colour_before_sc() -> None:
    # cs installs the colour space's initial colour (black) immediately.
    _, ns = _run(b"/CSRGB cs\n")
    _approx(ns.get_components(), [0.0, 0.0, 0.0])
    assert _cs_name(ns) == "DeviceRGB"


def test_cs_unresolvable_name_is_no_op() -> None:
    # An unknown /ColorSpace resource leaves the colour space unchanged.
    _, ns = _run(b"/DoesNotExist cs 0.1 0.2 0.3 scn\n")
    # No cs switch happened; the bare scn ran against initial DeviceGray (1
    # component) and consumed only the first operand (upstream: comps[0.1]).
    _approx(ns.get_components(), [0.1])
    assert _cs_name(ns) == "DeviceGray"


def test_separation_cs_then_scn() -> None:
    _, ns = _run(b"/Sep cs 0.7 scn\n")
    _approx(ns.get_components(), [0.7])
    assert _cs_name(ns) == "Separation"


def test_cs_then_scn_too_few_leaves_initial() -> None:
    # RGB needs 3; only 2 supplied -> scn skips, colour stays at the initial
    # colour installed by cs.
    _, ns = _run(b"/CSRGB cs 0.1 0.2 scn\n")
    _approx(ns.get_components(), [0.0, 0.0, 0.0])
    assert _cs_name(ns) == "DeviceRGB"


def test_cs_then_scn_non_numeric_sets_invalid() -> None:
    _, ns = _run(b"/CSRGB cs /Foo /Bar /Baz scn\n")
    assert ns.get_components() == []
    assert ns.get_color_space() is None


def test_cs_then_sc_non_numeric_sets_invalid() -> None:
    stroke, _ = _run(b"/CSRGB CS /Foo /Bar /Baz SC\n")
    assert stroke.get_components() == []
    assert stroke.get_color_space() is None


def test_cs_then_scn_extra_operands_truncates() -> None:
    _, ns = _run(b"/CSRGB cs 0.1 0.2 0.3 0.9 scn\n")
    _approx(ns.get_components(), [0.1, 0.2, 0.3])
    assert _cs_name(ns) == "DeviceRGB"


# ---------------------------------------------------------------------------
# Pattern colour space: scn with a trailing /PatternName operand.
# ---------------------------------------------------------------------------


def test_pattern_cs_then_scn_name_only() -> None:
    _, ns = _run(b"/Pattern cs /P1 scn\n")
    assert ns.get_components() == []
    pattern = ns.get_pattern_name()
    assert pattern is not None
    assert pattern.get_name() == "P1"
    assert _cs_name(ns) == "Pattern"


def test_pattern_cs_uncolored_with_components() -> None:
    _, ns = _run(b"/PatternU cs 0.5 /P1 scn\n")
    _approx(ns.get_components(), [0.5])
    pattern = ns.get_pattern_name()
    assert pattern is not None
    assert pattern.get_name() == "P1"
    assert _cs_name(ns) == "Pattern"


def test_pattern_cs_stroking_scn_name() -> None:
    stroke, _ = _run(b"/Pattern CS /P1 SCN\n")
    pattern = stroke.get_pattern_name()
    assert pattern is not None
    assert pattern.get_name() == "P1"
    assert _cs_name(stroke) == "Pattern"


# ---------------------------------------------------------------------------
# Direct-operator unit cases (no content-stream parsing) — exercise the
# get_color_space hook of the device operators and the invalid-colour path
# in set_device_color in isolation.
# ---------------------------------------------------------------------------


def test_device_operator_get_color_space_singletons() -> None:
    # The faithful device RGB operator advertises the matching singleton.
    from pypdfbox.contentstream.operator.color.set_non_stroking_device_rgb_color import (  # noqa: E501
        SetNonStrokingDeviceRGBColor,
    )

    assert SetNonStrokingDeviceRGBColor().get_color_space() is PDDeviceRGB.INSTANCE


def test_set_device_color_helper_invalid_colour_direct() -> None:
    from pypdfbox.contentstream.operator.color._device_color import (
        set_device_color,
    )

    class _Spy(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[PDColor] = []

        def set_non_stroking_color(self, color: PDColor) -> None:
            self.calls.append(color)

    engine = _Spy()
    set_device_color(
        engine,
        [COSName.get_pdf_name("Bad"), COSFloat(0.2), COSFloat(0.3)],
        color_space=PDDeviceRGB.INSTANCE,
        component_count=3,
        stroking=False,
    )
    [color] = engine.calls
    assert color.get_components() == []
    assert color.get_color_space() is None


def test_set_device_color_helper_none_engine_is_no_op() -> None:
    from pypdfbox.contentstream.operator.color._device_color import (
        set_device_color,
    )

    # Should not raise with a None engine.
    set_device_color(
        None,
        [COSFloat(0.1)],
        color_space=PDDeviceGray.INSTANCE,
        component_count=1,
        stroking=True,
    )


def test_set_device_color_helper_valid_cmyk_direct() -> None:
    from pypdfbox.contentstream.operator.color._device_color import (
        set_device_color,
    )

    class _Spy(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[PDColor] = []

        def set_stroking_color(self, color: PDColor) -> None:
            self.calls.append(color)

    engine = _Spy()
    set_device_color(
        engine,
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
        color_space=PDDeviceCMYK.INSTANCE,
        component_count=4,
        stroking=True,
    )
    [color] = engine.calls
    _approx(color.get_components(), [0.1, 0.2, 0.3, 0.4])
    assert color.get_color_space() is PDDeviceCMYK.INSTANCE


def test_non_numeric_via_cosstring_in_device_op() -> None:
    # A COSString (not COSName) operand is also non-numeric -> invalid colour.
    _, ns = _run(b"(a) (b) (c) rg\n")
    assert ns.get_components() == []
    assert ns.get_color_space() is None


def test_cos_string_operand_constructs_to_cosstring() -> None:
    # Sanity: the tokenizer turns (x) into a COSString, the non-numeric type.
    assert isinstance(COSString("x"), COSString)
