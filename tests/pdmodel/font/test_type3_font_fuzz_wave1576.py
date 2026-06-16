"""Fuzz / parity hammering for :class:`PDType3Font` (wave 1576).

Targets the Type 3 font dictionary surface against upstream PDFBox 3.0.7
``PDType3Font`` behaviour:

- ``get_font_matrix`` — spec default ``[0.001 0 0 0.001 0 0]`` when the
  ``/FontMatrix`` entry is missing or malformed; honoured 6-numeric array
  otherwise (upstream ``checkFontMatrixValues``).
- ``get_char_proc(name)`` / ``get_char_proc(code)`` — code resolves through
  ``/Encoding`` to a glyph name, then through ``/CharProcs``; a missing name
  or missing/non-stream entry yields ``None``.
- ``get_width(code)`` — ``/Widths[code - /FirstChar]`` inside the
  FirstChar..LastChar window; NOT scaled by /FontMatrix (upstream returns
  the raw width; the matrix scaling happens only in ``getDisplacement``).
- ``/FontBBox`` accessor — built from any COSArray (zero-padded / truncated
  to four corners, corners normalised min/max).
- ``/Encoding`` required — a Type 3 font with no /Encoding resolves no glyph
  procs by code (upstream ``getCharProc(int)`` returns ``null``).
- ``d0`` / ``d1`` glyph-metric operators inside a char proc set the width.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

_DEFAULT_MATRIX = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


# ---------- builders ----------


def _glyph(body: bytes) -> COSStream:
    s = COSStream()
    s.set_raw_data(body)
    return s


def _font_with(
    char_procs: dict[str, COSStream] | None = None,
    encoding_differences: dict[int, str] | None = None,
    widths: list[float] | None = None,
    first_char: int | None = None,
    font_matrix: list[float] | None = None,
    font_bbox: COSArray | None = None,
) -> PDType3Font:
    d = COSDictionary()
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    if char_procs is not None:
        cp = COSDictionary()
        for name, stream in char_procs.items():
            cp.set_item(COSName.get_pdf_name(name), stream)
        d.set_item(COSName.get_pdf_name("CharProcs"), cp)
    if encoding_differences is not None:
        enc = COSDictionary()
        diffs = COSArray()
        for code in sorted(encoding_differences):
            diffs.add(COSInteger.get(code))
            diffs.add(COSName.get_pdf_name(encoding_differences[code]))
        enc.set_item(COSName.get_pdf_name("Differences"), diffs)
        d.set_item(COSName.get_pdf_name("Encoding"), enc)
    if widths is not None:
        d.set_item(
            COSName.get_pdf_name("Widths"),
            COSArray([COSFloat(float(w)) for w in widths]),
        )
    if first_char is not None:
        d.set_int(COSName.get_pdf_name("FirstChar"), first_char)
        last = first_char + (len(widths) - 1 if widths else 0)
        d.set_int(COSName.get_pdf_name("LastChar"), last)
    if font_matrix is not None:
        d.set_item(
            COSName.get_pdf_name("FontMatrix"),
            COSArray([COSFloat(float(v)) for v in font_matrix]),
        )
    if font_bbox is not None:
        d.set_item(COSName.get_pdf_name("FontBBox"), font_bbox)
    return PDType3Font(d)


# ---------- /FontMatrix default vs honoured ----------


def test_font_matrix_default_when_missing() -> None:
    assert PDType3Font().get_font_matrix() == _DEFAULT_MATRIX


@pytest.mark.parametrize(
    "matrix",
    [
        [0.001, 0.0, 0.0, 0.001, 0.0, 0.0],
        [0.01, 0.0, 0.0, 0.01, 0.0, 0.0],
        [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        [0.002, 0.0, 0.0, 0.004, 5.0, 6.0],
        [0.001, 0.1, 0.2, 0.001, 0.0, 0.0],
    ],
    ids=["spec_1000", "em_100", "identity", "non_square", "skewed"],
)
def test_font_matrix_honoured_when_six_numeric(matrix: list[float]) -> None:
    font = _font_with(font_matrix=matrix)
    assert font.get_font_matrix() == pytest.approx(matrix, rel=1e-6)


@pytest.mark.parametrize(
    "size", [0, 1, 3, 5, 7, 12], ids=lambda n: f"len{n}"
)
def test_font_matrix_falls_back_when_wrong_length(size: int) -> None:
    arr = COSArray([COSFloat(0.5) for _ in range(size)])
    font = PDType3Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("FontMatrix"), arr)
    assert font.get_font_matrix() == _DEFAULT_MATRIX


def test_font_matrix_falls_back_when_entry_non_numeric() -> None:
    arr = COSArray(
        [
            COSFloat(0.001),
            COSFloat(0.0),
            COSName.get_pdf_name("oops"),  # non-numeric corner
            COSFloat(0.001),
            COSFloat(0.0),
            COSFloat(0.0),
        ]
    )
    font = PDType3Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("FontMatrix"), arr)
    assert font.get_font_matrix() == _DEFAULT_MATRIX


def test_font_matrix_falls_back_when_not_array() -> None:
    font = PDType3Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("FontMatrix"), COSInteger.get(5)
    )
    assert font.get_font_matrix() == _DEFAULT_MATRIX


def test_check_font_matrix_values_static() -> None:
    good = COSArray([COSInteger.get(i) for i in range(6)])
    bad_len = COSArray([COSInteger.get(i) for i in range(5)])
    bad_type = COSArray(
        [COSInteger.get(0)] * 5 + [COSName.get_pdf_name("x")]
    )
    assert PDType3Font.check_font_matrix_values(good) is True
    assert PDType3Font.check_font_matrix_values(bad_len) is False
    assert PDType3Font.check_font_matrix_values(bad_type) is False
    assert PDType3Font.check_font_matrix_values(None) is False


# ---------- get_char_proc(name) ----------


def test_char_proc_by_name_present() -> None:
    glyph = _glyph(b"100 0 d0\n")
    font = _font_with(char_procs={"a": glyph})
    assert font.get_char_proc("a") is glyph


def test_char_proc_by_name_missing_returns_none() -> None:
    font = _font_with(char_procs={"a": _glyph(b"100 0 d0\n")})
    assert font.get_char_proc("zzz") is None


def test_char_proc_by_name_no_charprocs_dict_returns_none() -> None:
    assert PDType3Font().get_char_proc("a") is None


def test_char_proc_by_name_non_stream_entry_returns_none() -> None:
    cp = COSDictionary()
    cp.set_item(COSName.get_pdf_name("a"), COSInteger.get(7))
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("CharProcs"), cp)
    font = PDType3Font(d)
    assert font.get_char_proc("a") is None


def test_empty_char_procs_dict() -> None:
    font = _font_with(char_procs={})
    assert font.get_char_proc("a") is None
    assert font.get_char_procs() is not None
    assert font.get_char_procs().key_set() == set()


# ---------- get_char_proc(code) through encoding ----------


def test_char_proc_by_code_resolves_through_encoding() -> None:
    glyph = _glyph(b"250 0 d0\n")
    font = _font_with(
        char_procs={"alpha": glyph},
        encoding_differences={65: "alpha"},
    )
    proc = font.get_char_proc(65)
    assert isinstance(proc, PDType3CharProc)
    assert proc.get_cos_object() is glyph


def test_char_proc_by_code_no_encoding_returns_none() -> None:
    # Type 3 MUST have /Encoding; without it, code lookups resolve nothing.
    font = _font_with(char_procs={"alpha": _glyph(b"250 0 d0\n")})
    assert font.get_encoding_typed() is None
    assert font.get_char_proc(65) is None


def test_char_proc_by_code_unmapped_code_returns_none() -> None:
    # No-base DictionaryEncoding: code 66 maps to .notdef (absent name).
    font = _font_with(
        char_procs={"alpha": _glyph(b"250 0 d0\n")},
        encoding_differences={65: "alpha"},
    )
    assert font.get_char_proc(66) is None


def test_char_proc_by_code_name_without_proc_returns_none() -> None:
    # Encoding maps 65 -> 'beta' but /CharProcs has only 'alpha'.
    font = _font_with(
        char_procs={"alpha": _glyph(b"250 0 d0\n")},
        encoding_differences={65: "beta"},
    )
    assert font.get_char_proc(65) is None


def test_char_proc_by_code_bool_rejected() -> None:
    font = _font_with(
        char_procs={"alpha": _glyph(b"250 0 d0\n")},
        encoding_differences={1: "alpha"},
    )
    with pytest.raises(TypeError):
        font.get_char_proc(True)


@pytest.mark.parametrize("code", [0, 32, 127, 255], ids=lambda c: f"code{c}")
def test_char_proc_by_code_full_byte_range(code: int) -> None:
    glyph = _glyph(b"300 0 d0\n")
    font = _font_with(
        char_procs={"g": glyph}, encoding_differences={code: "g"}
    )
    proc = font.get_char_proc(code)
    assert isinstance(proc, PDType3CharProc)
    assert proc.get_cos_object() is glyph


# ---------- get_width via /Widths (NOT scaled by FontMatrix) ----------


def test_width_inside_window() -> None:
    font = _font_with(widths=[100.0, 200.0, 300.0], first_char=65)
    assert font.get_width(65) == 100.0
    assert font.get_width(66) == 200.0
    assert font.get_width(67) == 300.0


def test_width_not_scaled_by_font_matrix() -> None:
    # Upstream PDType3Font.getWidth returns the raw /Widths entry; the
    # /FontMatrix scaling is applied only by getDisplacement, not getWidth.
    font = _font_with(
        widths=[500.0],
        first_char=65,
        font_matrix=[0.01, 0.0, 0.0, 0.01, 0.0, 0.0],
    )
    assert font.get_width(65) == 500.0


def test_width_first_char_offset() -> None:
    # code - FirstChar indexes /Widths; verify the offset is correct.
    font = _font_with(widths=[10.0, 20.0, 30.0, 40.0], first_char=100)
    assert font.get_width(100) == 10.0
    assert font.get_width(103) == 40.0


def test_width_below_first_char_no_descriptor_uses_font() -> None:
    # Out of window, no descriptor -> getWidthFromFont (char proc d0/d1).
    glyph = _glyph(b"777 0 d0\n")
    font = _font_with(
        char_procs={"g": glyph},
        encoding_differences={64: "g"},
        widths=[100.0],
        first_char=65,
    )
    assert font.get_width(64) == 777.0


def test_width_above_last_char_uses_font() -> None:
    glyph = _glyph(b"888 0 d0\n")
    font = _font_with(
        char_procs={"g": glyph},
        encoding_differences={70: "g"},
        widths=[100.0],
        first_char=65,
    )
    assert font.get_width(70) == 888.0


def test_width_none_entry_returns_zero() -> None:
    # A sparse /Widths entry (null) inside the window yields 0.0, mirroring
    # upstream's ``w == null ? 0 : w``.
    from pypdfbox.cos import COSNull

    arr = COSArray()
    arr.add(COSFloat(100.0))
    arr.add(COSNull.NULL)
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Widths"), arr)
    d.set_int(COSName.get_pdf_name("FirstChar"), 65)
    d.set_int(COSName.get_pdf_name("LastChar"), 66)
    font = PDType3Font(d)
    assert font.get_width(66) == 0.0


# ---------- d0 / d1 glyph metric operators ----------


@pytest.mark.parametrize(
    "body,expected",
    [
        (b"100 0 d0\n", 100.0),
        (b"250.5 0 d0\n", 250.5),
        (b"500 0 0 0 700 800 d1\n", 500.0),
        (b"  42   0   d0  ", 42.0),
        (b"% comment\n333 0 d0\n", 333.0),
        (b"0 0 d0\n", 0.0),
    ],
    ids=["d0", "d0_real", "d1", "d0_ws", "d0_comment", "d0_zero"],
)
def test_char_proc_width_from_metric_op(body: bytes, expected: float) -> None:
    font = _font_with(
        char_procs={"g": _glyph(body)}, encoding_differences={65: "g"}
    )
    proc = font.get_char_proc(65)
    assert isinstance(proc, PDType3CharProc)
    assert proc.get_width() == expected


def test_width_from_font_empty_proc_is_zero() -> None:
    # Empty char proc stream short-circuits to 0.0 (length 0).
    font = _font_with(
        char_procs={"g": _glyph(b"")}, encoding_differences={64: "g"}
    )
    assert font.get_width_from_font(64) == 0.0


def test_width_from_font_no_proc_is_zero() -> None:
    font = _font_with(encoding_differences={64: "missing"})
    assert font.get_width_from_font(64) == 0.0


def test_d1_glyph_bbox_parsed() -> None:
    font = _font_with(
        char_procs={"g": _glyph(b"500 0 10 20 110 220 d1\n")},
        encoding_differences={65: "g"},
    )
    proc = font.get_char_proc(65)
    assert isinstance(proc, PDType3CharProc)
    bbox = proc.get_glyph_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 10.0
    assert bbox.get_upper_right_y() == 220.0


def test_d0_glyph_bbox_is_none() -> None:
    font = _font_with(
        char_procs={"g": _glyph(b"500 0 d0\n")},
        encoding_differences={65: "g"},
    )
    proc = font.get_char_proc(65)
    assert isinstance(proc, PDType3CharProc)
    assert proc.get_glyph_bbox() is None


# ---------- /FontBBox accessor ----------


def test_font_bbox_missing_returns_none() -> None:
    assert PDType3Font().get_font_bbox() is None


def test_font_bbox_four_corners() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSInteger.get(0), COSInteger.get(1000), COSInteger.get(800)]
    )
    font = _font_with(font_bbox=arr)
    bbox = font.get_font_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 0.0
    assert bbox.get_upper_right_x() == 1000.0
    assert bbox.get_upper_right_y() == 800.0


def test_font_bbox_reversed_corners_normalised() -> None:
    arr = COSArray(
        [COSInteger.get(1000), COSInteger.get(800), COSInteger.get(0), COSInteger.get(0)]
    )
    bbox = _font_with(font_bbox=arr).get_font_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 0.0
    assert bbox.get_lower_left_y() == 0.0
    assert bbox.get_upper_right_x() == 1000.0
    assert bbox.get_upper_right_y() == 800.0


@pytest.mark.parametrize("size", [0, 1, 2, 3], ids=lambda n: f"short{n}")
def test_font_bbox_short_array_zero_padded(size: int) -> None:
    arr = COSArray([COSInteger.get(5) for _ in range(size)])
    bbox = _font_with(font_bbox=arr).get_font_bbox()
    assert bbox is not None  # short array still yields a (zero-padded) rect


def test_font_bbox_long_array_truncated_to_four() -> None:
    arr = COSArray([COSInteger.get(v) for v in (0, 0, 100, 200, 999, 999)])
    bbox = _font_with(font_bbox=arr).get_font_bbox()
    assert bbox is not None
    assert bbox.get_upper_right_x() == 100.0
    assert bbox.get_upper_right_y() == 200.0


def test_font_bbox_non_numeric_coerced_to_zero() -> None:
    arr = COSArray(
        [COSName.get_pdf_name("x"), COSInteger.get(0), COSInteger.get(100), COSInteger.get(200)]
    )
    bbox = _font_with(font_bbox=arr).get_font_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 0.0


def test_font_bbox_not_array_returns_none() -> None:
    font = PDType3Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("FontBBox"), COSString("nope")
    )
    assert font.get_font_bbox() is None


# ---------- /Name identity ----------


def test_name_accessor() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Name"), COSName.get_pdf_name("F1"))
    assert PDType3Font(d).get_name() == "F1"


def test_name_absent_returns_none() -> None:
    assert PDType3Font().get_name() is None


# ---------- has_glyph ----------


def test_has_glyph_by_code_requires_encoding_and_proc() -> None:
    font = _font_with(
        char_procs={"g": _glyph(b"100 0 d0\n")},
        encoding_differences={65: "g"},
    )
    assert font.has_glyph(65) is True
    assert font.has_glyph(66) is False


def test_has_glyph_notdef_is_false() -> None:
    font = _font_with(
        char_procs={".notdef": _glyph(b"0 0 d0\n")},
        encoding_differences={65: ".notdef"},
    )
    # hasGlyph(int) treats a .notdef mapping as "no glyph".
    assert font.has_glyph(65) is False


def test_has_glyph_by_name() -> None:
    font = _font_with(char_procs={"g": _glyph(b"100 0 d0\n")})
    assert font.has_glyph("g") is True
    assert font.has_glyph("h") is False


# ---------- invariants ----------


def test_is_embedded_always_true() -> None:
    assert PDType3Font().is_embedded() is True


def test_is_standard14_always_false() -> None:
    assert PDType3Font().is_standard_14() is False
    assert PDType3Font().is_standard14() is False


def test_is_damaged_false() -> None:
    assert PDType3Font().is_damaged() is False
