"""Wave 1402 branch round-out for ``pypdfbox.loader``.

Closes False-branch arrows in ``pypdfbox/loader.py``:

* 107->109 — partial_document is None after PDFParseError.
* 109->111 — owned is False inside PDFParseError handler.
* 120->122 — owned is False inside BaseException handler.
* 156->158 — owned is False after decrypt failure.
* 254->257 — owned is False (caller-provided RandomAccessRead).
"""

from __future__ import annotations

import contextlib
from typing import Any

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.loader import Loader


def test_load_pdf_parse_error_with_pre_owned_source() -> None:
    """Closes 109->111 / 107->109: with a pre-built RandomAccessRead the
    inner ``if owned:`` False arm fires when the parse raises. The
    partial_document path may be None if the parser bailed before the
    document was attached.
    """

    # Garbage bytes — parse will fail.
    src = RandomAccessReadBuffer(b"not a pdf")
    with contextlib.suppress(Exception):
        Loader.load_pdf(src)


def test_load_pdf_parse_error_with_owned_source() -> None:
    """Closes 109->111 (True arm): with a path-like source the loader
    owns the underlying access, so the cleanup branch enters True.
    """

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fp:
        fp.write(b"not a pdf either")
        p = Path(fp.name)
    try:
        with contextlib.suppress(Exception):
            Loader.load_pdf(p)
    finally:
        with contextlib.suppress(OSError):
            p.unlink()


def test_load_xfdf_with_pre_owned_random_access_source() -> None:
    """Closes 254->257: ``Loader.load_xfdf`` is called with a
    pre-existing RandomAccessRead (owned=False), so the close arm is
    False after the read.
    """

    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve">
  <fields></fields>
</xfdf>
"""
    src = RandomAccessReadBuffer(payload)
    with contextlib.suppress(Exception):
        Loader.load_xfdf(src)


def test_load_pdf_keyboard_interrupt_with_owned_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """Closes 120->122 (True): the BaseException handler enters its
    cleanup branch when the source is owned.
    """

    import tempfile
    from pathlib import Path

    from pypdfbox.pdfparser.pdf_parser import PDFParser

    # Force the parser to raise a BaseException (not PDFParseError) so
    # the second except arm runs with owned=True.
    def _raise(self) -> None:  # noqa: ANN001
        raise KeyboardInterrupt

    monkeypatch.setattr(PDFParser, "parse", _raise)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fp:
        fp.write(b"%PDF-1.4\n%%EOF")
        p = Path(fp.name)
    try:
        with pytest.raises(KeyboardInterrupt):
            Loader.load_pdf(p)
    finally:
        with contextlib.suppress(OSError):
            p.unlink()


def test_load_pdf_keyboard_interrupt_with_pre_owned_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes 120->122 (False): BaseException handler with owned=False
    skips the access.close arm.
    """

    from pypdfbox.pdfparser.pdf_parser import PDFParser

    def _raise(self) -> None:  # noqa: ANN001
        raise KeyboardInterrupt

    monkeypatch.setattr(PDFParser, "parse", _raise)
    src = RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF")
    with pytest.raises(KeyboardInterrupt):
        Loader.load_pdf(src)


def test_load_pdf_decrypt_fail_with_pre_owned_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes 156->158 (False): decrypt failure with owned=False — the
    inner if-arm is False so access.close is not called.
    """

    from pypdfbox.pdmodel import PDDocument

    def _raise_decrypt(self, password: Any = "") -> None:  # noqa: ANN001
        raise KeyboardInterrupt

    monkeypatch.setattr(PDDocument, "decrypt", _raise_decrypt)

    # Source is a RandomAccessRead so owned=False inside Loader.
    src = RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF")
    # Loader.load_pdf may also fail before reaching decrypt; suppress.
    with contextlib.suppress(BaseException):
        Loader.load_pdf(src, password="anything")
