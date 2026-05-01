from __future__ import annotations

import io
from typing import IO, Any

import pytest

from pypdfbox.contentstream import (
    WIND_EVEN_ODD,
    WIND_NON_ZERO,
    PDContentStream,
    PDFGraphicsStreamEngine,
)
from pypdfbox.cos import COSName
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDPage, PDRectangle, PDResources
from pypdfbox.pdmodel.graphics.color import PDColor


class _RecordingGraphicsEngine(PDFGraphicsStreamEngine):
    """Concrete subclass that records every abstract-hook invocation in
    source order, so tests can assert the parse → dispatch → hook
    pipeline end-to-end without poking at private operator internals."""

    def __init__(self, page: PDPage | None = None) -> None:
        super().__init__(page=page)
        self.events: list[tuple[str, tuple[Any, ...]]] = []
        self._current: tuple[float, float] | None = None

    # --- path construction ---

    def append_rectangle(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
    ) -> None:
        self.events.append(("append_rectangle", (p0, p1, p2, p3)))
        self._current = p0

    def move_to(self, x: float, y: float) -> None:
        self.events.append(("move_to", (x, y)))
        self._current = (x, y)

    def line_to(self, x: float, y: float) -> None:
        self.events.append(("line_to", (x, y)))
        self._current = (x, y)

    def curve_to(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> None:
        self.events.append(("curve_to", (x1, y1, x2, y2, x3, y3)))
        self._current = (x3, y3)

    def get_current_point(self) -> tuple[float, float] | None:
        return self._current

    def close_path(self) -> None:
        self.events.append(("close_path", ()))

    # --- painting ---

    def stroke_path(self) -> None:
        self.events.append(("stroke_path", ()))

    def fill_path(self, winding_rule: int) -> None:
        self.events.append(("fill_path", (winding_rule,)))

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        self.events.append(("fill_and_stroke_path", (winding_rule,)))

    def end_path(self) -> None:
        self.events.append(("end_path", ()))

    # --- clip ---

    def clip(self, winding_rule: int) -> None:
        self.events.append(("clip", (winding_rule,)))

    # --- shading ---

    def shading_fill(self, shading_name: COSName) -> None:
        self.events.append(("shading_fill", (shading_name,)))

    # --- color ---

    def set_stroking_color(self, color: PDColor) -> None:
        self.events.append(("set_stroking_color", (color,)))

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.events.append(("set_non_stroking_color", (color,)))

    # --- image ---

    def draw_image(self, pd_image: Any) -> None:
        self.events.append(("draw_image", (pd_image,)))


class _BytesContentStream(PDContentStream):
    """Tiny PDContentStream wrapping raw bytes for round-trip tests."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return PDResources()

    def get_bbox(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 612.0, 792.0)

    def get_matrix(self) -> Any:
        return None


# ---------- abstract-hook contract ----------


def test_abstract_hooks_raise_not_implemented() -> None:
    """Direct calls into the unimplemented hooks must raise. Mirrors
    upstream's ``abstract`` declaration on the same methods."""
    engine = PDFGraphicsStreamEngine()
    with pytest.raises(NotImplementedError):
        engine.move_to(0.0, 0.0)
    with pytest.raises(NotImplementedError):
        engine.line_to(0.0, 0.0)
    with pytest.raises(NotImplementedError):
        engine.curve_to(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    with pytest.raises(NotImplementedError):
        engine.append_rectangle((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    with pytest.raises(NotImplementedError):
        engine.close_path()
    with pytest.raises(NotImplementedError):
        engine.stroke_path()
    with pytest.raises(NotImplementedError):
        engine.fill_path(WIND_NON_ZERO)
    with pytest.raises(NotImplementedError):
        engine.fill_and_stroke_path(WIND_NON_ZERO)
    with pytest.raises(NotImplementedError):
        engine.end_path()
    with pytest.raises(NotImplementedError):
        engine.clip(WIND_EVEN_ODD)
    with pytest.raises(NotImplementedError):
        engine.draw_image(object())
    with pytest.raises(NotImplementedError):
        engine.shading_fill(COSName.get_pdf_name("Sh1"))
    with pytest.raises(NotImplementedError):
        engine.get_current_point()


def test_get_page_returns_constructor_arg() -> None:
    page = PDPage()
    engine = _RecordingGraphicsEngine(page=page)
    assert engine.get_page() is page


def test_get_page_defaults_to_none() -> None:
    engine = _RecordingGraphicsEngine()
    assert engine.get_page() is None


def test_transformed_point_default_is_identity() -> None:
    engine = _RecordingGraphicsEngine()
    assert engine.transformed_point(1.5, -2.25) == (1.5, -2.25)


# ---------- operator registration ----------


def test_constructor_registers_path_operators() -> None:
    """All path-construction operator processors should be wired up at
    construction so the operator-name registry is populated even before
    we override ``process_operator`` for hook routing."""
    engine = _RecordingGraphicsEngine()
    ops = engine.get_operators()
    for name in ("m", "l", "c", "v", "y", "re", "h", "n"):
        assert name in ops, f"missing path operator: {name}"


def test_constructor_registers_painting_operators() -> None:
    engine = _RecordingGraphicsEngine()
    ops = engine.get_operators()
    for name in ("S", "s", "f", "F", "f*", "B", "B*", "b", "b*"):
        assert name in ops, f"missing painting operator: {name}"


def test_constructor_registers_clip_and_state_operators() -> None:
    engine = _RecordingGraphicsEngine()
    ops = engine.get_operators()
    for name in (
        "W",
        "W*",
        "q",
        "Q",
        "cm",
        "gs",
        "i",
        "ri",
        "d",
    ):
        assert name in ops, f"missing clip/state operator: {name}"


def test_constructor_registers_image_and_text_operators() -> None:
    engine = _RecordingGraphicsEngine()
    ops = engine.get_operators()
    for name in ("Do", "BI", "BT", "ET", "Tj", "TJ", "Tf", "Tm"):
        assert name in ops, f"missing image/text operator: {name}"


def test_constructor_registers_marked_content_operators() -> None:
    engine = _RecordingGraphicsEngine()
    ops = engine.get_operators()
    for name in ("BMC", "BDC", "EMC"):
        assert name in ops, f"missing marked-content operator: {name}"


def test_constructor_binds_engine_context_to_every_registered_operator() -> None:
    """Upstream PDFGraphicsStreamEngine constructs every operator
    handler via ``addOperator(new X(this))`` so the engine reference is
    available on each processor. Verify the same invariant holds for
    pypdfbox: every registered processor's ``_context`` should be this
    engine, regardless of whether it was wired through ``add_operator``
    or through the lite-stub direct-registration path."""
    engine = _RecordingGraphicsEngine()
    ops = engine.get_operators()
    # Sample a path operator (lite stub), a state operator (lite stub),
    # a colour operator (engine-bound), and a text operator (engine-bound)
    # — all should report the engine as their context.
    for name in ("m", "h", "q", "Q", "cm", "BMC", "G", "BT"):
        processor = ops[name]
        assert processor._context is engine, (
            f"operator {name!r} processor was not bound to engine context"
        )


# ---------- end-to-end dispatch via the operator stream ----------


def test_round_trip_path_construction() -> None:
    """A small content stream exercising every path-construction
    operator should drive the abstract hooks in source order with the
    raw user-space operands."""
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(
        b"10 20 m "                 # move_to
        b"30 40 l "                 # line_to
        b"50 60 70 80 90 100 c "    # curve_to
        b"110 120 130 140 v "       # curve_to (replicate initial point)
        b"150 160 170 180 y "       # curve_to (replicate final point)
        b"200 210 50 60 re "        # append_rectangle
        b"h "                       # close_path
    )
    engine.process_stream(stream)

    sequence = [name for name, _ in engine.events]
    assert sequence == [
        "move_to",
        "line_to",
        "curve_to",
        "curve_to",
        "curve_to",
        "append_rectangle",
        "close_path",
    ]
    by_index = engine.events
    assert by_index[0][1] == (10.0, 20.0)
    assert by_index[1][1] == (30.0, 40.0)
    assert by_index[2][1] == (50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
    # v: first control = current point (90, 100 from previous c)
    assert by_index[3][1] == (90.0, 100.0, 110.0, 120.0, 130.0, 140.0)
    # y: second control = end point
    assert by_index[4][1] == (150.0, 160.0, 170.0, 180.0, 170.0, 180.0)
    # re corners: (x,y), (x+w,y), (x+w,y+h), (x,y+h)
    assert by_index[5][1] == (
        (200.0, 210.0),
        (250.0, 210.0),
        (250.0, 270.0),
        (200.0, 270.0),
    )


def test_round_trip_painting_operators() -> None:
    """Each painting operator should drive the matching abstract hook
    with the correct winding rule."""
    engine = _RecordingGraphicsEngine()
    # ``n`` with no path, then every paint variant in a single stream.
    stream = _BytesContentStream(b"S s f F f* B B* b b* n")
    engine.process_stream(stream)

    sequence = [(name, args) for name, args in engine.events]
    # ``s``  : close_path + stroke_path
    # ``b``  : close_path + fill_and_stroke_path(non_zero)
    # ``b*`` : close_path + fill_and_stroke_path(even_odd)
    assert sequence == [
        ("stroke_path", ()),
        ("close_path", ()),
        ("stroke_path", ()),
        ("fill_path", (WIND_NON_ZERO,)),
        ("fill_path", (WIND_NON_ZERO,)),
        ("fill_path", (WIND_EVEN_ODD,)),
        ("fill_and_stroke_path", (WIND_NON_ZERO,)),
        ("fill_and_stroke_path", (WIND_EVEN_ODD,)),
        ("close_path", ()),
        ("fill_and_stroke_path", (WIND_NON_ZERO,)),
        ("close_path", ()),
        ("fill_and_stroke_path", (WIND_EVEN_ODD,)),
        ("end_path", ()),
    ]


def test_round_trip_clip_operators() -> None:
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(b"W W*")
    engine.process_stream(stream)
    assert engine.events == [
        ("clip", (WIND_NON_ZERO,)),
        ("clip", (WIND_EVEN_ODD,)),
    ]


def test_round_trip_shading_fill_with_name() -> None:
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(b"/Sh1 sh")
    engine.process_stream(stream)
    assert len(engine.events) == 1
    name, args = engine.events[0]
    assert name == "shading_fill"
    assert isinstance(args[0], COSName)
    assert args[0].get_name() == "Sh1"


def test_round_trip_shading_fill_without_name_is_silently_skipped() -> None:
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(b"sh")
    engine.process_stream(stream)
    assert engine.events == []


def test_round_trip_device_color_operators() -> None:
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(
        b"0.25 G 0.5 g "
        b"0.125 0.25 0.5 RG 0.25 0.5 0.75 rg "
        b"0.125 0.25 0.5 0.75 K 0.0 0.25 0.5 1.0 k"
    )
    engine.process_stream(stream)

    sequence = [(name, args[0]) for name, args in engine.events]
    assert [name for name, _ in sequence] == [
        "set_stroking_color",
        "set_non_stroking_color",
        "set_stroking_color",
        "set_non_stroking_color",
        "set_stroking_color",
        "set_non_stroking_color",
    ]
    assert [color.get_color_space_name() for _, color in sequence] == [
        "DeviceGray",
        "DeviceGray",
        "DeviceRGB",
        "DeviceRGB",
        "DeviceCMYK",
        "DeviceCMYK",
    ]
    assert [color.get_components() for _, color in sequence] == [
        [0.25],
        [0.5],
        [0.125, 0.25, 0.5],
        [0.25, 0.5, 0.75],
        [0.125, 0.25, 0.5, 0.75],
        [0.0, 0.25, 0.5, 1.0],
    ]


def test_close_and_stroke_decomposes_to_close_then_stroke() -> None:
    """The ``s`` operator should fire ``close_path`` *before*
    ``stroke_path`` — order matters because subclasses may rely on the
    closed subpath being part of the stroke."""
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(b"s")
    engine.process_stream(stream)
    assert engine.events == [("close_path", ()), ("stroke_path", ())]


def test_path_then_paint_full_sequence() -> None:
    """A realistic mini-stream: rectangle then fill-and-stroke."""
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(b"100 100 50 25 re B")
    engine.process_stream(stream)
    sequence = [name for name, _ in engine.events]
    assert sequence == ["append_rectangle", "fill_and_stroke_path"]
    assert engine.events[1][1] == (WIND_NON_ZERO,)


def test_legacy_F_routes_to_fill_path_non_zero() -> None:
    """``F`` is the legacy alias of ``f`` — it must drive
    :meth:`fill_path` with the non-zero winding rule."""
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(b"F")
    engine.process_stream(stream)
    assert engine.events == [("fill_path", (WIND_NON_ZERO,))]


def test_short_operand_lists_are_silently_dropped() -> None:
    """Path operators with too few operands should NOT crash the engine
    — upstream's pattern is to skip the malformed operator and continue
    processing. Verify by interleaving a bad ``m`` with a good one."""
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(b"10 m 20 30 m")
    engine.process_stream(stream)
    # Only the well-formed move_to should have fired.
    assert engine.events == [("move_to", (20.0, 30.0))]


def test_non_numeric_operands_silently_dropped() -> None:
    """COSName instead of COSNumber on a path op → skip the operator."""
    engine = _RecordingGraphicsEngine()
    stream = _BytesContentStream(b"/Foo /Bar m 50 60 m")
    engine.process_stream(stream)
    assert engine.events == [("move_to", (50.0, 60.0))]


def test_super_dispatch_for_unhandled_operators() -> None:
    """Operators NOT in the graphics-hook set (e.g. ``q`` / ``Q`` /
    ``cm``) should fall through to the parent ``process_operator`` and
    drive the existing engine hooks (or the lite no-op stubs)."""
    captured: list[str] = []

    class _Tracker(_RecordingGraphicsEngine):
        def save_graphics_state(self) -> None:
            captured.append("save")

        def restore_graphics_state(self) -> None:
            captured.append("restore")

    engine = _Tracker()
    stream = _BytesContentStream(b"q Q")
    engine.process_stream(stream)
    assert captured == ["save", "restore"]


def test_text_state_operators_dispatch_to_engine_hooks() -> None:
    captured: list[tuple[str, float | int]] = []

    class _Tracker(_RecordingGraphicsEngine):
        def set_character_spacing(self, spacing: float) -> None:
            captured.append(("Tc", spacing))

        def set_word_spacing(self, spacing: float) -> None:
            captured.append(("Tw", spacing))

        def set_horizontal_scaling(self, scaling: float) -> None:
            captured.append(("Tz", scaling))

        def set_text_leading(self, leading: float) -> None:
            captured.append(("TL", leading))

        def set_text_rendering_mode(self, mode: int) -> None:
            captured.append(("Tr", mode))

        def set_text_rise(self, rise: float) -> None:
            captured.append(("Ts", rise))

    engine = _Tracker()
    stream = _BytesContentStream(b"1 Tc 2 Tw 75 Tz 14 TL 3 Tr 4 Ts")
    engine.process_stream(stream)

    assert captured == [
        ("Tc", 1.0),
        ("Tw", 2.0),
        ("Tz", 75.0),
        ("TL", 14.0),
        ("Tr", 3),
        ("Ts", 4.0),
    ]


def test_next_line_dispatches_move_text_using_current_leading() -> None:
    captured: list[tuple[float, float]] = []

    class _Tracker(_RecordingGraphicsEngine):
        def get_text_leading(self) -> float:
            return 12.5

        def move_text_position(self, tx: float, ty: float) -> None:
            captured.append((tx, ty))

    engine = _Tracker()
    stream = _BytesContentStream(b"T*")
    engine.process_stream(stream)

    assert captured == [(0.0, -12.5)]
