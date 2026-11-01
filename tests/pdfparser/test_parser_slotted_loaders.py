"""``PDFParser`` attaches one small slotted loader per ``COSObject``.

A closure would cost a function, a cell and (on Python 3.14+) a generated
``__annotate__`` function per indirect object, all tracked by the cyclic
garbage collector for the life of the document.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary
from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _saved_pdf(compress: bool) -> bytes:
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.add_page(PDPage())
        out = io.BytesIO()
        if compress:
            doc.save(out, CompressParameters.DEFAULT_COMPRESSION)
        else:
            doc.save(out, CompressParameters.NO_COMPRESSION)
        return out.getvalue()


def test_parser_loaders_are_slotted_callables() -> None:
    for compress in (False, True):
        with PDDocument.load(_saved_pdf(compress)) as doc:
            cos_doc = doc.get_document()
            pending = [o for o in cos_doc.get_objects() if o.has_loader()]
            assert pending
            for obj in pending:
                loader = obj._loader
                assert not hasattr(loader, "__closure__")
                assert not hasattr(loader, "__dict__")
            # every lazy object still resolves through its loader
            for obj in pending:
                obj.get_object()
                assert not obj.has_loader()
            assert doc.get_number_of_pages() == 2
            page = doc.get_page(1).get_cos_object()
            assert isinstance(page, COSDictionary)
