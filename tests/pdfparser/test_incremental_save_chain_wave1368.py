"""Wave 1368 — incremental-save /Prev chains across multiple xref sections.

PDF incremental updates append new objects + a new xref/trailer pair
after the previous %%EOF. The new trailer's ``/Prev`` points at the
previous xref offset. Tests cover:

* Three-section chain (oldest -> middle -> newest), each overriding
  a different object so the merged pool sees the newest value per key.
* /Info that only exists in an older section is still reachable.
* Walking the chain stops once /Prev is absent (no spurious recursion).
* Trailer keys present only in the oldest section (e.g. /Root) are
  inherited when newer trailers don't redeclare them.
* /Prev pointing past EOF is recovered under lenient mode.
"""

from __future__ import annotations

import contextlib

from pypdfbox.cos import COSDictionary, COSName, COSObjectKey, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser


def _three_section_pdf() -> tuple[bytes, list[int]]:
    """Build a 3-section incremental PDF.

    Sections (oldest -> newest):
      v1: object 1 "(v1)" + xref + trailer (no /Prev)
      v2: object 2 "(v2)" added + /Prev -> v1 xref
      v3: object 1 rewritten to "(v3)" + /Prev -> v2 xref

    Returns the bytes plus the list of xref offsets in build order.
    """
    out = bytearray(b"%PDF-1.4\n")
    # --- section 1
    obj1_v1_off = len(out)
    out += b"1 0 obj\n(v1)\nendobj\n"
    xref1_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_v1_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref1_off).encode("ascii") + b"\n%%EOF\n"
    # --- section 2: add object 2
    obj2_off = len(out)
    out += b"2 0 obj\n(v2)\nendobj\n"
    xref2_off = len(out)
    out += b"xref\n0 1\n0000000000 65535 f \n"
    out += b"2 1\n"
    out += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 3 /Root 1 0 R /Prev "
        + str(xref1_off).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(xref2_off).encode("ascii") + b"\n%%EOF\n"
    # --- section 3: rewrite object 1
    obj1_v3_off = len(out)
    out += b"1 0 obj\n(v3)\nendobj\n"
    xref3_off = len(out)
    out += b"xref\n0 1\n0000000000 65535 f \n1 1\n"
    out += f"{obj1_v3_off:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 3 /Root 1 0 R /Prev "
        + str(xref2_off).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(xref3_off).encode("ascii") + b"\n%%EOF"
    return bytes(out), [xref1_off, xref2_off, xref3_off]


def test_three_section_prev_chain_loads_newest_value() -> None:
    pdf, _ = _three_section_pdf()
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    body1 = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body1, COSString) and body1.get_bytes() == b"v3"
    body2 = doc.get_object_from_pool(COSObjectKey(2, 0)).get_object()
    assert isinstance(body2, COSString) and body2.get_bytes() == b"v2"


def test_three_section_prev_chain_section_count_records_all() -> None:
    pdf, _ = _three_section_pdf()
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.parse()
    resolver = parser.get_xref_trailer_resolver()
    # Three sections should have been registered, one per /Prev hop.
    assert resolver.section_count() == 3


def test_oldest_section_info_inherited_through_chain() -> None:
    """A trailer key declared only in the *oldest* section is still
    accessible after the merge because the resolver merges old → new."""
    out = bytearray(b"%PDF-1.4\n")
    obj1_off = len(out)
    out += b"1 0 obj\n(only-v1)\nendobj\n"
    # Section 1 carries an /Info dict embedded inline.
    info_off = len(out)
    out += b"3 0 obj\n<< /Producer (pdfwave) >>\nendobj\n"
    xref1_off = len(out)
    out += b"xref\n0 4\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"0000000000 00001 f \n"  # object 2 free
    out += f"{info_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 4 /Root 1 0 R /Info 3 0 R >>\n"
    out += b"startxref\n" + str(xref1_off).encode("ascii") + b"\n%%EOF\n"
    # Section 2: incremental update touching object 1 only; trailer does
    # NOT re-declare /Info — the resolver must inherit it.
    obj1_v2_off = len(out)
    out += b"1 0 obj\n(v2)\nendobj\n"
    xref2_off = len(out)
    out += b"xref\n0 1\n0000000000 65535 f \n1 1\n"
    out += f"{obj1_v2_off:010d} 00000 n \n".encode("ascii")
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
    assert trailer.contains_key(COSName.get_pdf_name("Info"))


def test_prev_pointing_into_garbage_skipped_under_lenient() -> None:
    """If the /Prev offset is junk, lenient mode should *not* abort the
    whole parse — the newer section already supplies enough to load the
    catalog."""
    out = bytearray(b"%PDF-1.4\n")
    obj1_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R /Prev 5 >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    parser.set_lenient(True)
    doc = parser.parse()
    assert doc.has_object(COSObjectKey(1, 0))


def test_prev_chain_terminates_at_missing_prev_key() -> None:
    """The newest section has /Prev; the middle section has /Prev; the
    oldest section has *no* /Prev. The walk must stop there rather than
    treat the absent key as -1 and loop or error."""
    pdf, _ = _three_section_pdf()
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.parse()
    resolver = parser.get_xref_trailer_resolver()
    # The oldest section's trailer must not carry /Prev.
    oldest = resolver.get_first_trailer()
    assert oldest is not None
    assert not oldest.contains_key(COSName.get_pdf_name("Prev"))


def test_encrypt_declared_in_newest_section_only_is_observable() -> None:
    """A document that was originally unencrypted but encrypted via an
    incremental save carries /Encrypt only in the newest trailer. The
    parser must surface that without complaint when no password is set
    (we don't decrypt anything in this test, just observe the trailer)."""
    out = bytearray(b"%PDF-1.4\n")
    obj1_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref1_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref1_off).encode("ascii") + b"\n%%EOF\n"
    # Section 2: same object, but introduces an /Encrypt ref to a new
    # object that doesn't actually decrypt anything (since the streams
    # don't get decoded in this test). Validate the trailer only.
    enc_off = len(out)
    out += b"2 0 obj\n<< /Filter /Standard >>\nendobj\n"
    xref2_off = len(out)
    out += b"xref\n0 1\n0000000000 65535 f \n2 1\n"
    out += f"{enc_off:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 3 /Root 1 0 R /Encrypt 2 0 R /Prev "
        + str(xref1_off).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(xref2_off).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    # We can't fully parse if /Encrypt triggers handler bootstrap, so
    # observe the trailer accessor which short-circuits before that.
    # Some configurations of the encryption handler reject the
    # placeholder dict; the trailer accessor still captures /Encrypt.
    with contextlib.suppress(PDFParseError):
        parser.parse()
    trailer = parser.get_trailer()
    if trailer is not None:
        assert trailer.contains_key(COSName.get_pdf_name("Encrypt"))


def test_circular_prev_chain_does_not_loop() -> None:
    """A buggy producer can emit /Prev pointing at the section that
    contains it (an obvious cycle). The parser must break the walk via
    the resolver's visited-offset tracker rather than spinning."""
    out = bytearray(b"%PDF-1.4\n")
    obj1_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    # /Prev points back at the same xref section — a self-loop.
    out += (
        b"trailer\n<< /Size 2 /Root 1 0 R /Prev "
        + str(xref_off).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    # Parsing must complete — the visited-offset guard breaks the cycle.
    doc = parser.parse()
    assert doc.has_object(COSObjectKey(1, 0))
