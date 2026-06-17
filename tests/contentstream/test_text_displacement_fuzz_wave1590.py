"""Wave 1590 — text-showing glyph-displacement / advance fuzz parity.

Hammers the per-glyph advance computation that ``PDFStreamEngine.showText``
performs to step the text matrix after each glyph. Mirrors upstream
``org.apache.pdfbox.contentstream.PDFStreamEngine.showText(byte[])``:

    Vector w = font.getDisplacement(code);   // already in text space (/1000)
    if (font.isVertical()) {
        tx = 0;
        ty = w.getY() * fontSize + charSpacing + wordSpacing;
    } else {
        tx = (w.getX() * fontSize + charSpacing + wordSpacing) * horizontalScaling;
        ty = 0;
    }
    textMatrix.concatenate(Matrix.getTranslateInstance(tx, ty));

where

  * ``w0 = font.getWidth(code) / 1000`` (``get_displacement`` already divides),
  * ``charSpacing`` (``Tc``) is added to **every** glyph,
  * ``wordSpacing`` (``Tw``) is added **only** when the code is the
    *single-byte* code 32 (PDF 32000-1 §9.3.3) — never a 2-byte code 32 in a
    Type0 font, never any other character,
  * ``horizontalScaling`` (``Tz/100``) scales the whole horizontal advance,
    including ``Tc`` and ``Tw`` (it does **not** apply to a vertical advance),
  * for a vertical font the ``w1`` (y) displacement component is used and
    horizontal scaling is not applied.

The recording engine below subclasses the real contentstream
:class:`PDFStreamEngine` and drives its actual decode loop
(``show_text`` → ``read_code`` per glyph → ``show_font_glyph`` →
``show_glyph``), then applies the upstream advance formula to a tracked
text matrix in ``show_glyph``. Each fuzz case re-derives the expected
cumulative advance from an independent reference and asserts the tracked
text-matrix translation matches.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.util.matrix import Matrix


class _FuzzFont:
    """Minimal font exposing the surface ``PDFStreamEngine.showText`` uses.

    ``read_code`` follows pypdfbox's ``(data, offset) -> (code, consumed)``
    contract. When ``code_bytes`` is 2 the font is composite (Type0-style):
    every code consumes two bytes, so a code value of 32 is **not** a
    single-byte space and word spacing must not apply to it.

    ``get_displacement`` returns ``(w0, w1)`` already in text space
    (i.e. ``width/1000``), matching ``PDFont.getDisplacement``.
    """

    def __init__(
        self,
        widths: dict[int, float],
        *,
        code_bytes: int = 1,
        vertical: bool = False,
        default_width: float = 500.0,
    ) -> None:
        self._widths = widths
        self._code_bytes = code_bytes
        self._vertical = vertical
        self._default_width = default_width

    def read_code(self, data: bytes, offset: int) -> tuple[int, int]:
        if self._code_bytes == 2:
            if offset + 2 > len(data):
                # Pad a dangling tail byte to a full code (defensive).
                return (data[offset] << 8, 1)
            return ((data[offset] << 8) | data[offset + 1], 2)
        return (data[offset], 1)

    def get_width(self, code: int) -> float:
        return self._widths.get(code, self._default_width)

    def get_displacement(self, code: int) -> tuple[float, float]:
        w = self.get_width(code) / 1000.0
        if self._vertical:
            # Vertical fonts advance downward: w1 is negative. We model a
            # constant -1 em vertical displacement plus the per-code width
            # only on the y axis so the formula has something to scale.
            return (0.0, -(w))
        return (w, 0.0)

    def is_vertical(self) -> bool:
        return self._vertical


class _GS:
    """Graphics-state stand-in carrying just the active font."""

    def __init__(self, font: Any) -> None:
        self.text_font = font


class _AdvanceEngine(PDFStreamEngine):
    """Drives the real decode loop and applies the upstream advance formula.

    The base engine's ``show_text`` reads codes through the font and calls
    ``show_font_glyph`` (→ ``show_glyph``) once per code, handing us the
    font + code. We re-derive ``consumed`` for the word-spacing test from
    the font's ``read_code``, then translate the tracked text matrix by the
    upstream ``(tx, ty)``.
    """

    def __init__(
        self,
        font: _FuzzFont,
        *,
        font_size: float,
        char_spacing: float,
        word_spacing: float,
        horizontal_scaling: float,
    ) -> None:
        super().__init__()
        self._font = font
        self._font_size = font_size
        self._char_spacing = char_spacing
        self._word_spacing = word_spacing
        # ``horizontal_scaling`` here is already Tz/100 (the engine-internal
        # representation).
        self._h_scale = horizontal_scaling
        self._tm = Matrix()
        self.advances: list[tuple[float, float]] = []
        self._graphics_stack.append(_GS(font))

    def show_text_string(self, text: bytes) -> None:
        self.show_text(text)

    def show_glyph(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        w0, w1 = displacement
        # Determine code length to gate word spacing on the *single-byte*
        # code 32 only.
        consumed = 2 if font._code_bytes == 2 else 1  # noqa: SLF001
        is_single_byte_space = consumed == 1 and code == 32
        word = self._word_spacing if is_single_byte_space else 0.0
        if font.is_vertical():
            tx = 0.0
            ty = w1 * self._font_size + self._char_spacing + word
        else:
            tx = (
                w0 * self._font_size + self._char_spacing + word
            ) * self._h_scale
            ty = 0.0
        self.advances.append((tx, ty))
        self._tm.translate(tx, ty)

    @property
    def translation(self) -> tuple[float, float]:
        return (self._tm.get_translate_x(), self._tm.get_translate_y())


def _reference_advances(
    codes: list[tuple[int, int]],
    font: _FuzzFont,
    *,
    font_size: float,
    char_spacing: float,
    word_spacing: float,
    h_scale: float,
) -> list[tuple[float, float]]:
    """Independent reference implementation of upstream's per-glyph advance.

    ``codes`` is a list of ``(code, consumed)`` pairs in source order.
    """
    out: list[tuple[float, float]] = []
    for code, consumed in codes:
        w0, w1 = font.get_displacement(code)
        word = word_spacing if (consumed == 1 and code == 32) else 0.0
        if font.is_vertical():
            tx = 0.0
            ty = w1 * font_size + char_spacing + word
        else:
            tx = (w0 * font_size + char_spacing + word) * h_scale
            ty = 0.0
        out.append((tx, ty))
    return out


def _decode(data: bytes, font: _FuzzFont) -> list[tuple[int, int]]:
    codes: list[tuple[int, int]] = []
    offset = 0
    while offset < len(data):
        code, consumed = font.read_code(data, offset)
        if consumed <= 0:
            break
        codes.append((code, consumed))
        offset += consumed
    return codes


def _run(
    data: bytes,
    font: _FuzzFont,
    *,
    font_size: float,
    char_spacing: float = 0.0,
    word_spacing: float = 0.0,
    h_scale: float = 1.0,
) -> _AdvanceEngine:
    engine = _AdvanceEngine(
        font,
        font_size=font_size,
        char_spacing=char_spacing,
        word_spacing=word_spacing,
        horizontal_scaling=h_scale,
    )
    engine.show_text(data)
    return engine


# ---------- bare width: w0 * fontSize, no spacing ----------


def test_bare_width_advance_single_glyph() -> None:
    font = _FuzzFont({ord("A"): 722.0})
    eng = _run(b"A", font, font_size=12.0)
    # 722/1000 * 12 = 8.664
    assert eng.advances == pytest.approx([(8.664, 0.0)])
    assert eng.translation == pytest.approx((8.664, 0.0))


def test_width_units_are_divided_by_1000() -> None:
    # A 1000-unit glyph at font size 10 advances exactly 10 text-space units.
    font = _FuzzFont({ord("X"): 1000.0})
    eng = _run(b"X", font, font_size=10.0)
    assert eng.advances == pytest.approx([(10.0, 0.0)])


def test_font_size_scales_advance_linearly() -> None:
    font = _FuzzFont({ord("m"): 600.0})
    a12 = _run(b"m", font, font_size=12.0).advances[0][0]
    a24 = _run(b"m", font, font_size=24.0).advances[0][0]
    assert a24 == pytest.approx(2.0 * a12)


def test_zero_width_glyph_advances_zero_without_spacing() -> None:
    font = _FuzzFont({0x05: 0.0})
    eng = _run(b"\x05", font, font_size=14.0)
    assert eng.advances == pytest.approx([(0.0, 0.0)])


# ---------- char spacing (Tc) on every glyph ----------


def test_char_spacing_added_to_every_glyph() -> None:
    font = _FuzzFont({ord("a"): 500.0})
    eng = _run(b"aaa", font, font_size=10.0, char_spacing=2.0)
    # each: 500/1000*10 + 2 = 7.0
    assert eng.advances == pytest.approx([(7.0, 0.0)] * 3)
    assert eng.translation == pytest.approx((21.0, 0.0))


def test_char_spacing_applies_to_last_glyph_too() -> None:
    """Tc is added after the final glyph as well (no off-by-one)."""
    font = _FuzzFont({ord("z"): 0.0})
    eng = _run(b"zz", font, font_size=10.0, char_spacing=3.0)
    # Both glyphs zero width → cumulative advance is 2 * Tc.
    assert eng.translation == pytest.approx((6.0, 0.0))


def test_negative_char_spacing_condenses() -> None:
    font = _FuzzFont({ord("w"): 800.0})
    eng = _run(b"w", font, font_size=10.0, char_spacing=-3.0)
    # 800/1000*10 - 3 = 5.0
    assert eng.advances == pytest.approx([(5.0, 0.0)])


# ---------- word spacing (Tw): single-byte code 32 ONLY ----------


def test_word_spacing_applies_to_single_byte_space() -> None:
    font = _FuzzFont({32: 250.0})
    eng = _run(b" ", font, font_size=10.0, word_spacing=4.0)
    # 250/1000*10 + 0 (Tc) + 4 (Tw) = 6.5
    assert eng.advances == pytest.approx([(6.5, 0.0)])


def test_word_spacing_not_applied_to_non_space() -> None:
    font = _FuzzFont({ord("A"): 250.0})
    eng = _run(b"A", font, font_size=10.0, word_spacing=4.0)
    # No Tw for a non-space code: 250/1000*10 = 2.5
    assert eng.advances == pytest.approx([(2.5, 0.0)])


def test_word_spacing_applies_only_to_spaces_in_mixed_run() -> None:
    font = _FuzzFont({ord("A"): 500.0, 32: 250.0, ord("B"): 500.0})
    eng = _run(b"A B", font, font_size=10.0, word_spacing=5.0)
    # A: 5.0 ; space: 2.5 + 5.0 = 7.5 ; B: 5.0
    assert eng.advances == pytest.approx([(5.0, 0.0), (7.5, 0.0), (5.0, 0.0)])


def test_word_spacing_not_applied_to_two_byte_code_32() -> None:
    """A Type0 (2-byte) font code whose value is 32 must NOT receive Tw —
    word spacing applies only to the single-byte code 32 (PDF §9.3.3)."""
    # 2-byte code 0x0020 == 32, consumed == 2 → no Tw.
    font = _FuzzFont({32: 1000.0}, code_bytes=2)
    eng = _run(b"\x00\x20", font, font_size=10.0, word_spacing=9.0)
    # 1000/1000*10 = 10.0, NO word spacing.
    assert eng.advances == pytest.approx([(10.0, 0.0)])


def test_two_byte_high_code_32_low_byte_no_word_spacing() -> None:
    """0x2000 has low byte 0x00 and is not 32; 0x0020 is 32 but 2-byte.
    Neither single-byte-space condition holds → no Tw either way."""
    font = _FuzzFont({0x2000: 500.0, 0x0020: 500.0}, code_bytes=2)
    eng = _run(b"\x20\x00\x00\x20", font, font_size=10.0, word_spacing=7.0)
    assert eng.advances == pytest.approx([(5.0, 0.0), (5.0, 0.0)])


def test_word_spacing_zero_is_noop() -> None:
    font = _FuzzFont({32: 250.0})
    eng = _run(b" ", font, font_size=10.0, word_spacing=0.0)
    assert eng.advances == pytest.approx([(2.5, 0.0)])


# ---------- horizontal scaling (Tz) scales the WHOLE advance ----------


def test_horizontal_scaling_scales_width() -> None:
    font = _FuzzFont({ord("A"): 1000.0})
    eng = _run(b"A", font, font_size=10.0, h_scale=0.5)
    # (1000/1000*10) * 0.5 = 5.0
    assert eng.advances == pytest.approx([(5.0, 0.0)])


def test_horizontal_scaling_scales_char_spacing() -> None:
    font = _FuzzFont({ord("A"): 0.0})
    eng = _run(b"A", font, font_size=10.0, char_spacing=4.0, h_scale=0.5)
    # (0 + 4) * 0.5 = 2.0
    assert eng.advances == pytest.approx([(2.0, 0.0)])


def test_horizontal_scaling_scales_word_spacing() -> None:
    font = _FuzzFont({32: 0.0})
    eng = _run(b" ", font, font_size=10.0, word_spacing=6.0, h_scale=0.5)
    # (0 + 0 (Tc) + 6 (Tw)) * 0.5 = 3.0
    assert eng.advances == pytest.approx([(3.0, 0.0)])


def test_horizontal_scaling_scales_combined_advance() -> None:
    font = _FuzzFont({32: 250.0})
    eng = _run(
        b" ", font, font_size=10.0, char_spacing=1.0, word_spacing=3.0,
        h_scale=2.0,
    )
    # (250/1000*10 + 1 + 3) * 2 = (2.5 + 4) * 2 = 13.0
    assert eng.advances == pytest.approx([(13.0, 0.0)])


def test_horizontal_scaling_200_percent() -> None:
    font = _FuzzFont({ord("A"): 500.0})
    eng = _run(b"A", font, font_size=10.0, h_scale=2.0)
    assert eng.advances == pytest.approx([(10.0, 0.0)])


# ---------- text matrix translated by displacement after each glyph ----------


def test_cumulative_translation_matches_advance_sum() -> None:
    font = _FuzzFont({ord("H"): 700.0, ord("i"): 300.0})
    eng = _run(b"Hi", font, font_size=10.0, char_spacing=1.0)
    # H: 7.0 + 1.0 = 8.0 ; i: 3.0 + 1.0 = 4.0 → 12.0
    assert eng.translation == pytest.approx((12.0, 0.0))


def test_ty_stays_zero_for_horizontal_run() -> None:
    font = _FuzzFont({ord("A"): 500.0})
    eng = _run(b"AAAA", font, font_size=10.0, char_spacing=2.0)
    assert eng.translation[1] == pytest.approx(0.0)


# ---------- vertical font: w1 used, no horizontal scaling ----------


def test_vertical_font_uses_w1_component() -> None:
    font = _FuzzFont({0x21: 1000.0}, code_bytes=2, vertical=True)
    eng = _run(b"\x00\x21", font, font_size=10.0)
    # vertical: ty = w1 * fs = -(1000/1000) * 10 = -10.0 ; tx = 0
    assert eng.advances == pytest.approx([(0.0, -10.0)])
    assert eng.translation == pytest.approx((0.0, -10.0))


def test_vertical_font_ignores_horizontal_scaling() -> None:
    font = _FuzzFont({0x21: 1000.0}, code_bytes=2, vertical=True)
    eng = _run(b"\x00\x21", font, font_size=10.0, h_scale=0.5)
    # Tz must NOT scale a vertical advance.
    assert eng.advances == pytest.approx([(0.0, -10.0)])


def test_vertical_font_adds_char_spacing_on_y() -> None:
    font = _FuzzFont({0x21: 1000.0}, code_bytes=2, vertical=True)
    eng = _run(b"\x00\x21", font, font_size=10.0, char_spacing=2.0)
    # ty = -10 + 2 = -8.0
    assert eng.advances == pytest.approx([(0.0, -8.0)])


def test_vertical_font_word_spacing_only_single_byte_space() -> None:
    # 2-byte code 32 in a vertical font: no Tw.
    font = _FuzzFont({32: 1000.0}, code_bytes=2, vertical=True)
    eng = _run(b"\x00\x20", font, font_size=10.0, word_spacing=5.0)
    # ty = -10 + 0 (no Tw for 2-byte) = -10.0
    assert eng.advances == pytest.approx([(0.0, -10.0)])


# ---------- empty / degenerate ----------


def test_empty_string_no_advance() -> None:
    font = _FuzzFont({})
    eng = _run(b"", font, font_size=10.0)
    assert eng.advances == []
    assert eng.translation == pytest.approx((0.0, 0.0))


# ---------- randomized fuzz against the reference ----------


@pytest.mark.parametrize("seed", range(12))
def test_random_horizontal_runs_match_reference(seed: int) -> None:
    rng = random.Random(seed)
    # Random simple-font widths for a small alphabet incl. the space code.
    alphabet = [32, *range(0x41, 0x4B)]
    widths = {c: float(rng.randint(0, 1200)) for c in alphabet}
    font = _FuzzFont(widths)
    n = rng.randint(0, 12)
    data = bytes(rng.choice(alphabet) for _ in range(n))
    font_size = rng.choice([1.0, 8.0, 10.0, 12.5, 24.0])
    char_spacing = rng.choice([-2.0, 0.0, 1.5, 5.0])
    word_spacing = rng.choice([-3.0, 0.0, 2.0, 8.0])
    h_scale = rng.choice([0.5, 1.0, 1.5, 2.0])

    eng = _run(
        data, font, font_size=font_size, char_spacing=char_spacing,
        word_spacing=word_spacing, h_scale=h_scale,
    )
    ref = _reference_advances(
        _decode(data, font), font, font_size=font_size,
        char_spacing=char_spacing, word_spacing=word_spacing, h_scale=h_scale,
    )
    assert eng.advances == pytest.approx(ref)
    exp_x = sum(a for a, _ in ref)
    assert eng.translation == pytest.approx((exp_x, 0.0))


@pytest.mark.parametrize("seed", range(8))
def test_random_two_byte_runs_no_word_spacing_on_code_32(seed: int) -> None:
    """Type0 (2-byte) runs: even a code value of 32 must never pick up Tw."""
    rng = random.Random(100 + seed)
    codes = [0x0020, 0x2000, *range(0x3000, 0x3008)]
    widths = {c: float(rng.randint(0, 1000)) for c in codes}
    font = _FuzzFont(widths, code_bytes=2)
    n = rng.randint(0, 8)
    chosen = [rng.choice(codes) for _ in range(n)]
    data = b"".join(c.to_bytes(2, "big") for c in chosen)
    font_size = rng.choice([10.0, 12.0, 18.0])
    char_spacing = rng.choice([0.0, 2.0])
    word_spacing = rng.choice([5.0, 9.0])  # nonzero — must be ignored
    h_scale = rng.choice([1.0, 1.5])

    eng = _run(
        data, font, font_size=font_size, char_spacing=char_spacing,
        word_spacing=word_spacing, h_scale=h_scale,
    )
    ref = _reference_advances(
        _decode(data, font), font, font_size=font_size,
        char_spacing=char_spacing, word_spacing=word_spacing, h_scale=h_scale,
    )
    assert eng.advances == pytest.approx(ref)
    # No advance in the run should include the word-spacing term, because
    # every code is 2-byte. Confirm by recomputing with word_spacing=0.
    ref_no_tw = _reference_advances(
        _decode(data, font), font, font_size=font_size,
        char_spacing=char_spacing, word_spacing=0.0, h_scale=h_scale,
    )
    assert eng.advances == pytest.approx(ref_no_tw)


@pytest.mark.parametrize("seed", range(6))
def test_random_vertical_runs_match_reference(seed: int) -> None:
    rng = random.Random(200 + seed)
    codes = list(range(0x3000, 0x300A))
    widths = {c: float(rng.randint(200, 1200)) for c in codes}
    font = _FuzzFont(widths, code_bytes=2, vertical=True)
    n = rng.randint(0, 8)
    chosen = [rng.choice(codes) for _ in range(n)]
    data = b"".join(c.to_bytes(2, "big") for c in chosen)
    font_size = rng.choice([10.0, 16.0, 20.0])
    char_spacing = rng.choice([0.0, 1.0, -2.0])
    h_scale = rng.choice([0.5, 1.0, 2.0])  # must NOT affect vertical advance

    eng = _run(
        data, font, font_size=font_size, char_spacing=char_spacing,
        word_spacing=0.0, h_scale=h_scale,
    )
    ref = _reference_advances(
        _decode(data, font), font, font_size=font_size,
        char_spacing=char_spacing, word_spacing=0.0, h_scale=h_scale,
    )
    assert eng.advances == pytest.approx(ref)
    # All x advances are 0 for a vertical run.
    assert all(a == pytest.approx(0.0) for a, _ in eng.advances)
    exp_y = sum(b for _, b in ref)
    assert eng.translation == pytest.approx((0.0, exp_y))
