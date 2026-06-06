from __future__ import annotations

from typing import Any

import pytest

import pypdfbox.pdmodel

from . import test_encrypted_xref_stream as encrypted_tests


def _xref_stream_payload() -> bytes:
    body = b"5 0 obj\n<< /Type /XRef >>\nstream\nxpayload\nendstream\nendobj\n"
    return body + f"startxref\n{body.index(b'5 0 obj')}\n%%EOF\n".encode()


def test_wave918_writer_shape_accepts_lf_only_stream_newline(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        encrypted_tests,
        "_build_encrypted_xref_stream_pdf",
        lambda: _xref_stream_payload(),
    )

    encrypted_tests.test_writer_emits_plaintext_flate_xref_stream()


def test_wave918_full_load_decode_reports_garbled_records(monkeypatch: Any) -> None:
    """Meta-test driving the failure path of the (wave-1501-rewritten)
    ``test_xref_stream_decode_after_full_load_yields_plaintext_records``.

    That test now proves the xref stream was read as plaintext by asserting
    every pooled object resolves AND the page text decodes — a double-decipher
    would garble the offsets so the payload would be absent. Here we stub
    ``PDDocument.load`` to return a doc whose pool resolves cleanly but whose
    text comes back empty (simulating garbled content), and confirm the test
    raises ``AssertionError`` (payload not in extracted text). Replaces the
    old meta-test that matched the now-removed ``"no /Type /XRef stream
    surfaced"`` ``pytest.fail`` branch."""

    class _Resolvable:
        def get_object(self) -> object:
            return object()

    class _COSDocument:
        def get_objects(self) -> list[object]:
            return [_Resolvable()]

    class _LoadedDocument:
        def __enter__(self) -> _LoadedDocument:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def get_document(self) -> _COSDocument:
            return _COSDocument()

    class _PDDocument:
        @staticmethod
        def load(_source: bytes, password: str) -> _LoadedDocument:
            assert password == "user"
            return _LoadedDocument()

    class _Stripper:
        def get_text(self, _doc: object) -> str:
            return ""  # garbled / no decodable text

    monkeypatch.setattr(
        encrypted_tests,
        "_build_encrypted_xref_stream_pdf",
        lambda *, page_text="": b"%PDF-1.7\n%%EOF\n",
    )
    monkeypatch.setattr(pypdfbox.pdmodel, "PDDocument", _PDDocument)
    monkeypatch.setattr(
        "pypdfbox.text.pdf_text_stripper.PDFTextStripper", _Stripper
    )

    with pytest.raises(AssertionError):
        encrypted_tests.test_xref_stream_decode_after_full_load_yields_plaintext_records()

