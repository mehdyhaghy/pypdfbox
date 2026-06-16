"""Wave 1574 — text-showing + text-state operator fuzz (parity).

Hammers the text-showing operators (``Tj`` / ``TJ`` / ``'`` / ``"``) and
the text-state operators (``Tc`` / ``Tw`` / ``Tz`` / ``TL`` / ``Ts`` /
``Tr`` / ``Tf``) plus the line-positioning operators (``Td`` / ``TD`` /
``T*`` / ``Tm``), asserting the resulting graphics/text-state values and
text/line-matrix effects.

Parity reference: PDFBox 3.0.x
``org.apache.pdfbox.contentstream.operator.text.*``. Key invariants
pinned here:

* ``Td`` (``tx ty Td``) translates the text-line matrix and copies it to
  the text matrix (``MoveText``).
* ``TD`` (``tx ty TD``) sets leading to ``-ty`` then performs ``Td``
  (``MoveTextSetLeading``) — the leading sign is negated.
* ``T*`` performs ``0 -leading Td`` (``NextLine``).
* ``Tm`` (``a b c d e f Tm``) replaces *both* the text matrix and the
  text-line matrix with the six operands in order (``SetMatrix``).
* ``'`` (``string '``) == ``T*`` then ``Tj`` (``ShowTextLine``), and an
  operand-less ``'`` raises atomically with no ``T*`` side effect.
* ``"`` (``aw ac string "``) sets ``Tw`` = ``aw`` and ``Tc`` = ``ac``
  then performs ``'`` (``ShowTextLineAndSpace``) — operand order is
  ``aw`` (word) then ``ac`` (char).
* ``Tz`` stores the raw percentage (``100`` == 100%); the ``/100``
  conversion is applied downstream when the scaling is *used*, not at
  store time.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
    OperatorName,
)
from pypdfbox.contentstream.operator.text import (
    BeginText,
    EndText,
    MoveText,
    MoveTextSetLeading,
    NextLine,
    SetCharSpacing,
    SetFontAndSize,
    SetHorizontalTextScaling,
    SetMatrix,
    SetTextLeading,
    SetTextRenderingMode,
    SetTextRise,
    SetWordSpacing,
    ShowText,
    ShowTextAdjusted,
    ShowTextLine,
    ShowTextLineAndSpace,
)
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)


class _RecordingEngine(PDFStreamEngine):
    """Tracks every text-state notification and maintains a real text /
    line matrix so ``Td`` / ``TD`` / ``T*`` / ``Tm`` effects are
    observable.

    The text/line matrices are flat 6-tuples ``(a, b, c, d, e, f)`` in
    PDF column-major affine form. ``move_text_position`` post-multiplies
    a translation onto the line matrix and copies it to the text matrix,
    mirroring upstream ``MoveText`` (``Matrix.translate(tx, ty)`` *
    line-matrix).
    """

    def __init__(self) -> None:
        super().__init__()
        self.text_matrix: list[float] = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        self.line_matrix: list[float] = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        self.leading: float = 0.0
        self.word_spacing: float = 0.0
        self.char_spacing: float = 0.0
        self.horizontal_scaling: float = 100.0
        self.text_rise: float = 0.0
        self.rendering_mode: int = 0
        self.font_name: COSName | None = None
        self.font_size: float = 0.0
        self.shown_strings: list[bytes] = []
        self.shown_arrays: list[COSArray] = []

    # ---- notifications used by the operator classes ----

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        if matrix is not None:
            self.text_matrix = list(matrix)

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        if matrix is not None:
            self.line_matrix = list(matrix)

    def move_text_position(self, tx: float, ty: float) -> None:
        # translation * line_matrix (PDF affine, column-major):
        # [1 0 0 1 tx ty] then line_matrix gives new line matrix.
        a, b, c, d, e, f = self.line_matrix
        new = [
            a,
            b,
            c,
            d,
            tx * a + ty * c + e,
            tx * b + ty * d + f,
        ]
        self.line_matrix = new
        self.text_matrix = list(new)

    def set_text_leading(self, leading: float) -> None:
        self.leading = leading

    def get_text_leading(self) -> float:
        return self.leading

    def set_word_spacing(self, spacing: float) -> None:
        self.word_spacing = spacing

    def set_character_spacing(self, spacing: float) -> None:
        self.char_spacing = spacing

    def set_horizontal_scaling(self, scaling: float) -> None:
        self.horizontal_scaling = scaling

    def set_text_rise(self, rise: float) -> None:
        self.text_rise = rise

    def set_text_rendering_mode(self, mode: int) -> None:
        self.rendering_mode = mode

    def set_font(self, font_name: COSName, font_size: float) -> None:
        self.font_name = font_name
        self.font_size = font_size

    def show_text_string(self, text: bytes) -> None:
        self.shown_strings.append(text)

    def show_text_strings(self, array: COSArray) -> None:
        self.shown_arrays.append(array)


def _engine() -> _RecordingEngine:
    eng = _RecordingEngine()
    for cls in (
        BeginText,
        EndText,
        MoveText,
        MoveTextSetLeading,
        NextLine,
        SetMatrix,
        SetCharSpacing,
        SetWordSpacing,
        SetTextLeading,
        SetTextRise,
        SetHorizontalTextScaling,
        SetTextRenderingMode,
        SetFontAndSize,
        ShowText,
        ShowTextAdjusted,
        ShowTextLine,
        ShowTextLineAndSpace,
    ):
        eng.add_operator(cls())
    return eng


def _op(name: str) -> Operator:
    return Operator.get_operator(name)


def _num(value: float) -> COSFloat:
    return COSFloat(float(value))


def _str(value: str) -> COSString:
    return COSString(value)


# ---------------------------------------------------------------- Td (MoveText)


@pytest.mark.parametrize(
    ("tx", "ty"),
    [
        (10.0, 0.0),
        (0.0, 20.0),
        (5.0, -7.0),
        (-3.5, 4.25),
        (0.0, 0.0),
        (1000.0, -1000.0),
    ],
)
def test_td_translates_line_matrix_and_copies_to_text_matrix(
    tx: float, ty: float
) -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.MOVE_TEXT), [_num(tx), _num(ty)])
    # Starting from identity, translation moves only e/f.
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, tx, ty]
    assert eng.text_matrix == eng.line_matrix
    assert eng.text_matrix is not eng.line_matrix


def test_td_accumulates_on_successive_calls() -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.MOVE_TEXT), [_num(10.0), _num(5.0)])
    eng.process_operator(_op(OperatorName.MOVE_TEXT), [_num(2.0), _num(3.0)])
    # Second Td is relative to the line matrix left by the first.
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, 12.0, 8.0]


def test_td_missing_operand_raises() -> None:
    eng = _engine()
    proc = MoveText()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(_op(OperatorName.MOVE_TEXT), [_num(1.0)])


def test_td_non_number_operand_is_silently_dropped() -> None:
    eng = _engine()
    proc = MoveText()
    proc.set_context(eng)
    proc.process(_op(OperatorName.MOVE_TEXT), [_str("x"), _num(2.0)])
    # No update — line matrix stays at identity.
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


# ---------------------------------------------------- TD (MoveTextSetLeading)


@pytest.mark.parametrize(
    ("tx", "ty"),
    [
        (0.0, 12.0),
        (0.0, -12.0),
        (5.0, 8.0),
        (-2.0, -3.0),
    ],
)
def test_td_set_leading_negates_ty_then_moves(tx: float, ty: float) -> None:
    eng = _engine()
    eng.process_operator(
        _op(OperatorName.MOVE_TEXT_SET_LEADING), [_num(tx), _num(ty)]
    )
    # Leading is set to -ty (the sign-flip is the whole point of TD).
    assert eng.leading == -ty
    # And the move itself happened with the raw (tx, ty).
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, tx, ty]


def test_td_set_leading_missing_operand_raises() -> None:
    eng = _engine()
    proc = MoveTextSetLeading()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(_op(OperatorName.MOVE_TEXT_SET_LEADING), [_num(1.0)])


def test_td_set_leading_fires_exactly_one_leading_notification() -> None:
    eng = _engine()
    eng.process_operator(
        _op(OperatorName.MOVE_TEXT_SET_LEADING), [_num(0.0), _num(14.0)]
    )
    assert eng.leading == -14.0


# -------------------------------------------------------------- T* (NextLine)


@pytest.mark.parametrize("leading", [0.0, 12.0, -6.0, 18.5])
def test_next_line_moves_down_by_leading(leading: float) -> None:
    eng = _engine()
    # Establish leading via TL.
    eng.process_operator(_op(OperatorName.SET_TEXT_LEADING), [_num(leading)])
    eng.process_operator(_op(OperatorName.NEXT_LINE), [])
    # T* == 0 -leading Td → text/line matrix translate by (0, -leading).
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, -leading]
    assert eng.text_matrix == eng.line_matrix


def test_next_line_after_td_origin_is_relative_to_line_matrix() -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.SET_TEXT_LEADING), [_num(10.0)])
    eng.process_operator(_op(OperatorName.MOVE_TEXT), [_num(100.0), _num(700.0)])
    eng.process_operator(_op(OperatorName.NEXT_LINE), [])
    # Next line drops 10 below the current line origin.
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, 100.0, 690.0]


# ------------------------------------------------------------- Tm (SetMatrix)


@pytest.mark.parametrize(
    "matrix",
    [
        [1.0, 0.0, 0.0, 1.0, 72.0, 720.0],
        [2.0, 0.0, 0.0, 2.0, 0.0, 0.0],
        [1.0, 0.5, -0.5, 1.0, 10.0, 20.0],
        [0.0, 1.0, -1.0, 0.0, 100.0, 100.0],
    ],
)
def test_tm_replaces_both_matrices(matrix: list[float]) -> None:
    eng = _engine()
    # Dirty the matrices first to prove Tm overwrites (not composes).
    eng.process_operator(_op(OperatorName.MOVE_TEXT), [_num(5.0), _num(5.0)])
    operands: list[COSBase] = [_num(v) for v in matrix]
    eng.process_operator(_op(OperatorName.SET_MATRIX), operands)
    assert eng.text_matrix == matrix
    assert eng.line_matrix == matrix
    assert eng.text_matrix is not eng.line_matrix


def test_tm_missing_operand_raises() -> None:
    eng = _engine()
    proc = SetMatrix()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(
            _op(OperatorName.SET_MATRIX),
            [_num(1.0), _num(0.0), _num(0.0), _num(1.0), _num(0.0)],
        )


def test_tm_trailing_non_number_operand_is_noop() -> None:
    eng = _engine()
    proc = SetMatrix()
    proc.set_context(eng)
    proc.process(
        _op(OperatorName.SET_MATRIX),
        [_num(1.0)] * 6 + [_str("junk")],
    )
    # Whole operator no-ops when any operand is non-number.
    assert eng.text_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


# ---------------------------------------------------- Tc / Tw text-state store


@pytest.mark.parametrize("spacing", [0.0, 1.0, -2.5, 100.0, 0.25])
def test_tc_stores_char_spacing_raw(spacing: float) -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.SET_CHAR_SPACING), [_num(spacing)])
    assert eng.char_spacing == spacing


@pytest.mark.parametrize("spacing", [0.0, 3.0, -1.0, 250.0])
def test_tw_stores_word_spacing_raw(spacing: float) -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.SET_WORD_SPACING), [_num(spacing)])
    assert eng.word_spacing == spacing


def test_tc_uses_last_operand_for_malformed_streams() -> None:
    eng = _engine()
    # Upstream SetCharSpacing reads arguments.get(size-1).
    eng.process_operator(
        _op(OperatorName.SET_CHAR_SPACING), [_num(9.0), _num(4.0)]
    )
    assert eng.char_spacing == 4.0


def test_tc_missing_operand_raises() -> None:
    eng = _engine()
    proc = SetCharSpacing()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(_op(OperatorName.SET_CHAR_SPACING), [])


def test_tw_empty_operand_returns_silently() -> None:
    eng = _engine()
    proc = SetWordSpacing()
    proc.set_context(eng)
    proc.process(_op(OperatorName.SET_WORD_SPACING), [])
    assert eng.word_spacing == 0.0


# ----------------------------------------------------- Tz horizontal scaling


@pytest.mark.parametrize("scale", [100.0, 50.0, 200.0, 0.0, 75.5])
def test_tz_stores_raw_percentage(scale: float) -> None:
    eng = _engine()
    eng.process_operator(
        _op(OperatorName.SET_TEXT_HORIZONTAL_SCALING), [_num(scale)]
    )
    # Stored raw as a percentage (100 == 100%); /100 happens at use-time.
    assert eng.horizontal_scaling == scale


def test_tz_missing_operand_raises() -> None:
    eng = _engine()
    proc = SetHorizontalTextScaling()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(_op(OperatorName.SET_TEXT_HORIZONTAL_SCALING), [])


# ------------------------------------------------------------ TL / Ts / Tr


@pytest.mark.parametrize("leading", [0.0, 12.0, -5.0, 1000.0])
def test_tl_stores_leading(leading: float) -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.SET_TEXT_LEADING), [_num(leading)])
    assert eng.leading == leading


@pytest.mark.parametrize("rise", [0.0, 5.0, -3.0, 12.5])
def test_ts_stores_text_rise(rise: float) -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.SET_TEXT_RISE), [_num(rise)])
    assert eng.text_rise == rise


@pytest.mark.parametrize("mode", [0, 1, 2, 3, 4, 5, 6, 7])
def test_tr_stores_valid_rendering_mode(mode: int) -> None:
    eng = _engine()
    eng.process_operator(
        _op(OperatorName.SET_TEXT_RENDERINGMODE), [COSInteger.get(mode)]
    )
    assert eng.rendering_mode == mode


@pytest.mark.parametrize("mode", [-1, 8, 99])
def test_tr_out_of_range_mode_is_noop(mode: int) -> None:
    eng = _engine()
    eng.process_operator(
        _op(OperatorName.SET_TEXT_RENDERINGMODE), [COSInteger.get(mode)]
    )
    assert eng.rendering_mode == 0


def test_tl_missing_operand_raises() -> None:
    eng = _engine()
    proc = SetTextLeading()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(_op(OperatorName.SET_TEXT_LEADING), [])


def test_ts_empty_operand_returns_silently() -> None:
    eng = _engine()
    proc = SetTextRise()
    proc.set_context(eng)
    proc.process(_op(OperatorName.SET_TEXT_RISE), [])
    assert eng.text_rise == 0.0


# -------------------------------------------------------------- Tf (SetFont)


def test_tf_stores_font_name_and_size() -> None:
    eng = _engine()
    eng.process_operator(
        _op(OperatorName.SET_FONT_AND_SIZE),
        [COSName.get_pdf_name("F1"), _num(12.0)],
    )
    assert eng.font_name == COSName.get_pdf_name("F1")
    assert eng.font_size == 12.0


def test_tf_missing_operand_raises() -> None:
    eng = _engine()
    proc = SetFontAndSize()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(
            _op(OperatorName.SET_FONT_AND_SIZE),
            [COSName.get_pdf_name("F1")],
        )


def test_tf_non_name_first_operand_is_noop() -> None:
    eng = _engine()
    proc = SetFontAndSize()
    proc.set_context(eng)
    proc.process(
        _op(OperatorName.SET_FONT_AND_SIZE), [_str("F1"), _num(12.0)]
    )
    assert eng.font_name is None


# -------------------------------------------------------- Tj / TJ show text


def test_tj_shows_string() -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.SHOW_TEXT), [_str("Hello")])
    assert eng.shown_strings == [b"Hello"]


def test_tj_missing_operand_raises() -> None:
    eng = _engine()
    proc = ShowText()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(_op(OperatorName.SHOW_TEXT), [])


def test_tj_non_string_operand_is_silently_dropped() -> None:
    eng = _engine()
    proc = ShowText()
    proc.set_context(eng)
    proc.process(_op(OperatorName.SHOW_TEXT), [_num(1.0)])
    assert eng.shown_strings == []


def test_tj_array_forwarded_to_show_text_strings() -> None:
    eng = _engine()
    arr = COSArray()
    arr.add(_str("A"))
    arr.add(COSInteger.get(-250))
    arr.add(_str("B"))
    eng.process_operator(_op(OperatorName.SHOW_TEXT_ADJUSTED), [arr])
    assert eng.shown_arrays == [arr]


def test_tj_array_empty_raises() -> None:
    eng = _engine()
    proc = ShowTextAdjusted()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(_op(OperatorName.SHOW_TEXT_ADJUSTED), [])


def test_tj_array_non_array_operand_is_noop() -> None:
    eng = _engine()
    proc = ShowTextAdjusted()
    proc.set_context(eng)
    proc.process(_op(OperatorName.SHOW_TEXT_ADJUSTED), [_str("not-array")])
    assert eng.shown_arrays == []


def test_tj_array_with_only_numbers_still_forwarded() -> None:
    eng = _engine()
    arr = COSArray()
    arr.add(COSInteger.get(100))
    arr.add(_num(-50.0))
    eng.process_operator(_op(OperatorName.SHOW_TEXT_ADJUSTED), [arr])
    assert eng.shown_arrays == [arr]


# ----------------------------------------------- ' (ShowTextLine) = T* + Tj


def test_apostrophe_moves_to_next_line_then_shows() -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.SET_TEXT_LEADING), [_num(15.0)])
    eng.process_operator(_op(OperatorName.SHOW_TEXT_LINE), [_str("line2")])
    # T* dropped one leading, then the string was shown.
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, -15.0]
    assert eng.shown_strings == [b"line2"]


def test_apostrophe_empty_operand_raises_with_no_line_move() -> None:
    """Upstream rejects an operand-less ``'`` atomically (no ``T*``
    side effect) — the missing-operand guard fires before any
    sub-operator dispatch."""
    eng = _engine()
    eng.process_operator(_op(OperatorName.SET_TEXT_LEADING), [_num(15.0)])
    proc = ShowTextLine()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(_op(OperatorName.SHOW_TEXT_LINE), [])
    # The spurious vertical shift must NOT have happened.
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert eng.shown_strings == []


# ----------------------- " (ShowTextLineAndSpace) = Tw + Tc + T* + Tj


def test_quote_sets_word_then_char_spacing_then_shows_line() -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.SET_TEXT_LEADING), [_num(10.0)])
    # Operand order is: aw (word) ac (char) string.
    eng.process_operator(
        _op(OperatorName.SHOW_TEXT_LINE_AND_SPACE),
        [_num(3.0), _num(1.0), _str("hi")],
    )
    assert eng.word_spacing == 3.0
    assert eng.char_spacing == 1.0
    # ' decomposition dropped one leading.
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, -10.0]
    assert eng.shown_strings == [b"hi"]


def test_quote_operand_order_is_aw_then_ac() -> None:
    eng = _engine()
    eng.process_operator(
        _op(OperatorName.SHOW_TEXT_LINE_AND_SPACE),
        [_num(7.0), _num(2.0), _str("x")],
    )
    # aw → word spacing, ac → char spacing (NOT swapped).
    assert eng.word_spacing == 7.0
    assert eng.char_spacing == 2.0


def test_quote_missing_operand_raises() -> None:
    eng = _engine()
    proc = ShowTextLineAndSpace()
    proc.set_context(eng)
    with pytest.raises(MissingOperandException):
        proc.process(
            _op(OperatorName.SHOW_TEXT_LINE_AND_SPACE),
            [_num(1.0), _num(2.0)],
        )


# --------------------------------------------- combined state sequence sanity


def test_full_text_block_sequence_state_consistency() -> None:
    eng = _engine()
    eng.process_operator(_op(OperatorName.BEGIN_TEXT), [])
    eng.process_operator(
        _op(OperatorName.SET_FONT_AND_SIZE),
        [COSName.get_pdf_name("F1"), _num(10.0)],
    )
    eng.process_operator(_op(OperatorName.SET_TEXT_LEADING), [_num(12.0)])
    eng.process_operator(_op(OperatorName.SET_CHAR_SPACING), [_num(0.5)])
    eng.process_operator(_op(OperatorName.SET_WORD_SPACING), [_num(2.0)])
    eng.process_operator(
        _op(OperatorName.SET_TEXT_HORIZONTAL_SCALING), [_num(90.0)]
    )
    eng.process_operator(_op(OperatorName.SET_TEXT_RISE), [_num(1.0)])
    eng.process_operator(
        _op(OperatorName.SET_TEXT_RENDERINGMODE), [COSInteger.get(2)]
    )
    eng.process_operator(
        _op(OperatorName.SET_MATRIX),
        [_num(1.0), _num(0.0), _num(0.0), _num(1.0), _num(72.0), _num(720.0)],
    )
    eng.process_operator(_op(OperatorName.SHOW_TEXT), [_str("first")])
    eng.process_operator(_op(OperatorName.SHOW_TEXT_LINE), [_str("second")])
    eng.process_operator(_op(OperatorName.END_TEXT), [])

    assert eng.font_size == 10.0
    assert eng.leading == 12.0
    assert eng.char_spacing == 0.5
    assert eng.word_spacing == 2.0
    assert eng.horizontal_scaling == 90.0
    assert eng.text_rise == 1.0
    assert eng.rendering_mode == 2
    # Tm set origin to (72, 720); the apostrophe dropped one leading.
    assert eng.line_matrix == [1.0, 0.0, 0.0, 1.0, 72.0, 708.0]
    assert eng.shown_strings == [b"first", b"second"]
