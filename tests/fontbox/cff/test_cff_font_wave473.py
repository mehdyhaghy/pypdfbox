from __future__ import annotations

from pypdfbox.fontbox.cff.cff_font import CFFFont


class _StringsWithoutTable:
    pass


class _FontSetWithoutStringTable:
    fontNames = ["Wave473"]  # noqa: N815
    strings = _StringsWithoutTable()


class _RaisingCharStringsTop:
    GlobalSubrs = None  # noqa: N815
    Private = None
    rawDict: dict[str, object] = {}
    charset = None

    @property
    def CharStrings(self) -> object:  # noqa: N802
        msg = "no charstrings"
        raise ValueError(msg)


class _NoPrivateTop:
    FontMatrix = [0.001, 0, 0, 0.001, 0, 0]  # noqa: N815
    GlobalSubrs: list[object] = []  # noqa: N815
    rawDict: dict[str, object] = {}
    charset = [".notdef", "A"]
    CharStrings = {"A": object()}  # noqa: N815


def test_wave473_defensive_accessors_handle_missing_private_charset_and_subrs() -> None:
    font = CFFFont()
    font._top = _RaisingCharStringsTop()  # noqa: SLF001

    assert font.get_private_dict() == {}
    assert font.get_charset() == []
    assert font.get_num_char_strings() == 0
    assert font.get_global_subrs() == 0
    assert font.get_local_subrs() == 0
    assert font.get_subrs() == 0
    assert font.get_global_subr_index() == []
    assert font.get_char_string_bytes() == []
    assert font.get_default_width_x() == 0.0
    assert font.get_nominal_width_x() == 0.0
    assert font.get_glyph_widths() == {}
    assert font.has_glyph("A") is False


def test_wave473_string_sid_helpers_tolerate_missing_private_string_table() -> None:
    font = CFFFont()
    font._fontset = _FontSetWithoutStringTable()  # noqa: SLF001

    assert font.get_gid_for_sid(-1) == 0
    assert font.get_sid("") == 0
    assert font.get_sid("notInStandardOrPrivateStrings") == 0
    assert font.get_string(CFFFont.NUM_STANDARD_STRINGS) == ""


def test_wave473_unparsed_font_and_no_private_width_lookup_defaults() -> None:
    assert CFFFont().get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert CFFFont().has_glyph("A") is False

    font = CFFFont()
    font._top = _NoPrivateTop()  # noqa: SLF001

    assert font.get_width("A") == 0.0
    assert "A" not in font._widths  # noqa: SLF001
