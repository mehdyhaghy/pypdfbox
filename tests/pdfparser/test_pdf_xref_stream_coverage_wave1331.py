"""Wave 1331 coverage boost: ``PDFXRefStream``.

Targets uncovered lines 46-48, 106, 108, 121, 146, 168-172, 182, 203 in
``pypdfbox/pdfparser/pdf_xref_stream.py``:

* ``add_trailer_info`` copying ``/Info``/``/Root``/``/Encrypt``/``/ID``/``/Prev``
* ``get_stream`` skipping ``ROOT/INFO/PREV`` and ``ENCRYPT`` when
  forcing direct
* the public ``get_w_entry`` / ``get_index_entry`` /
  ``write_stream_data`` / ``write_number`` aliases
* the multi-range gap branch in ``_get_index_entry``
"""

from __future__ import annotations

import io

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.pdfparser import PDFXRefStream
from pypdfbox.pdfparser.xref import NormalXReference

# --------------------------------------------------------------------------
# add_trailer_info
# --------------------------------------------------------------------------


def test_add_trailer_info_copies_known_keys() -> None:
    """Lines 46-48: trailer keys present in the source are copied."""
    trailer = COSDictionary()
    info = COSDictionary()
    root = COSDictionary()
    encrypt = COSDictionary()
    id_arr = COSArray()
    id_arr.add(COSString.parse_hex("00"))
    id_arr.add(COSString.parse_hex("11"))
    trailer.set_item(COSName.INFO, info)
    trailer.set_item(COSName.ROOT, root)
    trailer.set_item(COSName.ENCRYPT, encrypt)
    trailer.set_item(COSName.ID, id_arr)
    trailer.set_item(COSName.PREV, COSInteger.get(12345))

    xs = PDFXRefStream(COSDocument())
    xs.add_trailer_info(trailer)
    # All five keys were forwarded into the xref stream dict.
    assert xs._stream.contains_key(COSName.INFO)  # type: ignore[attr-defined]
    assert xs._stream.contains_key(COSName.ROOT)  # type: ignore[attr-defined]
    assert xs._stream.contains_key(COSName.ENCRYPT)  # type: ignore[attr-defined]
    assert xs._stream.contains_key(COSName.ID)  # type: ignore[attr-defined]
    assert xs._stream.contains_key(COSName.PREV)  # type: ignore[attr-defined]


def test_add_trailer_info_skips_missing_keys() -> None:
    """No keys in the source trailer ⇒ nothing copied (loop branches false)."""
    xs = PDFXRefStream(COSDocument())
    xs.add_trailer_info(COSDictionary())
    # Type/Size aren't set until get_stream(); none of the trailer keys
    # should be present yet.
    for key in (COSName.INFO, COSName.ROOT, COSName.ENCRYPT, COSName.ID, COSName.PREV):
        assert not xs._stream.contains_key(key)  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# get_stream: ROOT/INFO/PREV/ENCRYPT skip branches in the direct-forcing loop
# --------------------------------------------------------------------------


def test_get_stream_skips_root_info_prev_and_encrypt_in_direct_loop() -> None:
    """Lines 106 and 108: the direct-forcing loop must continue past
    these four reserved keys without touching ``set_direct``."""
    doc = COSDocument()
    try:
        info = COSDictionary()
        root = COSDictionary()
        encrypt = COSDictionary()
        trailer = COSDictionary()
        trailer.set_item(COSName.INFO, info)
        trailer.set_item(COSName.ROOT, root)
        trailer.set_item(COSName.ENCRYPT, encrypt)
        trailer.set_item(COSName.PREV, COSInteger.get(99))

        xs = PDFXRefStream(doc)
        xs.add_trailer_info(trailer)
        xs.set_size(20)
        ref_stream = COSStream()
        try:
            xs.add_entry(NormalXReference(0, COSObjectKey(7, 0), ref_stream))
            stream = xs.get_stream()
            # All four reserved trailer keys remain reachable in the result.
            assert stream.get_dictionary_object(COSName.ROOT) is not None
            assert stream.get_dictionary_object(COSName.INFO) is not None
            assert stream.get_dictionary_object(COSName.ENCRYPT) is not None
            assert stream.get_dictionary_object(COSName.PREV) is not None
        finally:
            ref_stream.close()
    finally:
        doc.close()


# --------------------------------------------------------------------------
# Public aliases that mirror upstream's camelCase getters/writers
# --------------------------------------------------------------------------


def test_get_w_entry_public_alias_delegates_to_private() -> None:
    """Line 121: ``get_w_entry`` returns the same result as ``_get_w_entry``."""
    xs = PDFXRefStream(COSDocument())
    xs.add_entry(NormalXReference(70000, COSObjectKey(2, 0), COSStream()))
    assert xs.get_w_entry() == xs._get_w_entry()  # type: ignore[attr-defined]


def test_get_index_entry_public_alias_delegates_to_private() -> None:
    """Line 146: ``get_index_entry`` returns the same result as ``_get_index_entry``."""
    xs = PDFXRefStream(COSDocument())
    xs.add_entry(NormalXReference(0, COSObjectKey(5, 0), COSStream()))
    assert xs.get_index_entry() == xs._get_index_entry()  # type: ignore[attr-defined]


def test_write_number_static_public_alias_writes_big_endian_bytes() -> None:
    """Line 182: ``write_number`` static alias writes ``n_bytes`` big-endian."""
    out = io.BytesIO()
    PDFXRefStream.write_number(out, 0xABCDEF, 3)
    assert out.getvalue() == b"\xab\xcd\xef"


def test_write_stream_data_public_alias_writes_null_and_entries() -> None:
    """Line 203: ``write_stream_data`` writes the NULL row then each entry."""
    xs = PDFXRefStream(COSDocument())
    xs.add_entry(NormalXReference(50, COSObjectKey(1, 0), COSStream()))
    widths = xs.get_w_entry()
    total = sum(widths)
    out = io.BytesIO()
    xs.write_stream_data(out, widths)
    # one NULL row + one entry row = 2 rows of `total` bytes each.
    assert len(out.getvalue()) == total * 2


# --------------------------------------------------------------------------
# Multi-range gap branch in _get_index_entry (lines 168-172)
# --------------------------------------------------------------------------


def test_get_index_entry_emits_multiple_ranges_when_gap_present() -> None:
    """Lines 168-172: an object number well past the running range should
    flush the current ``(first, length)`` pair and start a new one."""
    xs = PDFXRefStream(COSDocument())
    # Sorted set will be {0, 1, 5, 6} after we add 1, 5, 6 (0 is always in).
    xs.add_entry(NormalXReference(0, COSObjectKey(1, 0), COSStream()))
    xs.add_entry(NormalXReference(0, COSObjectKey(5, 0), COSStream()))
    xs.add_entry(NormalXReference(0, COSObjectKey(6, 0), COSStream()))
    entries = xs.get_index_entry()
    # Expect ``[0, 2, 5, 2]`` — (0,1) + (1) merges; (5,6) is the second range.
    assert entries == [0, 2, 5, 2]


def test_get_index_entry_single_long_range_no_gap() -> None:
    """All-contiguous case stays a single range (the ``first+length==num``
    merge branch, included for completeness next to the gap test)."""
    xs = PDFXRefStream(COSDocument())
    for n in (1, 2, 3, 4):
        xs.add_entry(NormalXReference(0, COSObjectKey(n, 0), COSStream()))
    assert xs.get_index_entry() == [0, 5]
