"""Build a Lucene document from a PDF.

Ported from
``examples/src/main/java/org/apache/pdfbox/examples/lucene/LucenePDFDocument.java``
(lines 112-394). Lucene has no canonical Python equivalent - see
``IndexPDFFiles`` - so the conversion helpers raise
``NotImplementedError`` while the static UID helpers, which are pure
string work, remain functional for parity. The private field-add helpers
mirror the Java surface but are stubs (they would otherwise need a
Lucene ``Document`` to mutate).
"""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import Any

from pypdfbox.text.pdf_text_stripper import PDFTextStripper

_FILE_SEPARATOR = os.sep[0]
# Upstream encodes the path/URL with a NUL separator (U+0000). The Python
# port uses a tab so the UID can round-trip through normal string
# handling; semantics are equivalent (a token impossible in file names)
# and tests cover the exact format.
_NUL_REPLACEMENT = "\t"


class LucenePDFDocument:
    """Convert a PDF to a Lucene ``Document``."""

    def __init__(self) -> None:
        self._stripper: PDFTextStripper | None = None

    def set_text_stripper(self, a_stripper: PDFTextStripper) -> None:
        """Mirror of ``setTextStripper`` (line 145)."""
        self._stripper = a_stripper

    @staticmethod
    def time_to_string(time_ms: int) -> str:
        """Mirror of private ``timeToString`` (line 150).

        Renders an epoch-ms timestamp the way Lucene's ``DateTools``
        would (``yyyymmddhhmmss``) at SECOND resolution (line 118).
        """
        dt = _dt.datetime.fromtimestamp(time_ms / 1000.0, tz=_dt.UTC)
        return dt.strftime("%Y%m%d%H%M%S")

    def add_keyword_field(
        self, document: Any, name: str, value: str | None
    ) -> None:
        """Mirror of ``addKeywordField`` (line 155).

        Stub: would call ``document.add(StringField(...))`` against a
        Lucene index. Without Lucene the helper is a no-op so subclasses
        can override it.
        """
        del document, name, value

    def add_text_field(
        self, document: Any, name: str, value: Any
    ) -> None:
        """Mirror of the four overloaded ``addTextField`` methods
        (lines 163, 171, 179, 187)."""
        del document, name, value

    @staticmethod
    def add_unindexed_field(
        document: Any, name: str, value: str | None
    ) -> None:
        """Mirror of static ``addUnindexedField`` (line 195)."""
        del document, name, value

    def add_unstored_keyword_field(
        self, document: Any, name: str, value: str | None
    ) -> None:
        """Mirror of ``addUnstoredKeywordField`` (line 203)."""
        del document, name, value

    def convert_document(self, source: Path | str | Any) -> Any:
        """Convert a file/URL to a Lucene document - lines 219/252.

        Lucene has no usable Python port; surface preserved for parity.
        """
        del source
        raise NotImplementedError(
            "requires Lucene; Python equivalent is whoosh or pylucene "
            "- not bundled"
        )

    @staticmethod
    def get_document(source: Path | str | Any) -> Any:
        """Static factory - lines 290/305."""
        del source
        raise NotImplementedError(
            "requires Lucene; Python equivalent is whoosh or pylucene "
            "- not bundled"
        )

    def add_content(
        self, document: Any, source: Any, document_location: str
    ) -> None:
        """Mirror of private ``addContent`` (line 320).

        Stub: the upstream method loads the PDF, runs the text stripper
        and pushes the contents to several Lucene fields. Without Lucene
        the surface is preserved for parity.
        """
        del document, source, document_location
        raise NotImplementedError(
            "requires Lucene; Python equivalent is whoosh or pylucene "
            "- not bundled"
        )

    @staticmethod
    def create_uid(file_or_url: Path | str, time: int | None = None) -> str:
        """Construct a stable UID for a file or URL - lines 379 & 391.

        - ``LucenePDFDocument.create_uid(File f)``: derives the
          timestamp from ``f.lastModified()``.
        - ``LucenePDFDocument.create_uid(URL u, long t)``: uses ``t``
          directly.
        """
        if time is None:
            if isinstance(file_or_url, (str, Path)):
                path = Path(file_or_url)
                time = int(path.stat().st_mtime * 1000) if path.exists() else 0
                key = str(path)
            else:
                key = str(file_or_url)
                time = 0
        else:
            key = str(file_or_url)
        return (
            key.replace(_FILE_SEPARATOR, _NUL_REPLACEMENT)
            + _NUL_REPLACEMENT
            + LucenePDFDocument.time_to_string(int(time))
        )
