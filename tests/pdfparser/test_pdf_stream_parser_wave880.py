from __future__ import annotations

import pytest

import tests.pdfparser.test_pdf_stream_parser_parity as parity
from pypdfbox.pdfparser.pdf_stream_parser import Operator


class _FakeParser:
    def parse(self) -> list[object]:
        return [object(), object(), Operator("m")]


def test_wave880_parity_content_stream_stub_defensive_methods(monkeypatch) -> None:
    def from_content_stream(content_stream):  # noqa: ANN001
        with pytest.raises(NotImplementedError):
            content_stream.get_contents()
        with pytest.raises(NotImplementedError):
            content_stream.get_contents_for_random_access()
        assert content_stream.get_contents_for_stream_parsing().read() == ord("1")
        assert content_stream.get_resources() is None
        with pytest.raises(NotImplementedError):
            content_stream.get_bbox()
        with pytest.raises(NotImplementedError):
            content_stream.get_matrix()
        return _FakeParser()

    monkeypatch.setattr(
        parity.PDFStreamParser,
        "from_content_stream",
        staticmethod(from_content_stream),
    )

    parity.test_from_content_stream_uses_get_contents_for_stream_parsing()
