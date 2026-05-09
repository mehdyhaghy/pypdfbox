from __future__ import annotations

from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSName
from tests.integration import test_end_to_end as e2e


class _LoadedDocument:
    def __init__(self, contents: object) -> None:
        self._contents = contents

    def __enter__(self) -> _LoadedDocument:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def get_number_of_pages(self) -> int:
        return 1

    def get_pages(self) -> list[object]:
        page_dict = SimpleNamespace(
            get_dictionary_object=lambda _name: self._contents,
        )
        return [SimpleNamespace(get_cos_object=lambda: page_dict)]


def _stream(data: bytes) -> e2e.COSStream:
    stream = e2e.COSStream()
    stream.set_raw_data(data)
    return stream


def _patch_pd_document_load(monkeypatch: pytest.MonkeyPatch, contents: object) -> None:
    def load(_data: bytes, password: str = "") -> _LoadedDocument:
        assert password == "u"
        return _LoadedDocument(contents)

    monkeypatch.setattr(e2e.PDDocument, "load", staticmethod(load))


def test_wave861_encrypted_roundtrip_reads_array_contents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contents = e2e.COSArray()
    contents.add(_stream(b"prefix"))
    contents.add(COSName.get_pdf_name("IgnoredNonStream"))
    contents.add(_stream(b"Encrypted body"))
    _patch_pd_document_load(monkeypatch, contents)

    e2e.test_build_encrypt_save_reload_with_password()


def test_wave861_encrypted_roundtrip_reaches_unknown_contents_defense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pd_document_load(monkeypatch, object())

    with pytest.raises(AssertionError):
        e2e.test_build_encrypt_save_reload_with_password()
