"""Wave 1495 — coverage round-out for ``sig_utils``' BER indefinite-length
TLV scanner (``_ber_tlv_end``).

The existing signature suite already pins the DER definite-length and
indefinite-length-rejection paths and the ``strip_signature_padding`` slice;
these tests reach the remaining BER indefinite-length scanning branches:

* a multi-byte high-tag-number tag (low 5 bits all set, continuation bytes
  with the high bit set);
* an indefinite-length constructed value whose contents are a nested
  definite-length child terminated by end-of-contents octets (``00 00``);
* a lone ``0x00`` content byte that is not a complete EOC (scanner returns
  ``None`` → ``strip_signature_padding`` falls back to ``rstrip``);
* an offset already past the buffer end.
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.digitalsignature import strip_signature_padding
from pypdfbox.pdmodel.interactive.digitalsignature.sig_utils import _ber_tlv_end


def test_ber_indefinite_length_with_nested_definite_child() -> None:
    # SEQUENCE (0x30) indefinite length (0x80), one nested OCTET STRING child
    # (04 02 AA BB), then end-of-contents octets (00 00).
    blob = bytes([0x30, 0x80, 0x04, 0x02, 0xAA, 0xBB, 0x00, 0x00])
    padded = blob + b"\x00\x00\x00"  # placeholder padding after the EOC
    # The scanner returns exactly the blob length (just past the EOC) rather
    # than rstrip-ing into the trailing zero padding.
    assert _ber_tlv_end(padded, 0) == len(blob)
    assert strip_signature_padding(padded) == blob


def test_ber_high_tag_number_form_multi_byte_tag() -> None:
    # High-tag-number form: first tag byte low 5 bits all set (0x1F), then a
    # continuation byte with the high bit set (0x81) and a final byte clearing
    # it (0x01); definite length 0x02, body AA BB.
    blob = bytes([0x1F, 0x81, 0x01, 0x02, 0xAA, 0xBB])
    assert _ber_tlv_end(blob, 0) == len(blob)


def test_ber_single_trailing_zero_byte_ends_scan_with_no_match() -> None:
    # Indefinite-length SEQUENCE whose contents are a lone 0x00 with no second
    # 0x00 to complete the EOC → returns None (not a valid close).
    data = bytes([0x30, 0x80, 0x00])
    assert _ber_tlv_end(data, 0) is None
    # strip_signature_padding then falls back to rstrip of the trailing zero.
    assert strip_signature_padding(data) == bytes([0x30, 0x80])


def test_ber_tlv_end_offset_past_buffer_returns_none() -> None:
    assert _ber_tlv_end(b"\x30", 5) is None


def test_ber_high_tag_runs_off_buffer_end_returns_none() -> None:
    # High-tag-number form whose continuation bytes never terminate before
    # the buffer ends → ``offset > n`` after the tag scan.
    assert _ber_tlv_end(bytes([0x1F, 0x81]), 0) is None


def test_ber_truncated_after_tag_has_no_length_byte() -> None:
    # A definite single-byte tag (0x30) with no following length byte at all
    # → ``offset >= n`` before reading the length.
    assert _ber_tlv_end(bytes([0x30]), 0) is None


def test_ber_indefinite_with_truncated_nested_definite_length() -> None:
    # Indefinite SEQUENCE whose nested child declares a long-form length whose
    # octets run past the buffer → the nested _read_der_length raises and the
    # scan returns None.
    # 04 = OCTET STRING, 0x82 = 2 length octets declared, only one present.
    data = bytes([0x30, 0x80, 0x04, 0x82, 0xFF])
    assert _ber_tlv_end(data, 0) is None


def test_ber_indefinite_reaches_end_without_eoc() -> None:
    # Indefinite SEQUENCE whose single nested definite child exactly fills the
    # buffer with no end-of-contents octets → the while-loop exits and returns
    # None (no matching EOC found).
    data = bytes([0x30, 0x80, 0x04, 0x01, 0xAA])
    assert _ber_tlv_end(data, 0) is None
