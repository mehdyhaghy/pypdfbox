from __future__ import annotations

import builtins
from types import SimpleNamespace
from typing import Any

import pytest

import pypdfbox.loader as loader_module
import pypdfbox.pdmodel as pdmodel_module
from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.multipdf import PageExtractor
from pypdfbox.pdfparser import COSParser


class _EncryptedCOSDocument:
    def __init__(self) -> None:
        self.closed = False
        self._source: Any = None

    def is_encrypted(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


class _FakeParser:
    document = _EncryptedCOSDocument()
    password: str | bytes | None = None
    scratch_file: object | None = None

    def __init__(
        self,
        access: object,
        decryption_password: str | bytes | None = None,
        scratch_file: object | None = None,
    ) -> None:
        self.access = access
        self.decryption_password = decryption_password
        type(self).scratch_file = scratch_file

    def set_password(self, password: str | bytes) -> None:
        type(self).password = password

    def parse(self) -> _EncryptedCOSDocument:
        return type(self).document

    def get_document(self) -> _EncryptedCOSDocument:
        return type(self).document


def test_wave739_loader_returns_encrypted_document_when_pdmodel_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeParser.document = _EncryptedCOSDocument()
    _FakeParser.password = None
    monkeypatch.setattr(loader_module, "PDFParser", _FakeParser)
    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals: dict[str, object] | None = None,  # noqa: A002
        locals: dict[str, object] | None = None,  # noqa: A002
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "pypdfbox.pdmodel" and "PDDocument" in fromlist:
            raise ImportError("pdmodel unavailable")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    doc = Loader.load_pdf(b"%PDF-1.7\n%%EOF", "secret")

    assert doc is _FakeParser.document
    assert _FakeParser.password == "secret"
    assert doc._source is not None


def test_wave739_loader_closes_owned_source_when_auto_decrypt_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeParser.document = _EncryptedCOSDocument()
    monkeypatch.setattr(loader_module, "PDFParser", _FakeParser)

    class FailingPDDocument:
        def __init__(self, document: _EncryptedCOSDocument) -> None:
            self.document = document
            self._owns_document = True

        def decrypt(self, password: str | bytes) -> None:
            raise RuntimeError(f"bad password {password!r}")

    monkeypatch.setattr(pdmodel_module, "PDDocument", FailingPDDocument)

    with pytest.raises(RuntimeError, match="bad password"):
        Loader.load_pdf(b"%PDF-1.7\n%%EOF", "wrong")

    assert _FakeParser.document._source.is_closed()


def test_wave739_page_extractor_copy_helpers_ignore_none_and_failures() -> None:
    extractor = PageExtractor(SimpleNamespace(get_number_of_pages=lambda: 0), 1, 0)
    target = PDDocument()
    try:
        extractor._source_document = SimpleNamespace(get_document_information=lambda: None)
        extractor._copy_document_information(target)

        failing_source_catalog = SimpleNamespace(
            get_viewer_preferences=lambda: (_ for _ in ()).throw(
                RuntimeError("cannot read prefs")
            )
        )
        extractor._source_document = SimpleNamespace(
            get_document_catalog=lambda: failing_source_catalog
        )
        extractor._copy_viewer_preferences(target)

        prefs = object()
        source_catalog = SimpleNamespace(get_viewer_preferences=lambda: prefs)
        target_catalog = SimpleNamespace(
            set_viewer_preferences=lambda _prefs: (_ for _ in ()).throw(
                RuntimeError("cannot set prefs")
            )
        )
        extractor._source_document = SimpleNamespace(
            get_document_catalog=lambda: source_catalog
        )
        extractor._copy_viewer_preferences(
            SimpleNamespace(get_document_catalog=lambda: target_catalog)
        )
    finally:
        target.close()


class _ObjectScanBytes:
    """Bytes-like test double for otherwise defensive object-scan guards."""

    def __init__(
        self,
        raw: bytes,
        *,
        index_sequences: dict[int, list[int]] | None = None,
        slice_overrides: dict[tuple[int | None, int | None], bytes] | None = None,
    ) -> None:
        self._raw = raw
        self._index_sequences = index_sequences or {}
        self._slice_overrides = slice_overrides or {}

    def __len__(self) -> int:
        return len(self._raw)

    def find(self, sub: bytes, start: int = 0) -> int:
        return self._raw.find(sub, start)

    def __getitem__(self, key: int | slice) -> int | bytes:
        if isinstance(key, slice):
            override = self._slice_overrides.get((key.start, key.stop))
            if override is not None:
                return override
            return self._raw[key]
        sequence = self._index_sequences.get(key)
        if sequence:
            value = sequence.pop(0)
            if not sequence:
                self._index_sequences.pop(key)
            return value
        return self._raw[key]


def test_wave739_bf_search_for_objects_skips_split_long_number_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = COSParser(RandomAccessReadBuffer(b""))
    fake_bytes = _ObjectScanBytes(b"x12 0 obj", index_sequences={0: [ord("x"), ord("9")]})
    monkeypatch.setattr(parser, "_read_all_bytes", lambda: fake_bytes)

    assert parser.bf_search_for_objects() == {}


def test_wave739_bf_search_for_objects_skips_value_error_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = COSParser(RandomAccessReadBuffer(b""))
    fake_bytes = _ObjectScanBytes(
        b"12 0 obj",
        slice_overrides={(0, 2): b"not-an-int"},
    )
    monkeypatch.setattr(parser, "_read_all_bytes", lambda: fake_bytes)

    assert parser.bf_search_for_objects() == {}


def test_wave739_bf_search_for_objects_skips_negative_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = COSParser(RandomAccessReadBuffer(b""))
    fake_bytes = _ObjectScanBytes(
        b"12 0 obj",
        slice_overrides={(0, 2): b"-1"},
    )
    monkeypatch.setattr(parser, "_read_all_bytes", lambda: fake_bytes)

    assert parser.bf_search_for_objects() == {}
    assert COSObjectKey(12, 0) not in parser.bf_search_for_objects()
