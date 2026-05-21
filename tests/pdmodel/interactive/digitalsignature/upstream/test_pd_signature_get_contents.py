"""Ported from upstream PDFBox 3.0 ``PDSignatureFieldTest#testGetContents``.

Source:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDSignatureFieldTest.java``
(PDFBOX-4822).

The upstream test was placed under the form-field test suite but exercises
``PDSignature.getContents(byte[])`` / ``getContents(InputStream)`` — the
low-level routine that finds the ``<...>`` hex blob between the two
``/ByteRange`` slices and decodes it. In pypdfbox that behaviour belongs
on :class:`PDSignature` and is reached via
:meth:`PDSignature.get_contents_from_bytes`.

Skipped upstream pieces:

- ``InputStream`` overload — pypdfbox accepts ``bytes`` only (callers
  buffer the document themselves; the API surface stays one-shot to keep
  ``/ByteRange`` slice math obvious).
"""
from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
    PDSignature,
)


def test_get_contents() -> None:
    """Upstream ``testGetContents`` (PDFBOX-4822).

    Mirrors the upstream byte-layout:

        AAAAAAAAAA<313233343536373839>BBBBBBBBBB
        0123456789012345678901234567890123456789

    Where ``/ByteRange == [0, 10, 30, 10]`` — the first 10 bytes
    (``AAAAAAAAAA``) plus the last 10 (``BBBBBBBBBB``) are the bytes that
    were signed, and the gap between them (offsets 10..29) is the
    ``<...>``-framed hex-encoded ``/Contents``. Decoding the hex pairs
    yields the ASCII string ``"123456789"``.
    """
    signature = PDSignature()
    signature.set_byte_range([0, 10, 30, 10])
    pdf_bytes = (
        b"AAAAAAAAAA<313233343536373839>BBBBBBBBBB"
    )
    extracted = signature.get_contents_from_bytes(pdf_bytes)
    assert extracted == b"123456789"
    # And as a decoded string (mirrors upstream ``new String(...)``).
    assert extracted.decode("iso-8859-1") == "123456789"


# ---------------------------------------------------------------------------
# Defensive round-out — keep the pypdfbox surface honest for negative inputs.
# ---------------------------------------------------------------------------


def test_get_contents_raises_when_byte_range_missing() -> None:
    """No ``/ByteRange`` set → :class:`IndexError` (mirrors the upstream
    contract of "ByteRange is required"). pypdfbox surfaces this as
    ``IndexError("missing or malformed /ByteRange")``."""
    signature = PDSignature()
    with pytest.raises(IndexError):
        signature.get_contents_from_bytes(b"placeholder")


def test_get_contents_raises_when_byte_range_wrong_length() -> None:
    """A ``/ByteRange`` with the wrong length is rejected at ``set_byte_range``
    with :class:`ValueError`. Upstream rejects it lazily inside
    ``getContents(byte[])``; pypdfbox catches it eagerly at the setter
    boundary — same outcome (caller can't proceed with a 3-entry range).
    """
    signature = PDSignature()
    with pytest.raises(ValueError):
        signature.set_byte_range([0, 10, 30])  # 3 entries — must be 4


def test_get_contents_handles_empty_hex_body() -> None:
    """``<>`` (zero-length body) decodes to ``b""`` — upstream behaviour."""
    signature = PDSignature()
    # /Contents placeholder is two-bytes long ('<>') sitting at offsets 10-11.
    signature.set_byte_range([0, 10, 12, 10])
    pdf_bytes = b"AAAAAAAAAA<>BBBBBBBBBB"
    assert signature.get_contents_from_bytes(pdf_bytes) == b""


def test_get_contents_decodes_uppercase_and_lowercase_hex() -> None:
    """Hex decoding is case-insensitive (Python ``bytes.fromhex``)."""
    signature = PDSignature()
    # AAAAA<dEaDbEeF>BBBBB — `<` at 5, body 6..13, `>` at 14, B's at 15..19.
    signature.set_byte_range([0, 5, 15, 5])
    pdf_bytes = b"AAAAA<dEaDbEeF>BBBBB"
    assert signature.get_contents_from_bytes(pdf_bytes) == bytes.fromhex("deadbeef")


def test_get_contents_with_byte_range_out_of_bounds() -> None:
    """Offsets that exceed the document length raise ``IndexError``."""
    signature = PDSignature()
    signature.set_byte_range([0, 100, 200, 100])
    with pytest.raises(IndexError):
        signature.get_contents_from_bytes(b"short")
