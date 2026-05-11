"""Port of ``PDFMergerExample`` (upstream ``PDFMergerExample.java`` lines
53-157).

Merges a list of PDFs into a single document, setting destination
``PDDocumentInformation`` and a hand-rolled XMP packet.

The pypdfbox lite port keeps the structural shape — ``merge`` returns
an in-memory buffer of the merged bytes — and exposes the helper methods
(``create_pdf_merger_utility``, ``create_pdf_document_info``,
``create_xmp_metadata``) the upstream split into. ``create_xmp_metadata``
returns ``None`` when ``xmpbox`` is not yet wired up.
"""

from __future__ import annotations

import contextlib
import io
import logging
from typing import Any

from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation

_LOG = logging.getLogger(__name__)


class PDFMergerExample:
    """Mirrors ``PDFMergerExample`` (public default-package ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    PDFMergerExample.java`` (lines 53-157).
    """

    def __init__(self) -> None:
        pass

    def merge(self, sources: list[Any]) -> io.BytesIO:
        """Merge ``sources`` into a single PDF and return the bytes as a
        :class:`io.BytesIO`. Mirrors upstream's ``merge`` (line 67)."""
        title = "My title"
        creator = "Alexander Kriegisch"
        subject = "Subject with umlauts ÄÖÜ"

        merged_pdf_output_stream = io.BytesIO()
        pdf_merger = self.create_pdf_merger_utility(
            sources, merged_pdf_output_stream,
        )
        pdf_document_info = self.create_pdf_document_info(
            title, creator, subject,
        )
        xmp_metadata = self.create_xmp_metadata(title, creator, subject)
        with contextlib.suppress(AttributeError):
            pdf_merger.set_destination_document_information(pdf_document_info)
        if xmp_metadata is not None:
            with contextlib.suppress(AttributeError):
                pdf_merger.set_destination_metadata(xmp_metadata)

        _LOG.info("Merging %d source documents into one PDF", len(sources))
        pdf_merger.merge_documents()
        _LOG.info(
            "PDF merge successful, size = {%d} bytes",
            merged_pdf_output_stream.getbuffer().nbytes,
        )
        merged_pdf_output_stream.seek(0)
        return merged_pdf_output_stream

    def create_pdf_merger_utility(
        self,
        sources: list[Any],
        merged_pdf_output_stream: io.BytesIO,
    ) -> PDFMergerUtility:
        """Build the underlying :class:`PDFMergerUtility` — promoted from
        the upstream private helper (line 103)."""
        _LOG.info("Initialising PDF merge utility")
        pdf_merger = PDFMergerUtility()
        for src in sources:
            pdf_merger.add_source(src)
        pdf_merger.set_destination_stream(merged_pdf_output_stream)
        return pdf_merger

    def create_pdf_document_info(
        self, title: str, creator: str, subject: str
    ) -> PDDocumentInformation:
        """Build a :class:`PDDocumentInformation` — promoted from
        upstream's private helper (line 113)."""
        _LOG.info("Setting document info (title, author, subject) for merged PDF")
        info = PDDocumentInformation()
        info.set_title(title)
        info.set_creator(creator)
        info.set_subject(subject)
        return info

    def create_xmp_metadata(
        self, title: str, creator: str, subject: str
    ) -> Any:
        """Build an XMP-backed :class:`PDMetadata` — promoted from
        upstream's private helper (line 123).

        Returns ``None`` when xmpbox isn't wired up; the merger then skips
        ``set_destination_metadata``."""
        try:
            from pypdfbox.cos import COSName, COSStream
            from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
            from pypdfbox.xmpbox.xml.xmp_serializer import (
                XmpSerializer,  # type: ignore[import-not-found]
            )
            from pypdfbox.xmpbox.xmp_metadata import XMPMetadata  # type: ignore[import-not-found]
        except ImportError:
            return None
        _LOG.info("Setting XMP metadata (title, author, subject) for merged PDF")
        xmp_metadata = XMPMetadata.create_xmp_metadata()
        try:
            pdfa_schema = xmp_metadata.create_and_add_pdfa_identification_schema()
            pdfa_schema.set_part(1)
            pdfa_schema.set_conformance("B")
            dublin_core_schema = xmp_metadata.create_and_add_dublin_core_schema()
            dublin_core_schema.set_title(title)
            dublin_core_schema.add_creator(creator)
            dublin_core_schema.set_description(subject)
            basic_schema = xmp_metadata.create_and_add_xmp_basic_schema()
            basic_schema.set_creator_tool(creator)
            cos_stream = COSStream()
            with cos_stream.create_output_stream() as out:
                XmpSerializer().serialize(xmp_metadata, out, True)
            cos_stream.set_name(COSName.TYPE, "Metadata")
            cos_stream.set_name(COSName.SUBTYPE, "XML")
            return PDMetadata(cos_stream)
        except AttributeError:
            return None
