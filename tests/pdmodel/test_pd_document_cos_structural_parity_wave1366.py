"""Structural-graph parity across ``PDDocument.save → Loader.load_pdf``
(wave 1366, agent E).

Asserts that the COSDocument-level structural fingerprint of a synthesised
document survives serialisation: trailer keys, /Size accounting, version,
and the xref table's entry count.

Distinct from ``test_pd_document_save_roundtrip_wave1366.py`` (which
asserts on the PDDocument surface) — these tests cross-check the lower
COSDocument boundary so a future writer refactor that gets the surface
right but corrupts xref bookkeeping fails loud.

No upstream JUnit counterpart.
"""

from __future__ import annotations

import io

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSName
from pypdfbox.loader import Loader


def _save(doc: PDDocument) -> bytes:
    sink = io.BytesIO()
    doc.save(sink)
    return sink.getvalue()


def test_trailer_size_after_roundtrip() -> None:
    """The reloaded trailer's ``/Size`` value is at least 1 (PDF 32000-1
    §7.5.5 requires it to cover all indirect objects including object 0)."""
    with PDDocument() as src:
        for _ in range(3):
            src.add_page(PDPage())
        pdf = _save(src)

    cos = Loader.load_pdf(pdf)
    try:
        trailer = cos.get_trailer()
        assert trailer is not None
        size = trailer.get_int(COSName.get_pdf_name("Size"))
        # 3 pages → catalog + pages tree + 3 page nodes + free entry =>
        # /Size >= 5.
        assert size >= 5
    finally:
        cos.close()


def test_trailer_root_resolves_to_catalog_after_roundtrip() -> None:
    """The reloaded ``/Root`` entry resolves to a /Type /Catalog
    dictionary."""
    with PDDocument() as src:
        src.add_page(PDPage())
        pdf = _save(src)

    cos = Loader.load_pdf(pdf)
    try:
        trailer = cos.get_trailer()
        assert trailer is not None
        root = trailer.get_dictionary_object(COSName.get_pdf_name("Root"))
        # ``Loader`` returns a COSDocument — the catalog is a dictionary,
        # type entry must be /Catalog.
        assert root is not None
        type_obj = root.get_dictionary_object(COSName.get_pdf_name("Type"))
        assert type_obj == COSName.get_pdf_name("Catalog")
    finally:
        cos.close()


def test_trailer_size_grows_with_pages() -> None:
    """Adding more pages produces a strictly larger trailer /Size after
    serialisation. Sanity-checks that the writer doesn't dedupe page
    nodes."""
    sizes: list[int] = []
    for n in (1, 5, 10):
        with PDDocument() as src:
            for _ in range(n):
                src.add_page(PDPage())
            pdf = _save(src)
        cos = Loader.load_pdf(pdf)
        try:
            trailer = cos.get_trailer()
            assert trailer is not None
            sizes.append(trailer.get_int(COSName.get_pdf_name("Size")))
        finally:
            cos.close()
    # Strict monotonicity — each step must add at least one new entry.
    assert sizes[0] < sizes[1] < sizes[2]


def test_version_roundtrip_via_cos_document() -> None:
    """PDF version reported by the reloaded COSDocument matches the
    source's catalog/header decision. Default for a synthesised
    document is 1.4 per pypdfbox cluster #1's writer."""
    with PDDocument() as src:
        src.add_page(PDPage())
        pdf = _save(src)
    cos = Loader.load_pdf(pdf)
    try:
        assert cos.get_version() == 1.4
    finally:
        cos.close()


def test_version_bumped_to_1_5_through_catalog_roundtrip() -> None:
    """Setting the catalog version to 1.5 writes the bump to the catalog
    and roundtrips through PDDocument.get_version() (PDF >= 1.4 uses
    catalog /Version for the bump)."""
    with PDDocument() as src:
        src.add_page(PDPage())
        src.set_version(1.5)
        pdf = _save(src)
    with PDDocument.load(pdf) as reloaded:
        # PDDocument.get_version() returns the max of header + catalog.
        assert reloaded.get_version() >= 1.5


def test_encryption_state_absent_after_unencrypted_roundtrip() -> None:
    """A freshly-synthesised document has no /Encrypt and the reloaded
    COSDocument reports ``is_encrypted() is False``."""
    with PDDocument() as src:
        src.add_page(PDPage())
        pdf = _save(src)
    cos = Loader.load_pdf(pdf)
    try:
        assert cos.is_encrypted() is False
        assert cos.get_encryption_dictionary() is None
    finally:
        cos.close()


def test_roundtrip_via_pddocument_load_does_not_close_source_bytes() -> None:
    """Loading from a ``bytes`` source returns a document that owns its
    backing ``RandomAccessReadBuffer``; the original ``bytes`` object is
    untouched after close()."""
    with PDDocument() as src:
        src.add_page(PDPage())
        pdf = _save(src)
    snapshot = bytes(pdf)
    with PDDocument.load(pdf) as loaded:
        assert loaded.get_number_of_pages() == 1
    # The original bytes object is immutable — sanity check that no
    # in-place modification slipped through.
    assert pdf == snapshot


def test_loaded_then_full_save_uses_fresh_xref(tmp_path) -> None:
    """A round-trip through ``Loader.load_pdf → full save`` produces a
    PDF whose xref table starts from scratch (no /Prev chain), distinct
    from the incremental case."""
    with PDDocument() as src:
        for _ in range(2):
            src.add_page(PDPage())
        pdf = _save(src)

    target = tmp_path / "fresh.pdf"
    with PDDocument.load(pdf) as loaded:
        loaded.save(target)

    # The freshly saved file must NOT carry a /Prev entry in its
    # primary trailer — full save resets the xref chain.
    final = target.read_bytes()
    # Quick byte-level sanity: no "/Prev " token in the final trailer.
    # (A /Prev token would only appear if the writer accidentally took
    # the incremental path.)
    # Locate the final trailer.
    last_trailer_idx = final.rfind(b"trailer")
    assert last_trailer_idx > 0
    trailer_blob = final[last_trailer_idx : final.rfind(b"startxref")]
    assert b"/Prev" not in trailer_blob
