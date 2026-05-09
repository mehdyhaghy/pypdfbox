from __future__ import annotations

import builtins
from types import SimpleNamespace
from typing import Any

import pytest

import pypdfbox.loader as loader_module
import pypdfbox.pdmodel as pdmodel_module
from pypdfbox import Loader, PDDocument
from pypdfbox.multipdf import PageExtractor


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

    def __init__(self, access: object) -> None:
        self.access = access

    def set_password(self, password: str | bytes) -> None:
        type(self).password = password

    def parse(self) -> _EncryptedCOSDocument:
        return type(self).document

    def get_document(self) -> _EncryptedCOSDocument:
        return type(self).document


def test_wave728_page_extractor_best_effort_copy_helpers_swallow_failures() -> None:
    extractor = PageExtractor(SimpleNamespace(get_number_of_pages=lambda: 0), 1, 0)
    target = PDDocument()
    try:
        extractor._source_document = SimpleNamespace(get_document_information=lambda: None)
        extractor._copy_document_information(target)

        source_catalog = SimpleNamespace(
            get_viewer_preferences=lambda: (_ for _ in ()).throw(RuntimeError("prefs"))
        )
        extractor._source_document = SimpleNamespace(get_document_catalog=lambda: source_catalog)
        extractor._copy_viewer_preferences(target)

        prefs = object()
        source_catalog = SimpleNamespace(get_viewer_preferences=lambda: prefs)
        target_catalog = SimpleNamespace(
            set_viewer_preferences=lambda _prefs: (_ for _ in ()).throw(
                RuntimeError("set prefs")
            )
        )
        extractor._source_document = SimpleNamespace(get_document_catalog=lambda: source_catalog)
        failing_target = SimpleNamespace(get_document_catalog=lambda: target_catalog)
        extractor._copy_viewer_preferences(failing_target)  # type: ignore[arg-type]
    finally:
        target.close()


def test_wave728_loader_returns_encrypted_document_when_pdmodel_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeParser.document = _EncryptedCOSDocument()
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
    assert doc.is_encrypted() is True


def test_wave728_loader_closes_owned_source_when_auto_decrypt_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeParser.document = _EncryptedCOSDocument()
    monkeypatch.setattr(loader_module, "PDFParser", _FakeParser)

    class FailingPDDocument:
        def __init__(self, document: _EncryptedCOSDocument) -> None:
            self.document = document
            self._owns_document = True

        def decrypt(self, password: str | bytes) -> None:
            raise ValueError(f"bad password: {password!r}")

    monkeypatch.setattr(pdmodel_module, "PDDocument", FailingPDDocument)

    with pytest.raises(ValueError, match="bad password"):
        Loader.load_pdf(b"%PDF-1.7\n%%EOF", "wrong")

    assert _FakeParser.document._source is not None
    assert _FakeParser.document._source.is_closed()
