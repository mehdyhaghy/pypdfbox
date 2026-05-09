from __future__ import annotations

import io

from pypdfbox.pdmodel import PDRectangle, PDResources
from tests.contentstream import test_pdf_graphics_stream_engine as graphics_mod


def test_wave876_recording_graphics_engine_draw_image_records_payload() -> None:
    engine = graphics_mod._RecordingGraphicsEngine()  # noqa: SLF001
    image = object()

    engine.draw_image(image)

    assert engine.events == [("draw_image", (image,))]


def test_wave876_bytes_content_stream_exposes_content_and_metadata() -> None:
    stream = graphics_mod._BytesContentStream(b"10 20 m")  # noqa: SLF001

    contents = stream.get_contents()
    assert isinstance(contents, io.BytesIO)
    assert contents.read() == b"10 20 m"

    random_access = stream.get_contents_for_random_access()
    assert random_access.read() == ord("1")

    resources = stream.get_resources()
    assert isinstance(resources, PDResources)

    bbox = stream.get_bbox()
    assert isinstance(bbox, PDRectangle)
    assert bbox.get_width() == 612.0
    assert bbox.get_height() == 792.0

    assert stream.get_matrix() is None
