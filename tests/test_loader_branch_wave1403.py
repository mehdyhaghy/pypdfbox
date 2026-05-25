"""Wave 1403 branch round-out for ``pypdfbox.loader``.

Closes the still-open arcs left after wave 1402:

* 107->109 — ``partial_document`` is *None* after a ``PDFParseError`` (the
  False arm of ``if partial_document is not None``). Wave 1402's test was
  non-deterministic about this; here the parser is faked so that
  ``get_document()`` is guaranteed to return None.
* 156->158 — auto-decrypt failure with ``owned=False`` (the False arm of the
  inner ``if owned:`` inside the decrypt ``except``). Driven by a pre-built
  ``RandomAccessRead`` source so ownership stays with the caller while a
  faked ``PDDocument.decrypt`` raises.
"""

from __future__ import annotations

from typing import Any

import pytest

import pypdfbox.loader as loader_module
import pypdfbox.pdmodel as pdmodel_module
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.loader import Loader
from pypdfbox.pdfparser import PDFParseError


class _NoDocumentParser:
    """Parser stub whose ``parse`` raises and whose ``get_document`` is None.

    This forces the loader's ``PDFParseError`` handler into the False arm of
    ``if partial_document is not None`` (arc 107->109).
    """

    def __init__(
        self,
        access: object,
        decryption_password: str | bytes | None = None,
        scratch_file: object | None = None,
    ) -> None:
        self.access = access

    def set_password(self, password: str | bytes) -> None:
        pass

    def parse(self) -> Any:
        raise PDFParseError("boom")

    def get_document(self) -> Any:
        return None


def test_parse_error_with_none_partial_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes 107->109: ``get_document()`` returns None so the close call on
    line 108 is skipped and control jumps straight to ``if owned:``.
    """
    monkeypatch.setattr(loader_module, "PDFParser", _NoDocumentParser)

    # Pre-built source => owned=False; the loader surfaces the parse failure
    # as OSError per its upstream-mirroring contract.
    src = RandomAccessReadBuffer(b"%PDF-1.7\nnot really a pdf")
    with pytest.raises(OSError):
        Loader.load_pdf(src)


class _EncryptedCOSDocument:
    def __init__(self) -> None:
        self.closed = False
        self._source: Any = None

    def is_encrypted(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


class _EncryptedParser:
    document = _EncryptedCOSDocument()
    password: str | bytes | None = None

    def __init__(
        self,
        access: object,
        decryption_password: str | bytes | None = None,
        scratch_file: object | None = None,
    ) -> None:
        self.access = access

    def set_password(self, password: str | bytes) -> None:
        type(self).password = password

    def parse(self) -> _EncryptedCOSDocument:
        return type(self).document

    def get_document(self) -> _EncryptedCOSDocument:
        return type(self).document


def test_decrypt_failure_with_unowned_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes 156->158: decrypt raises while the source is caller-owned
    (``owned=False``), so the inner ``if owned: access.close()`` arm is False
    and the exception just propagates.
    """
    _EncryptedParser.document = _EncryptedCOSDocument()
    monkeypatch.setattr(loader_module, "PDFParser", _EncryptedParser)

    class FailingPDDocument:
        def __init__(self, document: _EncryptedCOSDocument) -> None:
            self.document = document
            self._owns_document = True
            self._security_handler = None
            self._encryption = None

        def decrypt(self, password: str | bytes) -> None:
            raise RuntimeError(f"bad password {password!r}")

    monkeypatch.setattr(pdmodel_module, "PDDocument", FailingPDDocument)

    # Pre-built RandomAccessRead => owned=False inside Loader.
    src = RandomAccessReadBuffer(b"%PDF-1.7\n%%EOF")
    with pytest.raises(RuntimeError, match="bad password"):
        Loader.load_pdf(src, "wrong")
