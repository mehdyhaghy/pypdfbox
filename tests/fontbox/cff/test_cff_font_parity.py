"""Parity tests for the PDFBox-shaped accessors on ``CFFFont``.

We need a real CFF byte stream to exercise these. There is no checked-in
CFF fixture under ``tests/fixtures/`` (CFF outline data is non-trivial
to synthesise by hand the way the TTF tests do for hmtx), so we look in
a couple of well-known macOS / Linux font locations for an OTF whose
``CFF`` table we can re-compile into a standalone byte stream. When the
host has no suitable font available the entire module is skipped — the
suite is still expected to pass on every other module's tests.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont, read_charset, read_encoding

# Candidate OTF locations. First match wins; missing files are skipped.
_OTF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/STIXGeneral.otf",
    "/System/Library/Fonts/Supplemental/STIXGeneralItalic.otf",
    "/usr/share/fonts/opentype/stix/STIXGeneral.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _load_cff_bytes() -> bytes | None:
    """Return raw CFF bytes extracted from the first available OTF, or
    ``None`` when nothing usable is on the host."""
    try:
        from fontTools.ttLib import TTFont  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError:
        return None
    for candidate in _OTF_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            ttf = TTFont(str(path))
            if "CFF " not in ttf:
                continue
            buf = io.BytesIO()
            ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            continue
    return None


_CFF_BYTES = _load_cff_bytes()
_SKIP_REASON = "no CFF/OTF fixture available on this host"


@pytest.fixture(scope="module")
def cff_font() -> CFFFont:
    if _CFF_BYTES is None:
        pytest.skip(_SKIP_REASON)
    return CFFFont.from_bytes(_CFF_BYTES)


def test_get_name_non_empty(cff_font: CFFFont) -> None:
    name = cff_font.get_name()
    assert isinstance(name, str)
    assert name  # at least one PostScript name


def test_get_top_dict_has_charstrings_pointer(cff_font: CFFFont) -> None:
    td = cff_font.get_top_dict()
    assert isinstance(td, dict)
    # CharStrings is mandatory in every CFF Top DICT.
    assert "CharStrings" in td


def test_get_private_dict_has_widths(cff_font: CFFFont) -> None:
    pd = cff_font.get_private_dict()
    assert isinstance(pd, dict)
    # defaultWidthX / nominalWidthX are standard Private DICT entries.
    assert "defaultWidthX" in pd
    assert "nominalWidthX" in pd


def test_get_default_and_nominal_width_x_are_numeric(cff_font: CFFFont) -> None:
    default_w = cff_font.get_default_width_x()
    nominal_w = cff_font.get_nominal_width_x()
    assert isinstance(default_w, float)
    assert isinstance(nominal_w, float)


def test_is_cid_font_for_typical_otf(cff_font: CFFFont) -> None:
    # The candidate fonts we probe (STIX et al.) are all name-keyed,
    # not CID-keyed, so this should be False. The accessor itself just
    # needs to return a bool — that's the parity contract.
    assert cff_font.is_cid_font() is False


def test_get_charset_and_num_char_strings_agree(cff_font: CFFFont) -> None:
    charset = cff_font.get_charset()
    n = cff_font.get_num_char_strings()
    assert isinstance(charset, list)
    assert n > 0
    assert len(charset) == n
    # ".notdef" is always GID 0 in well-formed CFF.
    assert charset[0] == ".notdef"


def test_get_global_and_local_subrs_are_ints(cff_font: CFFFont) -> None:
    g = cff_font.get_global_subrs()
    l_ = cff_font.get_local_subrs()
    assert isinstance(g, int) and g >= 0
    assert isinstance(l_, int) and l_ >= 0
    # Alias must agree with get_global_subrs.
    assert cff_font.get_subrs() == g


def test_get_property_known_keys(cff_font: CFFFont) -> None:
    # FontBBox is mandatory in CFF Top DICT.
    bbox = cff_font.get_property("FontBBox")
    assert bbox is not None
    assert len(bbox) == 4
    # Unknown keys return None.
    assert cff_font.get_property("ThisKeyDoesNotExist") is None


def test_get_glyph_widths_batch_matches_get_width(cff_font: CFFFont) -> None:
    widths = cff_font.get_glyph_widths()
    assert isinstance(widths, dict)
    assert len(widths) == cff_font.get_num_char_strings()
    # Every value is a float; widths cache should agree with single-glyph lookup.
    sample = next(iter(widths))
    assert widths[sample] == cff_font.get_width(sample)


def test_empty_cff_font_accessors_are_safe() -> None:
    """A freshly-constructed ``CFFFont`` (no bytes parsed) must not blow
    up when callers probe the accessors — they should return sensible
    empty / zero values."""
    f = CFFFont()
    assert f.get_name() == ""
    assert f.get_top_dict() == {}
    assert f.get_private_dict() == {}
    assert f.get_charset() == []
    assert f.get_num_char_strings() == 0
    assert f.get_global_subrs() == 0
    assert f.get_local_subrs() == 0
    assert f.get_subrs() == 0
    assert f.is_cid_font() is False
    assert f.get_property("FullName") is None
    assert f.get_default_width_x() == 0.0
    assert f.get_nominal_width_x() == 0.0
    assert f.get_width("A") == 0.0
    assert f.get_path("A") == []
    assert f.get_glyph_widths() == {}
    # Wave 41 round-out additions.
    assert f.get_data() == b""
    assert f.get_global_subr_index() == []
    assert f.get_char_string_bytes() == []
    assert f.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert f.get_font_b_box() == [0.0, 0.0, 0.0, 0.0]
    assert f.get_font_bbox() == [0.0, 0.0, 0.0, 0.0]
    assert f.get_name_for_gid(0) == ".notdef"
    assert f.get_name_for_gid(99) == ".notdef"
    assert f.get_sid_for_gid(0) == 0
    assert f.get_gid_for_sid(0) == 0
    assert f.get_cid_for_gid(0) == 0
    assert f.get_gid_for_cid(0) == 0


def test_get_string_standard_strings_table() -> None:
    """SIDs 0..390 resolve via the Adobe Standard Strings table even on
    an unparsed CFFFont (the table is font-independent)."""
    f = CFFFont()
    assert f.get_string(0) == ".notdef"
    assert f.get_string(1) == "space"
    # Per Adobe Technote #5176 Appendix A, SID 34 = "A".
    assert f.get_string(34) == "A"
    # Negative / out-of-range → empty string.
    assert f.get_string(-1) == ""
    # Past the standard strings range with no font set → empty string.
    assert f.get_string(10_000) == ""


def test_get_sid_resolves_standard_names() -> None:
    f = CFFFont()
    assert f.get_sid(".notdef") == 0
    assert f.get_sid("A") == 34
    assert f.get_sid("space") == 1
    assert f.get_sid("__not_a_real_glyph__") == 0
    assert f.get_sid("") == 0


def test_add_value_to_top_dict_overlay() -> None:
    f = CFFFont()
    f.add_value_to_top_dict("CustomKey", "CustomValue")
    assert f.get_property("CustomKey") == "CustomValue"
    assert f.get_top_dict()["CustomKey"] == "CustomValue"
    # Setting None is a no-op (matches upstream null-guard).
    f.add_value_to_top_dict("OtherKey", None)
    assert "OtherKey" not in f.get_top_dict()


def test_get_data_round_trip(cff_font: CFFFont) -> None:
    """``get_data()`` returns the exact byte payload the font was
    parsed from."""
    raw = cff_font.get_data()
    assert isinstance(raw, bytes)
    assert raw == _CFF_BYTES


def test_charset_sid_round_trip(cff_font: CFFFont) -> None:
    """For a typical name-keyed CFF font GID 0 is .notdef, SID 0."""
    assert cff_font.get_name_for_gid(0) == ".notdef"
    assert cff_font.get_sid_for_gid(0) == 0
    # SID 0 round-trips back to GID 0.
    assert cff_font.get_gid_for_sid(0) == 0
    # The "A" glyph (if present) round-trips through SID lookup.
    charset = cff_font.get_charset()
    if "A" in charset:
        a_gid = charset.index("A")
        a_sid = cff_font.get_sid_for_gid(a_gid)
        # SID for "A" is 34 in the standard strings table; round-trip back.
        assert a_sid == 34
        assert cff_font.get_gid_for_sid(a_sid) == a_gid


def test_get_global_subr_index_returns_bytes_list(cff_font: CFFFont) -> None:
    gsubrs = cff_font.get_global_subr_index()
    assert isinstance(gsubrs, list)
    assert all(isinstance(b, bytes) for b in gsubrs)
    # Count must agree with the int accessor.
    assert len(gsubrs) == cff_font.get_global_subrs()


# ---------- explicit CFF charset / encoding parser tests ----------
# Upstream: org.apache.fontbox.cff.CFFParser.readCharset / readEncoding.
# Adobe Technote #5176 §13 (charsets) and §12 (encodings).


class TestReadCharset:
    """Synthetic byte streams exercising the three charset formats."""

    def test_format_0_reads_card16_sids(self) -> None:
        # Format 0: nGlyphs - 1 Card16 SIDs after .notdef.
        # Three glyphs total (.notdef + 2): SIDs [0, 100, 200].
        data = bytes([0x00, 0x00, 0x64, 0x00, 0xC8])
        stream = io.BytesIO(data)
        out = read_charset(stream, n_glyphs=3)
        assert out == [0, 100, 200]
        # Stream fully consumed.
        assert stream.read() == b""

    def test_format_1_card8_nleft_ranges(self) -> None:
        # Format 1: ranges of (Card16 first, Card8 nLeft).
        # 5 glyphs total = .notdef (implicit) + range [10..13] (nLeft=3).
        data = bytes([0x01, 0x00, 0x0A, 0x03])
        stream = io.BytesIO(data)
        out = read_charset(stream, n_glyphs=5)
        assert out == [0, 10, 11, 12, 13]

    def test_format_1_multiple_ranges(self) -> None:
        # Two ranges: (first=5, nLeft=1) → [5,6]; (first=20, nLeft=2) → [20,21,22].
        # 6 glyphs total (incl. .notdef).
        data = bytes([0x01, 0x00, 0x05, 0x01, 0x00, 0x14, 0x02])
        stream = io.BytesIO(data)
        out = read_charset(stream, n_glyphs=6)
        assert out == [0, 5, 6, 20, 21, 22]

    def test_format_2_card16_nleft_for_large_ranges(self) -> None:
        # Format 2: ranges of (Card16 first, Card16 nLeft) — used by CID
        # fonts where nLeft can exceed 255. Synthesise a single range
        # covering 300 CIDs.
        n_left = 299  # 300 entries in the range
        n_glyphs = 1 + 300
        data = bytes([0x02]) + struct.pack(">H", 1000) + struct.pack(">H", n_left)
        stream = io.BytesIO(data)
        out = read_charset(stream, n_glyphs=n_glyphs)
        assert out[0] == 0
        assert out[1] == 1000
        assert out[-1] == 1000 + n_left
        assert len(out) == n_glyphs

    def test_unknown_format_raises(self) -> None:
        stream = io.BytesIO(bytes([0x05]))
        with pytest.raises(ValueError, match="charset format"):
            read_charset(stream, n_glyphs=2)

    def test_explicit_fmt_skips_format_byte(self) -> None:
        # When fmt is supplied, the helper does NOT consume a format byte.
        data = bytes([0x00, 0x07])  # raw Card16 = 7
        stream = io.BytesIO(data)
        out = read_charset(stream, n_glyphs=2, fmt=0)
        assert out == [0, 7]


class TestReadEncoding:
    """Synthetic byte streams exercising both encoding formats and the
    supplement, plus the high-bit-set form."""

    # Charset for the test fonts: GID 0=.notdef (SID 0), GID 1=SID 100,
    # GID 2=SID 200, GID 3=SID 300.
    CHARSET = [0, 100, 200, 300]

    def test_format_0_simple_codes(self) -> None:
        # nCodes=3: codes 0x41 ('A'), 0x42 ('B'), 0x43 ('C') → GIDs 1,2,3.
        data = bytes([0x00, 0x03, 0x41, 0x42, 0x43])
        stream = io.BytesIO(data)
        encoding, sup = read_encoding(stream, self.CHARSET)
        assert sup == []
        assert encoding[0x41] == 100
        assert encoding[0x42] == 200
        assert encoding[0x43] == 300
        # Untouched codes stay 0.
        assert encoding[0] == 0
        assert encoding[0xFF] == 0
        assert len(encoding) == 256

    def test_format_1_range_based(self) -> None:
        # Single range: code=0x41, nLeft=2 → 3 codes [0x41, 0x42, 0x43]
        # mapping to GIDs 1,2,3.
        data = bytes([0x01, 0x01, 0x41, 0x02])
        stream = io.BytesIO(data)
        encoding, sup = read_encoding(stream, self.CHARSET)
        assert sup == []
        assert encoding[0x41] == 100
        assert encoding[0x42] == 200
        assert encoding[0x43] == 300

    def test_format_0_with_supplement_high_bit(self) -> None:
        # Format byte 0x80 = format 0 + supplement bit.
        # Base: nCodes=1, code 0x41 → GID 1 (SID 100).
        # Supplement: nSups=2, (0x42 → SID 999), (0x41 → SID 555 — overrides base).
        data = (
            bytes([0x80, 0x01, 0x41])
            + bytes([0x02, 0x42])
            + struct.pack(">H", 999)
            + bytes([0x41])
            + struct.pack(">H", 555)
        )
        stream = io.BytesIO(data)
        encoding, sup = read_encoding(stream, self.CHARSET)
        # Supplement entries returned in stream order.
        assert sup == [(0x42, 999), (0x41, 555)]
        # Supplement applied to encoding (last write wins for 0x41).
        assert encoding[0x42] == 999
        assert encoding[0x41] == 555

    def test_format_1_with_supplement_high_bit(self) -> None:
        # Format byte 0x81 = format 1 + supplement bit.
        # Single range: code=0x30, nLeft=1 → codes 0x30, 0x31 → GIDs 1,2.
        # Supplement: nSups=1, (0x99 → SID 777).
        data = (
            bytes([0x81, 0x01, 0x30, 0x01])
            + bytes([0x01, 0x99])
            + struct.pack(">H", 777)
        )
        stream = io.BytesIO(data)
        encoding, sup = read_encoding(stream, self.CHARSET)
        assert encoding[0x30] == 100
        assert encoding[0x31] == 200
        assert sup == [(0x99, 777)]
        assert encoding[0x99] == 777

    def test_unknown_encoding_format_raises(self) -> None:
        # Low 7 bits = 5 (not 0 or 1) → ValueError.
        stream = io.BytesIO(bytes([0x05]))
        with pytest.raises(ValueError, match="encoding format"):
            read_encoding(stream, self.CHARSET)

    def test_explicit_fmt_byte_skips_read(self) -> None:
        # nCodes=1, code 0x10 → GID 1 (SID 100).
        data = bytes([0x01, 0x10])
        stream = io.BytesIO(data)
        encoding, sup = read_encoding(stream, self.CHARSET, fmt_byte=0x00)
        assert encoding[0x10] == 100
        assert sup == []

    def test_truncated_stream_raises_eof(self) -> None:
        # Format 0 with promised nCodes=3 but only 1 code byte present.
        stream = io.BytesIO(bytes([0x00, 0x03, 0x41]))
        with pytest.raises(EOFError):
            read_encoding(stream, self.CHARSET)


# ---------- set_name override (mirrors CFFFont.setName) ----------


def test_set_name_overrides_fontset_name() -> None:
    """``set_name`` populates the override consulted by ``get_name``
    and the ``name`` property — round-trip and clear semantics both
    work."""
    f = CFFFont()
    # Nothing parsed → empty default.
    assert f.get_name() == ""
    f.set_name("CustomFontName")
    assert f.get_name() == "CustomFontName"
    assert f.name == "CustomFontName"
    # Clearing the override restores the default ("" for an unparsed font).
    f.set_name(None)
    assert f.get_name() == ""


def test_set_name_takes_precedence_over_parsed_name(cff_font: CFFFont) -> None:
    """When the font set already has a name, ``set_name`` still wins."""
    original = cff_font.get_name()
    assert original  # parsed font must have a non-empty name
    try:
        cff_font.set_name("Synthetic-Override")
        assert cff_font.get_name() == "Synthetic-Override"
    finally:
        cff_font.set_name(None)
    assert cff_font.get_name() == original


# ---------- __repr__ (mirrors CFFFont.toString) ----------


def test_repr_shape_unparsed() -> None:
    """``repr`` mirrors upstream ``toString()`` shape:
    ``ClassName[name=..., topDict=..., charset=..., charStrings=...]``."""
    f = CFFFont()
    text = repr(f)
    assert text.startswith("CFFFont[")
    assert "name=" in text
    assert "topDict=" in text
    assert "charset=" in text
    assert "charStrings=" in text
    assert text.endswith("]")


def test_repr_includes_font_name(cff_font: CFFFont) -> None:
    text = repr(cff_font)
    assert cff_font.get_name() in text
    # charStrings count appears as a number, not a byte dump.
    assert f"charStrings={cff_font.get_num_char_strings()}" in text
