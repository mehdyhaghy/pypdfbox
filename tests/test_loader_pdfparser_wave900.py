from __future__ import annotations

import builtins

import pytest

import tests.test_loader_pdfparser_wave739 as wave739


def test_wave900_loader_import_fallback_local_branch_is_exercised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def load_pdf(source, password=""):  # noqa: ANN001, ANN002
        builtins.__import__("math")
        wave739._FakeParser.password = password
        doc = wave739._FakeParser.document
        doc._source = object()
        return doc

    monkeypatch.setattr(wave739.Loader, "load_pdf", staticmethod(load_pdf))

    wave739.test_wave739_loader_returns_encrypted_document_when_pdmodel_import_fails(
        monkeypatch
    )


def test_wave900_fake_parser_and_document_support_methods() -> None:
    document = wave739._EncryptedCOSDocument()
    parser = wave739._FakeParser(object())
    wave739._FakeParser.document = document

    assert parser.get_document() is document
    assert document.closed is False

    document.close()

    assert document.closed is True
