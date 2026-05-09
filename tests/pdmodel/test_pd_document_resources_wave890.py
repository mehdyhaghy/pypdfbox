from __future__ import annotations

import tests.pdmodel.test_pd_document_resources_wave507 as wave507


def test_wave890_buffer_write_helper_methods_track_state() -> None:
    sink = wave507._BufferWrite()

    sink.write(ord("A"))
    sink.write_bytes(b"012345", offset=2, length=3)

    assert bytes(sink.data) == b"A234"
    assert sink.is_closed() is False

    sink.clear()
    assert bytes(sink.data) == b""

    sink.close()
    assert sink.is_closed() is True
