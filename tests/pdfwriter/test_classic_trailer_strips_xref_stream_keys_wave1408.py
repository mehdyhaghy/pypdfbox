"""Wave 1408 regression: a classic ``trailer`` block must not carry the
cross-reference *stream* dictionary's own keys.

When a source document uses an xref stream (PDF 1.5+), its trailer
COSDictionary IS that stream's dictionary and still carries the stream-only
keys ``/Type /XRef``, ``/W``, ``/Index``, ``/Filter``, ``/Length``,
``/DecodeParms``. pypdfbox's default full save emits a classic ``xref`` table
followed by a ``trailer`` keyword block, so before this fix those keys leaked
into the classic trailer — a structurally malformed file (PDF 32000-1 §7.5.5
confines the permitted trailer entries; §7.5.8 confines the stream-only keys
to the xref *stream* dictionary). qpdf recovers via the table, but strict
readers can choke and the bytes are non-conformant.

``COSWriter._do_write_trailer`` now strips those keys. This test is
oracle-free so it gates in CI even without the live PDFBox jar / qpdf.
"""

from __future__ import annotations

import io
import re

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdfwriter.cos_writer import COSWriter


def _doc_with_polluted_trailer() -> COSDocument:
    """A COSDocument whose trailer carries leftover xref-stream-only keys —
    exactly what the parser leaves behind when the source's cross-reference
    section was a ``/Type /XRef`` stream (its dictionary doubles as the
    trailer)."""
    doc = COSDocument()
    doc.set_version(1.6)

    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog_obj = COSObject(1, 0, resolved=catalog)

    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    # Pollute with the xref-stream-only keys.
    trailer.set_item(COSName.TYPE, COSName.get_pdf_name("XRef"))  # type: ignore[attr-defined]
    trailer.set_item(COSName.W, COSArray())  # type: ignore[attr-defined]
    trailer.set_item(COSName.INDEX, COSArray())  # type: ignore[attr-defined]
    trailer.set_item(COSName.FILTER, COSName.get_pdf_name("FlateDecode"))  # type: ignore[attr-defined]
    trailer.set_int(COSName.LENGTH, 79)  # type: ignore[attr-defined]
    trailer.set_item(  # type: ignore[attr-defined]
        COSName.get_pdf_name("DecodeParms"), COSDictionary()
    )
    doc.set_trailer(trailer)
    return doc


def test_classic_trailer_omits_xref_stream_keys() -> None:
    doc = _doc_with_polluted_trailer()
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        writer.write(doc)
    out = sink.getvalue()

    # Default full-save strategy is a classic ``xref`` table.
    assert re.search(rb"(?:^|\r?\n)xref\r?\n\d+ \d+\r?\n", out) is not None

    # Isolate the ``trailer`` dictionary block and assert the stream-only keys
    # were stripped.
    m = re.search(rb"\btrailer\b\s*<<(.*?)>>", out, re.DOTALL)
    assert m is not None, "no trailer dictionary found"
    trailer_blob = m.group(1)
    for forbidden in (
        b"/Type",
        b"/XRef",
        b"/W",
        b"/Index",
        b"/Filter",
        b"/Length",
        b"/DecodeParms",
    ):
        assert forbidden not in trailer_blob, (
            f"classic trailer leaked xref-stream key {forbidden!r}: {trailer_blob!r}"
        )

    # The legitimate trailer entries survive.
    assert b"/Root" in trailer_blob
    assert b"/Size" in trailer_blob
