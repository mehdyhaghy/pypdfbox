"""Port of ``org.apache.pdfbox.examples.pdmodel.EmbeddedFiles`` (lines 44-147).

Creates a PDF with an embedded text file attachment.
"""

from __future__ import annotations

import datetime as _dt
import io
import sys


class EmbeddedFiles:
    """Mirrors ``EmbeddedFiles`` (line 44)."""

    def __init__(self) -> None:
        pass

    def do_it(self, file_: str) -> None:
        """Mirrors ``doIt(String file)`` (line 60)."""
        from pypdfbox.examples.pdmodel._font_helpers import (
            make_standard14_type1_font,
        )
        from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (  # noqa: E501
            PDComplexFileSpecification,
        )
        from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import (
            PDEmbeddedFile,
        )
        from pypdfbox.pdmodel.font.standard14_fonts import FontName
        from pypdfbox.pdmodel.page_mode import PageMode
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.pdmodel.pd_document_name_dictionary import (
            PDDocumentNameDictionary,
        )
        from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
            PDEmbeddedFilesNameTreeNode,
        )
        from pypdfbox.pdmodel.pd_page import PDPage
        from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)
            font = make_standard14_type1_font(FontName.HELVETICA_BOLD)
            with PDPageContentStream(doc, page) as contents:
                contents.begin_text()
                contents.set_font(font, 12)
                contents.new_line_at_offset(100, 700)
                contents.show_text(
                    "Go to Document->File Attachments to View Embedded Files",
                )
                contents.end_text()

            # Embedded files are stored in a named tree.
            ef_tree = PDEmbeddedFilesNameTreeNode()

            # First create the file specification, which holds the embedded file.
            fs = PDComplexFileSpecification()
            # Use both methods for backwards, cross-platform, cross-language compatibility.
            fs.set_file("Test.txt")
            fs.set_file_unicode("Test.txt")

            # Create a dummy file stream — would normally be a real input stream.
            data = b"This is the contents of the embedded file"
            fake_file = io.BytesIO(data)
            ef = PDEmbeddedFile(doc, fake_file)
            ef.set_subtype("text/plain")
            ef.set_size(len(data))
            ef.set_creation_date(_dt.datetime.now())

            fs.set_embedded_file(ef)
            fs.set_embedded_file_unicode(ef)
            fs.set_file_description("Very interesting file")

            # Create a new tree node and add the embedded file.
            tree_node = PDEmbeddedFilesNameTreeNode()
            tree_node.set_names({"My first attachment": fs})
            ef_tree.set_kids([tree_node])

            # Add the tree to the document catalog.
            names = PDDocumentNameDictionary(doc.get_document_catalog())
            names.set_embedded_files(ef_tree)
            doc.get_document_catalog().set_names(names)

            # Show attachments panel in some viewers.
            doc.get_document_catalog().set_page_mode(PageMode.USE_ATTACHMENTS)

            doc.save(file_)

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 127)."""
        argv = argv if argv is not None else []
        app = EmbeddedFiles()
        if len(argv) != 1:
            app.usage()
        else:
            app.do_it(argv[0])

    def usage(self) -> None:
        sys.stderr.write("usage: EmbeddedFiles <output-file>\n")
