from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cff.fd_array import FDArray
from pypdfbox.fontbox.cff.type1_char_string import Type1CharString


def test_wave700_type1_local_subrs_private_none_returns_empty() -> None:
    class _Top:
        Private = None  # noqa: N815

    font = CFFType1Font()
    font._top = _Top()  # noqa: SLF001

    assert font.get_local_subr_index() == []


def test_wave700_type1_unknown_predefined_encoding_falls_back_to_notdef() -> None:
    class _Top:
        Encoding = "UnexpectedEncoding"  # noqa: N815
        rawDict: dict[str, Any] = {}  # noqa: N815

    font = CFFType1Font()
    font._top = _Top()  # noqa: SLF001

    assert font.code_to_name(65) == ".notdef"
    assert font.name_to_code("A") == -1


def test_wave700_type1_name_to_code_empty_or_missing_encoding() -> None:
    font = CFFType1Font()

    assert font.name_to_code("") == -1
    assert font.name_to_code("A") == -1


def test_wave700_type1_custom_encoding_bad_lookup_shapes_are_safe() -> None:
    class _Mapping:
        def __getitem__(self, code: int) -> str:
            raise KeyError(code)

    class _NotIterable:
        def __iter__(self) -> object:
            raise TypeError

    class _Top:
        Encoding: Any = _Mapping()  # noqa: N815
        rawDict: dict[str, Any] = {}  # noqa: N815

    font = CFFType1Font()
    font._top = _Top()  # noqa: SLF001

    assert font.code_to_name(65) == ".notdef"

    _Top.Encoding = _NotIterable()
    assert font.name_to_code("A") == -1


def test_wave700_type1_has_glyph_rejects_empty_name() -> None:
    assert CFFType1Font().has_glyph("") is False


def test_wave700_fd_array_len_type_error_reports_empty() -> None:
    class _NoLen:
        def __len__(self) -> int:
            raise TypeError

    arr = FDArray.from_fonttools(_NoLen())

    assert arr.size() == 0


def test_wave700_fd_array_private_widths_missing_private_dict() -> None:
    class _Font:
        rawDict: dict[str, Any] = {}  # noqa: N815
        Private = None  # noqa: N815

    arr = FDArray.from_fonttools([_Font()])

    assert arr.get_private_dict(0) == {}
    assert arr.get_default_width_x(0) == 0.0
    assert arr.get_nominal_width_x(0) == 0.0


def test_wave700_fd_array_raw_lookup_exceptions_are_safe() -> None:
    class _BadLookup:
        def __len__(self) -> int:
            return 1

        def __getitem__(self, index: int) -> object:
            raise KeyError(index)

    arr = FDArray.from_fonttools(_BadLookup())

    assert arr.get_raw_font_dict(0) is None
    assert arr[0] == {}


def test_wave700_fd_array_repr_includes_size() -> None:
    assert repr(FDArray(None)) == "FDArray(size=0)"


def test_wave700_type1_charstring_width_uses_cached_path_width() -> None:
    cs = Type1CharString(None, "F", "A", None)
    cs._cached_path = [("moveto", 1.0, 2.0)]  # noqa: SLF001
    cs._t1.width = 321.0  # noqa: SLF001

    assert cs.get_width() == 321.0


def test_wave700_type1_charstring_bad_program_width_and_path_are_safe() -> None:
    cs = Type1CharString(None, "F", "A", ["not-an-operator"])

    assert cs.get_width() == 0.0
    assert cs.get_path() == []


def test_wave700_type1_charstring_bounds_include_curve_control_points() -> None:
    program = [
        0,
        500,
        "hsbw",
        0,
        0,
        "rmoveto",
        10,
        20,
        30,
        40,
        50,
        60,
        "rrcurveto",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "curve", program)

    assert cs.get_bounds() == (0.0, 0.0, 90.0, 120.0)


def test_wave700_type1_charstring_stringifies_name_tokens() -> None:
    class _Command:
        name = "hsbw"

    cs = Type1CharString(None, "F", "A", [0, 500, _Command()])

    assert str(cs) == "[0  500  hsbw]"


def test_wave700_type1_charstring_coerces_unknown_program_token_to_string() -> None:
    class _Token:
        def __str__(self) -> str:
            return "endchar"

    cs = Type1CharString(None, "F", "A", [0, 500, "hsbw", _Token()])

    assert cs.t1.program[-1] == "endchar"
