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


def test_wave918_full_load_decode_reports_missing_xref_stream(monkeypatch: Any) -> None:
    class _COSDocument:
        def get_objects(self) -> list[object]:
            return []

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

    monkeypatch.setattr(
        encrypted_tests,
        "_build_encrypted_xref_stream_pdf",
        lambda: b"%PDF-1.7\n%%EOF\n",
    )
    monkeypatch.setattr(pypdfbox.pdmodel, "PDDocument", _PDDocument)

    with pytest.raises(pytest.fail.Exception, match="no /Type /XRef stream surfaced"):
        encrypted_tests.test_xref_stream_decode_after_full_load_yields_plaintext_records()

