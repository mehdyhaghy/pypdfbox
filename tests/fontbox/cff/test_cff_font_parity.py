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
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont

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
        from fontTools.ttLib import TTFont  # noqa: PLC0415
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
