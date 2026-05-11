"""Port of ``org.apache.pdfbox.examples.pdmodel.PrintDocumentMetaData`` (lines 37-117).

Prints a document's metadata to stdout.
"""

from __future__ import annotations

import sys
from datetime import datetime

from pypdfbox.pdmodel.pd_document import PDDocument


class PrintDocumentMetaData:
    """Mirrors ``PrintDocumentMetaData`` (line 37)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 46)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            PrintDocumentMetaData.usage()
            return
        with PDDocument.load(argv[0]) as document:
            meta = PrintDocumentMetaData()
            meta.print_metadata(document)

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (line 117)."""
        sys.stderr.write(
            "Usage: PrintDocumentMetaData <input-pdf>\n",
        )

    def print_metadata(self, document: PDDocument) -> None:
        """Mirrors ``printMetadata(PDDocument document)`` (line 77)."""
        info = document.get_document_information()
        cat = document.get_document_catalog()
        metadata = cat.get_metadata()
        sys.stdout.write(f"Page Count={document.get_number_of_pages()}\n")
        sys.stdout.write(f"Title={info.get_title()}\n")
        sys.stdout.write(f"Author={info.get_author()}\n")
        sys.stdout.write(f"Subject={info.get_subject()}\n")
        sys.stdout.write(f"Keywords={info.get_keywords()}\n")
        sys.stdout.write(f"Creator={info.get_creator()}\n")
        sys.stdout.write(f"Producer={info.get_producer()}\n")
        sys.stdout.write(
            f"Creation Date={self.format_date(info.get_creation_date())}\n",
        )
        sys.stdout.write(
            f"Modification Date={self.format_date(info.get_modification_date())}\n",
        )
        sys.stdout.write(f"Trapped={info.get_trapped()}\n")
        if metadata is not None:
            bytes_ = metadata.to_byte_array()
            string = bytes_.decode("iso-8859-1")
            sys.stdout.write(f"Metadata={string}\n")

    @staticmethod
    def format_date(date: datetime | None) -> str | None:
        """Mirrors ``formatDate(Calendar)`` (line 106)."""
        if date is None:
            return None
        # Python equivalent of ``SimpleDateFormat`` default locale output.
        return date.strftime("%m/%d/%y %I:%M %p")
