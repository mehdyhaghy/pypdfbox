from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSInteger, COSName
from tests.contentstream.test_pdf_stream_engine_wave684 import (
    _RecordingGraphicsEngine,
)


def test_wave854_recording_graphics_engine_records_valid_path_ops() -> None:
    engine = _RecordingGraphicsEngine()

    engine.process_operator("m", [COSInteger.get(1), COSInteger.get(2)])
    engine.process_operator("l", [COSInteger.get(3), COSInteger.get(4)])
    engine.process_operator(
        "c",
        [
            COSInteger.get(5),
            COSInteger.get(6),
            COSInteger.get(7),
            COSInteger.get(8),
            COSInteger.get(9),
            COSInteger.get(10),
        ],
    )
    engine.process_operator(
        "v",
        [COSInteger.get(11), COSInteger.get(12), COSInteger.get(13), COSInteger.get(14)],
    )
    engine.process_operator(
        "y",
        [COSInteger.get(15), COSInteger.get(16), COSInteger.get(17), COSInteger.get(18)],
    )
    engine.process_operator(
        "re",
        [COSInteger.get(1), COSInteger.get(2), COSInteger.get(3), COSInteger.get(4)],
    )

    assert engine.events == [
        ("move_to", (1.0, 2.0)),
        ("line_to", (3.0, 4.0)),
        ("curve_to", (5.0, 6.0, 7.0, 8.0, 9.0, 10.0)),
        ("curve_to", (9.0, 10.0, 11.0, 12.0, 13.0, 14.0)),
        ("curve_to", (15.0, 16.0, 17.0, 18.0, 17.0, 18.0)),
        (
            "append_rectangle",
            ((1.0, 2.0), (4.0, 2.0), (4.0, 6.0), (1.0, 6.0)),
        ),
    ]


def test_wave854_recording_graphics_engine_records_paint_clip_and_shading() -> None:
    engine = _RecordingGraphicsEngine()
    shade = COSName.get_pdf_name("Shade1")

    for name in ("h", "S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n", "W", "W*"):
        engine.process_operator(name, [])
    engine.process_operator("sh", [shade])

    # No MoveTo establishes a current point, so ``h`` and the close-then-paint
    # operators (``s``, ``b``, ``b*``) guard out their ``close_path`` step
    # (upstream ``ClosePath`` warn-skips without a current point).
    assert engine.events == [
        ("stroke_path", ()),
        ("stroke_path", ()),
        ("fill_path", (1,)),
        ("fill_path", (1,)),
        ("fill_path", (0,)),
        ("fill_and_stroke_path", (1,)),
        ("fill_and_stroke_path", (0,)),
        ("fill_and_stroke_path", (1,)),
        ("fill_and_stroke_path", (0,)),
        ("end_path", ()),
        ("clip", (1,)),
        ("clip", (0,)),
        ("shading_fill", (shade,)),
    ]


def test_wave854_recording_graphics_engine_draw_image_hook_records() -> None:
    image = object()
    engine = _RecordingGraphicsEngine()

    engine.show_inline_image(image)

    assert engine.events == [("draw_image", (image,))]


def test_wave854_show_form_with_positive_length_processes_stream() -> None:
    class PositiveLengthCOS:
        def get_length(self) -> int:
            return 1

    class Form:
        def get_cos_object(self) -> PositiveLengthCOS:
            return PositiveLengthCOS()

    class Engine(_RecordingGraphicsEngine):
        def __init__(self) -> None:
            super().__init__()
            self.processed = False

        def process_stream(self, content_stream: Any) -> None:
            self.processed = True

    engine = Engine()
    engine._current_page = object()

    engine.show_form(Form())  # type: ignore[arg-type]

    assert engine.processed is True
