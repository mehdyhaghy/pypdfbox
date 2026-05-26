"""Wave 1410 — regression tests for ``strip_signature_padding``.

A signature ``/Contents`` is a fixed-width hex string with the PKCS#7 DER
blob followed by ``\\x00`` placeholder padding. The old code stripped that
padding with ``rstrip(b"\\x00")``, which truncates a DER blob that
legitimately ends in ``0x00`` — an intermittent failure (it depends on the
random signing key's blob ending) that surfaced as a flaky PKCS#7-parse in
the signature suite (wave 1409). ``strip_signature_padding`` slices by the
outer SEQUENCE's DER length instead. These cases pin that behaviour
deterministically.
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.digitalsignature import strip_signature_padding


def test_recovers_blob_ending_in_zero_byte() -> None:
    # DER SEQUENCE (0x30), length 3, body 01 02 00 — ends in a real 0x00.
    blob = bytes([0x30, 0x03, 0x01, 0x02, 0x00])
    padded = blob + b"\x00" * 64
    assert strip_signature_padding(padded) == blob
    # The old rstrip approach would have truncated the trailing real 0x00.
    assert padded.rstrip(b"\x00") != blob


def test_blob_with_no_padding_is_unchanged() -> None:
    blob = bytes([0x30, 0x02, 0x01, 0x05])
    assert strip_signature_padding(blob) == blob


def test_long_form_der_length() -> None:
    # 0x30 0x81 0x80 => SEQUENCE, long-form length 0x80 (128) bytes of body.
    body = bytes(range(128))
    blob = bytes([0x30, 0x81, 0x80]) + body
    padded = blob + b"\x00" * 200
    assert strip_signature_padding(padded) == blob


def test_non_sequence_falls_back_to_rstrip() -> None:
    # Not a DER SEQUENCE (no 0x30 lead) — fall back to trailing-NUL strip.
    data = b"hello\x00\x00\x00"
    assert strip_signature_padding(data) == b"hello"


def test_truncated_length_falls_back_to_rstrip() -> None:
    # 0x30 with a long-form length claiming more bytes than present.
    data = bytes([0x30, 0x82, 0xFF, 0xFF, 0x01]) + b"\x00" * 3
    # total would exceed len(data); helper must not slice past the end.
    assert strip_signature_padding(data) == bytes([0x30, 0x82, 0xFF, 0xFF, 0x01])


def test_empty_input() -> None:
    assert strip_signature_padding(b"") == b""
