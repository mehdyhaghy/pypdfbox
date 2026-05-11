"""Port of ``org.apache.pdfbox.examples.pdmodel.CreatePortableCollection`` (lines 49-229).

Creates a portable collection ("PDF Package") with two embedded files.

Wave 1286 deviation
-------------------
Upstream relies on the ``COSName.COLLECTION_*`` static constants
(``COLLECTION``, ``COLLECTION_SCHEMA``, ``COLLECTION_SORT``,
``COLLECTION_FIELD``, ``COLLECTION_ITEM``, ``CI``, ``SCHEMA``, ``SORT``,
``VIEW``, ``O``, ``N``, ``S``). pypdfbox only exposes a subset of those
as class attributes today, so the names are built via
:meth:`COSName.get_pdf_name` at module load — observable PDF output is
byte-identical.
"""

from __future__ import annotations

import datetime as _dt
import io
import sys

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
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

# Collection-schema names looked up once at module load (cheap, deduped
# inside :class:`COSName`).
_COLLECTION = COSName.get_pdf_name("Collection")
_COLLECTION_SCHEMA = COSName.get_pdf_name("CollectionSchema")
_COLLECTION_SORT = COSName.get_pdf_name("CollectionSort")
_COLLECTION_FIELD = COSName.get_pdf_name("CollectionField")
_COLLECTION_ITEM = COSName.get_pdf_name("CollectionItem")
_CI = COSName.get_pdf_name("CI")
_SCHEMA = COSName.get_pdf_name("Schema")
_SORT = COSName.get_pdf_name("Sort")
_VIEW = COSName.get_pdf_name("View")
_O = COSName.get_pdf_name("O")
_N = COSName.get_pdf_name("N")
_S_NAME = COSName.get_pdf_name("S")


def _make_collection_field(
    subtype: COSName, header: str, order: int,
) -> COSDictionary:
    """Build a single ``/CollectionField`` dictionary entry.

    Mirrors upstream lines 159-176 — each field declares a header string
    and an explicit screen-order integer.
    """
    field = COSDictionary()
    field.set_item(COSName.TYPE, _COLLECTION_FIELD)  # type: ignore[attr-defined]
    field.set_item(COSName.SUBTYPE, subtype)  # type: ignore[attr-defined]
    field.set_string(_N, header)
    field.set_int(_O, order)
    return field


class CreatePortableCollection:
    """Mirrors ``CreatePortableCollection`` (line 49)."""

    def __init__(self) -> None:
        pass

    def do_it(self, file_: str) -> None:
        """Mirrors ``doIt(String file)`` (line 66).

        Builds a one-page PDF carrying two embedded files exposed
        through a portable-collection schema (``/Collection``). The
        schema declares three fields (description, name, size) and
        sorts ascending on field two — byte-identical to upstream lines
        146-196.
        """
        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)

            with PDPageContentStream(doc, page) as content_stream:
                content_stream.begin_text()
                content_stream.set_font(
                    make_standard14_type1_font(FontName.HELVETICA), 12,
                )
                content_stream.new_line_at_offset(100, 700)
                content_stream.show_text("Example of a portable collection")
                content_stream.end_text()

            # Embedded files are stored in a named tree (upstream line 83).
            ef_tree = PDEmbeddedFilesNameTreeNode()

            # File spec #1 (upstream lines 86-103).
            fs1 = PDComplexFileSpecification()
            fs1.set_file("Test1.txt")
            fs1.set_file_unicode("Test1.txt")
            data1 = b"This is the contents of the first embedded file"
            ef1 = PDEmbeddedFile(
                doc, io.BytesIO(data1), COSName.FLATE_DECODE,  # type: ignore[attr-defined]
            )
            ef1.set_subtype("text/plain")
            ef1.set_size(len(data1))
            ef1.set_creation_date(_dt.datetime.now(_dt.UTC))
            fs1.set_embedded_file(ef1)
            fs1.set_embedded_file_unicode(ef1)
            fs1.set_file_description("The first file")

            # File spec #2 (upstream lines 106-123).
            fs2 = PDComplexFileSpecification()
            fs2.set_file("Test2.txt")
            fs2.set_file_unicode("Test2.txt")
            data2 = b"This is the contents of the second embedded file"
            ef2 = PDEmbeddedFile(
                doc, io.BytesIO(data2), COSName.FLATE_DECODE,  # type: ignore[attr-defined]
            )
            ef2.set_subtype("text/plain")
            ef2.set_size(len(data2))
            ef2.set_creation_date(_dt.datetime.now(_dt.UTC))
            fs2.set_embedded_file(ef2)
            fs2.set_embedded_file_unicode(ef2)
            fs2.set_file_description("The second file")

            # Build the name-tree leaf node (upstream lines 125-135).
            tree_node = PDEmbeddedFilesNameTreeNode()
            tree_node.set_names({"Attachment 1": fs1, "Attachment 2": fs2})
            ef_tree.set_kids([tree_node])

            names = PDDocumentNameDictionary(doc.get_document_catalog())
            names.set_embedded_files(ef_tree)
            doc.get_document_catalog().set_names(names)

            # Show attachments panel in supporting viewers.
            doc.get_document_catalog().set_page_mode(PageMode.USE_ATTACHMENTS)

            # --- collection dictionary (upstream lines 146-178) ---
            collection_dic = COSDictionary()
            schema_dict = COSDictionary()
            schema_dict.set_item(COSName.TYPE, _COLLECTION_SCHEMA)  # type: ignore[attr-defined]

            sort_dic = COSDictionary()
            sort_dic.set_item(COSName.TYPE, _COLLECTION_SORT)  # type: ignore[attr-defined]
            sort_dic.set_string(COSName.A, "true")  # type: ignore[attr-defined]  # ascending sort
            sort_dic.set_item(
                _S_NAME, COSName.get_pdf_name("fieldtwo"),
            )

            collection_dic.set_item(COSName.TYPE, _COLLECTION)  # type: ignore[attr-defined]
            collection_dic.set_item(_SCHEMA, schema_dict)
            collection_dic.set_item(_SORT, sort_dic)
            collection_dic.set_item(_VIEW, COSName.D)  # type: ignore[attr-defined]  # Details mode

            # Three fields: description (text), name (text), size (number).
            field_dict1 = _make_collection_field(
                COSName.get_pdf_name("S"),
                "field header one (description)",
                1,
            )
            field_dict2 = _make_collection_field(
                COSName.get_pdf_name("S"),
                "field header two (name)",
                2,
            )
            field_dict3 = _make_collection_field(
                COSName.get_pdf_name("N"),
                "field header three (size)",
                3,
            )
            schema_dict.set_item("fieldone", field_dict1)
            schema_dict.set_item("fieldtwo", field_dict2)
            schema_dict.set_item("fieldthree", field_dict3)

            doc.get_document_catalog().get_cos_object().set_item(
                _COLLECTION, collection_dic,
            )
            doc.get_document_catalog().set_version("1.7")

            # Per-file collection-item dictionaries (upstream lines 181-196).
            ci_dict1 = COSDictionary()
            ci_dict1.set_item(COSName.TYPE, _COLLECTION_ITEM)  # type: ignore[attr-defined]
            ci_dict1.set_string("fieldone", fs1.get_file_description() or "")
            ci_dict1.set_string("fieldtwo", fs1.get_file() or "")
            embedded1 = fs1.get_embedded_file()
            ci_dict1.set_int(
                "fieldthree", embedded1.get_size() if embedded1 else 0,
            )
            fs1.get_cos_object().set_item(_CI, ci_dict1)

            ci_dict2 = COSDictionary()
            ci_dict2.set_item(COSName.TYPE, _COLLECTION_ITEM)  # type: ignore[attr-defined]
            ci_dict2.set_string("fieldone", fs2.get_file_description() or "")
            ci_dict2.set_string("fieldtwo", fs2.get_file() or "")
            embedded2 = fs2.get_embedded_file()
            ci_dict2.set_int(
                "fieldthree", embedded2.get_size() if embedded2 else 0,
            )
            fs2.get_cos_object().set_item(_CI, ci_dict2)

            doc.save(file_)

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 209)."""
        argv = argv if argv is not None else []
        app = CreatePortableCollection()
        if len(argv) != 1:
            app.usage()
        else:
            app.do_it(argv[0])

    def usage(self) -> None:
        sys.stderr.write(
            "usage: CreatePortableCollection <output-file>\n",
        )
