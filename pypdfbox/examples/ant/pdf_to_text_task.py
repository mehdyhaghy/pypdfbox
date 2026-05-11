"""Ant task that batch-converts PDFs to text.

Ported from
``examples/src/main/java/org/apache/pdfbox/examples/ant/PDFToTextTask.java``
(lines 34-73). Apache Ant has no Python equivalent — the public surface
is preserved for parity; ``execute()`` raises ``NotImplementedError``.
"""

from __future__ import annotations

from typing import Any


class PDFToTextTask:
    """Mirror of ``org.apache.pdfbox.examples.ant.PDFToTextTask``."""

    def __init__(self) -> None:
        self._file_sets: list[Any] = []

    def add_fileset(self, file_set: Any) -> None:
        """Mirror of ``addFileset`` (line 43)."""
        self._file_sets.append(file_set)

    def execute(self) -> None:
        """Mirror of ``execute`` (line 52).

        Apache Ant has no Python equivalent — for a similar
        batch-conversion pipeline, drive
        :class:`pypdfbox.tools.ExtractText` from a Makefile / shell glob
        instead.
        """
        raise NotImplementedError("Apache Ant has no Python equivalent")
