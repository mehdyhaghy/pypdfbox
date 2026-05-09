from __future__ import annotations

import tests.contentstream.test_inline_image_engine_wiring as inline_helpers
import tests.contentstream.test_stream_engine_wave742 as stream_helpers
import tests.pdmodel.test_pd_resource_cache as resource_helpers
from pypdfbox.cos import COSName


def test_wave860_inline_image_graphics_helper_noop_hooks_are_callable() -> None:
    engine = inline_helpers._RecordingGraphicsEngine()
    image = object()

    assert engine.append_rectangle((0, 0), (1, 0), (1, 1), (0, 1)) is None
    engine.draw_image(image)
    assert engine.clip(1) is None
    assert engine.move_to(1.0, 2.0) is None
    assert engine.line_to(3.0, 4.0) is None
    assert engine.curve_to(1.0, 2.0, 3.0, 4.0, 5.0, 6.0) is None
    assert engine.get_current_point() is None
    assert engine.close_path() is None
    assert engine.end_path() is None
    assert engine.stroke_path() is None
    assert engine.fill_path(1) is None
    assert engine.fill_and_stroke_path(1) is None
    assert engine.shading_fill(COSName.get_pdf_name("S1")) is None
    assert engine.drawn == [image]


def test_wave860_stream_engine_recording_helper_records_all_hooks() -> None:
    engine = stream_helpers._RecordingGraphicsEngine()
    image = object()
    shading = COSName.get_pdf_name("Shade")

    engine.append_rectangle((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    engine.draw_image(image)
    engine.clip(1)
    engine.move_to(2.0, 3.0)
    engine.line_to(4.0, 5.0)
    engine.curve_to(1.0, 2.0, 3.0, 4.0, 6.0, 7.0)
    assert engine.get_current_point() == (6.0, 7.0)
    engine.close_path()
    engine.end_path()
    engine.stroke_path()
    engine.fill_path(1)
    engine.fill_and_stroke_path(1)
    engine.shading_fill(shading)

    assert engine.events == [
        (
            "append_rectangle",
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        ),
        ("draw_image", (image,)),
        ("clip", (1,)),
        ("move_to", (2.0, 3.0)),
        ("line_to", (4.0, 5.0)),
        ("curve_to", (1.0, 2.0, 3.0, 4.0, 6.0, 7.0)),
        ("close_path", ()),
        ("end_path", ()),
        ("stroke_path", ()),
        ("fill_path", (1,)),
        ("fill_and_stroke_path", (1,)),
        ("shading_fill", (shading,)),
    ]


def test_wave860_minimal_resource_cache_helper_abstract_methods_are_noops() -> None:
    cache = resource_helpers._MinimalCache()
    key = resource_helpers._ref(860)
    value = object()

    assert cache.get_font(key) is None
    assert cache.put_font(key, value) is None
    assert cache.get_x_object(key) is None
    assert cache.put_x_object(key, value) is None
    assert cache.get_color_space(key) is None
    assert cache.put_color_space(key, value) is None
    assert cache.get_pattern(key) is None
    assert cache.put_pattern(key, value) is None
    assert cache.get_shading(key) is None
    assert cache.put_shading(key, value) is None
    assert cache.get_ext_g_state(key) is None
    assert cache.put_ext_g_state(key, value) is None
