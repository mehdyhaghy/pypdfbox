"""Wave 1370 — object-number reuse / dedup.

Covers the writer's ``_add_object_to_write`` dedup logic (and the
``_actuals_added`` / ``_object_keys`` identity sets backing it):

* Writing the same indirect twice — referenced from two different
  parents — must allocate exactly one xref entry and exactly one
  ``num gen obj`` frame.
* The two parents must end up emitting the same ``num gen R`` token,
  so the file actually points at the shared body (not at a duplicate).
* The /Size value in the trailer counts each shared body once.
"""

from __future__ import annotations

import io
import re

from pypdfbox.cos import (
    COSDictionary,
    COSDocument,
    COSName,
    COSObject,
)
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter


def _write(doc: COSDocument) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


def _shared_target_doc() -> tuple[COSDocument, COSObject]:
    """Build a small document where /Root and /Info both reference the
    same downstream COSObject — so the writer must dedup it."""
    shared = COSDictionary()
    shared.set_int(COSName.get_pdf_name("Shared"), 1)
    shared_obj = COSObject(2, 0, resolved=shared)

    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_item(COSName.get_pdf_name("Ref"), shared_obj)
    catalog_obj = COSObject(1, 0, resolved=catalog)

    info = COSDictionary()
    info.set_item(COSName.get_pdf_name("Ref"), shared_obj)
    info_obj = COSObject(3, 0, resolved=info)

    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    trailer.set_item(COSName.INFO, info_obj)  # type: ignore[attr-defined]

    doc = COSDocument()
    doc.set_version(1.4)
    doc.set_trailer(trailer)
    return doc, shared_obj


def test_shared_indirect_produces_single_object_frame() -> None:
    """A COSObject referenced from two parents emits one ``n g obj`` frame."""
    doc, shared_obj = _shared_target_doc()
    out = _write(doc)
    # Count ``n g obj`` frames — one per indirect object.
    # The shared target carries key (2, 0); it must appear once.
    frames_2_0 = re.findall(rb"(?m)^2 0 obj\b", out)
    assert len(frames_2_0) == 1, (
        f"shared object 2 0 emitted {len(frames_2_0)} times: {frames_2_0!r}"
    )


def test_shared_indirect_appears_once_in_xref() -> None:
    """Each indirect-object key must show up exactly once in the xref
    table — the writer's dedup must NOT emit two xref rows for the same
    key just because two parents referenced it."""
    doc, _ = _shared_target_doc()
    out = _write(doc)
    # Pull the xref body and scan for non-free rows.
    xref_idx = out.index(b"\nxref\n") + len(b"\nxref\n")
    trailer_idx = out.index(b"trailer\n", xref_idx)
    body = out[xref_idx:trailer_idx]
    header_end = body.index(b"\n") + 1
    rows = body[header_end:]
    # Build {key_no: count} by walking 20-byte rows.
    used_count = 0
    for i in range(0, len(rows), 20):
        row = rows[i:i + 20]
        if row.endswith(b"n\r\n"):  # type-1 in-use entry
            used_count += 1
    # We seeded keys 1, 2, 3 — so exactly 3 in-use entries.
    assert used_count == 3, f"expected 3 in-use xref rows, saw {used_count}"


def test_shared_indirect_round_trips() -> None:
    """The two parents must both resolve to the same actual via the
    parser after a round trip — confirming the references really point
    at the same body."""
    doc, _ = _shared_target_doc()
    out = _write(doc)
    parsed = Loader.load_pdf(out)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        ref_from_cat = cat.get_dictionary_object(COSName.get_pdf_name("Ref"))
        assert isinstance(ref_from_cat, COSDictionary)
        trailer = parsed.get_trailer()
        assert trailer is not None
        info_dict = trailer.get_dictionary_object(COSName.INFO)  # type: ignore[attr-defined]
        assert isinstance(info_dict, COSDictionary)
        ref_from_info = info_dict.get_dictionary_object(
            COSName.get_pdf_name("Ref")
        )
        # Both /Ref entries must point at the same resolved dict — the
        # parser dedups by object key, so identity holds.
        assert ref_from_cat is ref_from_info
        assert ref_from_cat.get_int(COSName.get_pdf_name("Shared")) == 1
    finally:
        parsed.close()


def test_get_number_does_not_overcount_shared() -> None:
    """``get_number`` tracks the auto-mint counter only. Every declared
    COSObject (catalog #1, shared #2, info #3) keeps its declared key,
    so no fresh number was minted for the duplicate reference — the
    counter must stay at zero (no minting happened)."""
    doc, _ = _shared_target_doc()
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
        # Three declared keys were used as-is; no auto-mint fired.
        assert w.get_number() == 0
        # And exactly three xref entries (free head + 3 in-use rows is
        # checked elsewhere; here we confirm the writer didn't allocate
        # a fourth entry for the duplicated reference).
        entries = w.get_xref_entries()
        # Filter out the free-list head (object 0).
        in_use = {
            e.get_key() for e in entries if not e.is_free()
        }
        assert len(in_use) == 3


def test_size_in_trailer_counts_shared_object_once() -> None:
    """ISO 32000-1 §7.5.5: /Size = max_obj_num + 1. A shared body must
    not inflate /Size — we declared 1, 2, 3, so /Size = 4."""
    doc, _ = _shared_target_doc()
    out = _write(doc)
    trailer_idx = out.index(b"\ntrailer\n")
    sizes = re.findall(rb"/Size (\d+)", out[trailer_idx:])
    assert sizes == [b"4"]


def test_distinct_objects_get_distinct_keys() -> None:
    """Sanity check the opposite case: two *separate* dicts sharing a
    structural layout (not the same identity) must each get their own
    indirect frame."""
    a = COSDictionary()
    a.set_int(COSName.get_pdf_name("V"), 1)
    a_obj = COSObject(2, 0, resolved=a)
    b = COSDictionary()
    b.set_int(COSName.get_pdf_name("V"), 1)
    b_obj = COSObject(3, 0, resolved=b)

    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_item(COSName.get_pdf_name("A"), a_obj)
    catalog.set_item(COSName.get_pdf_name("B"), b_obj)
    cat_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, cat_obj)  # type: ignore[attr-defined]
    doc = COSDocument()
    doc.set_version(1.4)
    doc.set_trailer(trailer)

    out = _write(doc)
    # Both 2 0 obj and 3 0 obj must be present.
    assert re.search(rb"(?m)^2 0 obj\b", out) is not None
    assert re.search(rb"(?m)^3 0 obj\b", out) is not None
