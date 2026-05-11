"""Port of ``org.apache.pdfbox.examples.pdmodel.ExtractMetadata`` (lines 43-201).

Pretty-prints a document's XMP metadata to stdout.
"""

from __future__ import annotations

import sys
from typing import Any


class ExtractMetadata:
    """Mirrors ``ExtractMetadata`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 59)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            ExtractMetadata.usage()
            raise SystemExit(1)
        # TODO: XMP schema accessors (DublinCoreSchema, AdobePDFSchema,
        # XMPBasicSchema) need to be exposed via pypdfbox.xmpbox to back this
        # example.
        raise NotImplementedError(
            "ExtractMetadata awaits xmpbox schema accessors.",
        )

    @staticmethod
    def show_xmp_basic_schema(metadata: Any) -> None:
        """Mirrors ``showXMPBasicSchema(XMPMetadata)`` (line 103)."""
        basic = getattr(metadata, "get_xmp_basic_schema", lambda: None)()
        if basic is not None:
            ExtractMetadata.display("Create Date:", basic.get_create_date())
            ExtractMetadata.display("Modify Date:", basic.get_modify_date())
            ExtractMetadata.display("Creator Tool:", basic.get_creator_tool())

    @staticmethod
    def show_adobe_pdf_schema(metadata: Any) -> None:
        """Mirrors ``showAdobePDFSchema(XMPMetadata)`` (line 114)."""
        pdf = getattr(metadata, "get_adobe_pdf_schema", lambda: None)()
        if pdf is not None:
            ExtractMetadata.display("Keywords:", pdf.get_keywords())
            ExtractMetadata.display("PDF Version:", pdf.get_pdf_version())
            ExtractMetadata.display("PDF Producer:", pdf.get_producer())

    @staticmethod
    def show_dublin_core_schema(metadata: Any) -> None:
        """Mirrors ``showDublinCoreSchema(XMPMetadata)`` (line 125)."""
        dc = getattr(metadata, "get_dublin_core_schema", lambda: None)()
        if dc is not None:
            ExtractMetadata.display("Title:", dc.get_title())
            ExtractMetadata.display("Description:", dc.get_description())
            ExtractMetadata.list_string("Creators: ", dc.get_creators())
            ExtractMetadata.list_calendar("Dates:", dc.get_dates())
            ExtractMetadata.list_string("Subjects:", dc.get_subjects())

    @staticmethod
    def show_document_information(information: Any) -> None:
        """Mirrors ``showDocumentInformation(PDDocumentInformation)`` (line 138)."""
        ExtractMetadata.display("Title:", information.get_title())
        ExtractMetadata.display("Subject:", information.get_subject())
        ExtractMetadata.display("Author:", information.get_author())
        ExtractMetadata.display("Creator:", information.get_creator())
        ExtractMetadata.display("Producer:", information.get_producer())

    @staticmethod
    def list_string(title: str, items: list[str] | None) -> None:
        """Mirrors ``listString(String, List<String>)`` (line 147)."""
        if items is None:
            return
        print(title)
        for s in items:
            print("  " + s)

    @staticmethod
    def list_calendar(title: str, items: list[Any] | None) -> None:
        """Mirrors ``listCalendar(String, List<Calendar>)`` (line 160)."""
        if items is None:
            return
        print(title)
        for cal in items:
            print("  " + ExtractMetadata.format(cal))

    @staticmethod
    def format(value: Any) -> str:
        """Mirrors ``format(Object)`` (line 173)."""
        import datetime

        if isinstance(value, (datetime.datetime, datetime.date)):
            return value.strftime("%b %d, %Y")
        return str(value)

    @staticmethod
    def display(title: str, value: Any) -> None:
        """Mirrors ``display(String, Object)`` (line 186)."""
        if value is not None:
            print(title + " " + ExtractMetadata.format(value))

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (line 197)."""
        sys.stderr.write("Usage: ExtractMetadata <input-pdf>\n")
