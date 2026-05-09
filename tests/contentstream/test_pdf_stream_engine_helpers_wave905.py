from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel import PDRectangle, PDResources
from tests.contentstream import test_pdf_stream_engine as stream_mod


def test_wave905_recording_engine_text_leading_hook_records_event() -> None:
    engine = stream_mod._RecordingEngine()  # noqa: SLF001

    engine.set_text_leading(12.5)

    assert engine.events == [("set_text_leading", (12.5,))]


def test_wave905_bytes_content_stream_helper_methods_expose_metadata() -> None:
    stream = stream_mod._BytesContentStream(b"BT ET")  # noqa: SLF001

    contents = stream.get_contents()
    assert isinstance(contents, io.BytesIO)
    assert contents.read() == b"BT ET"

    random_access = stream.get_contents_for_random_access()
    assert random_access.read() == ord("B")

    assert isinstance(stream.get_resources(), PDResources)
    assert isinstance(stream.get_bbox(), PDRectangle)
    assert stream.get_matrix() is None


def test_wave905_show_form_boom_stub_raises_when_form_is_not_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_make_form = stream_mod._make_form_xobject  # noqa: SLF001

    def non_empty_form(_body: bytes) -> object:
        return original_make_form(b"(boom) Tj")

    monkeypatch.setattr(stream_mod, "_make_form_xobject", non_empty_form)

    with pytest.raises(AssertionError, match="operator dispatch must not happen"):
        stream_mod.test_show_form_skips_empty_stream()
