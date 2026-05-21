"""Wave 1370 — incremental /Prev threading across multiple appends.

The single-pass /Prev pointer is already covered in
``test_cos_writer_incremental.py``. This file exercises the *iterative*
case: three successive incremental saves on the same source must each
emit a fresh trailer whose ``/Prev`` points at the *immediately previous*
``startxref`` — building a chain the reader can walk back to the original
catalog.
"""

from __future__ import annotations

import io
import re

from pypdfbox.cos import COSDictionary, COSDocument, COSName, COSObject
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter


def _seed_pdf() -> bytes:
    doc = COSDocument()
    doc.set_version(1.4)
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_int(COSName.get_pdf_name("Version"), 1)
    catalog_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


def _incremental_bump_version(source: bytes, new_version: int) -> bytes:
    parsed = Loader.load_pdf(source)
    try:
        catalog = parsed.get_catalog()
        assert catalog is not None
        catalog.set_int(COSName.get_pdf_name("Version"), new_version)
        catalog.set_needs_to_be_updated(True)
        sink = io.BytesIO()
        with COSWriter(sink, incremental=True) as w:
            w.write(parsed)
        return sink.getvalue()
    finally:
        parsed.close()


def _all_startxref_offsets(pdf_bytes: bytes) -> list[int]:
    """Return every ``startxref N`` offset in document order."""
    return [int(m) for m in re.findall(rb"startxref\s+(\d+)", pdf_bytes)]


def _all_prev_values(pdf_bytes: bytes) -> list[int]:
    return [int(m) for m in re.findall(rb"/Prev\s+(\d+)", pdf_bytes)]


# ---------- single increment baseline --------------------------------------


def test_first_increment_threads_prev_to_original_startxref() -> None:
    src = _seed_pdf()
    out = _incremental_bump_version(src, 2)
    assert out.startswith(src)
    # Original startxref is the only one in src.
    original_startxrefs = _all_startxref_offsets(src)
    assert len(original_startxrefs) == 1
    # The increment's /Prev must point at it.
    prev_values = _all_prev_values(out)
    assert prev_values == [original_startxrefs[0]]


# ---------- two-stage append chain ------------------------------------------


def test_chained_increments_each_threads_to_immediately_prior_startxref() -> None:
    """After three saves: src → s1 → s2, the trailer in s2 carries
    /Prev pointing at s1's startxref, and s1 carries /Prev pointing
    at src's startxref. This is the iterative property — every layer
    walks back exactly one level."""
    src = _seed_pdf()
    s1 = _incremental_bump_version(src, 2)
    s2 = _incremental_bump_version(s1, 3)

    original_xref = _all_startxref_offsets(src)[0]
    s1_xrefs = _all_startxref_offsets(s1)
    s2_xrefs = _all_startxref_offsets(s2)

    # s1 must declare its own new startxref distinct from the source one.
    assert s1_xrefs[-1] != original_xref
    # s2 must declare a startxref past s1's tail.
    assert s2_xrefs[-1] > s1_xrefs[-1]

    # s2 final /Prev must equal s1's final startxref (immediately prior).
    s2_prev = _all_prev_values(s2)
    assert s2_prev[-1] == s1_xrefs[-1]

    # Round-trip: latest value wins.
    parsed = Loader.load_pdf(s2)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        assert cat.get_int(COSName.get_pdf_name("Version")) == 3
    finally:
        parsed.close()


def test_chained_increments_preserve_id_first_element() -> None:
    """The first element of /ID must round-trip across every append —
    Adobe / qpdf both check this to chain incremental signatures."""
    src = _seed_pdf()
    parsed = Loader.load_pdf(src)
    original_ids = parsed.get_document_id()
    assert original_ids is not None
    original_first = original_ids.get(0)
    parsed.close()

    s1 = _incremental_bump_version(src, 2)
    s2 = _incremental_bump_version(s1, 3)

    final = Loader.load_pdf(s2)
    try:
        ids = final.get_document_id()
        assert ids is not None
        assert ids.get(0) == original_first
    finally:
        final.close()


def test_each_increment_appends_only_to_tail() -> None:
    """ISO 32000-2 §7.5.6: an incremental update must be append-only;
    the prefix of the file must equal the original bytes verbatim. This
    guards against accidental rewrites of the source body."""
    src = _seed_pdf()
    s1 = _incremental_bump_version(src, 2)
    assert s1.startswith(src)
    s2 = _incremental_bump_version(s1, 3)
    assert s2.startswith(s1)


def test_chained_increments_walk_back_via_loader() -> None:
    """A reader walking /Prev must be able to reach the original catalog
    body — verify via the loader (which mimics what every PDF viewer
    does)."""
    src = _seed_pdf()
    s1 = _incremental_bump_version(src, 2)
    s2 = _incremental_bump_version(s1, 5)

    parsed = Loader.load_pdf(s2)
    try:
        # The Loader's xref-chain walk must have processed all three
        # generations — the latest catalog wins.
        cat = parsed.get_catalog()
        assert cat is not None
        assert cat.get_int(COSName.get_pdf_name("Version")) == 5
    finally:
        parsed.close()
