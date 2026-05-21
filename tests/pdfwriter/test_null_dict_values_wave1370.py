"""Wave 1370 — COSNull vs Python ``None`` in dictionary values.

The writer treats these two cases asymmetrically:

* ``COSNull.NULL`` → emitted on the wire as ``null`` (PDF 32000-1 §7.3.9).
* Python ``None`` → the key is removed from the dict (mirrors the
  ``set_item(key, None)`` semantics in ``COSDictionary``). The writer
  also defensively skips ``None`` values inside ``visit_from_dictionary``
  even if a caller somehow injected one.

Coverage:

* explicit ``COSNull`` round-trips as ``null``,
* ``None`` removes the key (cannot reach the writer at all),
* a ``None`` smuggled past ``set_item`` (e.g. via direct items-dict
  mutation) is still skipped, not emitted as a stray value,
* nested null inside an array: arrays preserve null elements verbatim.
"""

from __future__ import annotations

import io
import re

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
)
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter


def _make_doc(catalog: COSDictionary) -> COSDocument:
    doc = COSDocument()
    doc.set_version(1.4)
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    cat_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, cat_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    return doc


def _write(doc: COSDocument) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


# ---------- explicit COSNull -----------------------------------------------


def test_explicit_cosnull_emits_null_token() -> None:
    """COSNull.NULL inside a dict value must serialize as the literal
    ``null`` token (no quotes, no /Null name)."""
    catalog = COSDictionary()
    catalog.set_item(COSName.get_pdf_name("Maybe"), COSNull.NULL)
    out = _write(_make_doc(catalog))
    assert b"/Maybe null" in out
    # Must NOT have promoted it to a /Null name accidentally.
    assert b"/Maybe /Null" not in out


def test_explicit_cosnull_round_trips_to_null() -> None:
    """Parser must read the emitted ``null`` back as a missing entry
    (or a COSNull, depending on the resolver)."""
    catalog = COSDictionary()
    catalog.set_item(COSName.get_pdf_name("Maybe"), COSNull.NULL)
    catalog.set_int(COSName.get_pdf_name("Other"), 99)
    out = _write(_make_doc(catalog))
    parsed = Loader.load_pdf(out)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        # /Other must still round-trip.
        assert cat.get_int(COSName.get_pdf_name("Other")) == 99
        # /Maybe must either be absent or resolve to None (parser-level
        # COSNull entries are typically materialised as missing keys).
        val = cat.get_dictionary_object(COSName.get_pdf_name("Maybe"))
        assert val is None or isinstance(val, COSNull)
    finally:
        parsed.close()


# ---------- Python None ----------------------------------------------------


def test_set_item_with_none_removes_key() -> None:
    """``set_item(key, None)`` is the upstream removal idiom — the key
    must not appear in the emitted dict at all."""
    catalog = COSDictionary()
    catalog.set_int(COSName.get_pdf_name("Stays"), 1)
    catalog.set_int(COSName.get_pdf_name("Goes"), 2)
    catalog.set_item(COSName.get_pdf_name("Goes"), None)
    out = _write(_make_doc(catalog))
    assert b"/Stays 1" in out
    assert b"/Goes" not in out


def test_smuggled_none_in_items_dict_is_skipped_at_write() -> None:
    """Defensive: even if a caller bypasses ``set_item`` and stuffs a
    ``None`` directly into the underlying items dict, the writer's
    visitor must skip it instead of crashing or emitting a malformed
    value."""
    catalog = COSDictionary()
    catalog.set_int(COSName.get_pdf_name("Real"), 42)
    # Bypass the public setter to inject a None value.
    catalog._items[COSName.get_pdf_name("Smuggled")] = None  # type: ignore[assignment]  # noqa: SLF001
    out = _write(_make_doc(catalog))
    assert b"/Real 42" in out
    # The smuggled value must not appear — no /Smuggled key on the wire.
    assert b"/Smuggled" not in out


# ---------- null inside an array ------------------------------------------


def test_null_array_element_emits_null_token() -> None:
    """Arrays preserve null elements verbatim — null is a legal array
    element per ISO 32000-1 §7.3.6."""
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSNull.NULL)
    arr.add(COSInteger.get(3))
    arr.set_direct(True)
    catalog = COSDictionary()
    catalog.set_item(COSName.get_pdf_name("Mix"), arr)
    out = _write(_make_doc(catalog))
    assert b"/Mix [1 null 3]" in out


def test_only_null_value_dict_still_emits_well_formed_braces() -> None:
    """A dict whose only entry is a null value must still emit a
    syntactically valid ``<< /Key null >>`` block — no empty braces
    and no spurious /Null name."""
    catalog = COSDictionary()
    catalog.set_item(COSName.get_pdf_name("Solo"), COSNull.NULL)
    out = _write(_make_doc(catalog))
    # Locate the catalog frame "1 0 obj" and check its body.
    obj_match = re.search(rb"(?ms)^1 0 obj\s*<<(.*?)>>\s*endobj", out)
    assert obj_match is not None, "catalog object 1 not found"
    body = obj_match.group(1)
    # The body must contain both /Type /Catalog and /Solo null tokens.
    assert b"/Type /Catalog" in body
    assert b"/Solo null" in body
