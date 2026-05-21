"""Wave 1369 round-out tests for :class:`TTFParser`.

Targets the lesser-tested branches of TTFParser:

* ``_check_scaler_type`` — every supported magic + the rejection path.
* ``_build_directory_entry`` — checksum / offset / length wiring.
* ``parse_tables`` re-run on an already-initialized font (idempotent).
* ``parse_table_headers`` reporting per-mandatory-table errors.
* ``parse_embedded`` permanence (the ``is_embedded`` flag stays flipped).
* ``parse_table_headers`` honours OTF + ``allow_cff`` for the OTF parser
  subclass (returns no error on a real OTTO stream).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders, TTFParser

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def ttf_bytes() -> bytes:
    return _FIXTURE_TTF.read_bytes()


# ---------- _check_scaler_type ---------------------------------------------


def test_check_scaler_accepts_truetype_magic() -> None:
    parser = TTFParser()
    # 0x00010000 is the canonical TrueType scaler; this should not raise.
    parser._check_scaler_type(0x00010000)  # noqa: SLF001


def test_check_scaler_accepts_true_magic() -> None:
    parser = TTFParser()
    parser._check_scaler_type(0x74727565)  # 'true'  # noqa: SLF001


def test_check_scaler_accepts_typ1_magic() -> None:
    parser = TTFParser()
    parser._check_scaler_type(0x74797031)  # 'typ1'  # noqa: SLF001


def test_check_scaler_rejects_otto_with_specific_message() -> None:
    parser = TTFParser()
    with pytest.raises(OSError, match="OTTO"):
        parser._check_scaler_type(0x4F54544F)  # 'OTTO'  # noqa: SLF001


def test_check_scaler_rejects_unknown_with_hex_in_message() -> None:
    parser = TTFParser()
    with pytest.raises(OSError, match="0xCAFEBABE"):
        parser._check_scaler_type(0xCAFEBABE)  # noqa: SLF001


# ---------- _build_directory_entry -----------------------------------------


def test_build_directory_entry_sets_all_fields() -> None:
    parser = TTFParser()
    table = parser._build_directory_entry("name", 0x12345678, 0x4000, 200)  # noqa: SLF001
    assert table is not None
    assert table.get_tag() == "name"
    assert table.get_check_sum() == 0x12345678
    assert table.get_offset() == 0x4000
    assert table.get_length() == 200


def test_build_directory_entry_zero_length_non_glyf_returns_none() -> None:
    parser = TTFParser()
    # Tag 'fpgm' with length 0 — upstream's L394-L398 guard says drop it.
    table = parser._build_directory_entry("fpgm", 0, 0, 0)  # noqa: SLF001
    assert table is None


def test_build_directory_entry_zero_length_glyf_returned() -> None:
    parser = TTFParser()
    # 'glyf' is the only tag legal at length 0.
    table = parser._build_directory_entry("glyf", 0, 0, 0)  # noqa: SLF001
    assert table is not None
    assert table.get_tag() == "glyf"
    assert table.get_length() == 0


# ---------- parse_tables idempotence ---------------------------------------


def test_parse_tables_is_idempotent(ttf_bytes: bytes) -> None:
    """Re-running ``parse_tables`` on a fully-parsed font must not flip
    table state or raise. Upstream guards each per-table load with the
    ``initialized`` flag (TTFParser.java L186-L195) — exercising the
    happy path twice confirms that flag is honoured."""
    parser = TTFParser()
    font = parser.parse(ttf_bytes)
    # First parse_tables ran during parse() via _check_tables. Re-run.
    parser.parse_tables(font)
    parser.parse_tables(font)
    # State unchanged.
    for table in font.get_tables():
        assert table.get_initialized() is True


# ---------- parse_table_headers — error reporting --------------------------


def test_parse_table_headers_reports_table_dir_via_font_load(ttf_bytes: bytes) -> None:
    """Garbled bytes that pass the magic guard but break the directory
    walk must surface as ``set_error(...)``, not as an exception."""
    parser = TTFParser()
    # Valid scaler magic followed by 200 bytes of nonsense — fontTools
    # will raise during directory parse; TTFParser must trap it.
    bad = b"\x00\x01\x00\x00" + b"\xFF" * 200
    headers = parser.parse_table_headers(bad)
    assert headers.get_error() is not None


def test_parse_table_headers_for_otf_parser_tolerates_truetype(
    ttf_bytes: bytes,
) -> None:
    """``OTFParser._check_scaler_type`` deliberately tolerates a TrueType
    scaler too (see comment on that method) — the OTFParser is used by
    upstream as the OpenType-metadata entry point even for TTF-outlined
    fonts shipped as ``.otf``. ``parse_table_headers`` should therefore
    succeed with no error on a real TTF, with the OTF-and-PostScript
    flag set to ``False``."""
    parser = OTFParser()
    headers = parser.parse_table_headers(ttf_bytes)
    assert headers.get_error() is None
    assert headers.is_open_type_post_script() is False


# ---------- parse_embedded flag permanence ----------------------------------


def test_parse_embedded_flips_flag_permanently(ttf_bytes: bytes) -> None:
    """Upstream's ``parseEmbedded`` does ``this.isEmbedded = true`` as a
    side-effect that persists after the call (TTFParser.java line 91).
    Mirror behaviour: a follow-up ``parse`` on the same instance sees
    ``is_embedded`` True too."""
    parser = TTFParser()
    assert parser.is_embedded is False
    parser.parse_embedded(ttf_bytes)
    assert parser.is_embedded is True
    # Subsequent parse() does not reset the flag.
    parser.parse(ttf_bytes)
    assert parser.is_embedded is True


# ---------- FontHeaders default values --------------------------------------


def test_font_headers_initial_state_has_no_error() -> None:
    fh = FontHeaders()
    assert fh.get_error() is None
    assert fh.get_name() is None
    assert fh.get_font_family() is None
    assert fh.get_font_sub_family() is None
    assert fh.get_header_mac_style() is None
    assert fh.get_os2_windows() is None
    assert fh.is_open_type_post_script() is False
    assert fh.get_non_otf_table_gcid_142() is None
    assert fh.get_non_otf_table_gcid142() is None  # numeric-suffix alias
    assert fh.get_otf_registry() is None
    assert fh.get_otf_ordering() is None
    assert fh.get_otf_supplement() == 0


def test_font_headers_set_non_otf_gcid_aliases_agree() -> None:
    """Both ``set_non_otf_gcid_142`` and ``set_non_otf_gcid142`` set the
    same underlying field — the second is the numeric-suffix alias that
    mirrors upstream's ``setNonOtfGcid142`` exactly."""
    fh = FontHeaders()
    fh.set_non_otf_gcid_142(b"first")
    assert fh.get_non_otf_table_gcid_142() == b"first"
    assert fh.get_non_otf_table_gcid142() == b"first"
    fh.set_non_otf_gcid142(b"second")
    assert fh.get_non_otf_table_gcid_142() == b"second"


def test_font_headers_set_otf_ros_round_trip() -> None:
    fh = FontHeaders()
    fh.set_otf_ros("Adobe", "Japan1", 6)
    assert fh.get_otf_registry() == "Adobe"
    assert fh.get_otf_ordering() == "Japan1"
    assert fh.get_otf_supplement() == 6
    # Reset back to None / 0.
    fh.set_otf_ros(None, None, 0)
    assert fh.get_otf_registry() is None
    assert fh.get_otf_ordering() is None
    assert fh.get_otf_supplement() == 0


# ---------- parse_font / parse_embedded_font classmethods -------------------


def test_parse_font_classmethod_returns_truetypefont(ttf_bytes: bytes) -> None:
    font = TTFParser.parse_font(ttf_bytes)
    try:
        # Liberation Sans has a 'head' table.
        assert font.has_table("head")
    finally:
        font.close()


def test_parse_embedded_font_classmethod_returns_truetypefont(
    ttf_bytes: bytes,
) -> None:
    font = TTFParser.parse_embedded_font(ttf_bytes)
    try:
        assert font.has_table("head")
    finally:
        font.close()


# ---------- allow_cff override surface -------------------------------------


def test_otf_parser_allows_cff() -> None:
    assert OTFParser().allow_cff() is True


def test_ttf_parser_rejects_cff_by_default() -> None:
    assert TTFParser().allow_cff() is False


# ---------- check_tables in non-embedded mode -------------------------------


def test_check_tables_missing_required_raises() -> None:
    """``_check_tables`` raises when the font is missing a required table
    and the parser is in non-embedded mode."""

    class StubFont:
        def has_table(self, tag: str) -> bool:
            return tag != "cmap"  # pretend cmap missing

    parser = TTFParser(is_embedded=False)
    with pytest.raises(OSError, match="missing required SFNT tables"):
        parser._check_tables(StubFont())  # type: ignore[arg-type]  # noqa: SLF001


def test_check_tables_in_embedded_mode_skips_validation() -> None:
    class StubFont:
        def has_table(self, tag: str) -> bool:  # noqa: ARG002
            return False

    parser = TTFParser(is_embedded=True)
    # No exception expected.
    parser._check_tables(StubFont())  # type: ignore[arg-type]  # noqa: SLF001
