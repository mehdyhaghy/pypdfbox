"""An unreachable, unclosed COSDocument does not close buffers others use.

Upstream has no finalizer: objects that outlive an unclosed document keep
working. pypdfbox's finalizer only logs the missing close.
"""

from __future__ import annotations

import gc
import io

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

_CONTENTS = COSName.get_pdf_name("Contents")


def _read(stream: COSStream) -> bytes:
    with stream.create_input_stream() as data:
        return data.read()


def test_imported_page_outlives_dropped_destination() -> None:
    src = PDDocument()
    page = PDPage()
    original = COSStream()
    with original.create_output_stream() as out:
        out.write(b"0 0 m")
    page.get_cos_object().set_item(_CONTENTS, original)
    src.add_page(page)

    imported = PDDocument().import_page(page)
    gc.collect()

    contents = imported.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSStream)
    assert _read(contents) == b"0 0 m"
    src.close()


def test_page_of_dropped_loaded_document_still_resolves_lazily() -> None:
    with PDDocument() as doc:
        for _ in range(3):
            doc.add_page(PDPage())
        buf = io.BytesIO()
        doc.save(buf)

    page = PDDocument.load(buf.getvalue()).get_page(2)
    gc.collect()
    # resolving the media box walks lazily loaded objects of the source
    assert page.get_media_box().get_width() > 0
