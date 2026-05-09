from __future__ import annotations

import re
import zlib
from typing import Any

import pypdfbox
import pypdfbox.pdmodel

from . import test_xref_stream_output as xref_tests


def _xref_stream_bytes() -> bytes:
    compressed = zlib.compress(b"\x02")
    body = (
        b"7 0 obj\n"
        b"<< /Type /XRef /W [1 0 0] >>\n"
        b"stream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )
    return body + b"startxref\n0\n%%EOF\n"


def _with_correct_startxref(payload: bytes) -> bytes:
    match = re.search(rb"\d+ 0 obj", payload)
    if match is None:
        raise AssertionError("payload has no indirect object")
    return payload.replace(b"startxref\n0\n", f"startxref\n{match.start()}\n".encode())


def test_wave887_object_stream_parser_takes_lf_stream_newline_branch(monkeypatch: Any) -> None:
    payload = _with_correct_startxref(_xref_stream_bytes())

    def fake_write_xref_stream(_doc: object, *, object_stream: bool = False) -> bytes:
        assert object_stream is True
        return payload

    monkeypatch.setattr(xref_tests, "_write_xref_stream", fake_write_xref_stream)

    xref_tests.test_object_stream_yields_type2_xref_entries()


def test_wave887_encrypted_xref_parser_takes_lf_stream_newline_branch(monkeypatch: Any) -> None:
    payload = _with_correct_startxref(_xref_stream_bytes())

    class _Reloaded:
        def __enter__(self) -> _Reloaded:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def is_encrypted(self) -> bool:
            return True

    class _FakePDDocument:
        def add_page(self, _page: object) -> None:
            return None

        def protect(self, _policy: object) -> None:
            return None

        @staticmethod
        def load(_source: bytes, password: str) -> _Reloaded:
            assert password == "user"
            return _Reloaded()

    class _FakeWriter:
        def __init__(self, sink: object, **_kwargs: object) -> None:
            self._sink = sink

        def __enter__(self) -> _FakeWriter:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def write(self, _doc: object) -> None:
            self._sink.write(payload)  # type: ignore[attr-defined]

    monkeypatch.setattr(xref_tests, "COSWriter", _FakeWriter)
    monkeypatch.setattr(pypdfbox, "PDDocument", _FakePDDocument)
    monkeypatch.setattr(pypdfbox.pdmodel, "PDDocument", _FakePDDocument)

    xref_tests.test_xref_stream_body_stays_plaintext_when_handler_active()


def test_wave887_startxref_helper_reports_missing_object() -> None:
    try:
        _with_correct_startxref(b"startxref\n0\n")
    except AssertionError as exc:
        assert "payload has no indirect object" in str(exc)
    else:
        raise AssertionError("expected missing-object assertion")
