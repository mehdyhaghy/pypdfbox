"""Live PDFBox differential parity for the catalog /Metadata XMP *stream wire*.

This complements three sibling oracle surfaces that all touch the catalog
``/Metadata`` XMP packet but each from a different angle:

* ``test_metadata_oracle.py`` (``MetaProbe``) — hashes the *decoded* XMP packet.
* ``test_catalog_meta_oracle.py`` (``CatalogMetaProbe``) — presence only.
* ``test_info_xmp_oracle.py`` (``InfoXmpProbe``) — *parsed* XMP schema fields.

The uncovered facet is the **raw COSStream dictionary** that
``PDDocumentCatalog.getMetadata()`` returns: the ``/Type`` (``Metadata``) and
``/Subtype`` (``XML``) tags, and — the behaviourally load-bearing one — the
``/Filter`` chain. A document-level XMP metadata stream is, by spec
recommendation, stored *uncompressed* so a non-PDF reader can scrape the packet
without a PDF stack; PDFBox's ``PDMetadata`` writes it with **no filter by
default**. When a caller explicitly declares a filter chain (e.g.
``FlateDecode``) the stored bytes are encoded and ``exportXMPMetadata()``
decodes them back. Both paths are pinned here.

The Java side is ``oracle/probes/MetadataStreamProbe.java``: it loads a PDF and
dumps ``/Type``, ``/Subtype``, the *raw undecoded* ``/Filter`` chain, the stored
(encoded) byte length, and the decoded packet length + SHA-1. Here we build the
matching PDFs with pypdfbox, reproduce the identical dump from pypdfbox's
``PDMetadata`` read path, and assert byte-for-byte parity.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from tests.oracle.harness import requires_oracle, run_probe_text

# A realistic XMP packet: xpacket wrapper + a tiny RDF body. Large enough that
# FlateDecode actually shrinks it, so the encoded-vs-decoded length divergence
# is visible in the compressed case.
_XMP = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    b'  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    b'    <rdf:Description rdf:about=""\n'
    b'        xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
    b"      <dc:title><rdf:Alt>"
    b'<rdf:li xml:lang="x-default">pypdfbox parity</rdf:li>'
    b"</rdf:Alt></dc:title>\n"
    b"      <dc:creator><rdf:Seq>"
    b"<rdf:li>Agent G</rdf:li>"
    b"</rdf:Seq></dc:creator>\n"
    b"    </rdf:Description>\n"
    b"  </rdf:RDF>\n"
    b"</x:xmpmeta>\n"
    b'<?xpacket end="w"?>'
)


def _build(out_path: Path, *, compress: bool) -> None:
    """Build a one-page PDF whose catalog carries an XMP /Metadata stream,
    optionally FlateDecode-compressed."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        meta = PDMetadata(doc)
        if compress:
            meta.set_filters([COSName.FLATE_DECODE])
        meta.import_xmp_metadata(_XMP)
        doc.get_document_catalog().set_metadata(meta)
        doc.save(out_path)
    finally:
        doc.close()


def _filter_chain(cos) -> str:  # noqa: ANN001 - COSStream
    """Mirror MetadataStreamProbe.filterChain: the raw, undecoded /Filter as
    a US-joined name list, or the literal "none"."""
    filters = cos.get_filters_as_strings()
    if not filters:
        return "none"
    return "\x1f".join(filters)


def _py_dump(fixture: Path) -> str:
    """Reproduce the line-oriented dump MetadataStreamProbe.java emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        metadata = doc.get_document_catalog().get_metadata()
        if metadata is None:
            return "metadata NONE\n"
        cos = metadata.get_cos_object()

        lines.append(f"type={metadata.get_type() or 'null'}")
        lines.append(f"subtype={metadata.get_subtype() or 'null'}")
        lines.append(f"filter={_filter_chain(cos)}")

        with cos.create_raw_input_stream() as raw:
            raw_bytes = raw.read()
        lines.append(f"raw.len={len(raw_bytes)}")

        decoded = metadata.export_xmp_metadata()
        lines.append(f"decoded.len={len(decoded)}")
        lines.append(f"decoded.sha1={hashlib.sha1(decoded).hexdigest()}")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize("compress", [False, True], ids=["uncompressed", "flate"])
def test_metadata_stream_matches_pdfbox(tmp_path: Path, compress: bool) -> None:
    """pypdfbox-built XMP /Metadata stream (default-uncompressed and
    FlateDecode-compressed): /Type, /Subtype, raw /Filter chain, stored byte
    length, and decoded packet length + SHA-1 all compared against PDFBox's
    PDMetadata read path."""
    pdf = tmp_path / f"metadata_stream_{'flate' if compress else 'plain'}.pdf"
    _build(pdf, compress=compress)
    java = run_probe_text("MetadataStreamProbe", str(pdf))
    py = _py_dump(pdf)
    assert py == java, (
        "catalog /Metadata stream wire diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
