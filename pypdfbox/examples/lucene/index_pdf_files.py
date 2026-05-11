"""Index a directory of PDFs into a Lucene index.

Ported from
``examples/src/main/java/org/apache/pdfbox/examples/lucene/IndexPDFFiles.java``
(lines 46-234). Apache Lucene has no canonical Python equivalent —
``pylucene`` requires JNI and ``whoosh`` is unmaintained — so
``main()`` raises ``NotImplementedError``. The public surface is
preserved for parity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class IndexPDFFiles:
    """Command-line tool to populate a Lucene index from PDFs."""

    def __init__(self) -> None:
        # Upstream class has a private no-arg constructor (line 49).
        raise RuntimeError(
            "IndexPDFFiles is a utility class with only static helpers"
        )

    @staticmethod
    def main(args: list[str] | None = None) -> None:
        """Mirror of ``IndexPDFFiles.java:59``.

        Lucene has no usable Python port; surface preserved for parity.
        """
        del args
        raise NotImplementedError(
            "requires Lucene; Python equivalent is whoosh or pylucene "
            "— not bundled"
        )

    @staticmethod
    def index_docs(writer: Any, file: str | Path) -> None:
        """Recurse over a directory and call ``writer.addDocument``.

        Mirror of ``IndexPDFFiles.java:164``. Without a backing index
        writer this raises ``NotImplementedError``.
        """
        del writer, file
        raise NotImplementedError(
            "requires Lucene; Python equivalent is whoosh or pylucene "
            "— not bundled"
        )
