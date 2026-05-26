"""Tests for :mod:`pypdfbox.pdmodel.font.pd_type1_font_embedder`.

We can't easily round-trip a real PFB without a fixture, so we cover:

* ``_parse_pfb_segments`` — the segment-marker decoder.
* ``build_font_descriptor_from_metrics`` — the AFM-based factory used
  by the Standard 14 path.
* The Type1Encoding adapter for list-based encoding arrays.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.pd_type1_font_embedder import (
    PDType1FontEmbedder,
    _parse_pfb_segments,
    _Type1EncodingAdapter,
)


def test_parse_pfb_with_three_segments() -> None:
    # Build a tiny synthetic PFB: marker (0x80), kind, 4-byte LE length,
    # body. Three segments + EOF marker.
    seg1 = b"abc"
    seg2 = b"defg"
    seg3 = b"hi"
    pfb = (
        b"\x80\x01" + len(seg1).to_bytes(4, "little") + seg1
        + b"\x80\x02" + len(seg2).to_bytes(4, "little") + seg2
        + b"\x80\x01" + len(seg3).to_bytes(4, "little") + seg3
        + b"\x80\x03"  # EOF
    )
    body, lengths = _parse_pfb_segments(pfb)
    assert body == seg1 + seg2 + seg3
    assert lengths == [len(seg1), len(seg2), len(seg3)]


def test_parse_pfa_fallback_for_non_marker() -> None:
    # If the input lacks the 0x80 marker we return the buffer as one segment.
    pfa = b"%!PS-AdobeFont-1.0..."
    body, lengths = _parse_pfb_segments(pfa)
    assert body == pfa
    assert lengths[0] == len(pfa)
    assert lengths[1] == 0
    assert lengths[2] == 0


def test_build_font_descriptor_from_metrics_populates_fields() -> None:
    class _Metrics:
        def get_encoding_scheme(self) -> str:
            return "AdobeStandardEncoding"

        def get_font_name(self) -> str:
            return "Helvetica"

        def get_family_name(self) -> str:
            return "Helvetica"

        def get_font_bbox(self) -> tuple[int, int, int, int]:
            return (-166, -225, 1000, 931)

        def get_italic_angle(self) -> float:
            return 0.0

        def get_ascender(self) -> float:
            return 718.0

        def get_descender(self) -> float:
            return -207.0

        def get_cap_height(self) -> float:
            return 718.0

        def get_x_height(self) -> float:
            return 523.0

        def get_average_character_width(self) -> float:
            return 441.0

        def get_character_set(self) -> str:
            return ""

    fd = PDType1FontEmbedder.build_font_descriptor_from_metrics(_Metrics())
    assert fd.get_font_name() == "Helvetica"
    # Non-symbolic because encoding scheme != "FontSpecific".
    assert fd.is_non_symbolic() is True


def test_build_font_descriptor_from_metrics_marks_symbolic_when_specific() -> None:
    class _Metrics:
        def get_encoding_scheme(self) -> str:
            return "FontSpecific"

        def get_font_name(self) -> str:
            return "Symbol"

    fd = PDType1FontEmbedder.build_font_descriptor_from_metrics(_Metrics())
    assert fd.is_symbolic() is True


def test_type1_encoding_adapter_forwards_code_map() -> None:
    # The adapter now forwards pypdfbox Type1Font.get_encoding() (already a
    # resolved code -> glyph-name map).
    class _T1:
        def get_encoding(self) -> dict[int, str]:
            return {0: "one", 1: "two", 2: "three"}

    adapter = _Type1EncodingAdapter(_T1())  # type: ignore[arg-type]
    assert adapter.get_code_to_name_map() == {0: "one", 1: "two", 2: "three"}


def test_type1_encoding_adapter_for_empty_map() -> None:
    # An empty map (FontSpecific / built-in encoding) -> empty.
    class _T1:
        def get_encoding(self) -> dict[int, str]:
            return {}

    adapter = _Type1EncodingAdapter(_T1())  # type: ignore[arg-type]
    assert adapter.get_code_to_name_map() == {}


def test_type1_encoding_adapter_with_no_accessor() -> None:
    class _T1:
        pass

    adapter = _Type1EncodingAdapter(_T1())  # type: ignore[arg-type]
    assert adapter.get_code_to_name_map() == {}
