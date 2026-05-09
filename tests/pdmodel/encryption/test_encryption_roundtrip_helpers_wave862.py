from __future__ import annotations

from types import SimpleNamespace

from pypdfbox.cos import COSArray, COSName, COSStream
from tests.pdmodel.encryption import test_encryption_roundtrip as roundtrip


class _DocumentWithContents:
    def __init__(self, contents: object) -> None:
        self._contents = contents

    def get_pages(self) -> list[object]:
        page_dict = SimpleNamespace(
            get_dictionary_object=lambda _name: self._contents,
        )
        return [SimpleNamespace(get_cos_object=lambda: page_dict)]


def _stream(data: bytes) -> COSStream:
    stream = COSStream()
    stream.set_raw_data(data)
    return stream


def test_wave862_first_page_contents_joins_cos_array_streams() -> None:
    contents = COSArray()
    contents.add(_stream(b"first"))
    contents.add(COSName.get_pdf_name("IgnoredNonStream"))
    contents.add(_stream(b"second"))

    assert roundtrip._first_page_contents(_DocumentWithContents(contents)) == (
        b"first\nsecond"
    )


def test_wave862_first_page_contents_returns_empty_for_unknown_contents() -> None:
    assert roundtrip._first_page_contents(_DocumentWithContents(object())) == b""
