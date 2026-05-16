"""Tests for the newly-promoted view helpers on :class:`SignaturePane`."""

from __future__ import annotations

from pypdfbox.cos import COSString
from pypdfbox.debugger.signaturepane.signature_pane import SignaturePane


def test_get_text_string_returns_hex_dump_for_non_empty_blob() -> None:
    cos = COSString(b"\x01\x02\x03\x04")
    body = SignaturePane.get_text_string(cos)
    # Hex dump always starts with the eight-digit offset.
    assert body.startswith("00000000")
    assert "0102" in body


def test_get_text_string_empty_blob_falls_back_to_hex_brackets() -> None:
    # Mirrors upstream's IOException fallback: "<" + toHexString() + ">".
    cos = COSString(b"")
    body = SignaturePane.get_text_string(cos)
    assert body.startswith("<")
    assert body.endswith(">")


def test_create_text_view_populates_widget(tk_root) -> None:
    cos = COSString(b"\xde\xad\xbe\xef")
    pane = SignaturePane(tk_root, cos)
    widget = pane.create_text_view(cos)
    body = widget.get("1.0", "end-1c")
    assert body.startswith("00000000")
    assert "dead" in body


def test_create_text_view_alias_matches_public_method() -> None:
    assert SignaturePane._create_asn1_view is SignaturePane.create_text_view
