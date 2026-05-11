"""Ant task that batch-converts PDFs to text.

Ported from
``examples/src/main/java/org/apache/pdfbox/examples/ant/PDFToTextTask.java``
(lines 34-73).

Apache Ant has no Python equivalent — the upstream task is invoked by
the Ant build engine, which scans a ``<fileset>`` and feeds each match
to ``ExtractText``. The pypdfbox port keeps the class self-contained:
populate ``pdf_file`` / ``text_file`` / ``password`` (either directly or
via the Ant-style ``set_*`` accessors) and call :meth:`execute` from
Python. Bulk conversions can iterate ``execute`` over a glob.

The original ``add_fileset`` shim is preserved so transcoded Ant
build files can still reach the task surface — the file-set entries are
expanded inside :meth:`execute` when present.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PDFToTextTask:
    """Mirror of ``org.apache.pdfbox.examples.ant.PDFToTextTask``."""

    def __init__(self) -> None:
        self._file_sets: list[Any] = []
        self._pdf_file: Path | None = None
        self._text_file: Path | None = None
        self._password: str | None = None

    def add_fileset(self, file_set: Any) -> None:
        """Mirror of ``addFileset`` (line 43)."""
        self._file_sets.append(file_set)

    # --- Ant-style attribute setters ----------------------------------
    def set_pdf_file(self, path: str | Path) -> None:
        """Mirror of Ant ``setPdfFile`` — selects the source PDF."""
        self._pdf_file = Path(path)

    def set_text_file(self, path: str | Path) -> None:
        """Mirror of Ant ``setTextFile`` — selects the output text file."""
        self._text_file = Path(path)

    def set_password(self, password: str | None) -> None:
        """Mirror of Ant ``setPassword`` — supplies a decryption password."""
        self._password = password

    @property
    def pdf_file(self) -> Path | None:
        return self._pdf_file

    @property
    def text_file(self) -> Path | None:
        return self._text_file

    @property
    def password(self) -> str | None:
        return self._password

    # --- execution -----------------------------------------------------
    def execute(self) -> None:
        """Convert ``pdf_file`` (and any ``add_fileset`` entries) to text.

        Mirrors upstream ``execute`` (line 52): open each input PDF,
        run :class:`pypdfbox.text.PDFTextStripper`, and write the
        extracted text alongside (``foo.pdf`` → ``foo.txt``) — except
        that when ``text_file`` is set on the single-file path it wins
        over the derived name.

        File-set scanning is best-effort: each entry is asked for
        :meth:`get_included_files` (matching Ant's ``DirectoryScanner``),
        falling back to iterating the object directly. Any non-``.pdf``
        match is skipped silently, matching upstream.
        """
        # Local import to defer the heavy pdmodel/text pull-in until the
        # task actually runs; keeps ``PDFToTextTask()`` cheap.
        from pypdfbox.loader import Loader  # noqa: PLC0415
        from pypdfbox.pdmodel import PDDocument  # noqa: PLC0415
        from pypdfbox.text import PDFTextStripper  # noqa: PLC0415

        logger.info("PDFToTextTask executing")

        targets: list[tuple[Path, Path]] = []

        if self._pdf_file is not None:
            out = self._text_file or self._derive_text_path(self._pdf_file)
            targets.append((self._pdf_file, out))

        for file_set in self._file_sets:
            for pdf in self._iter_fileset(file_set):
                if pdf.suffix.lower() != ".pdf":
                    continue
                targets.append((pdf, self._derive_text_path(pdf)))

        for pdf_path, text_path in targets:
            logger.info("processing: %s", pdf_path)
            cos_doc = Loader.load_pdf(pdf_path, self._password or "")
            document = PDDocument(cos_doc)
            try:
                stripper = PDFTextStripper()
                with text_path.open("w", encoding="utf-8") as out_handle:
                    stripper.write_text(document, out_handle)
            finally:
                document.close()

    # --- internals -----------------------------------------------------
    @staticmethod
    def _derive_text_path(pdf_path: Path) -> Path:
        """Replicate upstream's ``foo.pdf`` → ``foo.txt`` naming rule."""
        return pdf_path.with_suffix(".txt")

    @staticmethod
    def _iter_fileset(file_set: Any) -> list[Path]:
        """Best-effort expansion of an Ant-style file-set entry.

        Supports three shapes:

        * a ``DirectoryScanner``-alike with ``get_included_files()`` /
          ``get_basedir()`` (mirrors upstream's actual API);
        * any iterable of path-like entries;
        * a single path-like value.
        """
        if hasattr(file_set, "get_included_files"):
            base = Path(getattr(file_set, "get_basedir", lambda: ".")())
            return [base / name for name in file_set.get_included_files()]
        if isinstance(file_set, (str, Path)):
            return [Path(file_set)]
        try:
            return [Path(item) for item in file_set]
        except TypeError:
            return []
