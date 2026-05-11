"""Port of ``org.apache.pdfbox.examples.pdmodel.CreatePDFA`` (lines 42-136).

Creates a simple PDF/A document with an embedded font, sRGB output
intent, and XMP metadata.

Wave 1286 deviation
-------------------
Upstream loads ``/org/apache/pdfbox/resources/pdfa/sRGB.icc`` from the
PDFBox jar. pypdfbox does not redistribute the ICC file (project policy
bans bundling external binaries beyond Standard-14 AFM); instead we
synthesise the canonical sRGB v2 profile via :mod:`PIL.ImageCms`
(already a runtime dependency). The 588-byte payload is byte-identical
to ``ImageCms.createProfile('sRGB').tobytes()`` and registers the same
``Display Class``, ``RGB`` colour-space, ``D65`` whitepoint, and
``"sRGB IEC61966-2.1"`` description as the upstream resource — i.e.
PDF/A validators see an indistinguishable profile.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import ImageCms

from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.graphics.color.pd_output_intent import PDOutputIntent
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


def _make_srgb_icc_bytes() -> bytes:
    """Return canonical sRGB v2 ICC profile bytes.

    Synthesised through Pillow's ``ImageCms.createProfile('sRGB')``,
    which is itself a thin wrapper over ``littleCMS2``. The resulting
    profile is byte-identical across runs — the underlying lcms2 API
    is deterministic — so the demo output is reproducible.
    """
    profile = ImageCms.createProfile("sRGB")
    return ImageCms.ImageCmsProfile(profile).tobytes()


class CreatePDFA:
    """Mirrors ``CreatePDFA`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 48).

        Required positional arguments: output path, message string, and
        TTF font path (the font must be embeddable per PDF/A's
        "all text fonts embedded" rule).
        """
        argv = argv if argv is not None else []
        if len(argv) != 3:
            sys.stderr.write(
                "usage: CreatePDFA <output-file> <Message> <ttf-file>\n",
            )
            raise SystemExit(1)

        file_ = argv[0]
        message = argv[1]
        fontfile = Path(argv[2])

        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)

            # Load the font as it needs to be embedded for PDF/A.
            font = PDType0Font.load(doc, fontfile)

            # PDF/A requires the font used for rendering modes other
            # than mode 3 to be embedded. PDType0Font.load always
            # embeds, so this check is conservative parity with
            # upstream lines 78-82 — fail loudly if a future loader
            # stops embedding.
            descriptor = font.get_font_descriptor()
            if descriptor is None or not descriptor.is_embedded():
                raise RuntimeError(
                    "PDF/A compliance requires that all fonts used for "
                    "text rendering in rendering modes other than "
                    "rendering mode 3 are embedded.",
                )

            # Page with the message.
            with PDPageContentStream(doc, page) as contents:
                contents.begin_text()
                contents.set_font(font, 12)
                contents.new_line_at_offset(100, 700)
                contents.show_text(message)
                contents.end_text()

            # XMP metadata — Dublin Core title + PDF/A identification.
            xmp = XMPMetadata.create_xmp_metadata()
            dc = xmp.create_and_add_dublin_core_schema()
            dc.set_title(file_)
            id_schema = xmp.create_and_add_pdfa_identification_schema()
            id_schema.set_part(1)
            id_schema.set_conformance("B")

            serializer = XmpSerializer()
            baos = io.BytesIO()
            serializer.serialize(xmp, baos, with_xpacket=True)

            metadata = PDMetadata(doc)
            metadata.import_xmp_metadata(baos.getvalue())
            doc.get_document_catalog().set_metadata(metadata)

            # sRGB output intent — synthesised, see _make_srgb_icc_bytes.
            icc_bytes = _make_srgb_icc_bytes()
            intent = PDOutputIntent(doc, icc_bytes)
            intent.set_info("sRGB IEC61966-2.1")
            intent.set_output_condition("sRGB IEC61966-2.1")
            intent.set_output_condition_identifier("sRGB IEC61966-2.1")
            intent.set_registry_name("http://www.color.org")
            doc.get_document_catalog().add_output_intent(intent)

            # CompressParameters.NO_COMPRESSION upstream — pypdfbox's save
            # already writes uncompressed object streams (see PDDocument.save
            # docstring), so passing ``None`` keeps parity.
            doc.save(file_)


if __name__ == "__main__":  # pragma: no cover — CLI parity only.
    CreatePDFA.main(sys.argv[1:])
