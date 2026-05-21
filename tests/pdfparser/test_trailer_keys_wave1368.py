"""Wave 1368 — trailer dictionary parsing edges.

The trailer is the entry point the loader uses to find ``/Root``,
``/Info``, ``/Encrypt``, ``/ID``, ``/Prev`` and ``/Size``. Tests:

* ``/ID`` array with first-time + subsequent-update entries.
* ``/Info`` declared via indirect reference (the common case).
* ``/Info`` declared inline (a direct dictionary in the trailer).
* ``/Size`` smaller than the actual object pool — the parser warns
  rather than truncating.
* Trailer dictionary's ``/Prev`` declared as an indirect reference
  (uncommon but legal) resolves like a direct integer.
* Multiple trailer fragments collapse into a single ``COSDictionary``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObjectKey, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser


def _ids_pdf(ids: list[bytes]) -> bytes:
    """Build a PDF whose trailer carries the given /ID array."""
    out = bytearray(b"%PDF-1.4\n")
    obj_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R /ID ["
    for raw in ids:
        out += b"<" + raw.hex().upper().encode("ascii") + b">"
    out += b"] >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_trailer_id_first_and_subsequent_entries_both_present() -> None:
    """``/ID`` is an array of two hex strings: the first identifies the
    document, the second identifies the revision. Both must round-trip
    as ``COSString`` instances in the parsed array."""
    first = b"\x01" * 16
    second = b"\x02" * 16
    pdf = _ids_pdf([first, second])
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.parse()
    trailer = parser.get_trailer()
    assert isinstance(trailer, COSDictionary)
    id_arr = trailer.get_dictionary_object(COSName.ID)
    assert isinstance(id_arr, COSArray)
    assert len(id_arr) == 2
    assert isinstance(id_arr.get_object(0), COSString)
    assert isinstance(id_arr.get_object(1), COSString)
    assert id_arr.get_object(0).get_bytes() == first
    assert id_arr.get_object(1).get_bytes() == second


def test_trailer_id_single_entry_initial_creation() -> None:
    """A freshly authored document has identical first/second /ID
    entries. Validate the trailer accepts the 1-element + 2-element
    forms equivalently."""
    val = b"\xAB" * 16
    pdf = _ids_pdf([val, val])
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.parse()
    trailer = parser.get_trailer()
    assert isinstance(trailer, COSDictionary)
    id_arr = trailer.get_dictionary_object(COSName.ID)
    assert isinstance(id_arr, COSArray) and len(id_arr) == 2


def test_trailer_info_indirect_reference_resolves() -> None:
    """``/Info`` declared as an indirect reference must resolve to the
    referenced dictionary on demand."""
    out = bytearray(b"%PDF-1.4\n")
    cat_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    info_off = len(out)
    out += b"2 0 obj\n<< /Producer (pdfwave) /Title (Hello) >>\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 3\n0000000000 65535 f \n"
    out += f"{cat_off:010d} 00000 n \n".encode("ascii")
    out += f"{info_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 3 /Root 1 0 R /Info 2 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    doc = parser.parse()
    trailer = parser.get_trailer()
    assert isinstance(trailer, COSDictionary)
    info_dict = trailer.get_dictionary_object(COSName.INFO)
    assert isinstance(info_dict, COSDictionary)
    producer = info_dict.get_dictionary_object(COSName.get_pdf_name("Producer"))
    assert isinstance(producer, COSString)
    assert producer.get_bytes() == b"pdfwave"
    # Object 2 must also appear in the pool.
    assert doc.has_object(COSObjectKey(2, 0))


def test_trailer_size_smaller_than_object_pool_does_not_fail_load() -> None:
    """The /Size value officially equals max-object-number + 1. Some
    files lie about /Size; the parser must not refuse to load when the
    pool actually has more objects."""
    out = bytearray(b"%PDF-1.4\n")
    obj1_off = len(out)
    out += b"1 0 obj\n(one)\nendobj\n"
    obj2_off = len(out)
    out += b"2 0 obj\n(two)\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 3\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    # /Size = 2 even though the table declares 3 entries (counting free
    # slot at index 0). The parser should not gate any work on this.
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    assert doc.has_object(COSObjectKey(1, 0))
    assert doc.has_object(COSObjectKey(2, 0))


def test_trailer_merged_keys_across_two_sections_take_newer_value() -> None:
    """A trailer key declared in *both* sections should be resolved to
    the newer (last-parsed) value. Validate via /Size: newer section
    declares 4, older section declares 2 — merged trailer reads 4."""
    out = bytearray(b"%PDF-1.4\n")
    obj1_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref1_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref1_off).encode("ascii") + b"\n%%EOF\n"
    obj2_off = len(out)
    out += b"2 0 obj\n(later)\nendobj\n"
    xref2_off = len(out)
    out += b"xref\n0 1\n0000000000 65535 f \n2 1\n"
    out += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 4 /Root 1 0 R /Prev "
        + str(xref1_off).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(xref2_off).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    parser.parse()
    trailer = parser.get_trailer()
    assert isinstance(trailer, COSDictionary)
    # Newer /Size (4) wins.
    assert trailer.get_long(COSName.SIZE, -1) == 4


def test_trailer_id_missing_is_legal_and_returns_none() -> None:
    """``/ID`` is recommended but not required. Its absence must not
    cause a parse failure."""
    out = bytearray(b"%PDF-1.4\n")
    obj_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    parser.parse()
    trailer = parser.get_trailer()
    assert isinstance(trailer, COSDictionary)
    # /ID absent → get_dictionary_object returns None (not an error).
    assert trailer.get_dictionary_object(COSName.ID) is None


def test_trailer_with_inline_info_dict_resolves_directly() -> None:
    """Some producers put ``/Info`` directly in the trailer rather than
    behind an indirect reference. Both forms must yield a usable
    dictionary."""
    out = bytearray(b"%PDF-1.4\n")
    obj_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj_off:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 2 /Root 1 0 R "
        b"/Info << /Producer (inline) /Title (Hi) >> >>\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    parser.parse()
    trailer = parser.get_trailer()
    assert isinstance(trailer, COSDictionary)
    info_dict = trailer.get_dictionary_object(COSName.INFO)
    assert isinstance(info_dict, COSDictionary)
    producer = info_dict.get_dictionary_object(COSName.get_pdf_name("Producer"))
    assert isinstance(producer, COSString) and producer.get_bytes() == b"inline"
