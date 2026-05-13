"""Hand-written tests for the Wave 1304 writer-surface additions.

Exercises:

* :meth:`TTFParser.parse_font` — static-style parse convenience.
* :meth:`TTFParser.parse_embedded_font` — static-style embedded parse.
* :meth:`TrueTypeFont.save` — fontTools-backed SFNT serialiser, round-trip.
* :meth:`TrueTypeFont.get_naming_table` — naming-table accessor alias.
* :meth:`TrueTypeFont.get_name` — extended four-arg overload that
  delegates to :meth:`NamingTable.get_name`.

The fixture is the bundled ``LiberationSans-Regular.ttf`` (already
shipped under ``tests/fixtures/fontbox/ttf/``) — no new fixtures are
introduced.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_parser import TTFParser

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def fixture_bytes() -> bytes:
    return _FIXTURE.read_bytes()


# ---------------------------------------------------------------------
# TTFParser.parse_font / parse_embedded_font
# ---------------------------------------------------------------------


class TestParserStaticConvenience:
    def test_parse_font_from_bytes(self, fixture_bytes: bytes) -> None:
        font = TTFParser.parse_font(fixture_bytes)
        try:
            assert isinstance(font, TrueTypeFont)
            assert font.get_units_per_em() > 0
            assert font.get_number_of_glyphs() > 0
        finally:
            font.close()

    def test_parse_font_from_path_str(self) -> None:
        font = TTFParser.parse_font(str(_FIXTURE))
        try:
            assert isinstance(font, TrueTypeFont)
            # Sanity: PostScript name is non-empty.
            assert font.get_name()
        finally:
            font.close()

    def test_parse_font_from_pathlike(self) -> None:
        font = TTFParser.parse_font(_FIXTURE)
        try:
            assert isinstance(font, TrueTypeFont)
        finally:
            font.close()

    def test_parse_font_from_file_like(self, fixture_bytes: bytes) -> None:
        with io.BytesIO(fixture_bytes) as buf:
            font = TTFParser.parse_font(buf)
        try:
            assert isinstance(font, TrueTypeFont)
        finally:
            font.close()

    def test_parse_embedded_font_tolerates_default_flags(
        self, fixture_bytes: bytes
    ) -> None:
        # The fixture is a complete TTF, so embedded-mode should still
        # succeed (embedded mode only relaxes the mandatory-table check).
        font = TTFParser.parse_embedded_font(fixture_bytes)
        try:
            assert isinstance(font, TrueTypeFont)
            assert font.has_table("head")
        finally:
            font.close()


# ---------------------------------------------------------------------
# TrueTypeFont.save — fontTools round-trip
# ---------------------------------------------------------------------


def _set_custom_name(
    font: TrueTypeFont,
    name_id: int,
    value: str,
    *,
    platform_id: int = 3,
    plat_enc_id: int = 1,
    lang_id: int = 0x0409,
) -> None:
    """Inject ``value`` as a name-table entry on the live fontTools
    ``TTFont`` so the next ``save()`` writes it out."""
    pytest.importorskip("fontTools")
    from fontTools.ttLib.tables._n_a_m_e import NameRecord as FtNameRecord

    nr = FtNameRecord()
    nr.nameID = name_id
    nr.platformID = platform_id
    nr.platEncID = plat_enc_id
    nr.langID = lang_id
    nr.string = value
    font._tt["name"].names.append(nr)  # noqa: SLF001


class TestTrueTypeFontSave:
    def test_save_to_bytes_io_round_trip(self, fixture_bytes: bytes) -> None:
        font = TTFParser.parse_font(fixture_bytes)
        try:
            sink = io.BytesIO()
            font.save(sink)
        finally:
            font.close()
        payload = sink.getvalue()
        assert payload, "save() must write a non-empty SFNT stream"
        # The header should still be a recognisable SFNT magic.
        assert payload[:4] in (
            b"\x00\x01\x00\x00",  # TrueType outlines
            b"true",
            b"OTTO",  # CFF outlines (LiberationSans is TrueType, but be defensive)
            b"typ1",
        )
        # Re-parse the saved bytes — must still be a usable TTF.
        reparsed = TTFParser.parse_font(payload)
        try:
            assert reparsed.get_number_of_glyphs() > 0
            assert reparsed.has_table("name")
        finally:
            reparsed.close()

    def test_save_modification_survives_round_trip(
        self, fixture_bytes: bytes, tmp_path: Path
    ) -> None:
        font = TTFParser.parse_font(fixture_bytes)
        # Use a high name_id (1000) that no real font ships, so we can
        # be sure the modification — not a pre-existing record — round
        # trips. The four-arg form of get_name lets us assert the exact
        # platform/encoding/language triple we wrote.
        marker = "pypdfbox-wave-1304-marker"
        try:
            _set_custom_name(font, 1000, marker)
            out_path = tmp_path / "modified.ttf"
            font.save(out_path)
        finally:
            font.close()
        assert out_path.exists()

        reparsed = TTFParser.parse_font(out_path)
        try:
            naming = reparsed.get_naming_table()
            assert naming is not None
            looked_up = naming.get_name(
                1000,
                NameRecord.PLATFORM_WINDOWS,
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
                NameRecord.LANGUAGE_WINDOWS_EN_US,
            )
            assert looked_up == marker
        finally:
            reparsed.close()

    def test_save_to_str_path(
        self, fixture_bytes: bytes, tmp_path: Path
    ) -> None:
        out_path = tmp_path / "via_str.ttf"
        font = TTFParser.parse_font(fixture_bytes)
        try:
            font.save(os.fspath(out_path))
        finally:
            font.close()
        assert out_path.is_file()
        assert out_path.stat().st_size > 0


# ---------------------------------------------------------------------
# TrueTypeFont.get_naming_table + extended get_name
# ---------------------------------------------------------------------


class TestNameTableAccessors:
    def test_get_naming_table_is_alias(self, fixture_bytes: bytes) -> None:
        font = TTFParser.parse_font(fixture_bytes)
        try:
            a = font.get_naming_table()
            b = font.get_naming()
            assert a is b
            assert isinstance(a, NamingTable)
        finally:
            font.close()

    def test_get_name_no_args_returns_post_script(
        self, fixture_bytes: bytes
    ) -> None:
        font = TTFParser.parse_font(fixture_bytes)
        try:
            ps = font.get_name()
            assert ps == "LiberationSans"
        finally:
            font.close()

    def test_get_name_with_name_id_only(self, fixture_bytes: bytes) -> None:
        font = TTFParser.parse_font(fixture_bytes)
        try:
            family = font.get_name(1)  # nameID 1 = family
            assert family == "Liberation Sans"
        finally:
            font.close()

    def test_get_name_with_full_quadruplet(self, fixture_bytes: bytes) -> None:
        font = TTFParser.parse_font(fixture_bytes)
        try:
            family = font.get_name(
                1,
                NameRecord.PLATFORM_WINDOWS,
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
                NameRecord.LANGUAGE_WINDOWS_EN_US,
            )
            assert family == "Liberation Sans"
        finally:
            font.close()

    def test_get_name_missing_returns_none(self, fixture_bytes: bytes) -> None:
        font = TTFParser.parse_font(fixture_bytes)
        try:
            # Name ID 999 should not exist in the fixture.
            assert font.get_name(999) is None
        finally:
            font.close()
