"""Parity tests for PDCIDFontType2 upstream-named accessors.

Covers ``get_cid_to_gid_map_bytes``, ``is_identity_cid_to_gid_map``,
``code_to_gid``, ``code_to_cid``, ``is_embedded``, and the lazy
``get_true_type_font`` / ``set_true_type_font`` plumbing for embedded
font program streams.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ---------- get_cid_to_gid_map_bytes (upstream-shape: bytes | None) ----------


def test_get_cid_to_gid_map_bytes_none_when_absent() -> None:
    font = PDCIDFontType2()
    assert font.get_cid_to_gid_map_bytes() is None


def test_get_cid_to_gid_map_bytes_none_for_identity_name() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    # Upstream: /Identity collapses to None — callers fall back to
    # identity cid->gid mapping.
    assert font.get_cid_to_gid_map_bytes() is None


def test_get_cid_to_gid_map_bytes_returns_stream_payload() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    payload = b"\x00\x01\x00\x02\x00\x03"
    stream.set_data(payload)
    font.set_cid_to_gid_map(stream)
    assert font.get_cid_to_gid_map_bytes() == payload


# ---------- is_identity_cid_to_gid_map ----------


def test_is_identity_cid_to_gid_map_true_when_absent() -> None:
    # Spec default: an unset /CIDToGIDMap is treated as /Identity.
    font = PDCIDFontType2()
    assert font.is_identity_cid_to_gid_map() is True


def test_is_identity_cid_to_gid_map_true_for_identity_name() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.is_identity_cid_to_gid_map() is True


def test_is_identity_cid_to_gid_map_false_for_stream() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(b"\x00\x05")
    font.set_cid_to_gid_map(stream)
    assert font.is_identity_cid_to_gid_map() is False


# ---------- code_to_gid (identity for /Identity) ----------


def test_code_to_gid_identity_when_no_cid_to_gid_map() -> None:
    font = PDCIDFontType2()
    assert font.code_to_gid(0) == 0
    assert font.code_to_gid(7) == 7
    assert font.code_to_gid(0xABCD) == 0xABCD


def test_code_to_gid_identity_for_identity_name() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.code_to_gid(0) == 0
    assert font.code_to_gid(42) == 42


def test_code_to_gid_uses_stream_for_explicit_map() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    # CID 0 -> GID 0x0001, CID 1 -> GID 0x0002, CID 2 -> GID 0x0003
    stream.set_data(b"\x00\x01\x00\x02\x00\x03")
    font.set_cid_to_gid_map(stream)
    assert font.code_to_gid(0) == 1
    assert font.code_to_gid(1) == 2
    assert font.code_to_gid(2) == 3
    # CIDs past the table -> 0 (matches PDFBox embedded-font path).
    assert font.code_to_gid(99) == 0


# ---------- code_to_cid (identity — parent CMap already mapped) ----------


def test_code_to_cid_default_identity() -> None:
    font = PDCIDFontType2()
    assert font.code_to_cid(0) == 0
    assert font.code_to_cid(257) == 257
    assert font.code_to_cid(0xFFFF) == 0xFFFF


# ---------- is_embedded ----------


def test_is_embedded_false_when_no_descriptor() -> None:
    font = PDCIDFontType2()
    assert font.is_embedded() is False


def test_is_embedded_false_when_descriptor_has_no_font_file2() -> None:
    font = PDCIDFontType2()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_embedded() is False


def test_is_embedded_true_when_font_file2_present() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


# ---------- get_true_type_font / set_true_type_font ----------


def test_get_true_type_font_none_when_no_descriptor() -> None:
    font = PDCIDFontType2()
    assert font.get_true_type_font() is None


def test_get_true_type_font_none_when_no_font_file2() -> None:
    font = PDCIDFontType2()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.get_true_type_font() is None


def test_get_true_type_font_none_for_unparseable_font_file2() -> None:
    # Garbage bytes -> fontTools fails to parse -> None (logged, not raised).
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"not-a-real-ttf")
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    assert font.get_true_type_font() is None


def test_set_true_type_font_injects_and_caches() -> None:
    # Bypass /FontFile2 — sentinel object stands in for a parsed TTF.
    font = PDCIDFontType2()
    sentinel = object()
    font.set_true_type_font(sentinel)  # type: ignore[arg-type]
    # The cache holds the injected value; subsequent reads return it
    # without touching the (absent) descriptor.
    assert font._ttf is sentinel  # noqa: SLF001


def test_set_true_type_font_none_marks_attempted() -> None:
    font = PDCIDFontType2()
    font.set_true_type_font(None)
    # Internal sentinel -- "tried, no program available".
    assert font._ttf is False  # noqa: SLF001
    assert font.get_true_type_font() is None


# ---------- get_glyph_path (empty when no embedded program) ----------


def test_get_glyph_path_empty_when_not_embedded() -> None:
    font = PDCIDFontType2()
    assert font.get_glyph_path(65) == []


def test_get_glyph_path_empty_for_unparseable_font_file2() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"not-a-real-ttf")
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    assert font.get_glyph_path(65) == []
