import logging
import math
import re
import struct
import sys
import unicodedata
from array import array
from collections.abc import Callable
from dataclasses import replace
from functools import cmp_to_key
from typing import TYPE_CHECKING, Protocol

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNumber, COSStream, COSString
from pypdfbox.fontbox.cmap import CMap, CMapParser
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.util.iterative_merge_sort import IterativeMergeSort
from pypdfbox.util.matrix import Matrix, f32

from ._tim_sort import ComparisonContractError, tim_sort
from .bidi import BidiResolver, get_paragraph_direction
from .bidi import _reorder_indices as _bidi_reorder_indices
from .position_wrapper import PositionWrapper
from .text_position import _IS_DIACRITIC, TextPosition
from .word_with_text_positions import WordWithTextPositions

_log = logging.getLogger(__name__)

# Unicode bidi-mirroring map for L4 — pairs are derived from
# ``unicodedata.mirrored`` at module load time. The PDFBox upstream
# parses ``BidiMirroring.txt`` from its bundled resources; we use the
# same data already vendored in Python's UCD via the ``mirrored``
# property. The map covers paired punctuation (`(` <-> `)`, `[` <-> `]`,
# `{` <-> `}`, the angle and corner brackets, the mathematical
# delimiters, etc.) — every codepoint whose mirrored bidi-class
# substitution is one well-defined other codepoint.
_BIDI_MIRROR_MAP: dict[str, str] = {
    "(": ")",
    ")": "(",
    "[": "]",
    "]": "[",
    "{": "}",
    "}": "{",
    "<": ">",
    ">": "<",
    "«": "»",  # « »
    "»": "«",
    "‹": "›",  # ‹ ›
    "›": "‹",
    "⌈": "⌉",  # ⌈ ⌉
    "⌉": "⌈",
    "⌊": "⌋",  # ⌊ ⌋
    "⌋": "⌊",
    "⟨": "⟩",  # ⟨ ⟩
    "⟩": "⟨",
    "⟪": "⟫",  # ⟪ ⟫
    "⟫": "⟪",
    "〈": "〉",  # 〈 〉
    "〉": "〈",
    "〈": "〉",  # 〈 〉 (CJK)
    "〉": "〈",
    "《": "》",  # 《 》
    "》": "《",
    "「": "」",  # 「 」
    "」": "「",
    "『": "』",  # 『 』
    "』": "『",
    "【": "】",  # 【 】
    "】": "【",
    "〔": "〕",  # 〔 〕
    "〕": "〔",
    "〖": "〗",  # 〖 〗
    "〗": "〖",
    "〘": "〙",  # 〘 〙
    "〙": "〘",
    "〚": "〛",  # 〚 〛
    "〛": "〚",
}

if TYPE_CHECKING:
    from pypdfbox.cos import COSBase
    from pypdfbox.pdmodel import PDDocument, PDPage
    from pypdfbox.pdmodel.font import PDFont
    from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
        PDOutlineItem,
    )
    from pypdfbox.pdmodel.pd_resources import PDResources


class _TextWriter(Protocol):
    def write(self, text: str) -> object: ...


def _dup_window_hit_flat(
    coords: list[float],
    x_lo: float,
    x_hi: float,
    y_lo: float,
    y_hi: float,
) -> bool:
    """Return ``True`` if any origin of the flat ``[x0, y0, x1, y1, ...]``
    list falls inside the half-open window ``[x_lo, x_hi) x [y_lo, y_hi)``.

    The exact predicate the duplicate-overlap suppressor applies to every
    recorded origin (Java's from-inclusive, to-exclusive ``subMap`` /
    ``subSet``), shared by its grid probe and its full scans.
    """
    it = iter(coords)
    return any(
        x_lo <= x_key < x_hi and y_lo <= y_val < y_hi
        for x_key, y_val in zip(it, it, strict=False)
    )


def _dup_grid_hit(
    grid: dict[int, list[float]],
    cx0: int | None,
    cx1: int,
    cy0: int,
    cy1: int,
    x_lo: float,
    x_hi: float,
    y_lo: float,
    y_hi: float,
) -> bool:
    """Whether a recorded origin in the duplicate suppressor's ``grid`` lies
    in the window, probing the cells ``cx0..cx1`` x ``cy0..cy1`` (``cx0`` is
    ``None`` when the window cannot be indexed)."""
    if cx0 is None or (cx1 - cx0 + 1) * (cy1 - cy0 + 1) > 128:
        # No cell yet, a non-finite window (inf tolerance), or a tolerance
        # spanning a huge multiple of the cell (widely varying per-run tol):
        # scanning every recorded origin is still exact and never slower
        # than the original linear scan.
        return any(
            _dup_window_hit_flat(cell_pts, x_lo, x_hi, y_lo, y_hi)
            for cell_pts in grid.values()
        )
    row_stride = _GRID_ROW
    grid_get = grid.get
    for cx in range(cx0, cx1 + 1):
        row = cx * row_stride
        for cy in range(cy0, cy1 + 1):
            cell_pts = grid_get(row + cy)
            if cell_pts and _dup_window_hit_flat(cell_pts, x_lo, x_hi, y_lo, y_hi):
                return True
    return False


_F32_STRUCT = struct.Struct("<f")
_f32_pack = _F32_STRUCT.pack
_f32_unpack = _F32_STRUCT.unpack


# The exact shortcuts of the hot paths (memos, float32 array narrowing,
# inlined stock hooks). Tests turn them off to rerun extraction on the plain
# code paths they shortcut and compare the results.
_USE_FAST_PATHS = True

_SINGLE_BYTE_READERS: frozenset[object] | None = None


def _single_byte_readers() -> frozenset[object]:
    """The stock ``read_code`` functions that read one byte per code."""
    global _SINGLE_BYTE_READERS
    if _SINGLE_BYTE_READERS is None:
        from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
        from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
        from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
        from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

        _SINGLE_BYTE_READERS = frozenset(
            {
                PDTrueTypeFont.read_code,
                PDType1Font.read_code,
                PDType1CFont.read_code,
                PDType3Font.read_code,
            }
        )
    return _SINGLE_BYTE_READERS


def _f32(value: float) -> float:
    """:func:`pypdfbox.util.matrix.f32` without its NaN / infinity checks
    (``struct`` round-trips those), for the per-glyph hot paths."""
    try:
        return _f32_unpack(_f32_pack(value))[0]
    except OverflowError:
        return f32(value)


_F32X2_STRUCT = struct.Struct("<2f")
_f32x2_pack = _F32X2_STRUCT.pack
_f32x2_unpack = _F32X2_STRUCT.unpack


def _f32x2(first: float, second: float) -> tuple[float, float]:
    """Two :func:`_f32` narrowings in one ``struct`` round trip."""
    try:
        return _f32x2_unpack(_f32x2_pack(first, second))
    except OverflowError:
        return f32(first), f32(second)


# Row stride of the duplicate suppressor's flattened grid keys. Two cells may
# share a key; the grid only proposes candidates, so that costs a comparison,
# never a wrong decision.
_GRID_ROW = 1_000_003

_F32X3_STRUCT = struct.Struct("<3f")
_f32x3_pack = _F32X3_STRUCT.pack
_f32x3_unpack = _F32X3_STRUCT.unpack
_F32X4_STRUCT = struct.Struct("<4f")
_f32x4_pack = _F32X4_STRUCT.pack
_f32x4_unpack = _F32X4_STRUCT.unpack
_F32X5_STRUCT = struct.Struct("<5f")


def _glyph_step_reference(
    glyph_x: float,
    glyph_y: float,
    displacement: float,
    font_size: float,
    th: float,
    char_spacing: float,
    word_spacing: float,
    tm_a: float,
    tm_b: float,
    c0: float,
    c4: float,
    c6: float,
    c7: float,
    x_scale: float,
) -> tuple[float, float, float, float, float, float, float, float]:
    """One glyph of :meth:`PDFTextStripper._emit_glyphs` without text rise or
    CTM shear, one float32 narrowing at a time.

    Returns ``(origin_x, origin_y, end_x, end_y, dx_display, width, next_x,
    next_y)``: the device origin and legacy end point (the bare displacement
    through the text matrix and CTM), the end point's distance from the
    origin, the scaled glyph width and the advanced text cursor. The
    reference for the batched narrowings of
    :meth:`PDFTextStripper._emit_glyphs`.
    """
    dx = _f32(_f32(displacement * font_size) * th)
    e, g = _f32x2(glyph_x, glyph_y)
    origin_x, origin_y = _f32x2(e * c0, g * c4)
    origin_x, origin_y = _f32x2(origin_x + c6, origin_y + c7)
    end_tx, end_ty = _f32x2(dx * tm_a, dx * tm_b)
    end_tx, end_ty = _f32x2(end_tx + e, end_ty + g)
    end_x, end_y = _f32x2(end_tx * c0, end_ty * c4)
    end_x, end_y = _f32x2(end_x + c6, end_y + c7)
    dx_display = _f32(end_x - origin_x)
    width = abs(_f32(dx * x_scale))
    advance = _f32(
        _f32(_f32(_f32(displacement * font_size) + char_spacing) + word_spacing) * th
    )
    step_x, step_y = _f32x2(advance * tm_a, advance * tm_b)
    next_x, next_y = _f32x2(glyph_x + step_x, glyph_y + step_y)
    return origin_x, origin_y, end_x, end_y, dx_display, width, next_x, next_y


def _plain_glyph_step(
    displacement: float,
    font_size: float,
    th: float,
    char_spacing: float,
    word_spacing: float,
    tm_a: float,
    tm_b: float,
    x_scale: float,
) -> tuple[float, float, float, float, float]:
    """The cursor-independent float steps of :func:`_glyph_step_reference`.

    Returns ``(f32(dx * tm_a), f32(dx * tm_b), step_x, step_y, width)``: the
    bare displacement through the text matrix (before the cursor is added),
    the advance through the text matrix and the scaled glyph width.
    """
    dfs = _f32(displacement * font_size)
    dx = _f32(dfs * th)
    advance = _f32(_f32(_f32(dfs + char_spacing) + word_spacing) * th)
    return (
        _f32(dx * tm_a),
        _f32(dx * tm_b),
        _f32(advance * tm_a),
        _f32(advance * tm_b),
        abs(_f32(dx * x_scale)),
    )


_PLAIN_STEP_KEY = struct.Struct("<7d")


# Java ``Float.MAX_VALUE`` — upstream's reset sentinels for the line state.
_FLT_MAX = 3.4028234663852886e38


def _java_round(value: float) -> int:
    """Java ``Math.round(float)``: round half up (``floor(x + 0.5)``)."""
    if math.isnan(value):
        return 0
    if math.isinf(value):
        return 2**31 - 1 if value > 0 else -(2**31)
    return math.floor(value + 0.5)


def _fdiv(numerator: float, denominator: float) -> float:
    """Java floating-point division: ``x / 0`` is a signed infinity or NaN."""
    if denominator == 0:
        if numerator == 0 or math.isnan(numerator):
            return math.nan
        return math.copysign(math.inf, numerator) * math.copysign(1.0, denominator)
    return numerator / denominator


def _java_dir(a: float, b: float, c: float, d: float) -> float:
    """Upstream ``TextPosition.getDir`` on a text rendering matrix.

    ``a`` / ``d`` are the matrix's Y and X scale cells and ``b`` / ``c`` its
    Y and X shear cells, in the order upstream reads them. Any matrix that
    matches none of the four quadrant patterns (e.g. a 45 degree rotation)
    reports ``0``.
    """
    if a > 0 and abs(b) < d and abs(c) < a and d > 0:
        return 0.0
    if a < 0 and abs(b) < abs(d) and abs(c) < abs(a) and d < 0:
        return 180.0
    if abs(a) < abs(c) and b > 0 and c < 0 and abs(d) < b:
        return 90.0
    if abs(a) < c and b < 0 and c > 0 and abs(d) < abs(b):
        return 270.0
    return 0.0


def _tj_step_reference(
    adjustment: float,
    font_size: float,
    th: float,
    tm_a: float,
    tm_b: float,
    text_x: float,
    text_y: float,
) -> tuple[float, float]:
    """The text cursor after a horizontal ``TJ`` number, one float32
    narrowing at a time (upstream ``tx = -tj / 1000 * fontSize *
    horizontalScaling``, then ``textMatrix.translate(tx, 0)``)."""
    tx = _f32(_f32(_f32(-adjustment / 1000.0) * font_size) * th)
    return _f32(text_x + _f32(tx * tm_a)), _f32(text_y + _f32(tx * tm_b))


def _tj_step(
    adjustment: float,
    font_size: float,
    th: float,
    tm_a: float,
    tm_b: float,
    text_x: float,
    text_y: float,
) -> tuple[float, float]:
    """:func:`_tj_step_reference` with the paired narrowings batched."""
    try:
        tx = _f32_unpack(_f32_pack(-adjustment / 1000.0))[0]
        tx = _f32_unpack(_f32_pack(tx * font_size))[0]
        tx = _f32_unpack(_f32_pack(tx * th))[0]
        step_x, step_y = _f32x2_unpack(_f32x2_pack(tx * tm_a, tx * tm_b))
        return _f32x2_unpack(_f32x2_pack(text_x + step_x, text_y + step_y))
    except OverflowError:
        return _tj_step_reference(adjustment, font_size, th, tm_a, tm_b, text_x, text_y)


def _word_metrics_reference(
    word_spacing: float,
    last_word_spacing: float,
    previous_ave_char_width: float,
    position_x: float,
    position_width: float,
    word_char_count: int,
    end_of_last_text_x: float,
    spacing_tolerance: float,
    average_char_tolerance: float,
) -> tuple[float, float, float, float]:
    """The per-glyph word-break metrics of upstream ``writePage``, one float32
    narrowing at a time.

    Returns ``(delta_space, average_char_width, new_end_of_text_x,
    expected_start_of_next_word_x)``. The reference for the batched copy in
    :meth:`PDFTextStripper._write_articles`.
    """
    if word_spacing == 0 or math.isnan(word_spacing):
        delta_space = _FLT_MAX
    elif last_word_spacing < 0:
        delta_space = _f32(word_spacing * spacing_tolerance)
    else:
        delta_space = _f32(
            _f32(_f32(word_spacing + last_word_spacing) / 2) * spacing_tolerance
        )
    if previous_ave_char_width < 0:
        average_char_width = _f32(position_width / word_char_count)
    else:
        average_char_width = _f32(
            _f32(previous_ave_char_width + _f32(position_width / word_char_count)) / 2
        )
    delta_char_width, new_end_of_text_x = _f32x2(
        average_char_width * average_char_tolerance, position_x + position_width
    )
    expected_start_of_next_word_x = -_FLT_MAX
    if end_of_last_text_x != -1.0:
        expected_start_of_next_word_x = _f32(
            end_of_last_text_x + min(delta_space, delta_char_width)
        )
    return delta_space, average_char_width, new_end_of_text_x, expected_start_of_next_word_x


class _JavaGeometry:
    """Upstream ``TextPosition`` coordinates of one position.

    Derived once from the device-space geometry with upstream's formulas
    (``getXRot`` / ``getYLowerLeftRot`` / ``getWidthRot``), in upstream's
    upper-left (y-down) frame and in float32, so the line, word, paragraph
    and sort logic can follow ``PDFTextStripper.writePage`` and
    ``TextPositionComparator`` literally.
    """

    __slots__ = (
        "dir",
        "x",
        "y",
        "width",
        "x_dir_adj",
        "y_dir_adj",
        "width_dir_adj",
        "height",
        "width_of_space",
    )

    def __init__(self, pos: TextPosition) -> None:
        tx = pos.device_x
        ty = pos.device_y
        end_x = pos.device_end_x
        end_y = pos.device_end_y
        if (
            tx is not None
            and ty is not None
            and end_x is not None
            and end_y is not None
            and pos.rotation % 360.0 == 0.0
            and pos.dir % 360.0 == 0.0
        ):
            # The common upright glyph on an unrotated page: the general
            # formulas below with rotation and direction 0 (``x = tx``,
            # ``y = pageHeight - ty``, ``width = |endX - tx|``).
            ph = _f32(pos.page_height)
            try:
                y, width = _f32x2_unpack(_f32x2_pack(ph - ty, end_x - tx))
            except OverflowError:
                y = f32(ph - ty)
                width = f32(end_x - tx)
            width = abs(width)
            self.dir = 0.0
            self.x = self.x_dir_adj = tx
            self.y = self.y_dir_adj = y
            self.width = self.width_dir_adj = width
            self.height = abs(pos.height)
            self.width_of_space = abs(pos.width_of_space)
            return
        if tx is None or ty is None or end_x is None or end_y is None:
            # A position built by hand: its stored origin and width stand in
            # for the device geometry, laid along its text direction.
            tx = _f32(pos.x)
            ty = _f32(pos.y)
            theta = math.radians(pos.dir % 360.0)
            end_x = _f32(tx + pos.width * math.cos(theta))
            end_y = _f32(ty + pos.width * math.sin(theta))
        pw = _f32(pos.page_width)
        ph = _f32(pos.page_height)
        rotation = pos.rotation % 360.0
        direction = pos.dir % 360.0

        def x_rot(r: float) -> float:
            if r == 0.0:
                return tx
            if r == 90.0:
                return ty
            if r == 180.0:
                return _f32(pw - tx)
            if r == 270.0:
                return _f32(ph - ty)
            return 0.0

        def y_lower_left_rot(r: float) -> float:
            if r == 0.0:
                return ty
            if r == 90.0:
                return _f32(pw - tx)
            if r == 180.0:
                return _f32(ph - ty)
            if r == 270.0:
                return tx
            return 0.0

        def width_rot(r: float) -> float:
            if r in (90.0, 270.0):
                return abs(_f32(end_y - ty))
            return abs(_f32(end_x - tx))

        self.dir = direction
        self.x = x_rot(rotation)
        extent = ph if rotation in (0.0, 180.0) else pw
        self.y = _f32(extent - y_lower_left_rot(rotation))
        self.width = width_rot(rotation)
        if direction == rotation:
            self.x_dir_adj = self.x
            self.y_dir_adj = self.y
            self.width_dir_adj = self.width
        else:
            self.x_dir_adj = x_rot(direction)
            extent = ph if direction in (0.0, 180.0) else pw
            self.y_dir_adj = _f32(extent - y_lower_left_rot(direction))
            self.width_dir_adj = width_rot(direction)
        if pos.device_x is not None:
            # A glyph from the stripper: float values, its real (possibly
            # zero) height.
            self.height = abs(pos.height)
            self.width_of_space = abs(pos.width_of_space)
        else:
            # A hand-built position falls back to its font size.
            self.height = abs(_f32(pos.get_height()))
            self.width_of_space = abs(_f32(pos.width_of_space))


def _java_geometry(pos: TextPosition) -> _JavaGeometry:
    """Return (and cache on ``pos``) its :class:`_JavaGeometry`."""
    # Plain attribute access (not ``pos.__dict__``) keeps the instance's
    # inline attribute storage instead of materialising a per-glyph dict.
    geometry = getattr(pos, "_java_geometry", None)
    if geometry is None:
        geometry = pos._java_geometry = _JavaGeometry(pos)
    return geometry


_F32_TENTH = _f32(0.1)
# The Unicode presentation-form blocks ``normalize_word`` decomposes.
_PRESENTATION_FORM = re.compile("[\uFB00-\uFDFF\uFE70-\uFEFF]")
# ``2 ** -125``: halving a float32 at least this large stays a normal
# float32, so the division is exact.
_F32_MIN_HALVABLE = 2.0**-125


def _java_overlap(y1: float, height1: float, y2: float, height2: float) -> bool:
    """Upstream ``PDFTextStripper.overlap`` (with ``within``) in float32."""
    variance = _F32_TENTH
    try:
        low, high = _f32x2_unpack(_f32x2_pack(y1 - variance, y1 + variance))
    except OverflowError:
        low, high = _f32x2(y1 - variance, y1 + variance)
    if low < y2 < high:
        return True
    if y2 <= y1 and y2 >= _f32(y1 - height1):
        return True
    return y1 <= y2 and y1 >= _f32(y2 - height2)


def _java_compare(pos1: TextPosition, pos2: TextPosition) -> int:
    """Upstream ``TextPositionComparator.compare`` on Java geometry."""
    try:
        g1 = pos1._java_geometry or _java_geometry(pos1)
    except AttributeError:
        g1 = _java_geometry(pos1)
    try:
        g2 = pos2._java_geometry or _java_geometry(pos2)
    except AttributeError:
        g2 = _java_geometry(pos2)
    dir1 = g1.dir
    dir2 = g2.dir
    if dir1 != dir2:
        return -1 if dir1 < dir2 else 1
    pos1_y_bottom = g1.y_dir_adj
    pos2_y_bottom = g2.y_dir_adj
    try:
        y_difference = abs(_f32_unpack(_f32_pack(pos1_y_bottom - pos2_y_bottom))[0])
    except OverflowError:
        y_difference = abs(f32(pos1_y_bottom - pos2_y_bottom))
    if y_difference >= _F32_TENTH or y_difference != y_difference:
        # (0, 0) is the upper-left corner: a position's top is above its
        # bottom. (Only needed when the bottoms are not within 0.1.)
        pos1_y_top, pos2_y_top = _f32x2(pos1_y_bottom - g1.height, pos2_y_bottom - g2.height)
        if not (
            pos1_y_top <= pos2_y_bottom <= pos1_y_bottom
            or pos2_y_top <= pos1_y_bottom <= pos2_y_bottom
        ):
            if pos1_y_bottom < pos2_y_bottom:
                return -1
            return 1
    x1 = g1.x_dir_adj
    x2 = g2.x_dir_adj
    if x1 < x2:
        return -1
    if x1 > x2:
        return 1
    return 0


def _java_contains(pos: TextPosition, other: TextPosition) -> bool:
    """Upstream ``TextPosition.contains`` (used for diacritic merging)."""
    g = _java_geometry(pos)
    o = _java_geometry(other)
    this_x_start = g.x_dir_adj
    this_width = g.width_dir_adj
    this_x_end = this_x_start + this_width
    other_x_start = o.x_dir_adj
    other_x_end = other_x_start + o.width_dir_adj
    if other_x_end <= this_x_start or other_x_start >= this_x_end:
        return False
    this_y_start = g.y_dir_adj
    other_y_start = o.y_dir_adj
    if (
        other_y_start + o.height < this_y_start
        or other_y_start > this_y_start + g.height
    ):
        return False
    if other_x_start > this_x_start and other_x_end > this_x_end:
        return _fdiv(this_x_end - other_x_start, this_width) > 0.15
    if other_x_start < this_x_start and other_x_end < this_x_end:
        return _fdiv(other_x_end - this_x_start, this_width) > 0.15
    return True


def _java_completely_contains(pos: TextPosition, other: TextPosition) -> bool:
    """Upstream ``TextPosition.completelyContains`` (contained spaces)."""
    g = _java_geometry(pos)
    o = _java_geometry(other)
    this_left = g.x_dir_adj
    this_right = _f32(this_left + g.width_dir_adj)
    other_left = o.x_dir_adj
    other_right = _f32(other_left + o.width_dir_adj)
    if this_left > other_left or other_right > this_right:
        return False
    this_top = g.y_dir_adj
    this_bottom = _f32(this_top + g.height)
    other_top = o.y_dir_adj
    other_bottom = _f32(other_top + o.height)
    return not (this_top > other_top or other_bottom > this_bottom)


def _java_individual_widths(pos: TextPosition) -> list[float]:
    widths = pos.individual_widths
    if widths is None:
        widths = pos.get_individual_widths()
    return widths


def _java_merge_diacritic(pos: TextPosition, diacritic: TextPosition) -> None:
    """Upstream ``TextPosition.mergeDiacritic`` / ``insertDiacritic``."""
    diacritic_text = diacritic.get_unicode()
    if len(diacritic_text) > 1:
        return
    diacritic_widths = _java_individual_widths(diacritic)
    diac_x_start = _java_geometry(diacritic).x_dir_adj
    diac_x_end = _f32(diac_x_start + (diacritic_widths[0] if diacritic_widths else 0.0))
    curr_char_x_start = _java_geometry(pos).x_dir_adj
    widths = list(_java_individual_widths(pos))
    unicode = pos.get_unicode()
    str_len = len(unicode)

    def insert(i: int) -> None:
        text = pos.get_unicode()
        new_widths = widths[:i] + [widths[i], 0.0] + widths[i + 1 :]
        head = text[: i + 1]
        rest_from = i + 1
        combined = TextPosition.combine_diacritic(diacritic_text)
        pos.text = head + combined + text[rest_from:]
        pos.individual_widths = new_widths

    for i in range(str_len):
        if i >= len(widths):
            _log.info(
                "diacritic %s on ligature %s is not supported yet and is ignored "
                "(PDFBOX-2831)",
                diacritic_text,
                unicode,
            )
            break
        curr_char_x_end = _f32(curr_char_x_start + widths[i])
        if diac_x_start < curr_char_x_start and diac_x_end <= curr_char_x_end:
            if i == 0:
                insert(i)
            else:
                percentage1 = _fdiv(_f32(diac_x_end - curr_char_x_start), widths[i])
                percentage2 = _fdiv(_f32(curr_char_x_start - diac_x_start), widths[i - 1])
                insert(i if percentage1 >= percentage2 else i - 1)
            return
        if diac_x_start < curr_char_x_start or diac_x_end <= curr_char_x_end:
            insert(i)
            return
        if i == str_len - 1:
            insert(i)
            return
        curr_char_x_start = _f32(curr_char_x_start + widths[i])


class PDFTextStripper:
    """Lite single-column text extractor.

    Mirrors the public surface of
    ``org.apache.pdfbox.text.PDFTextStripper`` for the subset that
    pypdfbox supports today: page-range selection, configurable line and
    word separators, a per-page extraction hook (``process_page``),
    ``/ToUnicode`` CMap decoding, ``/Differences``-based glyph→unicode
    decoding for simple fonts without ``/ToUnicode``, and font-width-
    based word-gap heuristics when the font carries a ``/Widths``
    array. Layout reconstruction, multi-column reading-order sorting,
    ``/MarkInfo`` semantic awareness, and paragraph detection are
    deliberately deferred — see ``CHANGES.md`` for the consolidated
    diverge list.

    The walk parses each page's content stream via :class:`PDFStreamParser`
    directly rather than going through
    :class:`pypdfbox.contentstream.operator.OperatorRegistry`. The
    registry is for typed, side-effecting dispatch (graphics-state mutation
    during rendering); the stripper just needs to fold operator tuples
    into a small text-state machine.
    """

    # Set by ``process_page`` while it extracts an unrotated page whose
    # positions ``_apply_page_rotation`` then folds: ``_emit_glyphs`` may
    # build an upright glyph's ``_JavaGeometry`` up front.
    _fold_upright_geometry: bool = False

    # Heuristic threshold (in multiples of the current font size) above
    # which a horizontal advance counts as a word break rather than a
    # tight glyph-to-glyph step. Loose because lite-mode lacks real
    # glyph-width metrics, but tight enough that two ``Tj`` calls on the
    # same line emit a single space when they're visibly apart.
    _WORD_GAP_FACTOR: float = 1.5

    # Regex source list mirroring upstream's private
    # ``LIST_ITEM_EXPRESSIONS`` array — common bullet/number/letter list
    # markers (e.g. ``1.``, ``[2]``, ``A)``, ``iv.``). Consulted by
    # ``get_list_item_patterns`` when no caller-supplied list has been
    # set via ``set_list_item_patterns``. Order matters: most specific
    # patterns come first so ``match_pattern`` finds the tightest fit.
    LIST_ITEM_EXPRESSIONS: tuple[str, ...] = (
        r"\.",
        r"\d+\.",
        r"\[\d+\]",
        r"\d+\)",
        r"[A-Z]\.",
        r"[a-z]\.",
        r"[A-Z]\)",
        r"[a-z]\)",
        r"[IVXL]+\.",
        r"[ivxl]+\.",
    )

    def __init__(self) -> None:
        # Upstream defaults end_page to ``Integer.MAX_VALUE`` (2**31 - 1);
        # pypdfbox keeps ``sys.maxsize`` for backward compatibility with
        # the existing lite stripper API. The practical effect is the
        # same — both sentinels are clamped to ``len(pages)`` in
        # ``get_text``.
        self._start_page: int = 1
        self._end_page: int = sys.maxsize
        self._should_separate_by_beads: bool = True
        self._suppress_duplicate_overlapping_text: bool = True  # inert holder
        self._sort_by_position: bool = False
        # Y-axis up vs Y-axis down. Upstream PDFBox flips the axes via
        # ``setShouldFlipAxes`` so that a rotated-90 page can be extracted
        # as if it were portrait. Lite mode mirrors the flag and applies it
        # at the formatting layer: when ``True`` the line-break heuristic
        # treats *X* as the line-stepping axis and *Y* as the word-flow
        # axis (transposing the role of the two coordinates).
        self._flip_axes: bool = False
        self._paragraph_start: str = ""
        # Upstream PDFBox defaults ``paragraphEnd`` to ``""`` and emits the
        # line terminator separately (``writeLineSeparator``). The lite
        # stripper previously defaulted this to ``"\n"``, which doubled the
        # newline at every detected paragraph break (``write_paragraph_end``
        # + ``write_line_separator`` both fired ``"\n"``), inserting a
        # spurious blank line that the Java oracle never emits. Match
        # upstream's empty default so a paragraph break collapses to the
        # single ``line_separator`` newline.
        self._paragraph_end: str = ""
        self._page_start: str = ""
        self._page_end: str = "\n"
        self._word_separator: str = " "
        self._line_separator: str = "\n"
        # Article delimiters — emitted around every "article" (one
        # ``/StructTreeRoot/Article`` bead chain in upstream, but the
        # lite stripper treats the whole page body as a single article
        # so these wrap the same span as ``page_start`` / ``page_end``
        # when ``setShouldSeparateByBeads(true)`` is in effect.
        self._article_start: str = ""
        self._article_end: str = ""
        # Bookmark-bounded extraction range. ``start_bookmark`` (when
        # set) clamps ``start_page`` to the page the bookmark resolves
        # to; ``end_bookmark`` does the same for ``end_page``. Either
        # may be ``None``. Per upstream, when both are set the bookmark
        # range overrides the explicit page range.
        self._start_bookmark: PDOutlineItem | None = None
        self._end_bookmark: PDOutlineItem | None = None
        # Inert layout-tuning holders preserved for upstream API parity.
        # The lite extraction loop doesn't yet consume these; they exist
        # so callers can configure a stripper exactly as they would in
        # Java PDFBox without having to branch on which subset is wired.
        self._drop_threshold: float = 2.5
        self._indent_threshold: float = 2.0
        self._spacing_tolerance: float = 0.5
        self._average_char_tolerance: float = 0.3
        self._add_more_formatting: bool = False
        self._lenient_stream_parsing: bool = True
        # Inert holder mirroring upstream's
        # ``setIgnoreContentStreamSpaceGlyphs`` (added on 3.x). When
        # ``True``, the upstream extractor drops space glyphs found in
        # the content stream and relies purely on the gap heuristic for
        # word breaks. The lite stripper exposes the flag so callers
        # can configure it identically; the formatting layer doesn't
        # currently consume it because the lite walk doesn't materialise
        # individual space glyphs separately from their host runs.
        self._ignore_content_stream_space_glyphs: bool = False
        # 1-based current-page cursor. Upstream ``getCurrentPageNo``
        # exposes this for subclasses that want to disambiguate the
        # active page within ``processPage`` / ``startPage`` /
        # ``endPage`` hooks. Reset at the start of every ``get_text``
        # walk; updated by ``process_page`` once we know the page index.
        self._current_page_no: int = 0
        # Per-page CMap cache + active page handle for /ToUnicode lookup.
        # ``_cmap_cache`` keys are font resource names (the same ones the
        # ``Tf`` operator names); the value is the parsed ``CMap`` or
        # ``None`` when the font has no ``/ToUnicode`` entry. The cache
        # lifetime is one ``process_page`` invocation — we reset it on
        # entry so a fresh page's ``/Resources`` chain is consulted from
        # scratch (font dicts may be re-defined per page).
        self._cmap_cache: dict[str, CMap | None] = {}
        # ``_read_glyphs`` memo, keyed by ``(id(font), id(cmap))``; each entry
        # holds the font and CMap so a reused id is never mistaken for them.
        self._glyph_memo: dict[tuple[int, int], tuple] = {}
        # ``(font, cmap, glyph memo, font name, per-byte glyph memo)`` of the
        # last horizontal one-byte font ``_emit_run`` read (see there).
        self._run_font: tuple | None = None
        # The position list ``_emit_glyphs`` last appended prefolded
        # positions to (see ``_apply_page_rotation``), and how many.
        self._prefolded_positions: list[TextPosition] | None = None
        self._prefolded_count = 0
        # ``_font_traits`` memo, keyed by ``id(font)`` (entries hold the font).
        self._font_traits_memo: dict[int, tuple] = {}
        self._font_vertical_memo: dict[int, tuple] = {}
        # Per-page typed-font cache. Lazily populated on ``Tf`` so the
        # glyph-decoder path (``/Differences`` lookup) and the width-based
        # word-gap heuristic can both consult ``PDFont.get_widths`` /
        # ``PDSimpleFont.decode`` without reparsing the font dict for
        # every show-text operator.
        self._font_cache: dict[str, PDFont | None] = {}
        self._active_page: PDPage | None = None
        # Page-rotation bookkeeping for the per-page coordinate fold. Mirrors
        # upstream ``LegacyPDFStreamEngine``'s ``pageRotation`` / ``pageSize``
        # fields (LegacyPDFStreamEngine.java:82-83, set in ``processPage``).
        # The page ``/Rotate`` (0/90/180/270) and the cropbox extents feed the
        # ``TextPosition`` page-rotation accessors (``getX``/``getY``/``getWidth``,
        # via ``getXRot``/``getYLowerLeftRot``/``getWidthRot`` —
        # TextPosition.java:293-446) so a rotated page's runs are grouped in the
        # device (rotated) frame, the way the default-path (``sortByPosition``
        # false) ``writePage`` consumes ``getX()``/``getY()``/``getWidth()``
        # (PDFTextStripper.java:585-591).
        self._page_rotation: int = 0
        self._page_width: float = 0.0
        self._page_height: float = 0.0
        # Cropbox lower-left corner; upstream ``LegacyPDFStreamEngine``
        # translates every glyph's device geometry by its negation.
        self._crop_lower_left_x: float = 0.0
        self._crop_lower_left_y: float = 0.0
        # Per-page cache of each font's text-space space width (see
        # ``_space_width_text``).
        self._space_width_cache: dict[int, float] = {}
        # ``id(stream) -> (stream, CMap)``: parsed ``/ToUnicode`` streams.
        self._to_unicode_memo: dict[int, tuple[COSStream, CMap]] = {}
        # Lazily-built Helvetica used when no font is set (upstream
        # ``PDFStreamEngine.getDefaultFont``).
        self._default_font: PDFont | None = None
        # Upstream ``inParagraph``: a paragraph was started and not yet ended.
        # Like upstream it is never reset between pages or documents.
        self._in_paragraph: bool = False
        # Counter tagging the glyphs of one show-text string (lite-only
        # flipped-axes mode regroups them into runs).
        self._run_counter: int = 0
        # ``_rendering_scale`` results keyed by their inputs.
        self._rendering_scale_cache: dict[tuple[float, ...], tuple[float, float]] = {}
        # ``_plain_glyph_step`` memos keyed by their run-invariant inputs.
        self._plain_step_memo: dict[bytes, tuple[dict, dict]] = {}
        # Size upstream's reused ``charactersByArticle`` list has reached in
        # the current walk (see ``_assign_articles``).
        self._article_slot_count: int = 0
        self._active_cmap: CMap | None = None
        self._active_font: PDFont | None = None
        # Resources override active while recursing into a form XObject's
        # content stream (the ``Do`` operator). When set, font / ToUnicode /
        # property-list lookups consult these resources instead of the host
        # page's — mirroring upstream ``PDFStreamEngine.showForm`` pushing the
        # form's ``/Resources`` for the duration of the form body. ``None``
        # restores the page-level resources.
        self._active_resources: PDResources | None = None
        # Form-XObject recursion depth guard, matching the upstream
        # ``DrawObject`` cap of 50 nested forms.
        self._form_level: int = 0
        # Per-glyph advance for the active font in user-space units (i.e.
        # already multiplied by ``font_size`` and divided by 1000). When
        # ``None`` we fall back to the legacy 0.5-em estimate so unknown
        # fonts still produce monotonic text-x advances.
        self._active_avg_advance: float | None = None
        # Glyph height (text-space fraction of the em) of the active font,
        # computed via ``_compute_font_height`` and recomputed on every
        # ``Tf``. ``None`` falls back to the half-em proxy. Cached per font
        # object in ``_font_height_cache`` for the page lifetime, mirroring
        # upstream's ``LegacyPDFStreamEngine.fontHeightMap``.
        self._active_font_height: float | None = None
        self._font_height_cache: dict[int, float] = {}
        # Output writer captured by ``write_text`` (the lite stripper
        # otherwise routes everything through ``get_text``'s in-memory
        # sink). Mirrors upstream's protected ``output`` field; exposed
        # via ``get_output`` so subclasses that override hooks like
        # ``write_string`` can write directly to the active stream when
        # the caller drives extraction through ``write_text``.
        self._output: object | None = None
        # Per-page list of articles (each article is a list of
        # ``TextPosition``). Mirrors upstream's protected
        # ``charactersByArticle`` field. Lite mode treats every page as
        # a single article so the outer list is always length 1 after
        # ``process_page`` runs (cleared on entry to ``get_text``).
        self._characters_by_article: list[list[TextPosition]] = []
        # Lazily-populated list of compiled regex patterns matching
        # common list-item prefixes. Mirrors upstream's private
        # ``listOfPatterns`` field; exposed via
        # ``get_list_item_patterns`` / ``set_list_item_patterns``.
        self._list_of_patterns: list[re.Pattern[str]] | None = None
        # Per-walk caches refreshed by ``process_pages`` / ``reset_engine``.
        self._bead_rectangles: list[tuple[float, float, float, float]] = []
        self._start_bookmark_page_number: int = -1
        self._end_bookmark_page_number: int = -1
        # Marked-content state. ``_marked_content_stack`` mirrors
        # upstream's ``Stack<PDMarkedContent>``; lite mode tracks just
        # the pieces it needs to surface ``/ActualText`` to subclasses.
        self._marked_content_stack: list[
            tuple[COSName | None, COSDictionary | None, str | None]
        ] = []
        self._actual_text: str | None = None
        self._first_actual_text_position: bool = False
        # Document handle for ``process_pages`` bookmark resolution.
        # Populated by ``get_text`` while a walk is in progress.
        self._active_document: PDDocument | None = None
        # Per-walk sink used by subclass hooks (``start_document`` /
        # ``end_document`` / ``start_article`` / ``end_article`` /
        # ``write_string`` overrides) that want to stream text through
        # the same gateway as the parent's page loop. Populated by
        # ``get_text`` for the duration of a walk; restored to its
        # previous value (typically ``None``) when the walk completes.
        # Mirrors upstream's per-walk ``output`` field but exposes it as
        # a callable so the lite stripper's in-memory ``chunks`` path
        # and any externally installed :class:`io.TextIO` writer share
        # the same emission point.
        self._active_sink: Callable[[str], None] | None = None

    # ---------- configuration accessors ----------

    def set_start_page(self, page: int) -> None:
        self._start_page = int(page)

    def get_start_page(self) -> int:
        return self._start_page

    def set_end_page(self, page: int) -> None:
        self._end_page = int(page)

    def get_end_page(self) -> int:
        return self._end_page

    def set_word_separator(self, separator: str) -> None:
        self._word_separator = separator

    def get_word_separator(self) -> str:
        return self._word_separator

    def set_line_separator(self, separator: str) -> None:
        self._line_separator = separator

    def get_line_separator(self) -> str:
        return self._line_separator

    def set_paragraph_start(self, value: str) -> None:
        self._paragraph_start = value

    def get_paragraph_start(self) -> str:
        return self._paragraph_start

    def set_paragraph_end(self, value: str) -> None:
        self._paragraph_end = value

    def get_paragraph_end(self) -> str:
        return self._paragraph_end

    def set_page_start(self, value: str) -> None:
        self._page_start = value

    def get_page_start(self) -> str:
        return self._page_start

    def set_page_end(self, value: str) -> None:
        self._page_end = value

    def get_page_end(self) -> str:
        return self._page_end

    def set_should_separate_by_beads(self, value: bool) -> None:
        self._should_separate_by_beads = bool(value)

    def get_should_separate_by_beads(self) -> bool:
        return self._should_separate_by_beads

    def is_should_separate_by_beads(self) -> bool:
        # Upstream PDFBox exposes this as ``isShouldSeparateByBeads`` as
        # well as the ``getShouldSeparateByBeads`` alias on some 3.x
        # branches. Mirror both so callers can pick either spelling.
        return self._should_separate_by_beads

    def get_separate_by_beads(self) -> bool:
        # Upstream's primary getter on 3.x is the abbreviated
        # ``getSeparateByBeads`` (no ``Should`` infix); the longer
        # ``getShouldSeparateByBeads`` is the alias. Mirror the
        # primary spelling explicitly so direct ports of upstream
        # snippets work without rewriting the call site.
        return self._should_separate_by_beads

    def set_sort_by_position(self, value: bool) -> None:
        self._sort_by_position = bool(value)

    def is_sort_by_position(self) -> bool:
        return self._sort_by_position

    def get_sort_by_position(self) -> bool:
        # Upstream PDFBox 3.0.x exposes ``getSortByPosition`` as a
        # boolean alias of ``isSortByPosition``. Mirror both spellings
        # so callers can pick either.
        return self._sort_by_position

    def set_suppress_duplicate_overlapping_text(self, value: bool) -> None:
        self._suppress_duplicate_overlapping_text = bool(value)

    def is_suppress_duplicate_overlapping_text(self) -> bool:
        return self._suppress_duplicate_overlapping_text

    def get_suppress_duplicate_overlapping_text(self) -> bool:
        # Same alias situation as ``get_sort_by_position``.
        return self._suppress_duplicate_overlapping_text

    def set_drop_threshold(self, value: float) -> None:
        self._drop_threshold = float(value)

    def get_drop_threshold(self) -> float:
        return self._drop_threshold

    def set_indent_threshold(self, value: float) -> None:
        self._indent_threshold = float(value)

    def get_indent_threshold(self) -> float:
        return self._indent_threshold

    def set_spacing_tolerance(self, value: float) -> None:
        self._spacing_tolerance = float(value)

    def get_spacing_tolerance(self) -> float:
        return self._spacing_tolerance

    def set_average_char_tolerance(self, value: float) -> None:
        self._average_char_tolerance = float(value)

    def get_average_char_tolerance(self) -> float:
        return self._average_char_tolerance

    def set_add_more_formatting(self, value: bool) -> None:
        self._add_more_formatting = bool(value)

    def get_add_more_formatting(self) -> bool:
        return self._add_more_formatting

    def set_lenient_stream_parsing(self, value: bool) -> None:
        self._lenient_stream_parsing = bool(value)

    def is_lenient_stream_parsing(self) -> bool:
        return self._lenient_stream_parsing

    def set_ignore_content_stream_space_glyphs(self, value: bool) -> None:
        """Mirror upstream's ``setIgnoreContentStreamSpaceGlyphs``.

        When ``True`` the extractor is asked to ignore literal space
        glyphs encoded in the content stream and rely solely on the gap
        heuristic for word breaks. The lite stripper stores the flag for
        API parity; see CHANGES.md for the consumer-side gap.
        """
        self._ignore_content_stream_space_glyphs = bool(value)

    def get_ignore_content_stream_space_glyphs(self) -> bool:
        return self._ignore_content_stream_space_glyphs

    def set_should_flip_axes(self, value: bool) -> None:
        """Toggle axis-flipped extraction (transposes the role of X and Y
        in the line-break / word-gap heuristic). Mirrors upstream
        ``PDFTextStripper.setShouldFlipAxes`` (added in 3.x for sideways
        text on rotated pages)."""
        self._flip_axes = bool(value)

    def is_should_flip_axes(self) -> bool:
        return self._flip_axes

    def get_should_flip_axes(self) -> bool:
        # Upstream exposes both spellings on the 3.x branch.
        return self._flip_axes

    def set_article_start(self, value: str) -> None:
        self._article_start = value

    def get_article_start(self) -> str:
        return self._article_start

    def set_article_end(self, value: str) -> None:
        self._article_end = value

    def get_article_end(self) -> str:
        return self._article_end

    def set_start_bookmark(self, bookmark: PDOutlineItem | None) -> None:
        self._start_bookmark = bookmark

    def get_start_bookmark(self) -> PDOutlineItem | None:
        return self._start_bookmark

    def set_end_bookmark(self, bookmark: PDOutlineItem | None) -> None:
        self._end_bookmark = bookmark

    def get_end_bookmark(self) -> PDOutlineItem | None:
        return self._end_bookmark

    def get_current_page_no(self) -> int:
        """Return the 1-based index of the page currently being
        processed by ``process_page`` (or ``0`` outside a walk).

        Mirrors upstream's protected ``getCurrentPageNo`` accessor —
        exposed publicly here because Python lacks Java's package /
        protected distinction and subclasses outside the package would
        otherwise have no way to consult it.
        """
        return self._current_page_no

    def get_output(self) -> object | None:
        """Return the active output writer, or ``None`` when no walk is
        in progress / when extraction is being driven through
        ``get_text`` (which collects into an in-memory list rather than
        a stream).

        Mirrors upstream's protected ``getOutput`` accessor — exposed
        publicly here since Python has no package-private visibility.
        Subclasses overriding write hooks may consult this when a caller
        drives extraction via ``write_text(doc, writer)``.
        """
        return self._output

    def get_characters_by_article(self) -> list[list[TextPosition]]:
        """Return the per-article list of :class:`TextPosition` objects
        for the page most recently walked. The outer list groups by
        article (one entry per ``/Beads`` chain in upstream PDFBox); the
        inner lists hold the glyph-positions in extraction order.

        Mirrors upstream's protected ``getCharactersByArticle``
        accessor. Lite mode emits a single article per page so the
        outer list is length 1 after every successful ``process_page``.
        Returns an empty list when called outside a walk.
        """
        return self._characters_by_article

    def set_list_item_patterns(
        self, patterns: list[re.Pattern[str]] | None
    ) -> None:
        """Override the list-item regex patterns used by
        ``match_pattern``. Pass ``None`` to revert to the defaults
        derived from :attr:`LIST_ITEM_EXPRESSIONS` on the next call to
        ``get_list_item_patterns``.

        Mirrors upstream's protected ``setListItemPatterns`` — exposed
        publicly here since Python lacks Java's protected visibility.
        """
        self._list_of_patterns = patterns

    def get_list_item_patterns(self) -> list[re.Pattern[str]]:
        """Return the list of compiled regex patterns matching common
        list-item starts (``"1."``, ``"[2]"``, ``"A)"``, ``"iv."`` ...).

        Lazily compiles :attr:`LIST_ITEM_EXPRESSIONS` on first access if
        no caller-supplied list has been installed via
        :meth:`set_list_item_patterns`. Mirrors upstream's protected
        ``getListItemPatterns`` accessor.
        """
        if self._list_of_patterns is None:
            self._list_of_patterns = [
                re.compile(expr) for expr in self.LIST_ITEM_EXPRESSIONS
            ]
        return self._list_of_patterns

    @staticmethod
    def match_pattern(
        string: str, patterns: list[re.Pattern[str]]
    ) -> re.Pattern[str] | None:
        """Return the first pattern in ``patterns`` whose
        :py:meth:`~re.Pattern.fullmatch` matches ``string``, or
        ``None`` when none match.

        Mirrors upstream's protected static ``matchPattern`` helper.
        Upstream's ``Matcher.matches()`` is anchored at both ends, so we
        use ``fullmatch`` (not ``search`` / ``match``) for parity.
        """
        for pattern in patterns:
            if pattern.fullmatch(string) is not None:
                return pattern
        return None

    # ---------- public API ----------

    def get_text(self, document: PDDocument) -> str:
        """Walk pages from ``start_page`` (1-based, inclusive) through
        ``min(end_page, page_count)`` and return the concatenated
        extracted text. Each page is wrapped in
        ``page_start`` / ``page_end``; each article (bead bucket) within a
        page is wrapped in ``article_start`` / ``article_end`` — mirroring
        upstream's per-``charactersByArticle`` ``startArticle`` /
        ``endArticle``. A page with no beads is a single article.

        When ``start_bookmark`` / ``end_bookmark`` are set, the
        resolved bookmark page numbers further clamp the range — see
        ``_resolve_bookmark_page``. This mirrors upstream's
        ``setStartBookmark`` / ``setEndBookmark`` behaviour.
        """
        pages = list(document.get_pages())
        total = len(pages)
        first = max(1, self._start_page)
        last = min(self._end_page, total)
        # Mirror upstream's ``resetEngine`` — clear the per-walk
        # ``charactersByArticle`` accumulator so a fresh walk doesn't
        # leak state from the previous one (subclasses introspecting via
        # ``get_characters_by_article`` rely on this).
        self.reset_engine()
        # Mirror upstream ``writeText``: when ``add_more_formatting`` is on,
        # the paragraph-end, page-start and article-start/end markers are all
        # promoted to the line separator so each structural boundary becomes a
        # visible break. Markers stay at their explicit (default "") values
        # otherwise.
        if self.get_add_more_formatting():
            self._paragraph_end = self._line_separator
            self._page_start = self._line_separator
            self._article_start = self._line_separator
            self._article_end = self._line_separator
        self._active_document = document
        # Bookmark clamping. Upstream takes the bookmark range as
        # authoritative when set, but only narrows (never widens) the
        # explicit page range.
        bm_first = (
            self._resolve_bookmark_page(self._start_bookmark, document)
            if self._start_bookmark is not None
            else None
        )
        bm_last = (
            self._resolve_bookmark_page(self._end_bookmark, document)
            if self._end_bookmark is not None
            else None
        )
        # Mirror upstream PDFTextStripper.processPages: when start/end
        # bookmarks both fail to resolve (i.e. they're orphans) AND they
        # refer to the same bookmark object, clamp the range to the empty
        # one — the result is empty extracted text. Without this clamp
        # any previously-set start_page / end_page leaks through and
        # yields content the caller explicitly opted out of.
        if (
            bm_first is None
            and bm_last is None
            and self._start_bookmark is not None
            and self._end_bookmark is not None
            and self._start_bookmark.get_cos_object()
            is self._end_bookmark.get_cos_object()
        ):
            return ""
        if bm_first is not None:
            first = max(first, bm_first)
        if bm_last is not None:
            last = min(last, bm_last)
        if first > last:
            return ""
        chunks: list[str] = []
        # When ``write_text`` installed an output writer, stream each
        # page's text into it as the page is processed so subclass
        # ``end_page`` hooks can inspect the buffer (e.g. PDFHighlighter
        # reads per-page text from a StringIO output to emit <loc>
        # entries against the searched words). Without per-page streaming
        # the writer would only see the joined text after the page loop
        # exits, by which point every ``end_page`` call has already run
        # with an empty buffer.
        out = self._output

        def _sink(piece: str) -> None:
            chunks.append(piece)
            if out is not None:
                out.write(piece)

        # Expose the active sink so subclass hooks
        # (``start_document``/``end_document``/etc.) can stream text
        # through the same gateway as the parent's page loop. Upstream
        # PDFBox accomplishes the same via a per-walk ``output`` field;
        # we mirror that contract here. The slot is restored in the
        # ``finally`` block so it does not leak across overlapping
        # ``get_text`` calls.
        previous_sink = self._active_sink
        self._active_sink = _sink

        # Mirror upstream's ``startDocument`` / ``endDocument`` hooks —
        # invoked once per ``get_text`` walk around the page loop. The
        # base implementations are no-ops; subclasses override.
        self.start_document(document)
        try:
            for one_based in range(first, last + 1):
                page = pages[one_based - 1]
                self._current_page_no = one_based
                self.start_page(page)
                self.write_page_start(_sink)
                # ``article_start`` / ``article_end`` are emitted per article
                # (bead bucket) inside ``_format_positions`` — mirroring
                # upstream's ``startArticle()`` / ``endArticle()`` around each
                # ``charactersByArticle`` entry — rather than once around the
                # whole page. For a page with no beads this collapses to a
                # single article wrap, preserving the prior single-group
                # behaviour.
                _sink(self.process_page(page))
                self.write_page_end(_sink)
                self.end_page(page)
        finally:
            self.end_document(document)
            self._current_page_no = 0
            self._active_document = None
            self._active_sink = previous_sink
        return "".join(chunks)

    def write_text(self, document: PDDocument, output: _TextWriter) -> None:
        """Write extracted text to ``output``.

        Mirrors upstream ``PDFTextStripper.writeText(PDDocument, Writer)``:
        the supplied writer is exposed through :meth:`get_output` while
        document/page/string hooks run, and is cleared when the walk
        completes or raises. Page text streams through ``output``
        incrementally — each page is flushed before its ``end_page``
        hook fires, matching upstream behaviour that subclasses like
        ``PDFHighlighter`` rely on.
        """
        previous_output = self._output
        self._output = output
        try:
            self.get_text(document)
        finally:
            self._output = previous_output

    @staticmethod
    def _resolve_bookmark_page(
        bookmark: PDOutlineItem, document: PDDocument
    ) -> int | None:
        """Return the 1-based page number that ``bookmark`` resolves to
        within ``document``, or ``None`` when the destination can't be
        resolved within the lite outline surface (named-destination
        resolution is deferred — see ``PDOutlineItem.find_destination_page``).
        """
        target = bookmark.find_destination_page(document)
        if target is None:
            return None
        for idx, page in enumerate(document.get_pages(), start=1):
            if page.get_cos_object() is target:
                return idx
        return None

    def process_page(self, page: PDPage) -> str:
        """Extract text from a single page. Subclasses may override to
        plug in custom layout logic without re-implementing the parser
        loop. Mirrors upstream's ``PDFTextStripper.processPage`` hook.
        """
        body = page.get_contents()
        if not body:
            # A page with no content stream is still an empty article in
            # upstream's ``writePage`` loop — emit the same empty-article
            # wrap a glyph-free (but non-empty) content stream would (see
            # :meth:`_empty_article_wrap`).
            self._characters_by_article = [[]]
            return self._empty_article_wrap()
        # Bind the page so ``Tf`` handlers can reach ``/Resources`` for
        # ``/ToUnicode`` and typed-font lookup, and clear the per-page
        # caches.
        self._active_page = page
        # Snapshot the page rotation + cropbox extents for the per-page
        # coordinate fold (``_apply_page_rotation`` below). Mirrors upstream
        # ``LegacyPDFStreamEngine.processPage`` (LegacyPDFStreamEngine.java:
        # 139-153), which records ``pageRotation`` and the cropbox so each
        # ``TextPosition`` is constructed with the page rotation and page
        # dimensions. Defensive against a malformed ``/Rotate`` or missing
        # cropbox so unrotated pages keep their existing raw-user-space frame.
        self._page_rotation = self._effective_page_rotation(page)
        self._capture_crop_box(page)
        self._cmap_cache = {}
        self._font_cache = {}
        self._glyph_memo = {}
        self._run_font = None
        self._font_traits_memo = {}
        self._font_vertical_memo = {}
        self._active_cmap = None
        self._active_font = None
        self._active_avg_advance = None
        self._active_font_height = None
        self._font_height_cache = {}
        self._fold_upright_geometry = (
            self._page_rotation == 0
            and type(self)._apply_page_rotation is PDFTextStripper._apply_page_rotation
        )
        try:
            positions = self._extract_positions(body)
            self._fold_upright_geometry = False
            # Fold the page ``/Rotate`` into each run's stored coordinates so
            # the line/word grouping consumes the device (rotated) frame, the
            # way upstream's default-path ``writePage`` reads
            # ``getX()``/``getY()``/``getWidth()`` (PDFTextStripper.java:
            # 585-591). No-op when the page is unrotated.
            self._apply_page_rotation(positions)
            # Stash the per-article TextPositions so subclasses /
            # ``get_characters_by_article`` can introspect the same
            # data the formatter consumed. Lite mode treats the whole
            # page body as a single article (PDFTextStripper-compatible
            # behaviour when ``setShouldSeparateByBeads(false)`` or no
            # beads are present).
            self._characters_by_article = [list(positions)]
            return self._format_positions(positions)
        finally:
            self._fold_upright_geometry = False
            self._prefolded_positions = None
            self._active_page = None
            self._active_cmap = None
            self._active_font = None
            self._active_avg_advance = None

    def _effective_page_rotation(self, page: PDPage) -> int:
        """The page ``/Rotate`` the glyph coordinates are folded with."""
        try:
            return int(page.get_rotation()) % 360
        except Exception:  # defensive: bad /Rotate
            return 0

    def _initial_ctm(self) -> Matrix:
        """The CTM a page's content stream starts with (identity, as for
        ``PDPage.getMatrix()``)."""
        return Matrix()

    def _capture_crop_box(self, page: PDPage) -> None:
        """Record the page's cropbox size and lower-left corner and reset the
        per-page space-width cache (upstream ``LegacyPDFStreamEngine.processPage``)."""
        try:
            crop = page.get_crop_box()
            self._page_width = float(crop.get_width())
            self._page_height = float(crop.get_height())
            self._crop_lower_left_x = _f32(float(crop.get_lower_left_x()))
            self._crop_lower_left_y = _f32(float(crop.get_lower_left_y()))
        except Exception:  # defensive: missing/odd CropBox
            self._page_width = 0.0
            self._page_height = 0.0
            self._crop_lower_left_x = 0.0
            self._crop_lower_left_y = 0.0
        self._space_width_cache = {}

    def _apply_page_rotation(self, positions: list[TextPosition]) -> None:
        """Fold the page ``/Rotate`` into each run's stored ``x``/``y``/``width``.

        Faithful port of upstream's page-rotation coordinate handling. In Apache
        PDFBox the page rotation is **not** baked into the CTM
        (``PDPage.getMatrix()`` returns the identity — PDPage.java:385-389);
        instead every ``TextPosition`` is constructed with the page rotation +
        page dimensions (``LegacyPDFStreamEngine.showGlyph`` →
        ``new TextPosition(pageRotation, pageWidth, pageHeight, ...)``,
        LegacyPDFStreamEngine.java:309-313) and the *page-rotation-adjusted*
        coordinates are derived lazily by ``TextPosition``'s constructor /
        accessors:

          * ``getX()``      = ``getXRot(rotation)``        (TextPosition.java:293)
          * ``getY()`` (raw lower-left) = ``getYLowerLeftRot(rotation)``
                                                            (TextPosition.java:356)
          * ``getWidth()``  = ``getWidthRot(rotation)``    (TextPosition.java:426)

        The default extraction path (``sortByPosition`` false — the
        ``PDFTextStripper`` default) groups on exactly these page-rotation
        accessors (``writePage``, PDFTextStripper.java:585-591), so a rotated
        page's glyphs land in the rotated *device* frame: a row of horizontal
        glyphs on a ``/Rotate 90`` page advances along the grouping's *line*
        axis (each glyph a new ``getY``) and reports zero ``getWidth`` (its
        text-space extent is perpendicular to the rotated width axis), which is
        what fragments the rotated rows in Java's output.

        The lite ``TextPosition`` carries Y in the PDF user-space (y-up,
        lower-left-origin) frame the existing heuristics are calibrated for, so
        this fold stores ``getYLowerLeftRot`` (upstream's ``getY()`` mirrored by
        a page-extent constant) rather than the upper-left ``getY()`` — the
        relative geometry the difference/overlap heuristics consume is
        identical, and ``/Rotate 0`` is a verbatim no-op (``getXRot(0)`` /
        ``getYLowerLeftRot(0)`` / ``getWidthRot(0)`` are the raw translate /
        run width the lite emitter already stored).
        """
        rotation = self._page_rotation
        if rotation == 0:
            # Unrotated page — leave the raw user-space coordinates untouched
            # (byte-exact with every pre-fold extraction). Still record the
            # page geometry + rotation on the positions for API parity with
            # upstream ``getRotation``/``getPageWidth``/``getPageHeight``.
            if (
                _USE_FAST_PATHS
                and self._prefolded_positions is positions
                and self._prefolded_count == len(positions)
            ):
                # Every position was built with the values set below.
                return
            pw = self._page_width
            ph = self._page_height
            for pos in positions:
                pos.rotation = 0.0
                pos.page_width = pw
                pos.page_height = ph
                if pos.device_x is not None:
                    # Upstream ``getWidth()`` = ``|endX - tx|``.
                    pos.width = (
                        getattr(pos, "_java_geometry", None) or _java_geometry(pos)
                    ).width
            return
        pw = self._page_width
        ph = self._page_height
        for pos in positions:
            raw_x = pos.x
            raw_y = pos.y
            raw_width = pos.width
            # ``getWidthRot`` (TextPosition.java:426-436): for 90/270 the width
            # is measured along Y (``|endY - ty|``), for 0/180 along X
            # (``|endX - tx|``). The lite run is laid along its text direction
            # (``dir``), so its raw end point is the origin stepped by the run
            # width along that direction: ``endX = x + width·cosθ``,
            # ``endY = y + width·sinθ``. A horizontal run (``dir == 0``) has
            # ``endY == y`` so its 90/270 rotated width is 0 — the zero-extent
            # that fragments the rotated row in Java's output.
            theta = math.radians(pos.dir % 360.0)
            end_x_raw = raw_x + raw_width * math.cos(theta)
            end_y_raw = raw_y + raw_width * math.sin(theta)
            width_adj = (
                abs(end_y_raw - raw_y)
                if rotation in (90, 270)
                else abs(end_x_raw - raw_x)
            )
            # ``getXRot`` (TextPosition.java:293-312).
            if rotation == 90:
                x_adj = raw_y
            elif rotation == 180:
                x_adj = pw - raw_x
            elif rotation == 270:
                x_adj = ph - raw_y
            else:
                x_adj = raw_x
            # Line-flow axis (``getY`` — TextPosition.java:325-328, the value
            # the default-path grouping reads at PDFTextStripper.java:588). The
            # grouping accumulates the line extent with ``maxYForLine = max(...)``
            # (PDFTextStripper.java:689-692; lite ``max_y_for_line``), which is
            # **not** symmetric under negation — so the stored Y must run in the
            # SAME direction as upstream's ``getY()`` for the line accumulation
            # to match, rather than the lower-left mirror. (For ``/Rotate 0``
            # the within-line Y is constant, so the lite's historical raw-``ty``
            # y-up frame and upstream's ``pageHeight - ty`` agree regardless of
            # direction and stay byte-exact; that no-op case is handled above.)
            # ``getY`` = ``pageHeight - getYLowerLeftRot`` (0/180) or
            # ``pageWidth - getYLowerLeftRot`` (90/270) — TextPosition.java:
            # 110-117 / 406-418.
            if rotation == 90:
                # getYLowerLeftRot(90) = pageWidth - tx ⇒ getY = tx = raw_x.
                y_adj = raw_x
            elif rotation == 180:
                y_adj = ph - raw_y
            elif rotation == 270:
                # getYLowerLeftRot(270) = tx ⇒ getY = pageWidth - tx.
                y_adj = pw - raw_x
            else:
                y_adj = raw_y
            pos.rotation = float(rotation)
            pos.page_width = pw
            pos.page_height = ph
            if pos.device_x is not None:
                # Exact upstream ``getWidthRot(rotation)`` from the glyph's
                # device end point.
                width_adj = _java_geometry(pos).width
            pos.x = x_adj
            pos.y = y_adj
            pos.width = width_adj

    # ---------- parser walk ----------

    def _extract_positions(self, body: bytes) -> list[TextPosition]:
        """Run the content stream through :class:`PDFStreamParser` and
        emit a flat list of :class:`TextPosition`. Operands are buffered
        in a list and flushed when an operator token is seen — mirroring
        upstream's ``processOperator(operator, operands)`` pattern.
        """
        positions: list[TextPosition] = []
        operands: list[COSBase] = []

        # Text-state machine. Tracks the text matrix plus the page CTM via
        # a graphics-state stack (``q`` / ``Q`` / ``cm``); the emitter
        # composes textMatrix × CTM to recover device-space glyph origins
        # and the effective font size, so producers that position lines
        # with a per-line ``cm`` and fold the point size into ``Tm`` lay
        # out correctly. See CHANGES.md.
        state = _TextState()
        state.ctm = self._initial_ctm()

        with RandomAccessReadBuffer(body) as src:
            parser = PDFStreamParser(src)
            for token in parser.tokens():
                if isinstance(token, Operator):
                    self._dispatch(token.get_name(), operands, state, positions)
                    operands = []
                else:
                    operands.append(token)

        return positions

    def _dispatch(
        self,
        op: str,
        operands: list[COSBase],
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        if op == "BT":
            # Begin text object — reset text matrix and line matrix to
            # identity (PDF 1.7 §9.4.1).
            state.text_x = 0.0
            state.text_y = 0.0
            state.line_x = 0.0
            state.line_y = 0.0
            state.tm_a = 1.0
            state.tm_b = 0.0
            state.tm_c = 0.0
            state.tm_d = 1.0
            # Text matrix reset — drop the derived-scale/dir cache (see
            # _scale_and_dir); it is a function of tm_a..tm_d + CTM + rise.
            state._trm_cache = None
            # Mark the text object open — text matrix + line matrix are now
            # non-null, so the show/move operators are permitted (upstream
            # ``BeginText`` sets both matrices to identity).
            state.in_text_object = True
        elif op == "ET":
            # End text object — clears the text + line matrices (upstream
            # ``EndText`` sets both to null). Subsequent text/positioning
            # operators stranded outside a BT…ET pair are ignored.
            state.in_text_object = False
            return
        elif op == "Tf":
            if len(operands) >= 2:
                name = operands[0]
                size = operands[1]
                if isinstance(name, COSName):
                    state.font_name = name.get_name()
                    # Resolve and cache the /ToUnicode CMap (if any) so
                    # Tj/TJ/'/" emitters can decode glyph codes; also
                    # resolve the typed PDFont so the /Differences-based
                    # glyph→unicode fallback and the font-width-based
                    # word-gap heuristic both have something to consult.
                    self._active_cmap = self._get_cmap_for_font(state.font_name)
                    self._active_font = self._get_font_for(state.font_name)
                    if self._active_font is None:
                        # Upstream ``SetFontAndSize`` keeps a null font and
                        # ``showText`` then falls back to Helvetica.
                        _log.warning("font '%s' not found in resources", state.font_name)
                        self._active_font = self._get_default_font()
                if isinstance(size, COSNumber):
                    state.font_size = size.float_value()
                # Recompute the per-glyph advance whenever the font OR
                # the size changes (Tf carries both — even Tf with the
                # same name re-anchors the size).
                self._active_avg_advance = self._compute_avg_advance(
                    self._active_font, state.font_size
                )
                self._active_font_height = self._compute_font_height(
                    self._active_font
                )
        elif op == "TL":
            if operands and isinstance(operands[0], COSNumber):
                state.leading = operands[0].float_value()
        elif op == "Td":
            # Upstream ``MoveText`` ignores ``Td`` when the text-line matrix
            # is null (outside a BT…ET pair).
            if not state.in_text_object:
                return
            tx, ty = _two_numbers(operands)
            # Translate the line matrix by (tx, ty), then reset the text
            # matrix to the new line origin (PDF 1.7 §9.4.2). ``(tx, ty)``
            # is a text-space delta, so it is carried through the
            # text-matrix scale/shear before moving the translation-space
            # line origin (otherwise a ``Tm`` that folds the point size
            # into its scale would under-translate every ``Td``).
            _move_text_line(state, tx, ty)
            state.text_x = state.line_x
            state.text_y = state.line_y
        elif op == "TD":
            if not state.in_text_object:
                return
            tx, ty = _two_numbers(operands)
            # ``TD`` = ``-ty TL`` then ``tx ty Td``.
            state.leading = -ty
            _move_text_line(state, tx, ty)
            state.text_x = state.line_x
            state.text_y = state.line_y
        elif op == "Tm":
            # ``a b c d e f Tm`` — set both text matrix and line matrix to
            # the supplied 3x3 affine. We track translation (e, f) for
            # the position cursor and the scale/shear components
            # (a, b, c, d) so emitted runs can report their text-matrix
            # rotation (used by ``FilteredTextStripper`` /
            # ``AngleCollector`` for ``-rotationMagic``).
            values = _six_numbers(operands)
            if values is not None:
                # ``Tm`` sets both the text matrix and the text-line matrix to
                # the supplied affine — making both non-null even when no
                # ``BT`` is open (upstream ``SetMatrix`` does not gate). So a
                # ``Tj`` after a stray ``Tm`` would render; mark the text
                # object effectively open to mirror that.
                state.in_text_object = True
                a, b, c, d, e, f = values
                state.tm_a = a
                state.tm_b = b
                state.tm_c = c
                state.tm_d = d
                # Text matrix scale/shear changed → invalidate derived cache.
                state._trm_cache = None
                state.line_x = e
                state.line_y = f
                state.text_x = e
                state.text_y = f
        elif op == "T*":
            if not state.in_text_object:
                return
            # Move to start of next line — equivalent to ``0 -leading Td``.
            # The ``(0, -leading)`` text-space delta is carried through the
            # text-matrix scale/shear before moving the line origin.
            _move_text_line(state, 0.0, -state.leading)
            state.text_x = state.line_x
            state.text_y = state.line_y
        elif op == "Tj":
            # Upstream ``ShowText`` ignores ``Tj`` when the text matrix is null
            # (outside a BT…ET pair).
            if not state.in_text_object:
                return
            if operands and isinstance(operands[0], COSString):
                self._emit(operands[0], state, positions)
        elif op == "TJ":
            # Upstream ``ShowTextAdjusted`` ignores ``TJ`` when the text matrix
            # is null (outside a BT…ET pair).
            if not state.in_text_object:
                return
            if operands and isinstance(operands[0], COSArray):
                self._emit_tj_array(operands[0], state, positions)
        elif op == "'":
            # ``'`` = ``T*`` then ``Tj``; both halves are no-ops outside a
            # text object (text-line / text matrix null).
            if not state.in_text_object:
                return
            # Move to next line then show string.
            _move_text_line(state, 0.0, -state.leading)
            state.text_x = state.line_x
            state.text_y = state.line_y
            if operands and isinstance(operands[0], COSString):
                self._emit(operands[0], state, positions)
        elif op == '"':
            # ``aw ac string "`` — set word + char spacing, next line, show.
            # Upstream runs ``Tw`` / ``Tc`` unconditionally, then a gated
            # ``T*`` + ``Tj`` (no-ops outside a text object). Set the spacing
            # first, then skip the show when no text object is open.
            if (
                len(operands) >= 3
                and isinstance(operands[0], COSNumber)
                and isinstance(operands[1], COSNumber)
                and isinstance(operands[2], COSString)
            ):
                state.word_spacing = operands[0].float_value()
                state.char_spacing = operands[1].float_value()
                if not state.in_text_object:
                    return
                _move_text_line(state, 0.0, -state.leading)
                state.text_x = state.line_x
                state.text_y = state.line_y
                self._emit(operands[2], state, positions)
        elif op == "Tc":
            if operands and isinstance(operands[0], COSNumber):
                state.char_spacing = operands[0].float_value()
        elif op == "Tw":
            if operands and isinstance(operands[0], COSNumber):
                state.word_spacing = operands[0].float_value()
        elif op == "Tz":
            # Horizontal text scaling — operand is a percentage (100 = no
            # scaling). Stored as a fraction (``Tz/100``); scales the
            # horizontal glyph displacement the word-gap heuristic measures
            # (PDF 32000-1 §9.3.4).
            if operands and isinstance(operands[0], COSNumber):
                state.horizontal_scaling = operands[0].float_value() / 100.0
        elif op == "Ts":
            # Text rise — a vertical baseline shift in unscaled text-space
            # units (PDF 32000-1 §9.3.7). Positive raises the baseline of
            # subsequent glyphs (superscript), negative lowers it
            # (subscript). It is applied to the rendered glyph origin via the
            # text-rendering matrix (see ``_text_rendering_matrix``) and does
            # not affect the cursor advance; a later ``0 Ts`` resets it.
            if operands and isinstance(operands[0], COSNumber):
                state.text_rise = operands[0].float_value()
                # Rise feeds the text-rendering matrix; invalidate the derived
                # cache (conservative — rise shifts only translation, but the
                # cache key treats it as an input).
                state._trm_cache = None
        elif op == "q":
            # Save graphics state (PDF 1.7 §8.4.2). Upstream's
            # ``PDGraphicsState`` carries the CTM *and* the text state (font,
            # size, Tc, Tw, Tz, TL, Ts), so ``Q`` restores both; the text
            # and text-line matrices are not part of it.
            state.gs_stack.append((state.ctm.clone(), self._save_text_state(state)))
        elif op == "Q":
            # Restore graphics state. Defensive: an unbalanced ``Q`` is a
            # no-op, as upstream only pops above the initial state.
            if state.gs_stack:
                ctm, saved_text_state = state.gs_stack.pop()
                state.ctm = ctm
                self._restore_text_state(state, saved_text_state)
                # CTM restored → derived scale/dir cache is stale.
                state._trm_cache = None
        elif op == "cm":
            # Concatenate the operand matrix onto the CTM (PDF 1.7 §8.3.4).
            # Upstream applies ``newCTM = operandMatrix × CTM``; with the
            # row-vector convention used by :class:`Matrix` this is
            # ``operandMatrix.multiply(ctm)``.
            values = _six_numbers(operands)
            if values is not None:
                a, b, c, d, e, f = values
                state.ctm = Matrix(a, b, c, d, e, f).multiply(state.ctm)
                # CTM concatenated → derived scale/dir cache is stale.
                state._trm_cache = None
        elif op == "BMC":
            # Begin marked content with a bare tag (no property list).
            # Upstream ``BeginMarkedContentSequence.process`` iterates the
            # whole operand list and keeps the *last* ``COSName`` (any
            # leading non-name junk is skipped), so ``1 (x) /Span BMC``
            # opens the ``/Span`` sequence. Mirror the registered operator
            # / ``_props.extract_tag`` here rather than taking ``operands[0]``.
            tag = self._last_cos_name(operands)
            self.begin_marked_content_sequence(tag, None)
        elif op == "BDC":
            # Begin marked content with a property list — the source of
            # an ``/ActualText`` replacement (PDF §14.9.4). Unlike BMC, the
            # tag is the *first* operand (``operands[0]``): the property
            # operand of the ``/Name`` form is itself a ``COSName`` and must
            # not be mistaken for the tag (matches upstream
            # ``BeginMarkedContentSequenceWithProperties`` / the registered
            # ``BeginMarkedContentWithProps`` operator). When the tag is not a
            # name, or the property list cannot be resolved to a dictionary
            # (unknown ``/Name``, wrong type, missing resources), upstream
            # ``BeginMarkedContentSequenceWithProperties.process`` returns
            # *without* opening a sequence (``propDict == null``) — so we do
            # not open one either; the matching EMC still pops the parent,
            # matching upstream's no-underflow ``endMarkedContentSequence``.
            tag = operands[0] if operands and isinstance(operands[0], COSName) else None
            if tag is None:
                return
            properties = self._resolve_bdc_properties(operands)
            if properties is None:
                return
            self.begin_marked_content_sequence(tag, properties)
        elif op == "EMC":
            self.end_marked_content_sequence()
        elif op == "Do":
            # Draw an XObject. For text extraction we descend into form
            # XObjects (and transparency groups, which are form XObjects)
            # so their show-text operators contribute to the page text —
            # mirroring upstream ``PDFStreamEngine.showForm`` reached via
            # the ``DrawObject`` operator. Image XObjects carry no text and
            # are skipped.
            self._show_form_xobject(operands, state, positions)
        # Other operators (paths, colour, marked-content points, etc.) are
        # intentionally ignored — they have no effect on the lite text
        # stream.

    def _show_form_xobject(
        self,
        operands: list[COSBase],
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        """``Do`` — recurse into a form XObject's content stream.

        Resolves the named XObject through the resources currently in
        effect, skips image XObjects (no text), and for a form / group
        XObject concatenates the form's ``/Matrix`` onto the current CTM
        and replays the form body so its show-text operators emit text.
        The form's ``/Resources`` are pushed for the duration so its own
        ``Tf`` names resolve against the right font dictionaries. Recursion
        depth is capped at 50, matching upstream's ``DrawObject`` guard.
        """
        if not operands or not isinstance(operands[0], COSName):
            return
        name = operands[0]
        resources = self._current_resources()
        if resources is None:
            return
        try:
            is_image = getattr(resources, "is_image_x_object", None)
            if is_image is not None and is_image(name):
                return
            xobject = resources.get_x_object(name)
        except Exception:  # defensive: malformed XObject entry
            return
        if xobject is None:
            return
        if type(xobject).__name__ not in {"PDFormXObject", "PDTransparencyGroup"}:
            return
        if self._form_level >= 50:
            _log.error("recursion is too deep, skipping form XObject")
            return

        try:
            body = self._get_form_contents(xobject)
        except Exception:  # defensive: malformed form stream
            return
        if not body:
            return

        # Concatenate the form's /Matrix onto the current CTM (PDF §8.10.1).
        form_matrix = self._form_matrix(xobject)
        form_ctm = form_matrix.multiply(state.ctm)

        # Save and swap the resolution context: the form's own resources and
        # a fresh per-context font/cmap cache (resource names like ``F0`` can
        # mean different fonts inside the form than on the host page).
        saved_resources = self._active_resources
        saved_cmap_cache = self._cmap_cache
        saved_font_cache = self._font_cache
        saved_active_cmap = self._active_cmap
        saved_active_font = self._active_font
        saved_avg_advance = self._active_avg_advance
        saved_font_height = self._active_font_height
        try:
            form_resources = xobject.get_resources()
        except Exception:  # defensive
            form_resources = None
        self._active_resources = form_resources
        self._cmap_cache = {}
        self._font_cache = {}
        self._form_level += 1

        # Upstream ``processStream`` pushes a clone of the graphics state, so
        # the form inherits the current font and text-state parameters (and
        # the text matrices, which are engine fields), and the CTM is
        # concatenated with the form's /Matrix.
        form_state = _TextState()
        self._restore_text_state(form_state, self._save_text_state(state))
        form_state.text_x = state.text_x
        form_state.text_y = state.text_y
        form_state.line_x = state.line_x
        form_state.line_y = state.line_y
        form_state.tm_a = state.tm_a
        form_state.tm_b = state.tm_b
        form_state.tm_c = state.tm_c
        form_state.tm_d = state.tm_d
        form_state.in_text_object = state.in_text_object
        form_state.ctm = form_ctm
        try:
            with RandomAccessReadBuffer(body) as src:
                parser = PDFStreamParser(src)
                form_operands: list[COSBase] = []
                for token in parser.tokens():
                    if isinstance(token, Operator):
                        self._dispatch(
                            token.get_name(), form_operands, form_state, positions
                        )
                        form_operands = []
                    else:
                        form_operands.append(token)
        finally:
            self._form_level -= 1
            self._active_resources = saved_resources
            self._cmap_cache = saved_cmap_cache
            self._font_cache = saved_font_cache
            self._active_cmap = saved_active_cmap
            self._active_font = saved_active_font
            self._active_avg_advance = saved_avg_advance
            self._active_font_height = saved_font_height

    def _save_text_state(self, state: _TextState) -> tuple:
        """Snapshot the text-state part of the graphics state, with the
        resolved font, for ``q`` / ``Q`` and form XObjects."""
        return (
            state.font_name,
            state.font_size,
            state.char_spacing,
            state.word_spacing,
            state.horizontal_scaling,
            state.leading,
            state.text_rise,
            self._active_font,
            self._active_cmap,
            self._active_avg_advance,
            self._active_font_height,
        )

    def _restore_text_state(self, state: _TextState, saved: tuple) -> None:
        (
            state.font_name,
            state.font_size,
            state.char_spacing,
            state.word_spacing,
            state.horizontal_scaling,
            state.leading,
            state.text_rise,
            self._active_font,
            self._active_cmap,
            self._active_avg_advance,
            self._active_font_height,
        ) = saved

    @staticmethod
    def _get_form_contents(xobject: object) -> bytes:
        """Return the decoded content-stream bytes of a form XObject."""
        cos = xobject.get_cos_object()  # type: ignore[attr-defined]
        if not isinstance(cos, COSStream):
            return b""
        with cos.create_input_stream() as src:
            return src.read()

    @staticmethod
    def _form_matrix(xobject: object) -> Matrix:
        """Return the form's ``/Matrix`` as a :class:`Matrix` (identity when
        absent or malformed)."""
        try:
            values = xobject.get_matrix()  # type: ignore[attr-defined]
        except Exception:  # defensive
            return Matrix()
        if values is None or len(values) != 6:
            return Matrix()
        a, b, c, d, e, f = (float(v) for v in values)
        return Matrix(a, b, c, d, e, f)

    @staticmethod
    def _last_cos_name(operands: list[COSBase]) -> COSName | None:
        """Return the **last** ``COSName`` among the operands, or ``None``.

        Mirrors upstream ``BeginMarkedContentSequence.process`` /
        ``MarkedContentPoint.process`` (and the shared
        ``_props.extract_tag`` helper used by the registered operators):
        the whole operand list is scanned and the most recent ``COSName``
        wins, so any leading non-name junk (numbers, strings) is skipped
        rather than aborting tag selection. Used for the inline ``BMC``
        dispatch; ``BDC`` deliberately uses ``operands[0]`` instead.
        """
        tag: COSName | None = None
        for argument in operands:
            if isinstance(argument, COSName):
                tag = argument
        return tag

    def _resolve_bdc_properties(
        self,
        operands: list[COSBase],
    ) -> COSDictionary | None:
        """``BDC`` carries either an inline property dictionary or a
        ``COSName`` referencing the active page resources' ``/Properties``
        subdictionary. The inline dictionary wins; otherwise resolve the
        name through the page resources. Returns ``None`` when neither is
        present or the resource lookup fails (defensive against malformed
        resources).
        """
        if len(operands) < 2:
            return None
        prop = operands[1]
        if isinstance(prop, COSDictionary):
            return prop
        if isinstance(prop, COSName) and self._active_page is not None:
            try:
                resources = self._current_resources()
                if resources is None:
                    return None
                pl = resources.get_property_list(prop)
                if pl is not None:
                    return pl.get_cos_object()
            except Exception:  # defensive: malformed resources
                return None
        return None

    # ---------- emission ----------

    @staticmethod
    def _text_rendering_matrix(state: _TextState) -> Matrix:
        """Compose the run's text matrix with the CTM.

        Mirrors upstream ``PDFStreamEngine.showText``'s
        ``textMatrix.multiply(ctm)`` (the font-size parameter matrix is
        applied separately to ``font_size`` rather than folded in here).
        The result's translation is the glyph origin in device space and
        its scaling factors give the effective glyph size — so producers
        that fold the point size into ``Tm`` (``14 0 0 14 … Tm`` with a
        ``1 Tf``) and position each line via a per-line ``cm`` are placed
        and scaled correctly instead of collapsing onto one baseline.

        Text rise (``Ts``) is folded in the way upstream
        ``PDFStreamEngine.showText`` does: as the f-translation of the
        font-parameter matrix applied *before* the text matrix
        (``parameterMatrix × textMatrix × ctm``). In this lite port the font
        size is applied separately, so the rise-bearing parameter matrix is
        just the translation ``[1, 0, 0, 1, 0, rise]``. Composing it first
        shifts the glyph origin along the text matrix's local Y axis — so a
        positive rise lifts a superscript run above the baseline (and a
        rotated ``Tm`` rotates the shift with it) without touching the
        glyph's scale or direction.
        """
        text_matrix = Matrix(
            state.tm_a, state.tm_b, state.tm_c, state.tm_d, state.text_x, state.text_y
        )
        rise = getattr(state, "text_rise", 0.0)
        if rise:
            parameter_matrix = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, rise)
            return parameter_matrix.multiply(text_matrix).multiply(state.ctm)
        return text_matrix.multiply(state.ctm)

    @staticmethod
    def _text_dir(trm: Matrix) -> float:
        """Text direction in degrees (0 / 90 / 180 / 270) for a run.

        Mirrors upstream ``TextPosition.getDir()`` cell by cell: the
        direction is read from the text rendering matrix's scale and shear
        cells with four quadrant tests, and a matrix that fits none of them
        (a 45 degree rotation, a strong skew) reports ``0`` rather than the
        nearest right angle.
        """
        return _java_dir(
            trm.get_scale_y(), trm.get_shear_y(), trm.get_shear_x(), trm.get_scale_x()
        )

    def _scale_and_dir(self, state: _TextState) -> tuple[float, float, float]:
        """Run-invariant ``(x_scale, y_scale, text_dir)`` for the current run.

        These are the only values every show-text emitter consumes from the
        full text-rendering matrix (:meth:`_text_rendering_matrix`): the X/Y
        scaling factors (effective font size / point size) and the text
        direction. All three read only the matrix's scale/shear cells
        (slots 0, 1, 3, 4), which — because the text matrix's third column is
        ``[0, 0, 1]`` — are a function of ``tm_a``..``tm_d`` and the CTM alone,
        **independent of the translation** (``text_x``/``text_y``) and of the
        text rise. So the value is stable across the frequent ``Tj``/``TJ``/
        ``Td`` cursor moves and only the rare ``BT``/``Tm``/``Ts``/``Q``/``cm``
        operators invalidate it (the dispatcher drops ``state._trm_cache`` at
        those). Caching it avoids a full 3x3 ``Matrix.multiply`` (and its ~45
        ``f32`` narrowings) per show-text run while returning a value that is
        bit-identical to recomputing ``_text_rendering_matrix(state)`` — the
        cached tuple *is* the result of that computation from unchanged inputs.
        """
        cached = getattr(state, "_trm_cache", None)
        if cached is not None:
            return cached
        trm = self._text_rendering_matrix(state)
        value = (
            trm.get_scaling_factor_x(),
            trm.get_scaling_factor_y(),
            self._text_dir(trm),
        )
        state._trm_cache = value
        return value

    def _origin_translate(
        self, state: _TextState, text_x: float, text_y: float
    ) -> tuple[float, float]:
        """Device-space glyph origin ``(tx, ty)`` for a text-space cursor.

        Every caller of :meth:`_origin_matrix` consumes only the composed
        matrix's translation row (``get_translate_x``/``get_translate_y``), so
        the eight non-translation cells of the 3x3 multiply are pure waste. In
        the common no-rise case we compute the two translation cells directly,
        reproducing ``Matrix(tm_a, tm_b, tm_c, tm_d, text_x, text_y)
        .multiply(ctm)``'s slots 6 and 7 exactly — every product and partial
        sum is narrowed through :func:`f32` in the same left-to-right order as
        ``util.matrix._multiply_arrays`` (which those cells depend on only
        through ``tm[6]=f32(text_x)``, ``tm[7]=f32(text_y)``, ``tm[8]=1`` and
        the CTM cells; ``tm_a``..``tm_d`` do not enter the translation row), so
        the result is bit-for-bit identical to the full multiply.

        ``multiply`` also runs ``checkFloatValues`` over all nine result cells
        and raises on a non-finite one. The eight cells we skip are already
        known finite: this method is only reached after
        :meth:`_text_rendering_matrix` has multiplied the *same* ``tm``/``ctm``
        (differing only in translation, which cannot change the finite
        scale/shear cells) and would have raised first; the third column is a
        structural ``[0, 0, 1]``. So checking only the two translation cells
        reproduces the exact same raise-or-not behaviour.

        The text-rise path stays on the full :meth:`_origin_matrix` (two
        chained multiplies) rather than hand-inline both — rise is 0.0 by
        default and set only by the rare ``Ts`` operator, so this keeps the
        risky arithmetic on the already-proven path with no measurable cost.
        """
        if getattr(state, "text_rise", 0.0):
            origin = self._origin_matrix(state, text_x, text_y)
            return origin.get_translate_x(), origin.get_translate_y()
        ctm = state.ctm
        # CTM cells (already float32): scaleX, shearY, shearX, scaleY, transX,
        # transY at flat slots 0, 1, 3, 4, 6, 7.
        c0 = ctm.get_scale_x()
        c1 = ctm.get_shear_y()
        c3 = ctm.get_shear_x()
        c4 = ctm.get_scale_y()
        c6 = ctm.get_translate_x()
        c7 = ctm.get_translate_y()
        # The Matrix ctor narrows the translation operands to float32 before
        # they become tm[6]/tm[7]; mirror that first.
        e = _f32(text_x)
        g = _f32(text_y)
        # slot 6 = f32(f32(tm[6]*ctm[0]) + f32(tm[7]*ctm[3])) + f32(tm[8]*ctm[6])
        #        with tm[8]=1.0, so f32(1.0*ctm[6]) == ctm[6] (already float32).
        if c1 == 0.0 and c3 == 0.0:
            # The shear products are zero and leave the sums unchanged.
            tx = _f32(_f32(e * c0) + c6)
            ty = _f32(_f32(g * c4) + c7)
        else:
            tx = _f32(_f32(_f32(e * c0) + _f32(g * c3)) + c6)
            ty = _f32(_f32(_f32(e * c1) + _f32(g * c4)) + c7)
        if not (math.isfinite(tx) and math.isfinite(ty)):
            # Matches util.matrix._check_float_values raising on a non-finite
            # product (the only cells that can be non-finite here).
            raise ValueError("Multiplying two matrices produces illegal values")
        return tx, ty

    def _decode_code_to_unicode(
        self, code_bytes: bytes, code: int, font: PDFont | None
    ) -> str | None:
        """Decode a single character code to its Unicode piece.

        Mirrors upstream ``LegacyPDFStreamEngine.showGlyph``: the font's
        ``toUnicode`` (``/ToUnicode`` CMap, then the encoding's glyph name)
        decides; when it has no answer a simple font's code is coerced to the
        character with that value, as Acrobat does, while a composite font's
        code returns ``None`` so the glyph is skipped (it still advances the
        cursor). Without a font the bytes are read as Latin-1.
        """
        if self._active_cmap is not None:
            piece = self._active_cmap.to_unicode(code)
            if piece is not None:
                return piece
        if font is not None:
            try:
                piece = font.to_unicode(code)
            except Exception:  # defensive
                piece = None
            if piece is not None:
                return piece
            from pypdfbox.pdmodel.font import PDSimpleFont

            if isinstance(font, PDSimpleFont):
                return chr(code) if 0 <= code <= 0x10FFFF else None
            if callable(getattr(font, "read_code", None)):
                return None
        return code_bytes.decode("latin-1", errors="replace")

    @staticmethod
    def _is_vertical_font(font: PDFont | None) -> bool:
        """``True`` when ``font`` paints glyphs in vertical writing mode
        (WMode 1).

        Mirrors upstream ``PDFont.isVertical`` — only composite (Type 0)
        fonts can be vertical, and only when their ``/Encoding`` CMap
        declares ``/WMode 1`` (e.g. ``/Identity-V``). Defensive: a font
        without an ``is_vertical`` predicate (every simple font) is treated
        as horizontal.
        """
        if font is None:
            return False
        is_vertical = getattr(font, "is_vertical", None)
        if not callable(is_vertical):
            return False
        try:
            return bool(is_vertical())
        except Exception:  # defensive: malformed CMap
            return False

    @staticmethod
    def _vertical_sort_width(font: PDFont, code: int) -> float:
        """Upstream ``LegacyPDFStreamEngine.showGlyph``'s horizontal width of
        a vertical glyph: ``getWidth(code) / 1000``, rescaled to a 1000-unit
        em for a TrueType program with another ``unitsPerEm``."""
        try:
            width = _f32(float(font.get_width(code)) / 1000.0)
        except Exception:  # defensive
            return 0.0
        try:
            from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

            descendant = font.get_descendant_font()  # type: ignore[attr-defined]
            if isinstance(descendant, PDCIDFontType2):
                ttf = descendant.get_true_type_font()
                units = ttf.get_units_per_em() if ttf is not None else 1000
                if units != 1000:
                    width = _f32(width * _f32(1000.0 / units))
        except Exception:  # defensive
            pass
        return width

    def _emit_vertical(
        self,
        raw_bytes: bytes,
        text: str,
        state: _TextState,
        positions: list[TextPosition],
        font: PDFont,
        resolved_font_name: str | None,
    ) -> None:
        """Per-glyph emission for a vertical (WMode 1) Type0 font.

        Ports upstream ``PDFStreamEngine.showText`` (PDFStreamEngine.java:
        430-470) vertical branch: each character code is read off
        ``raw_bytes`` via the font's ``read_code``, its origin is offset by
        the font's *position vector* (``font.get_position_vector(code)`` — in
        em, already negated per PDF 32000-1 §9.7.3) scaled by the font size,
        and the text cursor then advances DOWN the column by the *vertical
        displacement* ``ty = w1y·fontSize + Tc + Tw`` (where
        ``w1y = font.get_displacement(code)[1]`` is the negative ``/W2`` /
        ``/DW2`` advance in em). One :class:`TextPosition` is emitted per
        glyph, so the line-grouping heuristic (each glyph on a successive
        baseline, vertically disjoint) breaks a line after every glyph —
        reproducing Apache PDFBox's one-glyph-per-line vertical reading order
        (top-to-bottom within a column; the comparator orders columns
        right-to-left when ``sort_by_position`` is on, see
        :meth:`_compare_reading_order_vertical`).

        The text cursor lives in the text matrix's translation slots, so the
        text-space ``(0, ty)`` and position-vector deltas are carried through
        the text-matrix scale/shear ``(a, b, c, d)`` before they move
        ``text_x`` / ``text_y`` — matching the horizontal path's
        ``run_width × (tm_a, tm_b)`` cursor carry. Each glyph's device-space
        origin is the composed ``textMatrix × CTM`` translation.
        """
        font_size = state.font_size
        th = getattr(state, "horizontal_scaling", 1.0)
        char_spacing = state.char_spacing
        word_spacing = state.word_spacing
        # Effective font size / glyph height / direction are matrix-scaled the
        # same way the horizontal path does (the run's scale comes from the
        # text-rendering matrix, independent of the per-glyph translation).
        x_scale, y_scale, text_dir = self._scale_and_dir(state)
        effective_font_size = font_size * y_scale
        font_size_in_pt = font_size * x_scale
        per_char = self._active_avg_advance
        if per_char is None:
            per_char = font_size * 0.5
        space_text = self._space_width_text(font, per_char / font_size if font_size else 0.0)
        trm_scale_x, trm_scale_y = self._rendering_scale(state)
        glyph_width_of_space = abs(_f32(space_text * trm_scale_x))
        font_height_fraction = self._active_font_height
        run_height = (
            0.0 if font_height_fraction is None
            else abs(_f32(font_height_fraction * trm_scale_y))
        )
        # ``/ActualText`` substitution still applies per show-text run: inside
        # an ``/ActualText`` span the whole replacement string is emitted once
        # (at the span's first glyph), and every later glyph's text is
        # suppressed (the cursor still advances). ``actual_text`` is the
        # replacement for the first run / ``None`` for a suppressed later run,
        # and ``None`` (with ``has_actual_text`` False) when no span is active —
        # the latter is the common case where each glyph emits its own piece.
        has_actual_text = self._actual_text is not None
        actual_text = self._actual_text_for_run(text) if has_actual_text else None

        offset = 0
        n = len(raw_bytes)
        try:
            read_code = font.read_code
        except AttributeError:
            read_code = None
        emitted_any = False
        while offset < n:
            if read_code is None:
                break
            try:
                code, consumed = read_code(raw_bytes, offset)
            except Exception:  # defensive: malformed font / bytes
                break
            if consumed <= 0:
                break
            piece = self._decode_code_to_unicode(
                raw_bytes[offset : offset + consumed], code, font
            )
            offset += consumed
            # Position vector (em) — offsets the glyph origin so the vertical
            # baseline lands where the ``/W2`` / ``/DW2`` ``v`` component
            # places it (PDF 32000-1 §9.7.4.3). ``(0, 0)`` for fonts without
            # ``/W2``.
            try:
                v_x, v_y = font.get_position_vector(code)
            except Exception:  # defensive
                v_x, v_y = 0.0, 0.0
            # Vertical displacement (em); ``w1y`` is negative (advance down).
            try:
                _w0, w1y = font.get_displacement(code)
            except Exception:  # defensive
                w1y = -1.0
            # Glyph origin in text space = cursor + positionVector·fontSize,
            # carried through the text-matrix scale/shear into the
            # translation slots.
            glyph_tx = v_x * font_size
            glyph_ty = v_y * font_size
            origin_x = (
                state.text_x + glyph_tx * state.tm_a + glyph_ty * state.tm_c
            )
            origin_y = (
                state.text_y + glyph_tx * state.tm_b + glyph_ty * state.tm_d
            )
            # Under an ``/ActualText`` span the replacement is emitted once at
            # the first glyph (``actual_text``); later glyphs in the span carry
            # no text. Without a span each glyph emits its own decoded piece.
            if piece is None:
                # A composite-font code without a Unicode mapping: upstream
                # skips the glyph (it still advances the cursor).
                glyph_text = None
            elif has_actual_text:
                glyph_text = actual_text or ""
                actual_text = ""  # emit the span replacement only once
            else:
                glyph_text = piece
            if glyph_text is not None:
                origin_dx, origin_dy = self._origin_translate(state, origin_x, origin_y)
                # Upstream's legacy end point for a vertical glyph: the
                # horizontal width (``getWidth(code) / 1000``) from the
                # unshifted cursor, through the text matrix and CTM.
                dx = _f32(_f32(self._vertical_sort_width(font, code) * font_size) * th)
                end_x, end_y = self._ctm_point(
                    state,
                    _f32(_f32(dx * state.tm_a) + _f32(state.text_x)),
                    _f32(_f32(dx * state.tm_b) + _f32(state.text_y)),
                )
                crop_llx = self._crop_lower_left_x
                crop_lly = self._crop_lower_left_y
                positions.append(
                    TextPosition(
                        text=glyph_text,
                        x=origin_dx,
                        y=origin_dy,
                        font_size=effective_font_size,
                        font_size_in_pt=font_size_in_pt,
                        font_name=state.font_name,
                        font=font,
                        resolved_font_name=resolved_font_name,
                        width=0.0,
                        width_of_space=glyph_width_of_space,
                        char_spacing=char_spacing,
                        word_spacing=word_spacing,
                        dir=text_dir,
                        height=run_height,
                        individual_widths=[_f32(end_x - origin_dx)],
                        text_matrix=[
                            state.tm_a,
                            state.tm_b,
                            state.tm_c,
                            state.tm_d,
                            origin_x,
                            origin_y,
                        ],
                        device_x=_f32(origin_dx - crop_llx),
                        device_y=_f32(origin_dy - crop_lly),
                        device_end_x=_f32(end_x - crop_llx),
                        device_end_y=_f32(end_y - crop_lly),
                        tf_font_size=font_size,
                    )
                )
                emitted_any = True
            # Advance the cursor down the column by the vertical displacement
            # ``ty = w1y·fontSize + Tc (+ Tw on single-byte code 32)``.
            ty = w1y * font_size + char_spacing
            if consumed == 1 and code == 32:
                ty += word_spacing
            state.text_x += ty * state.tm_c
            state.text_y += ty * state.tm_d
        # When the font could not read any code (defensive), fall back to one
        # collapsed run at the cursor so no text is silently dropped.
        if not emitted_any:
            fallback_text = actual_text if has_actual_text else text
            if fallback_text:
                origin_dx, origin_dy = self._origin_translate(
                    state, state.text_x, state.text_y
                )
                positions.append(
                    TextPosition(
                        text=fallback_text,
                        x=origin_dx,
                        y=origin_dy,
                        font_size=effective_font_size,
                        font_size_in_pt=font_size_in_pt,
                        font_name=state.font_name,
                        font=font,
                        resolved_font_name=resolved_font_name,
                        width=0.0,
                        width_of_space=0.0,
                        char_spacing=char_spacing,
                        word_spacing=word_spacing,
                        dir=text_dir,
                        height=run_height,
                        text_matrix=[
                            state.tm_a,
                            state.tm_b,
                            state.tm_c,
                            state.tm_d,
                            state.text_x,
                            state.text_y,
                        ],
                    )
                )

    def _emit(
        self,
        s: COSString,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        """Emit the positions for one show-text string.

        Thin wrapper over :meth:`_emit_run` that tags every position the
        run produced while an ``/ActualText`` span was open. Upstream's
        ``PDFTextStripper.processTextPosition`` bypasses the
        duplicate-overlapping-text filter whenever ``actualText != null``
        (the glyph is always shown and never recorded in
        ``characterListMapping``); the lite pipeline dedups after the
        page walk, so the span membership must travel with the position.
        """
        mark = len(positions)
        in_actual_text = self._actual_text is not None
        self._emit_run(s, state, positions)
        if in_actual_text:
            for pos in positions[mark:]:
                pos.from_actual_text = True

    def _emit_run(
        self,
        s: COSString,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        raw_bytes = s.get_bytes()
        font = self._active_font
        run_font = self._run_font
        if (
            run_font is not None
            and run_font[0] is font
            and run_font[1] is self._active_cmap
            and run_font[2] is self._glyph_memo
        ):
            # The same horizontal one-byte font as a run already read on
            # this page: its name and per-byte glyph memo are known.
            byte_memo = run_font[4]
            try:
                glyphs = [byte_memo[b] for b in raw_bytes]
            except KeyError:
                pass
            else:
                self._emit_glyphs(state, positions, font, run_font[3], glyphs)
                return
        if font is None:
            # Upstream ``showText``: "No current font, will use default".
            _log.warning("No current font, will use default")
            font = self._active_font = self._get_default_font()
            self._active_avg_advance = self._compute_avg_advance(font, state.font_size)
            self._active_font_height = self._compute_font_height(font)
        resolved_font_name, vertical = self._font_traits(font)
        # Vertical writing mode (WMode 1): when the active font's encoding
        # CMap declares vertical writing, each glyph advances DOWN the page
        # by its vertical displacement vector rather than along the text
        # matrix's horizontal axis (upstream ``PDFStreamEngine.showText``).
        if vertical:
            text = self._decode_show_text(raw_bytes)
            if not text:
                return
            self._emit_vertical(raw_bytes, text, state, positions, font, resolved_font_name)
            return
        glyphs = self._read_glyphs(raw_bytes, font)
        if glyphs is None:
            # No usable font: decode the run as a whole and advance each
            # character by the average-width estimate.
            text = self._decode_show_text(raw_bytes)
            if not text:
                return
            per_char = self._active_avg_advance
            if per_char is None:
                per_char = state.font_size * 0.5
            fs = state.font_size
            em = per_char / fs if fs else 0.0
            glyphs = [(ch, em, 0, -1) for ch in text]
        elif (
            _USE_FAST_PATHS
            and font is not None
            and type(self)._is_vertical_font is PDFTextStripper._is_vertical_font
            and type(self)._decode_code_to_unicode is PDFTextStripper._decode_code_to_unicode
        ):
            cmap = self._active_cmap
            entry = self._glyph_memo.get((id(font), id(cmap)))
            if (
                entry is not None
                and entry[0] is font
                and entry[1] is cmap
                and entry[4] is not None
            ):
                self._run_font = (font, cmap, self._glyph_memo, resolved_font_name, entry[4])
        self._emit_glyphs(state, positions, font, resolved_font_name, glyphs)

    def _font_traits(self, font: PDFont | None) -> tuple[str | None, bool]:
        """``(font.get_name(), self._is_vertical_font(font))``, remembered per
        font for the page (both are fixed for a font)."""
        if (
            font is None
            or type(self)._is_vertical_font is not PDFTextStripper._is_vertical_font
        ):
            return (
                font.get_name() if font is not None else None,
                self._is_vertical_font(font),
            )
        key = id(font)
        entry = self._font_traits_memo.get(key)
        if entry is None or entry[0] is not font:
            entry = (font, font.get_name(), self._is_vertical_font(font))
            self._font_traits_memo[key] = entry
        return entry[1], entry[2]

    def _font_vertical(self, font: PDFont | None) -> bool:
        """``self._is_vertical_font(font)``, remembered per font for the page."""
        if (
            font is None
            or type(self)._is_vertical_font is not PDFTextStripper._is_vertical_font
        ):
            return self._is_vertical_font(font)
        key = id(font)
        entry = self._font_vertical_memo.get(key)
        if entry is None or entry[0] is not font:
            entry = (font, self._is_vertical_font(font))
            self._font_vertical_memo[key] = entry
        return entry[1]

    def _read_glyphs(
        self, raw_bytes: bytes, font: PDFont | None
    ) -> list[tuple[str | None, float, int, int]] | None:
        """Split a show-text string into ``(unicode, displacement, length, code)``.

        Mirrors the code loop of upstream ``PDFStreamEngine.showText``: each
        character code is read through the font (``readCode``), its Unicode
        comes from ``toUnicode`` (``None`` for a composite-font code without
        a mapping, which upstream skips instead of coercing) and its
        horizontal displacement from ``getDisplacement`` (``width / 1000``,
        or the ``/FontMatrix`` scale for Type 3), in text-space em units.
        Returns ``None`` when the font cannot read codes.
        """
        if font is None:
            return None
        read_code = getattr(font, "read_code", None)
        get_width = getattr(font, "get_width", None)
        if not callable(read_code) or not callable(get_width):
            return None
        # Per-page memo of ``code bytes -> (unicode, displacement, code)`` for
        # this font and ``/ToUnicode`` CMap: both lookups are functions of
        # those alone. A subclass that overrides the decoding hook is asked
        # every time.
        cmap = self._active_cmap
        memo_key = (id(font), id(cmap))
        entry = self._glyph_memo.get(memo_key)
        if entry is None or entry[0] is not font or entry[1] is not cmap:
            try:
                from pypdfbox.pdmodel.font import PDType3Font

                type3_scale = (
                    font.get_font_matrix()[0] if isinstance(font, PDType3Font) else None
                )
            except Exception:  # defensive
                type3_scale = None
            # Fonts whose ``read_code`` is one of the stock one-byte readers
            # (``(data[offset] & 0xFF, 1)``) also memoize the whole glyph
            # tuple per byte value.
            byte_memo = (
                {}
                if _USE_FAST_PATHS
                and getattr(type(font), "read_code", None) in _single_byte_readers()
                and "read_code" not in getattr(font, "__dict__", ())
                else None
            )
            entry = (font, cmap, type3_scale, {}, byte_memo)
            self._glyph_memo[memo_key] = entry
        type3_scale = entry[2]
        if type(self)._decode_code_to_unicode is PDFTextStripper._decode_code_to_unicode:
            memo = entry[3]
            byte_memo = entry[4]
            if byte_memo is not None:
                # One code per byte: the same ``(unicode, displacement,
                # length, code)`` tuples the loop below builds, looked up
                # by byte value. Misses go through the loop's own steps,
                # in order.
                try:
                    return [byte_memo[b] for b in raw_bytes]
                except KeyError:
                    pass
                try:
                    for b in raw_bytes:
                        if b not in byte_memo:
                            code_bytes = bytes((b,))
                            cached = memo.get(code_bytes)
                            if cached is None or cached[2] != b:
                                piece = self._decode_code_to_unicode(code_bytes, b, font)
                                w0 = float(get_width(b))
                                displacement = (
                                    _f32(w0 * type3_scale)
                                    if type3_scale is not None
                                    else _f32(w0 / 1000.0)
                                )
                                cached = (piece, displacement, b)
                                memo[code_bytes] = cached
                            byte_memo[b] = (cached[0], cached[1], 1, b)
                except Exception:  # defensive: malformed font / decode
                    return None
                return [byte_memo[b] for b in raw_bytes]
        else:
            memo = None
        glyphs: list[tuple[str | None, float, int, int]] = []
        append = glyphs.append
        offset = 0
        n = len(raw_bytes)
        try:
            while offset < n:
                code, consumed = read_code(raw_bytes, offset)
                if consumed <= 0:
                    return None
                code_bytes = raw_bytes[offset : offset + consumed]
                cached = memo.get(code_bytes) if memo is not None else None
                if cached is None or cached[2] != code:
                    piece = self._decode_code_to_unicode(code_bytes, code, font)
                    w0 = float(get_width(code))
                    displacement = (
                        _f32(w0 * type3_scale)
                        if type3_scale is not None
                        else _f32(w0 / 1000.0)
                    )
                    cached = (piece, displacement, code)
                    if memo is not None:
                        memo[code_bytes] = cached
                append((cached[0], cached[1], consumed, code))
                offset += consumed
        except Exception:  # defensive: malformed font / decode
            return None
        return glyphs

    def _space_width_text(self, font: PDFont | None, fallback: float) -> float:
        """Space width in text space, as upstream ``LegacyPDFStreamEngine.showGlyph``
        computes it: ``getSpaceWidth()``, else 80% of the average glyph width,
        else ``1.0``, all scaled from glyph space to text space."""
        if font is None:
            return fallback
        cache = self._space_width_cache
        key = id(font)
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            from pypdfbox.pdmodel.font import PDType3Font

            factor = (
                _f32(font.get_font_matrix()[0])
                if isinstance(font, PDType3Font)
                else _f32(1 / 1000)
            )
        except Exception:  # defensive
            factor = _f32(1 / 1000)
        try:
            space_width = _f32(_f32(float(font.get_space_width())) * factor)
        except Exception:  # defensive: upstream logs and keeps 0
            space_width = 0.0
        if space_width == 0:
            try:
                average = _f32(float(font.get_average_font_width()))
                space_width = _f32(_f32(average * factor) * _f32(0.8))
            except Exception:  # defensive
                space_width = 0.0
        if space_width == 0:
            space_width = 1.0
        cache[key] = space_width
        return space_width

    def _rendering_scale(self, state: _TextState) -> tuple[float, float]:
        """Scaling factors of upstream's text rendering matrix
        ``[fontSize * Th, 0, 0, fontSize, 0, rise] × textMatrix × CTM``, which
        scale the glyph height and the space width (cached per input)."""
        th = getattr(state, "horizontal_scaling", 1.0)
        ctm = state.ctm
        key = (
            state.font_size,
            th,
            state.tm_a,
            state.tm_b,
            state.tm_c,
            state.tm_d,
            ctm.get_scale_x(),
            ctm.get_shear_y(),
            ctm.get_shear_x(),
            ctm.get_scale_y(),
        )
        cache = self._rendering_scale_cache
        scale = cache.get(key)
        if scale is None:
            parameters = Matrix(
                _f32(state.font_size * th), 0.0, 0.0, state.font_size, 0.0, 0.0
            )
            text_matrix = Matrix(state.tm_a, state.tm_b, state.tm_c, state.tm_d, 0.0, 0.0)
            trm = parameters.multiply(text_matrix).multiply(ctm)
            scale = (trm.get_scaling_factor_x(), trm.get_scaling_factor_y())
            if len(cache) > 4096:
                cache.clear()
            cache[key] = scale
        return scale

    def _ctm_point(self, state: _TextState, x: float, y: float) -> tuple[float, float]:
        """Transform a text-space point (already through the text matrix) by
        the CTM, in float32 like ``Matrix.multiply``'s translation row."""
        ctm = state.ctm
        e = _f32(x)
        g = _f32(y)
        c1 = ctm.get_shear_y()
        c3 = ctm.get_shear_x()
        if c1 == 0.0 and c3 == 0.0:
            # The shear products are zero and leave the sums unchanged.
            return (
                _f32(_f32(e * ctm.get_scale_x()) + ctm.get_translate_x()),
                _f32(_f32(g * ctm.get_scale_y()) + ctm.get_translate_y()),
            )
        tx = _f32(_f32(_f32(e * ctm.get_scale_x()) + _f32(g * c3)) + ctm.get_translate_x())
        ty = _f32(_f32(_f32(e * c1) + _f32(g * ctm.get_scale_y())) + ctm.get_translate_y())
        return tx, ty

    def _run_context(
        self,
        state: _TextState,
        font: PDFont | None,
        key: tuple[object, ...],
        scratch: object,
    ) -> tuple[object, ...]:
        """The run-invariant inputs ``key`` of :meth:`_emit_glyphs` followed
        by the values it derives from them, and a float32 scratch buffer."""
        (
            scale_and_dir,
            font_size,
            th,
            char_spacing,
            word_spacing,
            _font,
            font_height_fraction,
            avg_advance,
            ctm,
            fold_upright,
            rise,
            tm_a,
            tm_b,
            _crop_llx,
            _crop_lly,
            page_height_raw,
            _tm_c,
            _tm_d,
        ) = key
        x_scale, y_scale, text_dir = scale_and_dir
        effective_font_size = font_size * y_scale
        trm_scale_x, trm_scale_y = self._rendering_scale(state)
        run_height = (
            0.0
            if font_height_fraction is None
            else abs(_f32(font_height_fraction * trm_scale_y))
        )
        per_char = avg_advance
        if per_char is None:
            per_char = font_size * 0.5
        space_text = self._space_width_text(font, per_char / font_size if font_size else 0.0)
        width_of_space = abs(_f32(space_text * trm_scale_x))
        c0 = ctm.get_scale_x()
        c4 = ctm.get_scale_y()
        c6 = ctm.get_translate_x()
        c7 = ctm.get_translate_y()
        # Without text rise or CTM shear the matrix products reduce to
        # per-axis float steps (same values as ``_origin_translate`` /
        # ``_ctm_point``).
        simple = not rise and ctm.get_shear_x() == 0.0 and ctm.get_shear_y() == 0.0
        font_size_in_pt = font_size * x_scale
        # Inside ``process_page`` on an unrotated page, an upright glyph gets
        # its upstream geometry (``_JavaGeometry``) here, from the values
        # ``_apply_page_rotation`` then stores (rotation 0, the cropbox
        # height), rather than lazily in a later pass over the page.
        upright = simple and fold_upright and text_dir % 360.0 == 0.0
        page_height = _f32(page_height_raw) if upright else 0.0
        plain_steps = None
        if (
            _USE_FAST_PATHS
            and simple
            and c0 == 1.0
            and c4 == 1.0
            and c6 == 0.0
            and c7 == 0.0
            and tm_b == 0.0
        ):
            # The memo of :func:`_plain_glyph_step` results for these step
            # inputs, keyed by their exact bits (signed zeros differ).
            try:
                steps_key = _PLAIN_STEP_KEY.pack(
                    font_size, th, char_spacing, word_spacing, tm_a, tm_b, x_scale
                )
            except (OverflowError, struct.error):  # (not a float input)
                steps_key = None
            if steps_key is not None:
                memo = self._plain_step_memo
                plain_steps = memo.get(steps_key)
                if plain_steps is None:
                    if len(memo) > 65536:
                        memo.clear()
                    plain_steps = memo[steps_key] = ({}, {})
        if scratch is None:
            scratch = array("f", bytes(16))
        return (
            *key,
            x_scale,
            text_dir,
            effective_font_size,
            run_height,
            width_of_space,
            c0,
            c4,
            c6,
            c7,
            simple,
            font_size_in_pt,
            upright,
            page_height,
            abs(run_height),
            abs(width_of_space),
            plain_steps,
            scratch,
        )

    def _emit_glyphs(
        self,
        state: _TextState,
        positions: list[TextPosition],
        font: PDFont | None,
        resolved_font_name: str | None,
        glyphs: list[tuple[str | None, float, int, int]],
    ) -> None:
        """Emit one :class:`TextPosition` per glyph and advance the cursor.

        Follows upstream ``PDFStreamEngine.showText`` and
        ``LegacyPDFStreamEngine.showGlyph``: each glyph's origin is the text
        rendering matrix at the cursor, its end point is the cursor moved by
        the bare displacement (no ``Tc`` / ``Tw``, as upstream's legacy
        width), its height is the font height times the matrix Y scale, and
        the cursor then advances by ``(w * fontSize + Tc + Tw) * Th``. Under an
        ``/ActualText`` span the first glyph carries the replacement text and
        the others an empty string.
        """
        font_size = state.font_size
        th = getattr(state, "horizontal_scaling", 1.0)
        char_spacing = state.char_spacing
        word_spacing_state = state.word_spacing
        scale_and_dir = self._scale_and_dir(state)
        tm_a = state.tm_a
        tm_b = state.tm_b
        tm_c = state.tm_c
        tm_d = state.tm_d
        ctm = state.ctm
        rise = getattr(state, "text_rise", 0.0)
        font_height_fraction = self._active_font_height
        avg_advance = self._active_avg_advance
        fold_upright = self._fold_upright_geometry
        crop_llx = self._crop_lower_left_x
        crop_lly = self._crop_lower_left_y
        page_height_raw = self._page_height
        # The run-invariant values below are functions of these inputs
        # alone; a run whose inputs are the very same objects as the last
        # run's reuses them (the context keeps every input alive, so an
        # identity match is a value match).
        ctx = getattr(state, "_run_ctx", None)
        if (
            ctx is None
            or ctx[0] is not scale_and_dir
            or ctx[1] is not font_size
            or ctx[2] is not th
            or ctx[3] is not char_spacing
            or ctx[4] is not word_spacing_state
            or ctx[5] is not font
            or ctx[6] is not font_height_fraction
            or ctx[7] is not avg_advance
            or ctx[8] is not ctm
            or ctx[9] is not fold_upright
            or ctx[10] is not rise
            or ctx[11] is not tm_a
            or ctx[12] is not tm_b
            or ctx[13] is not crop_llx
            or ctx[14] is not crop_lly
            or ctx[15] is not page_height_raw
            or ctx[16] is not tm_c
            or ctx[17] is not tm_d
        ):
            ctx = state._run_ctx = self._run_context(
                state,
                font,
                (
                    scale_and_dir,
                    font_size,
                    th,
                    char_spacing,
                    word_spacing_state,
                    font,
                    font_height_fraction,
                    avg_advance,
                    ctm,
                    fold_upright,
                    rise,
                    tm_a,
                    tm_b,
                    crop_llx,
                    crop_lly,
                    page_height_raw,
                    tm_c,
                    tm_d,
                ),
                None if ctx is None else ctx[-1],
            )
        (
            x_scale,
            text_dir,
            effective_font_size,
            run_height,
            width_of_space,
            c0,
            c4,
            c6,
            c7,
            simple,
            font_size_in_pt,
            upright,
            page_height,
            abs_height,
            abs_width_of_space,
            plain_steps,
            scratch,
        ) = ctx[18:]
        self._run_counter += 1
        run_id = self._run_counter
        font_name = state.font_name
        append = positions.append
        new_geometry = _JavaGeometry.__new__
        # ``/ActualText`` only changes at marked-content operators.
        actual_text = self._actual_text
        if plain_steps is not None:
            # An identity CTM and an unrotated, unsheared text matrix
            # (``tm_b == 0``): with a float32 cursor, the products with the
            # exactly-1.0 CTM scale, the sums with its zero translation and
            # the zero ``tm_b`` products are exact, so only three
            # narrowings per glyph remain; the cursor-independent ones come
            # from a memo of :func:`_plain_glyph_step`.
            glyph_x = state.text_x
            glyph_y = state.text_y
            scratch[0] = glyph_x
            scratch[1] = glyph_y
            if scratch[0] == glyph_x and scratch[1] == glyph_y:
                nonspace_steps, space_steps = plain_steps
                last_device_y = None
                start_count = len(positions)
                page_width_raw = self._page_width
                geometry_y = 0.0
                for piece, displacement, code_length, code in glyphs:
                    if code_length == 1 and code == 32:
                        # Word spacing applies to the single-byte code 32 only.
                        step = space_steps.get(displacement)
                        if step is None:
                            step = _plain_glyph_step(
                                displacement,
                                font_size,
                                th,
                                char_spacing,
                                word_spacing_state,
                                tm_a,
                                tm_b,
                                x_scale,
                            )
                            if displacement:
                                # (A zero key would conflate the signed zeros.)
                                space_steps[displacement] = step
                    else:
                        step = nonspace_steps.get(displacement)
                        if step is None:
                            step = _plain_glyph_step(
                                displacement,
                                font_size,
                                th,
                                char_spacing,
                                0.0,
                                tm_a,
                                tm_b,
                                x_scale,
                            )
                            if displacement:
                                nonspace_steps[displacement] = step
                    end_tx_offset, end_ty_offset, step_x, step_y, width = step
                    scratch[0] = end_tx_offset + glyph_x
                    scratch[1] = glyph_x + step_x
                    end_x = scratch[0] * c0 + c6
                    next_x = scratch[1]
                    next_y = glyph_y + step_y
                    if piece is None:
                        glyph_x = next_x
                        glyph_y = next_y
                        continue
                    origin_x = glyph_x * c0 + c6
                    origin_y = glyph_y * c4 + c7
                    end_y = (end_ty_offset + glyph_y) * c4 + c7
                    scratch[0] = end_x - origin_x
                    dx_display = scratch[0]
                    if actual_text is not None:
                        if self._first_actual_text_position:
                            piece = actual_text
                            self._first_actual_text_position = False
                        else:
                            piece = ""
                    if origin_x - origin_x + (origin_y - origin_y) != 0.0:
                        # (Zero exactly when both are finite.)
                        state.text_x = glyph_x
                        state.text_y = glyph_y
                        raise ValueError("Multiplying two matrices produces illegal values")
                    if crop_llx:
                        scratch[0] = origin_x - crop_llx
                        scratch[1] = end_x - crop_llx
                        device_x = scratch[0]
                        device_end_x = scratch[1]
                    else:
                        device_x = origin_x
                        device_end_x = end_x
                    if crop_lly:
                        scratch[0] = origin_y - crop_lly
                        scratch[1] = end_y - crop_lly
                        device_y = scratch[0]
                        device_end_y = scratch[1]
                    else:
                        device_y = origin_y
                        device_end_y = end_y
                    if upright:
                        # ``_JavaGeometry`` for rotation and direction 0. The
                        # width narrows ``device_end_x - device_x``, which
                        # without a cropbox offset is ``dx_display``.
                        if crop_llx:
                            scratch[0] = device_end_x - device_x
                            geometry_width = abs(scratch[0])
                        else:
                            geometry_width = abs(dx_display)
                        if device_y != last_device_y or not device_y:
                            scratch[0] = page_height - device_y
                            geometry_y = scratch[0]
                            last_device_y = device_y
                        # Built with the rotation, page size and width
                        # ``_apply_page_rotation`` then stores for an
                        # unrotated page.
                        position = TextPosition(
                            piece,
                            origin_x,
                            origin_y,
                            effective_font_size,
                            font_name,
                            font,
                            resolved_font_name,
                            geometry_width,
                            width_of_space,
                            char_spacing,
                            word_spacing_state,
                            text_dir,
                            0.0,
                            page_width_raw,
                            page_height_raw,
                            [tm_a, tm_b, tm_c, tm_d, glyph_x, glyph_y],
                            font_size_in_pt,
                            run_height,
                            [dx_display],
                            False,
                            device_x,
                            device_y,
                            device_end_x,
                            device_end_y,
                            font_size,
                        )
                        position._run_id = run_id
                        geometry = new_geometry(_JavaGeometry)
                        geometry.dir = 0.0
                        geometry.x = geometry.x_dir_adj = device_x
                        geometry.y = geometry.y_dir_adj = geometry_y
                        geometry.width = geometry.width_dir_adj = geometry_width
                        geometry.height = abs_height
                        geometry.width_of_space = abs_width_of_space
                        position._java_geometry = geometry
                    else:
                        position = TextPosition(
                            piece,
                            origin_x,
                            origin_y,
                            effective_font_size,
                            font_name,
                            font,
                            resolved_font_name,
                            width,
                            width_of_space,
                            char_spacing,
                            word_spacing_state,
                            text_dir,
                            0.0,
                            0.0,
                            0.0,
                            [tm_a, tm_b, tm_c, tm_d, glyph_x, glyph_y],
                            font_size_in_pt,
                            run_height,
                            [dx_display],
                            False,
                            device_x,
                            device_y,
                            device_end_x,
                            device_end_y,
                            font_size,
                        )
                        position._run_id = run_id
                    append(position)
                    glyph_x = next_x
                    glyph_y = next_y
                state.text_x = glyph_x
                state.text_y = glyph_y
                if upright:
                    # Count the positions built already folded (see
                    # ``_apply_page_rotation``).
                    if self._prefolded_positions is not positions:
                        self._prefolded_positions = positions
                        self._prefolded_count = 0
                    self._prefolded_count += len(positions) - start_count
                return
        isfinite = math.isfinite
        pack2 = _f32x2_pack
        unpack2 = _f32x2_unpack
        pack3 = _f32x3_pack
        unpack3 = _f32x3_unpack
        pack4 = _f32x4_pack
        unpack4 = _f32x4_unpack
        for piece, displacement, code_length, code in glyphs:
            glyph_x = state.text_x
            glyph_y = state.text_y
            # Word spacing applies to the single-byte code 32 only.
            word_spacing = word_spacing_state if code_length == 1 and code == 32 else 0.0
            if simple:
                # :func:`_glyph_step_reference` with independent float32
                # narrowings batched into one ``struct`` round trip each:
                # same operands, same order, so the same values.
                try:
                    dfs, e, g = unpack3(pack3(displacement * font_size, glyph_x, glyph_y))
                    dx, origin_x, origin_y, adv = unpack4(
                        pack4(dfs * th, e * c0, g * c4, dfs + char_spacing)
                    )
                    origin_x, origin_y, end_tx, end_ty = unpack4(
                        pack4(origin_x + c6, origin_y + c7, dx * tm_a, dx * tm_b)
                    )
                    end_tx, end_ty, adv = unpack3(
                        pack3(end_tx + e, end_ty + g, adv + word_spacing)
                    )
                    end_x, end_y, adv = unpack3(
                        pack3(end_tx * c0, end_ty * c4, adv * th)
                    )
                    end_x, end_y, step_x, step_y = unpack4(
                        pack4(end_x + c6, end_y + c7, adv * tm_a, adv * tm_b)
                    )
                    dx_display, width, next_x, next_y = unpack4(
                        pack4(
                            end_x - origin_x,
                            dx * x_scale,
                            glyph_x + step_x,
                            glyph_y + step_y,
                        )
                    )
                    width = abs(width)
                except OverflowError:
                    (
                        origin_x,
                        origin_y,
                        end_x,
                        end_y,
                        dx_display,
                        width,
                        next_x,
                        next_y,
                    ) = _glyph_step_reference(
                        glyph_x,
                        glyph_y,
                        displacement,
                        font_size,
                        th,
                        char_spacing,
                        word_spacing,
                        tm_a,
                        tm_b,
                        c0,
                        c4,
                        c6,
                        c7,
                        x_scale,
                    )
                if piece is None:
                    state.text_x = next_x
                    state.text_y = next_y
                    continue
            if piece is not None:
                if actual_text is not None:
                    if self._first_actual_text_position:
                        piece = actual_text
                        self._first_actual_text_position = False
                    else:
                        piece = ""
                if simple:
                    if not (isfinite(origin_x) and isfinite(origin_y)):
                        raise ValueError("Multiplying two matrices produces illegal values")
                else:
                    # Upstream's legacy end point: the bare displacement
                    # through the text matrix and CTM (no font-parameter
                    # matrix).
                    dx = _f32(_f32(displacement * font_size) * th)
                    origin_x, origin_y = self._origin_translate(state, glyph_x, glyph_y)
                    end_x, end_y = self._ctm_point(
                        state,
                        _f32(_f32(dx * tm_a) + _f32(glyph_x)),
                        _f32(_f32(dx * tm_b) + _f32(glyph_y)),
                    )
                    dx_display = _f32(end_x - origin_x)
                    width = abs(_f32(dx * x_scale))
                if crop_llx:
                    device_x, device_end_x = _f32x2(origin_x - crop_llx, end_x - crop_llx)
                else:
                    device_x = origin_x
                    device_end_x = end_x
                if crop_lly:
                    device_y, device_end_y = _f32x2(origin_y - crop_lly, end_y - crop_lly)
                else:
                    device_y = origin_y
                    device_end_y = end_y
                # Positional arguments in field order: keyword passing of
                # 25 fields dominates the construction cost.
                position = TextPosition(
                    piece,
                    origin_x,
                    origin_y,
                    effective_font_size,
                    font_name,
                    font,
                    resolved_font_name,
                    width,
                    width_of_space,
                    char_spacing,
                    word_spacing_state,
                    text_dir,
                    0.0,
                    0.0,
                    0.0,
                    [tm_a, tm_b, tm_c, tm_d, glyph_x, glyph_y],
                    font_size_in_pt,
                    run_height,
                    [dx_display],
                    False,
                    device_x,
                    device_y,
                    device_end_x,
                    device_end_y,
                    font_size,
                )
                position._run_id = run_id
                if upright:
                    # ``_JavaGeometry`` for rotation and direction 0.
                    try:
                        geometry_y, geometry_width = unpack2(
                            pack2(page_height - device_y, device_end_x - device_x)
                        )
                    except OverflowError:
                        geometry_y = f32(page_height - device_y)
                        geometry_width = f32(device_end_x - device_x)
                    geometry_width = abs(geometry_width)
                    geometry = new_geometry(_JavaGeometry)
                    geometry.dir = 0.0
                    geometry.x = geometry.x_dir_adj = device_x
                    geometry.y = geometry.y_dir_adj = geometry_y
                    geometry.width = geometry.width_dir_adj = geometry_width
                    geometry.height = abs_height
                    geometry.width_of_space = abs_width_of_space
                    position._java_geometry = geometry
                append(position)
            if simple:
                state.text_x = next_x
                state.text_y = next_y
            else:
                advance = _f32(
                    _f32(_f32(_f32(displacement * font_size) + char_spacing) + word_spacing)
                    * th
                )
                step_x, step_y = _f32x2(advance * tm_a, advance * tm_b)
                state.text_x, state.text_y = _f32x2(glyph_x + step_x, glyph_y + step_y)

    @staticmethod
    def _origin_matrix(state: _TextState, text_x: float, text_y: float) -> Matrix:
        """Text-rendering matrix for a glyph origin at ``(text_x, text_y)``.

        Like :meth:`_text_rendering_matrix` but for an explicit translation
        (a subdivided sub-run starts partway through the parent run). Folds
        text rise (``Ts``) in the same parameter-matrix-first way.
        """
        tm = Matrix(state.tm_a, state.tm_b, state.tm_c, state.tm_d, text_x, text_y)
        rise = getattr(state, "text_rise", 0.0)
        if rise:
            tm = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, rise).multiply(tm)
        return tm.multiply(state.ctm)

    def _emit_tj_array(
        self,
        arr: COSArray,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        emit = self._emit
        scratch = None
        for entry in arr:
            if isinstance(entry, COSString):
                emit(entry, state, positions)
            elif isinstance(entry, COSNumber):
                # ``TJ`` numeric adjustments are in thousandths of an em,
                # subtracted (negative = move forward). The adjustment is
                # in text space, so (like the show-text advance) it is
                # scaled horizontally by ``Tz/100`` (PDF 32000-1 §9.3.4)
                # and then carried through the text-matrix scale/shear
                # before it moves the translation-space cursor. Honouring
                # ``Tz`` here makes a ``TJ`` jump condense / expand with the
                # surrounding text, so word segmentation matches an engine
                # that scales the gap by ``Tz``.
                # Upstream: ``tx = -tj / 1000 * fontSize * horizontalScaling``
                # then ``textMatrix.translate(tx, 0)``, all in float.
                if self._font_vertical(self._active_font):
                    ty = _f32(_f32(-entry.float_value() / 1000.0) * state.font_size)
                    state.text_x = _f32(state.text_x + _f32(ty * state.tm_c))
                    state.text_y = _f32(state.text_y + _f32(ty * state.tm_d))
                    continue
                if not _USE_FAST_PATHS:
                    state.text_x, state.text_y = _tj_step(
                        entry.float_value(),
                        state.font_size,
                        getattr(state, "horizontal_scaling", 1.0),
                        state.tm_a,
                        state.tm_b,
                        state.text_x,
                        state.text_y,
                    )
                    continue
                # :func:`_tj_step`, narrowing through a float32 array; a
                # product with an exactly-1.0 size or scaling is exact.
                if scratch is None:
                    scratch = array("f", bytes(8))
                scratch[0] = -entry.float_value() / 1000.0
                font_size = state.font_size
                if font_size != 1.0:
                    scratch[0] = scratch[0] * font_size
                th = getattr(state, "horizontal_scaling", 1.0)
                if th != 1.0:
                    scratch[0] = scratch[0] * th
                tx = scratch[0]
                scratch[0] = tx * state.tm_a
                scratch[1] = tx * state.tm_b
                scratch[0] = state.text_x + scratch[0]
                scratch[1] = state.text_y + scratch[1]
                state.text_x = scratch[0]
                state.text_y = scratch[1]

    # ---------- /ToUnicode CMap helpers ----------

    def _current_resources(self) -> PDResources | None:
        """Resources in effect for font / property-list lookups.

        While recursing into a form XObject (``Do``) the form's own
        ``/Resources`` override the host page's, mirroring upstream's
        ``PDFStreamEngine.showForm`` pushing the form resources for the
        duration of the form body. Otherwise the active page's resources.
        """
        if self._active_resources is not None:
            return self._active_resources
        if self._active_page is None:
            return None
        return self._active_page.get_resources()

    def _get_cmap_for_font(self, font_resource_name: str | None) -> CMap | None:
        """Resolve and cache the parsed ``/ToUnicode`` CMap for the
        font registered as ``font_resource_name`` in the active page's
        ``/Resources/Font`` subdictionary.

        Returns ``None`` (and caches the negative result) when:
          - no page is active, or
          - the resources don't list this font, or
          - the font dict has no ``/ToUnicode`` entry, or
          - ``/ToUnicode`` isn't a stream.

        ``Encoding`` / ``Differences`` based glyph→unicode resolution for
        fonts without ``/ToUnicode`` is handled by the typed-font decode
        path after this lookup returns ``None``.
        """
        if font_resource_name is None or self._active_page is None:
            return None
        cached = self._cmap_cache.get(font_resource_name)
        if font_resource_name in self._cmap_cache:
            return cached
        cmap: CMap | None = None
        try:
            resources = self._current_resources()
            if resources is None:
                self._cmap_cache[font_resource_name] = None
                return None
            font_entry = resources.get_font(COSName.get_pdf_name(font_resource_name))
            if font_entry is not None:
                font_dict = (
                    font_entry
                    if isinstance(font_entry, COSDictionary)
                    else font_entry.get_cos_object()
                )
                to_unicode = font_dict.get_dictionary_object("ToUnicode")
                if isinstance(to_unicode, COSStream):
                    # The parse of a stream an earlier page already read.
                    known = self._to_unicode_memo.get(id(to_unicode))
                    if _USE_FAST_PATHS and known is not None and known[0] is to_unicode:
                        cmap = known[1]
                    else:
                        with to_unicode.create_input_stream() as src:
                            cmap = CMapParser().parse(src.read())
                        memo = self._to_unicode_memo
                        if len(memo) > 256:
                            memo.clear()
                        memo[id(to_unicode)] = (to_unicode, cmap)
        except Exception:  # defensive: malformed CMap → no decode
            cmap = None
        self._cmap_cache[font_resource_name] = cmap
        return cmap

    def _decode_show_text(self, text_bytes: bytes) -> str:
        """Decode a show-text byte string to a Python ``str``.

        Resolution order matches upstream's text-extraction pipeline:

        1. ``/ToUnicode`` CMap when present (most authoritative — present
           on all modern simple fonts and required for composite fonts).
        2. Typed ``PDSimpleFont.decode`` when the font is wired through
           the resources — this covers the ``/Encoding`` + ``/Differences``
           case where the font dictates a per-byte glyph name and the
           Adobe Glyph List supplies the Unicode value.
        3. ``COSString.get_string`` Latin-1 / PDFDocEncoding fallback for
           fonts with neither a ``/ToUnicode`` CMap nor a typed wrapper
           the resource lookup could resolve.
        """
        if self._active_cmap is not None:
            return self._decode_text_via_cmap(
                text_bytes, self._active_cmap, self._active_font
            )
        font = self._active_font
        if font is not None:
            # Local import to avoid pulling pdmodel.font into the text
            # module's import graph at top level (circular: pdmodel.font
            # imports COSStream which imports the filter module which
            # imports …).
            from pypdfbox.pdmodel.font import PDSimpleFont

            if isinstance(font, PDSimpleFont):
                try:
                    return font.decode(text_bytes)
                except Exception:  # defensive
                    pass
            else:
                decoded = self._decode_composite_codes(text_bytes, font)
                if decoded is not None:
                    return decoded
        # Fallback: construct a transient COSString purely for its
        # PDFDocEncoding-aware decode logic. We can't reuse ``s`` here
        # because callers pass raw bytes via ``s.get_bytes()`` already.
        return text_bytes.decode("latin-1", errors="replace")

    @staticmethod
    def _decode_composite_codes(text_bytes: bytes, font: PDFont) -> str | None:
        """Decode a composite (Type 0) font's show-text bytes code by code.

        Mirrors upstream ``LegacyPDFStreamEngine.showGlyph``: each code read
        through the font's encoding CMap is mapped with ``font.toUnicode``
        (which falls back to the predefined ``Adobe-<Ordering>-UCS2`` CMap
        for a font without ``/ToUnicode``), and a code with no Unicode
        mapping is skipped rather than coerced to a character, since Acrobat
        does not coerce composite-font codes either. Returns ``None`` when
        the font cannot read codes, so the caller keeps its Latin-1 fallback.
        """
        read_code = getattr(font, "read_code", None)
        if not callable(read_code):
            return None
        out: list[str] = []
        offset = 0
        n = len(text_bytes)
        try:
            while offset < n:
                code, consumed = read_code(text_bytes, offset)
                if consumed <= 0:
                    return None
                piece = font.to_unicode(code)
                if piece is not None:
                    out.append(piece)
                offset += consumed
        except Exception:  # defensive: malformed font / encoding
            return None
        return "".join(out)

    def _get_default_font(self) -> PDFont | None:
        """Upstream ``PDFStreamEngine.getDefaultFont``: a non-embedded
        Helvetica, built once per stripper."""
        font = self._default_font
        if font is None:
            try:
                from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
                from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

                font = PDType1Font(Standard14Fonts.FontName.HELVETICA)
            except Exception:  # defensive
                return None
            self._default_font = font
        return font

    def _get_font_for(self, font_resource_name: str | None) -> PDFont | None:
        """Resolve and cache the typed ``PDFont`` for the resource name
        last set by ``Tf``. Returns ``None`` when the page has no
        matching ``/Font`` entry, when the entry isn't a dictionary, or
        when ``PDFontFactory`` declines to wrap it (e.g. unsupported
        ``/Subtype``)."""
        if font_resource_name is None or self._active_page is None:
            return None
        if font_resource_name in self._font_cache:
            return self._font_cache[font_resource_name]
        font: PDFont | None = None
        try:
            # Local import to break the pdmodel.font ↔ text cycle.
            from pypdfbox.pdmodel.font import PDFontFactory

            resources = self._current_resources()
            if resources is None:
                self._font_cache[font_resource_name] = None
                return None
            font_entry = resources.get_font(COSName.get_pdf_name(font_resource_name))
            if font_entry is not None:
                if isinstance(font_entry, COSDictionary):
                    font = PDFontFactory.create_font(font_entry)
                else:
                    font = font_entry
        except Exception:  # defensive: malformed font → no decode
            font = None
        self._font_cache[font_resource_name] = font
        return font

    @staticmethod
    def _compute_avg_advance(font: PDFont | None, font_size: float) -> float | None:
        """Convert a font's average glyph width to a user-space
        per-character advance at the given ``font_size``. Returns ``None``
        when the font has no usable ``/Widths`` array — callers fall back to
        the legacy 0.5-em-per-char estimate.

        The glyph-space → user-space scale is ``1/1000`` for ordinary simple
        fonts but the font's ``/FontMatrix`` x-scale for a Type 3 font (see
        below)."""
        if font is None or font_size <= 0:
            return None
        # Local import to avoid pulling pdmodel.font into module-load
        # time (cycle).
        from pypdfbox.pdmodel.font import PDSimpleFont

        if not isinstance(font, PDSimpleFont):
            return None
        avg_width = font.get_average_font_width()
        if avg_width <= 0:
            return None
        # ``/Widths`` for most simple fonts are glyph-space thousandths of an
        # em (the implicit ``[0.001 0 0 0.001 0 0]`` FontMatrix), so the
        # user-space advance is ``width / 1000 × fontSize``. A Type 3 font is
        # the exception: its ``/Widths`` are in the glyph space defined by an
        # explicit ``/FontMatrix`` whose x-scale is rarely 0.001, so the
        # advance is ``width × fontMatrix[a] × fontSize`` — mirroring upstream
        # ``PDType3Font.getDisplacement`` (``fontMatrix.transform(width,0).x``)
        # which the rendering / text engine uses to advance the cursor. Using
        # the fixed 1/1000 here would mis-scale every Type 3 advance by the
        # ratio of the real FontMatrix x-scale to 0.001.
        from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

        if isinstance(font, PDType3Font):
            x_scale = font.get_font_matrix()[0]
            return avg_width * x_scale * font_size
        return avg_width / 1000.0 * font_size

    def _compute_font_height(self, font: PDFont | None) -> float:
        """Return the font's glyph height in text-space units (a fraction of
        the em), as upstream ``LegacyPDFStreamEngine.computeFontHeight``
        computes it in float: half the font bounding box height, replaced by
        the descriptor's ``/CapHeight`` when that is smaller (or the box is
        empty), and by ``(ascent - descent) / 2`` when even the cap height
        exceeds the ascent; then scaled from glyph space to text space
        (``/ 1000``, or the ``/FontMatrix`` for Type 3).

        The result is cached per font object for the active page, like
        upstream's ``fontHeightMap``. Returns ``0.5`` only when no font is
        given at all.
        """
        if font is None:
            return 0.5
        cached = self._font_height_cache.get(id(font))
        if cached is not None:
            return cached
        glyph_height = 0.0
        try:
            bbox = font.get_bounding_box()
        except Exception:  # defensive: malformed font program
            bbox = None
        if bbox is not None:
            lower_left_y = _f32(float(bbox.get_lower_left_y()))
            upper_right_y = _f32(float(bbox.get_upper_right_y()))
            if lower_left_y < -32768:
                # PDFBOX-2158 / PDFBOX-3130 over-/under-flowed lower-left Y.
                lower_left_y = _f32(-(lower_left_y + 65536))
            glyph_height = _f32(_f32(upper_right_y - lower_left_y) / 2)
        try:
            descriptor = font.get_font_descriptor()
        except Exception:  # defensive
            descriptor = None
        if descriptor is not None:
            cap_height = _f32(float(descriptor.get_cap_height()))
            if cap_height != 0 and (cap_height < glyph_height or glyph_height == 0):
                glyph_height = cap_height
            ascent = _f32(float(descriptor.get_ascent()))
            descent = _f32(float(descriptor.get_descent()))
            half_extent = _f32(_f32(ascent - descent) / 2)
            if (
                cap_height > ascent
                and ascent > 0
                and descent < 0
                and (half_extent < glyph_height or glyph_height == 0)
            ):
                glyph_height = half_extent
        # Glyph space → text space.
        from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

        if isinstance(font, PDType3Font):
            try:
                matrix = font.get_font_matrix()
                height = _f32(_f32(glyph_height * _f32(matrix[3])) + _f32(matrix[5]))
            except Exception:  # defensive
                height = _f32(glyph_height / 1000)
        else:
            height = _f32(glyph_height / 1000)
        self._font_height_cache[id(font)] = height
        return height

    @staticmethod
    def _compute_width_of_space(
        font: PDFont | None,
        font_size: float,
        *,
        fallback: float,
    ) -> float:
        """Return a user-space space width for the active font.

        Current font wrappers only expose per-code widths on some
        subclasses, so this is intentionally conservative: use
        ``get_glyph_width(32)`` when present and positive, otherwise
        reuse the per-character fallback already driving run advances.
        """
        if font is not None and font_size > 0:
            get_glyph_width = getattr(font, "get_glyph_width", None)
            if callable(get_glyph_width):
                try:
                    width = float(get_glyph_width(32))
                except Exception:  # defensive: malformed font metrics
                    width = 0.0
                if width > 0.0:
                    return width / 1000.0 * font_size
        return fallback

    @staticmethod
    def _decode_text_via_cmap(
        text_bytes: bytes, cmap: CMap, font: PDFont | None = None
    ) -> str:
        """Walk ``text_bytes`` consuming codes whose width is governed by
        the CMap's codespace ranges, look each up via ``cmap.to_unicode``,
        and concatenate.

        When the ``/ToUnicode`` CMap has no mapping for a code, resolve it
        through ``font.to_unicode(code)`` — this preserves upstream's
        ``PDFont.toUnicode`` fallback chain (ToUnicode → ``/Encoding`` glyph
        name → Adobe Glyph List). A simple font whose ``/ToUnicode`` CMap
        covers only some codes (a common subsetting/ligature pattern) would
        otherwise lose every uncovered glyph, diverging from Apache PDFBox's
        ``PDFTextStripper`` which emits ``font.toUnicode(code)`` per glyph.
        Only when the font fallback also yields nothing is the code dropped.

        Mirrors PDFBox's ``PDFont.encode``/``readCode`` loop, simplified
        for the lite stripper: we drive ``CMap.read_code`` directly off a
        ``BytesIO`` rather than threading the parser through a glyph
        positioning pass.
        """
        import io as _io  # local: only used here

        stream = _io.BytesIO(text_bytes)
        out: list[str] = []
        while True:
            pos_before = stream.tell()
            if pos_before >= len(text_bytes):
                break
            code = cmap.read_code(stream)
            # Guard against zero-length reads (defensive — read_code
            # always advances at least one byte for non-empty input).
            if stream.tell() == pos_before:
                break
            piece = cmap.to_unicode(code)
            if piece is None and font is not None:
                try:
                    piece = font.to_unicode(code)
                except Exception:  # defensive: malformed font
                    piece = None
            if piece is not None:
                out.append(piece)
        return "".join(out)

    # ---------- formatting ----------

    def _empty_article_wrap(self) -> str:
        """Text emitted for a page that yields no glyphs.

        Upstream ``PDFTextStripper.writePage`` still iterates
        ``charactersByArticle`` for a glyph-free page (a page with no beads
        contributes a single empty article slot) and brackets each slot in
        ``startArticle()`` / ``endArticle()`` regardless of whether it holds
        any text (PDFTextStripper.java:497-560). The page-body
        ``writeParagraphStart`` / ``writeParagraphEnd`` are gated on at least
        one written character (the ``startOfArticle`` / first-glyph path), so
        an empty article emits *only* the article markers, never paragraph
        ones. With the default empty markers this is invisible; under
        ``add_more_formatting`` (article markers promoted to the line
        separator) it supplies the per-page newlines the Java oracle emits for
        a whitespace-only page. Returning ``""`` here — as the lite stripper
        did before wave 1542 — dropped those markers, so a glyph-free page
        diverged from Java whenever any article marker was non-empty.
        """
        if not self._article_start and not self._article_end:
            return ""
        return self._article_start + self._article_end

    def _format_positions(self, positions: list[TextPosition]) -> str:
        """Lay a page's glyphs out as text, the way upstream
        ``PDFTextStripper`` does from ``processTextPosition`` on.

        In order: glyphs a subclass declines via :meth:`should_skip_glyph`
        are dropped; duplicate overlapping glyphs are suppressed (fake bold,
        ``suppressDuplicateOverlappingText``); the rest are assigned to their
        thread-bead articles (``2 * N + 1`` slots for ``N`` beads, see
        :meth:`_partition_by_beads`) and diacritics are merged into the glyph
        they overlap; each article is sorted with ``TextPositionComparator``
        when ``sort_by_position`` is set (dropping spaces contained in the
        previous glyph, PDFBOX-5487); and finally :meth:`_write_articles`
        runs upstream's ``writePage`` line, word and paragraph logic. The
        lite-only flipped-axes mode keeps its own formatter.
        """
        # Drop glyphs the subclass declines via ``should_skip_glyph``
        # before any sorting/grouping — keeps the position lists handed
        # to ``write_string`` in sync with what subclasses would have
        # seen via ``processTextPosition`` upstream.
        if _USE_FAST_PATHS and type(self).should_skip_glyph is _BASE_SHOULD_SKIP_GLYPH:
            # (The base hook keeps every glyph.)
            positions = list(positions)
        else:
            positions = [p for p in positions if not self.should_skip_glyph(p)]
        if self._flip_axes:
            if not positions:
                return self._empty_article_wrap()
            return self._format_positions_flipped(positions)
        if self._suppress_duplicate_overlapping_text:
            positions = self._drop_overlapping_duplicates(positions)
        groups = self._assign_articles(positions)
        groups = [self._merge_diacritics(group) for group in groups]
        if self._sort_by_position:
            for group in groups:
                # ``Collections.sort`` (Java's TimSort); the comparator is not
                # transitive, so the merge policy matters, and Java may reject
                # it, in which case upstream falls back to IterativeMergeSort.
                try:
                    tim_sort(group, _java_compare)
                except ComparisonContractError:
                    IterativeMergeSort.sort(group, _java_compare)
                self._remove_contained_spaces_java(group)
        # ``charactersByArticle`` as upstream's ``writePage`` iterates it.
        self._characters_by_article = groups
        chunks: list[str] = []

        def _sink(piece: str) -> None:
            chunks.append(piece)

        self._write_articles(groups, _sink)
        return "".join(chunks)

    @staticmethod
    def _merge_diacritics(positions: list[TextPosition]) -> list[TextPosition]:
        """Upstream ``processTextPosition``'s diacritic handling: a diacritic
        glyph that overlaps the previous glyph of its article is merged into
        it, and a previous diacritic overlapped by the current glyph is merged
        into the current one."""
        text_list: list[TextPosition] = []
        append = text_list.append
        # ``is_diacritic`` of the stock position class, read from its
        # per-character memo; ``previous_diacritic`` remembers the last
        # entry's answer while its text is unchanged (``None``: not known).
        known = _IS_DIACRITIC
        fast = _USE_FAST_PATHS
        previous: TextPosition | None = None
        previous_diacritic: bool | None = None
        for text in positions:
            if previous is None:
                append(text)
                previous = text
                previous_diacritic = None
                continue
            diacritic = None
            if fast and type(text) is TextPosition:
                piece = text.text
                diacritic = known.get(piece) if len(piece) == 1 else False
            if diacritic is None:
                diacritic = text.is_diacritic()
            if diacritic and _java_contains(previous, text):
                _java_merge_diacritic(previous, text)
                previous_diacritic = None
                continue
            if previous_diacritic is None or not fast:
                previous_diacritic = previous.is_diacritic()
            if previous_diacritic and _java_contains(text, previous):
                _java_merge_diacritic(text, previous)
                text_list[-1] = text
                previous = text
                previous_diacritic = None
            else:
                append(text)
                previous = text
                previous_diacritic = diacritic
        return text_list

    @staticmethod
    def _remove_contained_spaces_java(text_list: list[TextPosition]) -> None:
        """Upstream ``removeContainedSpaces`` (PDFBOX-5487) on Java geometry."""
        if not text_list:
            return
        previous = text_list[0]
        kept = [previous]
        for position in text_list[1:]:
            if position.get_unicode() == " " and _java_completely_contains(previous, position):
                continue
            kept.append(position)
            previous = position
        text_list[:] = kept

    def _write_articles(
        self, articles: list[list[TextPosition]], sink: Callable[[str], None]
    ) -> None:
        """Port of upstream ``PDFTextStripper.writePage``'s article loop.

        The line state (``lastPosition``, ``maxYForLine`` and friends) spans
        the whole page, so the first glyph of an article is line-broken
        against the last glyph of the previous one; only ``startOfArticle``
        and the running average character width reset per article. Glyphs
        are queued a line at a time as ``LineItem`` entries (word separators
        included) and written through :meth:`normalize` / :meth:`write_line`.

        A subclass that overrides ``write_article_start`` (``PDFText2HTML``)
        brackets paragraphs itself, so the page-opening paragraph start and
        the per-article paragraph end are left to it.
        """
        manages_own_paragraph = (
            type(self).write_article_start is not PDFTextStripper.write_article_start
        )
        emit_paragraph_markers = not manages_own_paragraph
        sort = self._sort_by_position
        ignore_spaces = self._ignore_content_stream_space_glyphs
        separator = self._word_separator
        spacing_tolerance = _f32(self._spacing_tolerance)
        average_char_tolerance = _f32(self._average_char_tolerance)

        font_or_size_changed = self._java_font_or_size_changed
        variance = _F32_TENTH
        # Float32 narrowing by a store into (and load from) a ``float``
        # array: the C ``(float)`` cast, which is Java's ``(float)`` (an
        # out-of-range magnitude becomes an infinity).
        scratch = array("f", bytes(16))
        fast = _USE_FAST_PATHS
        word_separator_item = _LineItem.get_word_separator()
        line_item = _LineItem
        # ``_LineItem(position)`` without the ``__init__`` call.
        new_line_item = _LineItem.__new__
        # With the stock ``normalize`` / ``normalize_add`` a line is queued
        # as its positions, ``None`` standing for the word separator.
        bare_line = (
            fast
            and type(self).normalize is _BASE_NORMALIZE
            and type(self).normalize_add is _BASE_NORMALIZE_ADD
        )
        normalize_positions = self._normalize_positions
        # With the stock line and word hooks as well, a line's words are
        # written straight from its positions.
        cls = type(self)
        bare_write = (
            bare_line
            and cls.write_line is _BASE_WRITE_LINE
            and cls.create_word is _BASE_CREATE_WORD
            and cls.write_string_with_positions is _BASE_WRITE_STRING_WITH_POSITIONS
            and cls.write_string is _BASE_WRITE_STRING
            and cls.process_text_position is _BASE_PROCESS_TEXT_POSITION
            and cls.write_word_separator is _BASE_WRITE_WORD_SEPARATOR
        )
        write_bare_line = self._write_bare_line
        max_y_for_line = -_FLT_MAX
        end_of_last_text_x = -1.0
        last_word_spacing = -1.0
        max_height_for_line = -1.0
        # The last position, and its ``PositionWrapper`` once one is needed:
        # a wrapper only carries flags, which are only ever set on wrappers
        # made at a line break, at the page start or for an article start,
        # so a later-made one is in the same state an earlier one would be.
        last_text: TextPosition | None = None
        last_stock = False
        last_wrapper: PositionWrapper | None = None
        last_geometry: _JavaGeometry | None = None
        last_line_start: PositionWrapper | None = None
        start_of_page = True
        # In-line spacing terms remembered for the last ``(word_spacing,
        # last_word_spacing)`` pair, and the ``within`` bounds for the last
        # ``y``: functions of those values alone.
        memo_word_spacing: float | None = None
        memo_last_word_spacing: float | None = None
        memo_delta_space = 0.0
        memo_space_limit = 0.0
        memo_y: float | None = None
        memo_within_low = 0.0
        memo_within_high = 0.0

        for text_list in articles:
            if self._article_start:
                self.write_article_start(sink)
                if manages_own_paragraph:
                    # The subclass's article start opened the paragraph.
                    self._in_paragraph = True
            start_of_article = True
            # ``_LineItem`` entries, or positions and ``None`` (``bare_line``).
            line: list = []
            previous_ave_char_width = -1.0
            for position in text_list:
                # (The stock position's ``get_unicode`` / ``get_font`` return
                # these fields.)
                stock = fast and type(position) is TextPosition
                character_value = position.text if stock else position.get_unicode()
                # PDFBOX-3774: conditionally ignore spaces from the content stream.
                if ignore_spaces and character_value == " ":
                    continue
                current: PositionWrapper | None = None
                if last_text is not None:
                    current_size = position.tf_font_size
                    # ``hasFontOrSizeChanged`` is false for the same ``Tf``
                    # size and font instance; anything else asks it.
                    if (
                        current_size is None
                        or current_size != last_text.tf_font_size
                        or (
                            position.font is not last_text.font
                            if stock and last_stock
                            else position.get_font() is not last_text.get_font()
                        )
                    ) and font_or_size_changed(position, last_text):
                        previous_ave_char_width = -1.0
                try:
                    g = position._java_geometry or _java_geometry(position)
                except AttributeError:
                    g = _java_geometry(position)
                if sort:
                    position_x = g.x_dir_adj
                    position_y = g.y_dir_adj
                    position_width = g.width_dir_adj
                else:
                    position_x = g.x
                    position_y = g.y
                    position_width = g.width
                position_height = g.height
                widths = position.individual_widths
                if widths is None:
                    widths = position.get_individual_widths()
                word_char_count = len(widths) or 1
                word_spacing = g.width_of_space
                within_low = None
                x_distance = None
                if (
                    fast
                    and last_word_spacing >= 0
                    and previous_ave_char_width >= 0
                    and end_of_last_text_x != -1.0
                    and word_spacing != 0
                    and word_spacing == word_spacing  # not NaN
                ):
                    # ``_word_metrics_reference`` for a glyph inside a line
                    # (so after a first position), with the ``within`` bounds
                    # of ``_java_overlap`` and the ``x`` distance to the last
                    # glyph.
                    if (
                        word_spacing == memo_word_spacing
                        and last_word_spacing == memo_last_word_spacing
                    ):
                        delta_space = memo_delta_space
                        space_limit = memo_space_limit
                    else:
                        scratch[0] = word_spacing + last_word_spacing
                        scratch[0] = scratch[0] / 2
                        scratch[0] = scratch[0] * spacing_tolerance
                        delta_space = scratch[0]
                        scratch[0] = word_spacing + delta_space
                        space_limit = scratch[0]
                        memo_word_spacing = word_spacing
                        memo_last_word_spacing = last_word_spacing
                        memo_delta_space = delta_space
                        memo_space_limit = space_limit
                    if position_y != memo_y:
                        scratch[0] = position_y - variance
                        scratch[1] = position_y + variance
                        memo_within_low = scratch[0]
                        memo_within_high = scratch[1]
                        memo_y = position_y
                    within_low = memo_within_low
                    within_high = memo_within_high
                    scratch[0] = position_width / word_char_count
                    scratch[1] = position_x + position_width
                    scratch[2] = g.x - last_geometry.x
                    new_end_of_text_x = scratch[1]
                    x_distance = scratch[2]
                    scratch[0] = previous_ave_char_width + scratch[0]
                    char_sum = scratch[0]
                    if char_sum >= _F32_MIN_HALVABLE:
                        # Halving a float32 this large is exact.
                        average_char_width = char_sum / 2
                    else:
                        scratch[0] = char_sum / 2
                        average_char_width = scratch[0]
                    scratch[0] = average_char_width * average_char_tolerance
                    delta_char_width = scratch[0]
                    # ``min(delta_space, delta_char_width)``, NaN cases included.
                    scratch[0] = end_of_last_text_x + (
                        delta_char_width if delta_char_width < delta_space else delta_space  # noqa: FURB136
                    )
                    expected_start_of_next_word_x = scratch[0]
                else:
                    (
                        delta_space,
                        average_char_width,
                        new_end_of_text_x,
                        expected_start_of_next_word_x,
                    ) = _word_metrics_reference(
                        word_spacing,
                        last_word_spacing,
                        previous_ave_char_width,
                        position_x,
                        position_width,
                        word_char_count,
                        end_of_last_text_x,
                        spacing_tolerance,
                        average_char_tolerance,
                    )
                if last_text is not None:
                    if start_of_article:
                        if last_wrapper is None:
                            last_wrapper = PositionWrapper(last_text)
                        last_wrapper.set_article_start()
                        start_of_article = False
                    if not (
                        within_low is not None and within_low < max_y_for_line < within_high
                    ) and not _java_overlap(
                        position_y, position_height, max_y_for_line, max_height_for_line
                    ):
                        if bare_write:
                            write_bare_line(line, sink)
                        else:
                            self.write_line(
                                normalize_positions(line) if bare_line else self.normalize(line),
                                sink,
                            )
                        line = []
                        if last_wrapper is None:
                            last_wrapper = PositionWrapper(last_text)
                        current = PositionWrapper(position)
                        last_line_start = self._java_handle_line_separation(
                            current, last_wrapper, last_line_start, max_height_for_line, sink
                        )
                        expected_start_of_next_word_x = -_FLT_MAX
                        max_y_for_line = -_FLT_MAX
                        max_height_for_line = -1.0
                    last_unicode = last_text.text if last_stock else last_text.get_unicode()
                    if (
                        expected_start_of_next_word_x != -_FLT_MAX
                        and expected_start_of_next_word_x < position_x
                        and (
                            not separator
                            or (last_unicode is not None and not last_unicode.endswith(separator))
                        )
                    ):
                        line.append(None if bare_line else word_separator_item)
                    if x_distance is None:
                        x_distance, space_limit = _f32x2(
                            g.x - last_geometry.x,
                            word_spacing + delta_space,
                        )
                    if x_distance > space_limit or -x_distance > space_limit:
                        # (``abs(x_distance) > space_limit``.)
                        max_y_for_line = -_FLT_MAX
                        max_height_for_line = -1.0
                if position_y >= max_y_for_line:
                    max_y_for_line = position_y
                end_of_last_text_x = new_end_of_text_x
                if character_value is not None:
                    if start_of_page and last_text is None and emit_paragraph_markers:
                        self.write_paragraph_start(sink)
                    if bare_line:
                        line.append(position)
                    else:
                        item = new_line_item(line_item)
                        item._text_position = position
                        line.append(item)
                if position_height > max_height_for_line:
                    max_height_for_line = position_height
                last_text = position
                last_stock = stock
                last_wrapper = current
                last_geometry = g
                if start_of_page:
                    if last_wrapper is None:
                        last_wrapper = PositionWrapper(position)
                    last_wrapper.set_paragraph_start()
                    last_wrapper.set_line_start()
                    last_line_start = last_wrapper
                    start_of_page = False
                last_word_spacing = word_spacing
                previous_ave_char_width = average_char_width
            if line:
                if bare_write:
                    write_bare_line(line, sink)
                else:
                    self.write_line(
                        normalize_positions(line) if bare_line else self.normalize(line), sink
                    )
                if emit_paragraph_markers:
                    self.write_paragraph_end(sink)
            if self._article_end:
                self.write_article_end(sink)
                if manages_own_paragraph:
                    self._in_paragraph = False

    @staticmethod
    def _java_font_or_size_changed(current: TextPosition, last: TextPosition) -> bool:
        """Upstream ``hasFontOrSizeChanged``: compares the ``Tf`` size, then
        the font instance, then the font name, then the font hash."""
        current_size = current.tf_font_size
        last_size = last.tf_font_size
        if current_size is None or last_size is None:
            current_size = current.get_font_size()
            last_size = last.get_font_size()
        if current_size != last_size:
            return True
        current_font = current.get_font()
        last_font = last.get_font()
        if current_font is last_font:
            return False
        current_name = current_font.get_name() if current_font is not None else None
        last_name = last_font.get_name() if last_font is not None else None
        if current_name is not None:
            return current_name != last_name
        if last_name is not None:
            return True
        return hash(current_font) != hash(last_font)

    def _java_handle_line_separation(
        self,
        current: PositionWrapper,
        last_position: PositionWrapper,
        last_line_start: PositionWrapper | None,
        max_height_for_line: float,
        sink: Callable[[str], None],
    ) -> PositionWrapper:
        """Upstream ``handleLineSeparation``: classify the break and write
        the line (and paragraph) separators."""
        current.set_line_start()
        self._java_is_paragraph_separation(
            current, last_position, last_line_start, max_height_for_line
        )
        if current.is_paragraph_start():
            if last_position.is_article_start():
                if last_position.is_line_start():
                    self.write_line_separator(sink)
                self.write_paragraph_start(sink)
            else:
                self.write_line_separator(sink)
                self.write_paragraph_separator(sink)
        else:
            self.write_line_separator(sink)
        return current

    @staticmethod
    def _java_multiply_float(value1: float, value2: float) -> float:
        """Upstream ``multiplyFloat``: ``Math.round(v1 * v2 * 1000) / 1000f``."""
        return _f32(_java_round(_f32(_f32(value1 * value2) * 1000)) / 1000)

    def _java_is_paragraph_separation(
        self,
        position: PositionWrapper,
        last_position: PositionWrapper,
        last_line_start: PositionWrapper | None,
        max_height_for_line: float,
    ) -> None:
        """Upstream ``isParagraphSeparation`` on Java geometry."""
        result = False
        if last_line_start is None:
            result = True
        else:
            g = _java_geometry(position.get_text_position())
            last_g = _java_geometry(last_position.get_text_position())
            start_g = _java_geometry(last_line_start.get_text_position())
            y_gap = abs(_f32(g.y_dir_adj - last_g.y_dir_adj))
            new_y_val = self._java_multiply_float(
                _f32(self.get_drop_threshold()), max_height_for_line
            )
            x_gap = _f32(g.x_dir_adj - start_g.x_dir_adj)
            new_x_val = self._java_multiply_float(
                _f32(self.get_indent_threshold()), g.width_of_space
            )
            position_width = self._java_multiply_float(0.25, g.width)
            if y_gap > new_y_val:
                result = True
            elif x_gap > new_x_val:
                # Indented, but screen for a hanging indent.
                if not last_line_start.is_paragraph_start():
                    result = True
                else:
                    position.set_hanging_indent()
            elif x_gap < -g.width_of_space:
                # Left of the previous line: was it a hanging indent?
                if not last_line_start.is_paragraph_start():
                    result = True
            elif abs(x_gap) < position_width:
                # Within a quarter character of the last line start.
                if last_line_start.is_hanging_indent():
                    position.set_hanging_indent()
                elif last_line_start.is_paragraph_start():
                    li_pattern = self.match_list_item_pattern(last_line_start)
                    if li_pattern is not None:
                        current_pattern = self.match_list_item_pattern(position)
                        if li_pattern is current_pattern:
                            result = True
        if result:
            position.set_paragraph_start()

    @staticmethod
    def _coalesce_runs(positions: list[TextPosition]) -> list[TextPosition]:
        """Merge consecutive glyphs painted by the same show-text string back
        into one run position (first glyph's origin, summed width)."""
        runs: list[TextPosition] = []
        last_run_id = None
        for pos in positions:
            run_id = getattr(pos, "_run_id", None)
            if run_id is not None and run_id == last_run_id and runs:
                head = runs[-1]
                head.text += pos.text
                head.width += pos.width
                if head.individual_widths is not None and pos.individual_widths is not None:
                    head.individual_widths = head.individual_widths + pos.individual_widths
                continue
            if run_id is not None:
                pos = replace(pos)
                pos._run_id = run_id
            runs.append(pos)
            last_run_id = run_id
        return runs

    def _format_positions_flipped(self, positions: list[TextPosition]) -> str:
        """Walk ``positions`` in emission order and stitch them into a
        single string using the configured line and word separators.

        Heuristic (single-column reading order):
          - If ``y`` differs from the previous position's ``y`` by more
            than half the font size, emit a line separator.
          - Otherwise, if ``x`` jumps by more than ``_WORD_GAP_FACTOR``
            times the font size from the previous position's right edge,
            emit a word separator.

        When ``sort_by_position`` is enabled the positions are first
        re-ordered top-to-bottom, left-to-right (descending ``y`` since
        PDF user space puts the origin at the lower-left) so emission
        respects geometric reading order rather than content-stream
        order. This mirrors upstream's ``setSortByPosition(true)``.

        When ``suppress_duplicate_overlapping_text`` is enabled (the
        upstream default), a position whose text was already painted on
        the page at (nearly) the same origin — within a half-open window
        of ``width / len(text) / 3`` on both axes, upstream
        ``processTextPosition``'s tolerance — is considered the same
        glyph painted twice (a common trick for fake bold) and the
        duplicate is dropped before formatting (see
        :meth:`_drop_overlapping_duplicates`).

        When ``should_separate_by_beads`` is enabled and the active page
        carries thread beads, positions are bucketed into upstream's
        per-article ``charactersByArticle`` slots (``2*N + 1`` for ``N``
        beads; see :meth:`_partition_by_beads`) and the slots are emitted in
        index order, matching upstream's ``setShouldSeparateByBeads(true)``
        semantics. The running line state carries across the slot boundaries
        the way ``writePage`` declares it outside the article loop.
        """
        if not positions:
            return self._empty_article_wrap()
        # This lite-only mode lays out whole show-text runs: regroup the
        # per-glyph positions (``should_skip_glyph`` already ran).
        positions = self._coalesce_runs(positions)
        if self._suppress_duplicate_overlapping_text:
            positions = self._drop_overlapping_duplicates(positions)
        # Upstream applies the comparator only when ``sortByPosition`` is
        # set — even when bead-separation is on, the in-bead ordering
        # follows content-stream order unless explicit sort is requested.
        # Lite mode follows the same gating.
        if self._sort_by_position:
            # Upstream's ``TextPositionComparator`` keys on ``getDir()``
            # first, so glyphs are grouped by text direction (0/90/180/270)
            # before any positional ordering — a page that mixes runs
            # rotated by different right angles emits each direction's runs
            # contiguously, in ascending-direction order, rather than
            # interleaving them by raw device coordinate. Within a single
            # direction the positional sort below reproduces the per-group
            # reading order.
            if self._flip_axes:
                # Rotated frame: sort by ascending x (top-to-bottom in
                # the rotated reading order) then ascending y (left-to-
                # right within a column). Mirrors upstream's flipped
                # comparator.
                positions = sorted(positions, key=lambda p: (p.dir % 360.0, p.x, p.y))
            else:
                positions = sorted(
                    positions, key=cmp_to_key(self._compare_reading_order)
                )

        # Bead-separation: bucket positions into upstream's per-article
        # ``charactersByArticle`` slots (``2*N + 1`` for ``N`` beads), then
        # emit one slot at a time in index order — the gap slots interleave
        # between the bead columns, reproducing the reading flow. Text outside
        # every bead lands in the first gap slot it is left-of / above (see
        # :meth:`_partition_by_beads`), not a single trailing residual.
        groups: list[list[TextPosition]] = []
        if self._should_separate_by_beads and self._active_page is not None:
            groups = self._partition_by_beads(positions)
        if not groups:
            groups = [positions]
        # Mirror upstream ``processPage``: ``charactersByArticle`` *is* the
        # per-article (bead-bucket) structure that ``writePage`` iterates, not
        # the flat pre-partition position list. ``process_page`` seeds it with
        # a provisional single group before calling here; overwrite it with the
        # post-filter, post-sort, partitioned buckets so
        # ``get_characters_by_article`` and the upstream-signature
        # ``write_page`` both see the same article slots upstream exposes. (When
        # bead separation is off or the page has no usable beads this is a
        # single all-positions group, matching the prior behaviour.)
        self._characters_by_article = groups

        chunks: list[str] = []

        def _sink(piece: str) -> None:
            chunks.append(piece)

        # Upstream wraps EACH article (bead bucket) in ``startArticle()`` /
        # ``endArticle()`` — i.e. ``article_start`` before and ``article_end``
        # after every group — with NO implicit line separator between
        # consecutive articles. Both markers default to "" (they only become a
        # line separator when ``add_more_formatting`` is enabled), so by
        # default adjacent bead buckets are concatenated directly. Emitting a
        # hardcoded line separator here would diverge from PDFBox, which only
        # inserts a break between articles when the producer asked for one via
        # the article separators.
        # Upstream ``writePage`` emits the page-body ``writeParagraphStart``
        # exactly once, on the first character of the first non-empty article
        # (the ``startOfPage`` flag, set false after the first glyph), and a
        # ``writeParagraphEnd`` after the last line of *each* article
        # (PDFTextStripper.java:700-724). ``_emit_group`` reproduces both: it
        # opens the page paragraph on its first written run when
        # ``open_page_paragraph`` is set, clearing the page-level flag so a
        # later article does not re-open it, and always closes the paragraph
        # after its final line. With the default empty paragraph markers these
        # emissions are invisible; under ``add_more_formatting`` (both promoted
        # to the line separator) they supply the trailing per-article and
        # leading per-page newlines the Java oracle emits.
        #
        # A subclass that overrides ``write_article_start`` (e.g.
        # ``PDFText2HTML``, which brackets each article's body with its own
        # ``<p>`` / ``</p>`` inside the article hooks) takes over paragraph
        # bracketing; for those the base ``_emit_group`` wrapping is
        # suppressed so the markers are not emitted twice. The plain base
        # stripper keeps the wrapping so its ``add_more_formatting`` cadence
        # matches the Java oracle.
        manages_own_paragraph = (
            type(self).write_article_start is not PDFTextStripper.write_article_start
        )
        open_page_paragraph = not manages_own_paragraph
        # Upstream's ``writePage`` declares the running line-extent /
        # previous-glyph state (``lastPosition``, ``maxYForLine``,
        # ``maxHeightForLine``, ``lastLineStartPosition``) *outside* the
        # ``for (List<TextPosition> textList : charactersByArticle)`` loop
        # (PDFTextStripper.java:497-503), so that state persists across
        # article boundaries: the first glyph of a new article is line-broken
        # against the *last* glyph of the previous article whenever their
        # vertical spans do not overlap. Only ``startOfArticle`` resets per
        # article. The lite emitter mirrors that by threading a shared carry
        # dict through each ``_emit_group`` call rather than re-seeding the
        # line state for every bead bucket. Without it, a glyph that fell
        # into a trailing residual slot (e.g. a final line below the last
        # bead) would be concatenated onto the previous article's last line
        # instead of starting its own.
        carry: dict[str, object] | None = {} if len(groups) > 1 else None
        for group in groups:
            if self._article_start:
                self.write_article_start(_sink)
            wrote = self._emit_group(
                group,
                _sink,
                open_page_paragraph,
                emit_paragraph_markers=not manages_own_paragraph,
                carry=carry,
            )
            if wrote:
                open_page_paragraph = False
            if self._article_end:
                self.write_article_end(_sink)
        return "".join(chunks)

    def _emit_group(
        self,
        positions: list[TextPosition],
        sink: Callable[[str], None],
        open_page_paragraph: bool = False,
        emit_paragraph_markers: bool = True,
        carry: dict[str, object] | None = None,
    ) -> bool:
        """Emit a single ordered list of positions. Splits out from
        ``_format_positions`` so the bead-bucket loop can reuse the same
        line/word/paragraph heuristics for each bucket independently.

        When ``emit_paragraph_markers`` is ``True`` the group reproduces
        upstream ``writePage``'s page-body paragraph bracketing: a
        ``write_paragraph_start`` before its first written run when
        ``open_page_paragraph`` is set (fired once per page, on the first
        glyph of the first non-empty article), and a ``write_paragraph_end``
        after its final line when it wrote at least one run (upstream's
        per-article ``writeParagraphEnd``, PDFTextStripper.java:700-724). A
        subclass that brackets paragraphs itself (e.g. ``PDFText2HTML`` via
        its overridden article hooks) passes ``False`` so the markers are not
        emitted twice. The mid-page paragraph-separation break is emitted in
        either case. Returns ``True`` when the group wrote at least one run,
        so the caller can clear its page-level paragraph-open flag.

        Wave 1387 buffers each adjacent run of TextPositions (those
        not separated by a line break or word break) into a
        ``word_buffer`` and runs :meth:`handle_direction` (UAX #9 BiDi)
        once per word — matching upstream Apache PDFBox's per-word
        ``handleDirection`` contract in ``LegacyPDFStreamEngine.normalize``.
        The buffer is flushed on every word separator, line separator,
        and paragraph break.
        """
        # Per-word bidi buffer — concatenate adjacent TextPosition
        # fragments belonging to the same word, then run them through
        # handle_direction at the next break (word / line / paragraph).
        word_buffer: list[str] = []

        def _buffered_sink(piece: str) -> None:
            word_buffer.append(piece)

        def _flush_word() -> None:
            if not word_buffer:
                return
            text = "".join(word_buffer)
            word_buffer.clear()
            # ``normalize_word`` decomposes Unicode presentation forms
            # (Alphabetic Presentation Forms FB00–FDFF, e.g. the ``ﬁ``/``ﬂ``
            # ligatures → ``fi``/``fl``, and Arabic Presentation Forms-B)
            # via NFKC and then applies the per-word ``handle_direction``
            # bidi reorder — mirroring upstream's ``normalizeWord`` →
            # ``handleDirection`` chain in ``LegacyPDFStreamEngine.normalize``.
            # It already wraps ``handle_direction`` in both branches, so
            # this also covers the pure-LTR bidi fast path.
            sink(self.normalize_word(text))

        # Running line-extent accumulators mirroring upstream
        # ``writePage`` (PDFTextStripper.java:497-501). A position joins
        # the current line when its vertical glyph span overlaps the
        # *line's* accumulated span (``max_y_for_line`` / its height) —
        # not merely the immediately-previous glyph. This is what keeps a
        # wrapped row label's continuation (e.g. ``(as HCl)``) and its
        # value cells (``10 000 - -``, painted a few points higher on a
        # slightly different baseline) on one logical line in a
        # multi-column table, where the flat prev-only 0.5·fontSize test
        # split them. The accumulators reset on a line break and on a
        # horizontal jump larger than one space (a new column whose font
        # size may differ), matching upstream lines 681-687.
        #
        # Per-axis line-extent accumulator. Upstream tracks
        # ``maxYForLine = MAX(positionY)`` in its y-down *device* frame
        # (PDFTextStripper.java:689-692), i.e. the lowest (bottom-most)
        # baseline seen on the line, reset to ``-Float.MAX_VALUE``. Which
        # coordinate frame the lite stripper's stored ``pos.y`` lives in
        # depends on the path:
        #
        #   * upright, unrotated page (``not _flip_axes and
        #     _page_rotation == 0``): ``pos.y`` is the raw PDF user-space
        #     (y-up) baseline — a larger Y is *higher* on the page. The
        #     y-up mirror of "max device-Y" is therefore "**min user-Y**":
        #     the accumulator must track the lowest baseline as ``MIN`` and
        #     reset to ``+inf`` (update ``if position_y <= acc``). Keeping
        #     the literal ``MAX`` / ``-inf`` here is the long-standing sign
        #     mismatch that split a single visual line mixing very different
        #     glyph heights (a large-font run between two normal-font
        #     anchors) where Java merges them. ``_overlaps_line`` is already
        #     the correct y-up transform of upstream ``overlap`` *given* a
        #     MIN-user-Y accumulator (its two span clauses carry the matching
        #     heights — verified by substituting ``device_y = -user_y`` into
        #     upstream's ``overlap``), so only the accumulation direction was
        #     wrong.
        #
        #   * rotated page (``_page_rotation in (90, 180, 270)``):
        #     ``_apply_page_rotation`` has already rewritten ``pos.y`` into
        #     upstream's ``getY()`` device frame (see that method's lines
        #     866-878: the stored Y runs in the SAME direction as upstream's
        #     ``getY()`` precisely so this accumulation matches). There the
        #     literal ``MAX`` / ``-inf`` is upstream's verbatim behaviour and
        #     the 90/270 fragmentation pattern depends on it — flipping the
        #     sense would regress
        #     ``test_right_angle_rotation_byte_exact``.
        #
        #   * flip-axes (``set_should_flip_axes``): a lite-only manual X/Y
        #     transpose with no upstream counterpart; ``_overlaps_line`` is
        #     not consulted on that path (it uses ``_is_line_break``), so the
        #     accumulator is dead for line-breaking there — kept on the
        #     legacy ``MAX`` / ``-inf`` sense for stability (documented
        #     carve-out, see ``set_should_flip_axes`` DEFERRED entry).
        #
        # ``min_y_line_axis`` selects the upright-unrotated MIN-user-Y path.
        min_y_line_axis = not self._flip_axes and self._page_rotation == 0
        max_y_reset = math.inf if min_y_line_axis else -math.inf
        max_height_reset = -1.0
        # When a ``carry`` dict is supplied the running line state persists
        # across article (bead-bucket) boundaries — mirroring upstream's
        # ``writePage``, which declares this state outside the per-article
        # loop (PDFTextStripper.java:497-503). The first bucket seeds an
        # empty carry; later buckets resume from the previous bucket's final
        # glyph so an inter-article line break fires when their vertical
        # spans do not overlap. ``open_page_paragraph`` already guards the
        # once-per-page paragraph open, so resuming ``prev`` does not re-open
        # the page paragraph.
        max_y_for_line = max_y_reset
        max_height_for_line = max_height_reset

        wrote_any = False
        prev: TextPosition | None = None
        # Upstream tracks the wrapper of the first glyph of the previous
        # line (``lastLineStartPosition``) and the wrapper of the
        # immediately-previous glyph (``lastPosition``) so
        # ``isParagraphSeparation`` can compare the current X to the
        # *previous line's* left margin rather than to the prior glyph
        # (PDFTextStripper.java:503, 660, 709-713). The lite stripper
        # mirrors that here. The flip-axes path keeps the legacy prev-only
        # indent heuristic — its transposed frame is not calibrated for the
        # wrapper-based indent test, and (verified wave 1493) the
        # wrapper-based ``_classify_paragraph_separation`` cannot be reused
        # there: ``set_should_flip_axes`` is a lite-only *manual* X/Y
        # transpose with NO upstream counterpart (a full scan of
        # pdfbox-app-3.0.7.jar finds no ``flipAxes`` symbol) and it carries
        # no rotation in the coordinate matrix, so ``dir`` stays 0 and the
        # dir-adjusted fields (``get_x_dir_adj`` / ``get_y_dir_adj``) the
        # classifier reads are pure identity — there is nothing for them to
        # normalise. (Page ``/Rotate`` parity is a separate surface handled
        # by the page-rotation CTM fold in ``LegacyPDFStreamEngine``; see
        # ``tests/text/oracle/test_rotated_page_extraction_oracle.py`` and
        # a deferred follow-up.)
        last_line_start: PositionWrapper | None = None
        last_wrapper: PositionWrapper | None = None
        if carry is not None and carry:
            max_y_for_line = carry.get("max_y_for_line", max_y_reset)  # type: ignore[assignment]
            max_height_for_line = carry.get(  # type: ignore[assignment]
                "max_height_for_line", max_height_reset
            )
            prev = carry.get("prev")  # type: ignore[assignment]
            last_line_start = carry.get("last_line_start")  # type: ignore[assignment]
            last_wrapper = carry.get("last_wrapper")  # type: ignore[assignment]
        # Upstream resets ``startOfArticle = true`` at the head of every
        # article iteration (PDFTextStripper.java:534); the first glyph of an
        # article with a non-null ``lastPosition`` then flags that previous
        # glyph as the article start (line 641-645). The lite emitter only
        # carries ``last_wrapper`` across buckets, so this flag governs the
        # one inter-article transition handled inside this call.
        start_of_article = True
        for pos in positions:
            position_y = pos.x if self._flip_axes else pos.y
            position_height = pos.get_height_dir()
            cur_wrapper = PositionWrapper(pos)
            if (
                start_of_article
                and last_wrapper is not None
                and not self._flip_axes
            ):
                # ``lastPosition.setArticleStart()`` — the previous bucket's
                # final glyph becomes the article-start anchor consulted by
                # the article-start branch of ``handleLineSeparation``.
                last_wrapper.set_article_start()
            start_of_article = False
            if prev is None and open_page_paragraph and emit_paragraph_markers:
                # Upstream opens the page-body paragraph on the first glyph
                # (``startOfPage && lastPosition == null`` →
                # ``writeParagraphStart``, PDFTextStripper.java:700-703).
                self.write_paragraph_start(sink)
            if prev is None and not self._flip_axes:
                # Upstream marks the first glyph of the page as both a
                # paragraph start and a line start, seeding
                # ``lastLineStartPosition`` (PDFTextStripper.java:709-713).
                cur_wrapper.set_paragraph_start()
                cur_wrapper.set_line_start()
                last_line_start = cur_wrapper
            if prev is not None:
                # Flip-axes extraction keeps the legacy prev-only
                # line-stepping heuristic — the running-overlap model is
                # calibrated for the upright frame where Y is the line-flow
                # axis and ``get_height_dir`` is the glyph's vertical extent;
                # under the lite-only ``set_should_flip_axes`` transpose the
                # stepping axis is X and the relevant extent would be the
                # glyph width, which the overlap model does not track. The
                # overlap model is NOT reusable here via the dir-adjusted
                # fields: flip-axes carries no rotation in the matrix
                # (``dir == 0``), so those fields are identity (verified
                # wave 1493). Page ``/Rotate`` is a separate surface (the
                # missing page-rotation CTM fold — a deferred follow-up).
                if self._flip_axes:
                    line_broke = self._is_line_break(pos, prev)
                else:
                    line_broke = not self._overlaps_line(
                        position_y,
                        position_height,
                        max_y_for_line,
                        max_height_for_line,
                    )
                if line_broke:
                    _flush_word()
                    # Mark the new line's first glyph and run upstream's
                    # paragraph-separation classifier against the *previous*
                    # line's start glyph (``handleLineSeparation``,
                    # PDFTextStripper.java:1559-1587). The flip-axes path
                    # keeps the legacy prev-only indent test.
                    cur_wrapper.set_line_start()
                    if self._flip_axes:
                        para_break = self.is_paragraph_separation(pos, prev)
                    else:
                        self._classify_paragraph_separation(
                            cur_wrapper,
                            last_wrapper,  # type: ignore[arg-type]
                            last_line_start,
                            max_height_for_line
                            if max_height_for_line > 0.0
                            else position_height,
                        )
                        para_break = cur_wrapper.is_paragraph_start()
                    # Faithful port of upstream ``handleLineSeparation``'s
                    # emission tree (PDFTextStripper.java:1566-1585). When the
                    # previous glyph was flagged an article start (the first
                    # glyph of a new bead bucket whose ``lastPosition`` is the
                    # prior bucket's tail), a *paragraph* break across that
                    # boundary collapses to just ``writeParagraphStart`` (plus
                    # a line separator only if that tail was itself a line
                    # start) — i.e. NO inter-article line break is emitted for
                    # a large vertical jump between columns. Only a non-article
                    # paragraph break expands to ``writeLineSeparator +
                    # writeParagraphSeparator`` (= end+start). A plain
                    # (non-paragraph) line break between two articles, by
                    # contrast, still emits a single line separator — which is
                    # what splits a column's trailing line from a residual
                    # final line one row below it (the ``mon Dieu`` case).
                    last_is_article_start = (
                        last_wrapper is not None and last_wrapper.is_article_start()
                    )
                    if para_break and last_is_article_start:
                        # Upstream's inner ``if (lastPosition.isLineStart())
                        # writeLineSeparator()`` (PDFTextStripper.java:1570-
                        # 1573) keys on the *last glyph* of the previous
                        # article. The lite stripper emits one TextPosition per
                        # show-text run rather than per glyph (the documented
                        # run-vs-glyph carve-out), so its ``last_wrapper`` is
                        # the whole final run; a multi-glyph final line's last
                        # glyph is never a line start in Java, so the run-level
                        # ``is_line_start`` would over-fire here. Mirror Java's
                        # effective behaviour for multi-glyph runs by emitting
                        # only the paragraph start.
                        self.write_paragraph_start(sink)
                    elif para_break:
                        # Upstream ``handleLineSeparation`` emits the line
                        # separator *first*, then the paragraph separator
                        # (``writeParagraphEnd`` + ``writeParagraphStart``)
                        # for a mid-page paragraph break — i.e.
                        # ``writeLineSeparator → writeParagraphEnd →
                        # writeParagraphStart`` (PDFTextStripper.java:1578-
                        # 1579, where ``writeParagraphSeparator`` expands to
                        # end+start). In PDFText2HTML this surfaces as
                        # ``\n</p>\n<p>`` rather than the previously-emitted
                        # ``</p>\n\n<p>``.
                        self.write_line_separator(sink)
                        self.write_paragraph_end(sink)
                        self.write_paragraph_start(sink)
                    else:
                        self.write_line_separator(sink)
                    # The new line's first glyph becomes the next
                    # ``lastLineStartPosition`` (PDFTextStripper.java:1565).
                    last_line_start = cur_wrapper
                    max_y_for_line = max_y_reset
                    max_height_for_line = max_height_reset
                else:
                    if self._is_word_break(pos, prev):
                        _flush_word()
                        self.write_word_separator(sink)
                    # A horizontal jump of more than one space may mark a
                    # new column whose font (and thus glyph height) differs
                    # — reset the line extents so the next glyph re-anchors
                    # them (upstream PDFTextStripper.java:681-687).
                    if not self._flip_axes and self._is_column_jump(pos, prev):
                        max_y_for_line = max_y_reset
                        max_height_for_line = max_height_reset
            # Accumulate the line's vertical extent (upstream lines
            # 689-707): track the bottom-most baseline and the tallest glyph.
            # In the upright unrotated y-up frame the bottom-most baseline is
            # the *minimum* user-Y (mirror of upstream's max device-Y); the
            # rotated / flip-axes paths keep upstream's literal max sense (see
            # the ``min_y_line_axis`` note above).
            if min_y_line_axis:
                if position_y <= max_y_for_line:
                    max_y_for_line = position_y
            elif position_y >= max_y_for_line:
                max_y_for_line = position_y
            max_height_for_line = max(max_height_for_line, position_height)
            self.write_string_with_positions(pos.text, [pos], _buffered_sink)
            wrote_any = True
            prev = pos
            last_wrapper = cur_wrapper
        _flush_word()
        if wrote_any and emit_paragraph_markers:
            # Upstream closes the article's paragraph after its final line
            # (``writeLine(...); writeParagraphEnd()``,
            # PDFTextStripper.java:720-724).
            self.write_paragraph_end(sink)
        if carry is not None:
            # Persist the running line state for the next bead bucket so the
            # inter-article line-break test resumes from this bucket's final
            # glyph (upstream's loop-scoped ``lastPosition`` / ``maxYForLine``).
            carry["max_y_for_line"] = max_y_for_line
            carry["max_height_for_line"] = max_height_for_line
            carry["prev"] = prev
            carry["last_line_start"] = last_line_start
            carry["last_wrapper"] = last_wrapper
        return wrote_any

    # Tolerance (user-space units) below which two runs are treated as
    # sharing a baseline. Mirrors upstream ``TextPositionComparator``'s
    # ``yDifference < .1`` literal.
    _SORT_Y_TOLERANCE: float = 0.1

    def _compare_reading_order(
        self, pos1: TextPosition, pos2: TextPosition
    ) -> int:
        """Reading-order comparison for the non-flipped (``dir==0``) sort.

        Mirrors upstream ``org.apache.pdfbox.text.TextPositionComparator``:
        glyphs are grouped by direction first, then two runs that share a
        baseline (Y difference under tolerance) *or whose vertical glyph
        extents overlap* are ordered left-to-right by X rather than by their
        raw Y. Only runs that are vertically disjoint fall through to a
        Y comparison.

        The lite stripper carries Y in the PDF user-space frame (y-up: a
        larger Y is higher on the page), so the directions of the tolerance
        and Y comparisons are the user-space mirror of upstream's
        upper-left (y-down) frame: "top first" means *larger* Y first.

        Replacing the previous naive ``(-y, x)`` key (wave 1471) fixes the
        case where two runs on a visually shared line differ in Y by a
        sub-line-height jitter: the naive key reordered them by raw Y
        (putting the higher glyph first regardless of X) and then the
        word-break test, keyed on X gaps, misfired — diverging from Java,
        which keeps such runs in left-to-right reading order.
        """
        d1 = pos1.dir % 360.0
        d2 = pos2.dir % 360.0
        if d1 < d2:
            return -1
        if d1 > d2:
            return 1

        x1 = pos1.x
        x2 = pos2.x
        # Baselines in the user-space (y-up) frame.
        y1 = pos1.y
        y2 = pos2.y
        # Top edge of each run (one line height above its baseline).
        y1_top = y1 + pos1.get_height_dir()
        y2_top = y2 + pos2.get_height_dir()

        y_difference = abs(y1 - y2)
        if (
            y_difference < self._SORT_Y_TOLERANCE
            or (y1 <= y2 <= y1_top)
            or (y2 <= y1 <= y2_top)
        ):
            if x1 < x2:
                return -1
            if x1 > x2:
                return 1
            return 0

        # Vertically disjoint — top-to-bottom: larger Y (higher) first.
        if y1 > y2:
            return -1
        return 1

    def _is_line_break(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """True when ``pos`` belongs to a new line relative to ``prev``."""
        if self._flip_axes:
            # Rotated frame: line stepping happens along X.
            return abs(pos.x - prev.x) > max(prev.font_size, 0.1) * 0.5
        # The sole caller (_format_positions, ~line 2759) only invokes
        # _is_line_break inside its ``if self._flip_axes:`` branch — the
        # upright path uses the running-overlap model (_overlaps_line)
        # instead — so this non-flip fallback is structurally unreachable.
        # Kept for API symmetry with the flip-axes carve-out it serves.
        return abs(pos.y - prev.y) > max(prev.font_size, 0.1) * 0.5  # pragma: no cover

    @staticmethod
    def _overlaps_line(
        position_y: float,
        position_height: float,
        max_y_for_line: float,
        max_height_for_line: float,
    ) -> bool:
        """True when a glyph's vertical span overlaps the running line span.

        y-up mirror of upstream's private ``overlap``
        (PDFTextStripper.java:762-766), which in the device (y-down) frame
        reads::

            within(y1, y2, .1f)
            || y2 <= y1 && y2 >= y1 - height1
            || y1 <= y2 && y1 >= y2 - height2

        Here ``y1`` is the glyph baseline (``position_y``) and ``y2`` is the
        line's accumulated baseline (``max_y_for_line``). On the upright
        unrotated path the lite TextPosition carries Y in PDF user space
        (y-up: a larger Y is higher on the page) and ``max_y_for_line`` is
        the line's MIN user-Y (the bottom-most baseline — the y-up mirror of
        upstream's max device-Y; see ``_emit_group``). Substituting
        ``device_y = -user_y`` into upstream's ``overlap`` yields exactly the
        two clauses below: the glyph-span clause carries the *line's* height
        (``y2 <= y1 <= y2 + height2``) and the line-span clause carries the
        *glyph's* height (``y1 <= y2 <= y1 + height1``). A run's top edge is
        ``baseline + height`` (y-up) rather than ``baseline - height``. The
        ``within`` (shared-baseline) clause is sign-agnostic. When the line
        extents are still at their reset sentinels (no glyph yet), the height
        clauses correctly report no overlap so the first glyph always opens
        the line.
        """
        if PDFTextStripper.within(position_y, max_y_for_line, 0.1):
            return True
        # Glyph baseline sits within the line's [baseline, top] span.
        if max_y_for_line <= position_y <= max_y_for_line + max_height_for_line:
            return True
        # Line baseline sits within the glyph's [baseline, top] span.
        return position_y <= max_y_for_line <= position_y + position_height

    def _is_column_jump(self, pos: TextPosition, prev: TextPosition) -> bool:
        """True when ``pos`` starts more than one space past ``prev``'s
        origin along the flow axis.

        Mirrors upstream PDFTextStripper.java:681-682
        (``abs(position.getX() - lastPosition.getX()) > wordSpacing +
        deltaSpace``) — the trigger that resets the running line extents so
        a new column whose font size differs re-anchors the overlap test.
        Uses the previous run's space width and the configured spacing
        tolerance (``deltaSpace = wordSpacing × spacingTolerance``), falling
        back to the coarse ``font_size`` estimate for a metric-less run.
        """
        prev_origin = prev.y if self._flip_axes else prev.x
        cur_origin = pos.y if self._flip_axes else pos.x
        word_spacing = prev.width_of_space
        if word_spacing <= 0.0:
            word_spacing = prev.font_size * 0.5
        delta_space = word_spacing * self._spacing_tolerance
        return abs(cur_origin - prev_origin) > word_spacing + delta_space

    def _is_word_break(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """True when ``pos`` is far enough past ``prev``'s right edge to
        warrant a word separator.

        Mirrors upstream ``PDFTextStripper.writeString``'s word-segmentation
        gate (PDF 32000-1 text-layout reconstruction): a separator is
        inserted when the horizontal gap between the previous run's right
        edge and this run's origin exceeds the *space-glyph-width-relative*
        threshold

            ``min(widthOfSpace × spacingTolerance,
                  averageCharWidth × averageCharTolerance)``

        with the default ``spacingTolerance = 0.5`` and
        ``averageCharTolerance = 0.3``. This replaces the legacy coarse
        ``font_size × 1.5`` heuristic, which fired ~36pt later than Java for a
        24pt font and missed mid-size positioning gaps (a deferred
        follow-up on word-break gap-threshold calibration). The space width
        and average char width are now real per-glyph metrics threaded
        through ``_emit``
        from the font's ``/Widths`` (wave 1408 per-code lookups), so the
        threshold tracks the active font's metrics the way upstream does.

        When the font supplies no usable space width (``width_of_space`` is
        zero — a malformed font with no metrics), upstream sets
        ``deltaSpace = Float.MAX_VALUE`` so only the average-char-width prong
        governs; we fall back to the same average-char prong, and finally to
        the legacy ``font_size`` estimate when neither metric is available.
        """
        # Upstream gates the gap-driven separator on a single, purely
        # previous-glyph test (PDFTextStripper.java:670-674):
        #
        #     (wordSeparator.isEmpty() ||
        #         (lastPosition.getUnicode() != null &&
        #          !lastPosition.getUnicode().endsWith(wordSeparator)))
        #
        # i.e. emit the separator unless the *previous* glyph's unicode
        # already ends with the configured word-separator string. There is
        # NO suppression keyed on the *current* glyph: when a producer
        # widens the gap *into* an explicit space glyph (a large ``Tc`` over
        # ``(AB CD)``), Java emits a gap separator *before* the space glyph
        # AND keeps the space glyph itself — yielding the double space in
        # ``A B  C D`` — and only suppresses the redundant separator on the
        # transition *out of* that space glyph (where the previous glyph's
        # unicode is the separator). Mirror that exactly: never inspect
        # ``pos`` here, and key the suppression on whether ``prev`` ends with
        # the word-separator string (not arbitrary whitespace).
        separator = self._word_separator
        if (
            separator
            and prev.text is not None
            and prev.text.endswith(separator)
        ):
            return False
        if prev.width > 0.0:
            prev_right = prev.x + prev.width if not self._flip_axes else prev.y + prev.width
        else:
            stretch = len(prev.text) * prev.font_size * 0.5
            prev_right = (prev.x + stretch) if not self._flip_axes else (prev.y + stretch)
        gap = (pos.x - prev_right) if not self._flip_axes else (pos.y - prev_right)
        # The space-width-relative threshold is only trustworthy when the
        # previous run carries *real* font metrics (a resolved ``PDFont`` whose
        # ``/Widths`` fed the run width and space width — wave 1408/1488). For a
        # malformed / font-less run both metrics are the coarse 0.5-em estimate,
        # so the fine threshold would over-segment; fall back to the legacy
        # ``font_size × 1.5`` estimate there (preserving pre-1488 behaviour for
        # streams whose font could not be resolved).
        if prev.font is None or prev.width_of_space <= 0.0 or prev.width <= 0.0:
            return gap > prev.font_size * self._WORD_GAP_FACTOR
        # Space-width-relative threshold (upstream ``deltaSpace`` prong).
        word_spacing = prev.width_of_space
        delta_space = word_spacing * self._spacing_tolerance
        # Average-char-width prong (upstream ``averageCharWidth``). Derived
        # from the previous run's true advance / glyph count.
        n_prev = len(prev.text)
        if n_prev > 0:
            average_char_width = prev.width / n_prev
            delta_char = average_char_width * self._average_char_tolerance
        else:
            delta_char = math.inf
        threshold = min(delta_space, delta_char)
        if not math.isfinite(threshold):
            threshold = prev.font_size * self._WORD_GAP_FACTOR
        return gap > threshold

    def is_paragraph_separation(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """Heuristic: ``pos`` starts a new paragraph relative to ``prev``.

        Upstream PDFBox's ``isParagraphSeparation`` fires on either:
          - a vertical drop larger than ``drop_threshold`` × line height
            (a blank line — a "paragraph drop"), or
          - a noticeable indent — ``pos.x`` jumps right by more than
            ``indent_threshold`` × space width vs the previous line's
            start (an "indented first line").

        Lite mode applies the same two-prong test. ``drop_threshold`` and
        ``indent_threshold`` honour the configured values.
        """
        # Drop test (vertical gap exceeds drop_threshold × line height).
        line_height = max(prev.font_size, 0.1)
        drop = abs(pos.x - prev.x) if self._flip_axes else abs(pos.y - prev.y)
        if drop > line_height * self._drop_threshold:
            return True
        # Indent test — only meaningful when a line-break has been
        # detected; callers gate on ``_is_line_break`` first.
        space_width = prev.width_of_space if prev.width_of_space > 0 else (
            prev.font_size * 0.25
        )
        indent = pos.y - prev.y if self._flip_axes else pos.x - prev.x
        return indent > space_width * self._indent_threshold

    def _classify_paragraph_separation(
        self,
        position: PositionWrapper,
        last_position: PositionWrapper,
        last_line_start: PositionWrapper | None,
        max_height_for_line: float,
    ) -> None:
        """Faithful port of upstream ``isParagraphSeparation``
        (PDFTextStripper.java:1611-1683).

        Unlike the public 2-arg :meth:`is_paragraph_separation` (which
        compares the current glyph to the *immediately-previous* glyph and
        is kept for the existing unit API), this mirrors upstream exactly:
        the y-gap drop prong compares ``position`` to ``last_position``,
        but the indent / hanging-indent / list-item prongs compare
        ``position``'s X to ``last_line_start`` — the first glyph of the
        *previous line*. It toggles ``set_paragraph_start`` /
        ``set_hanging_indent`` on ``position`` rather than returning a bool,
        matching upstream's flag-mutating contract.
        """
        result = False
        if last_line_start is None:
            result = True
        else:
            pos_tp = position.get_text_position()
            last_tp = last_position.get_text_position()
            lls_tp = last_line_start.get_text_position()
            # y-gap drop prong vs the immediately-previous glyph
            # (PDFTextStripper.java:1621-1623).
            y_gap = abs(pos_tp.get_y_dir_adj() - last_tp.get_y_dir_adj())
            new_y_val = self.multiply_float(
                self.get_drop_threshold(), max_height_for_line
            )
            # indent prong vs the previous line's start glyph
            # (PDFTextStripper.java:1625-1629).
            x_gap = pos_tp.get_x_dir_adj() - lls_tp.get_x_dir_adj()
            new_x_val = self.multiply_float(
                self.get_indent_threshold(), pos_tp.get_width_of_space()
            )
            position_width = self.multiply_float(0.25, pos_tp.get_width())

            if y_gap > new_y_val:
                result = True
            elif x_gap > new_x_val:
                # text is indented, but try to screen for hanging indent
                if not last_line_start.is_paragraph_start():
                    result = True
                else:
                    position.set_hanging_indent()
            elif x_gap < -pos_tp.get_width_of_space():
                # text is left of previous line. Was it a hanging indent?
                if not last_line_start.is_paragraph_start():
                    result = True
            elif abs(x_gap) < position_width:
                # within 1/4 char of the last line start — lined up.
                if last_line_start.is_hanging_indent():
                    position.set_hanging_indent()
                elif last_line_start.is_paragraph_start():
                    # previous line looks like a list item?
                    li_pattern = self.match_list_item_pattern(last_line_start)
                    if li_pattern is not None:
                        current_pattern = self.match_list_item_pattern(position)
                        if li_pattern is current_pattern:
                            result = True
        if result:
            position.set_paragraph_start()

    def is_para_break_indented(self, pos: TextPosition, prev: TextPosition) -> bool:
        """Convenience predicate: only the indent prong of
        :meth:`is_paragraph_separation`. Mirrors upstream's helper used
        by callers that want to detect indented-first-line paragraphs
        without conflating them with blank-line paragraph drops."""
        space_width = prev.width_of_space if prev.width_of_space > 0 else (
            prev.font_size * 0.25
        )
        indent = pos.y - prev.y if self._flip_axes else pos.x - prev.x
        return indent > space_width * self._indent_threshold

    def start_of_paragraph(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """Alias for :meth:`is_paragraph_separation` matching upstream's
        ``isParagraphStart`` accessor name spelling. Both names are
        present on the 3.x surface; we honour both for porting parity."""
        return self.is_paragraph_separation(pos, prev)

    def _assign_articles(self, positions: list[TextPosition]) -> list[list[TextPosition]]:
        """Upstream's ``charactersByArticle`` for the page: one slot without
        bead separation, ``2 * N + 1`` slots for ``N`` beads otherwise.

        Upstream reuses the list from page to page and only clears it, so a
        page never has fewer slots than an earlier page of the same walk had
        (the slots past this page's need stay empty, and glyphs outside every
        bead go to the last one); ``reset_engine`` starts over.
        """
        rects: list[tuple[float, float, float, float] | None] = []
        if self._should_separate_by_beads and self._active_page is not None:
            rects = self._bead_rectangles_java(self._active_page)
        sections = 1 + 2 * len(rects)
        slot_count = max(sections, self._article_slot_count)
        self._article_slot_count = slot_count
        if not self._should_separate_by_beads:
            slots: list[list[TextPosition]] = [[] for _ in range(slot_count)]
            slots[0].extend(positions)
            return slots
        return self._partition_into_slots(positions, rects, slot_count)

    def _partition_by_beads(
        self, positions: list[TextPosition], keep_empty: bool = False
    ) -> list[list[TextPosition]]:
        """Bucket ``positions`` into the per-article ``charactersByArticle``
        slots upstream maintains when ``shouldSeparateByBeads`` is enabled.

        Port of the article assignment in upstream ``processTextPosition``
        with the bead rectangles of ``fillBeadRectangles``. For ``N`` thread
        beads there are ``2 * N + 1`` slots: slot ``i * 2 + 1`` holds glyphs
        inside bead ``i``, slot ``i * 2`` the glyphs left of or above bead
        ``i`` that did not land inside an earlier bead, and the last slot
        everything else. Upstream flips each bead rectangle into the glyphs'
        upper-left frame against the *media box* height and shifts it by the
        cropbox corner, then tests ``getX()`` / ``getY()`` with the inclusive
        ``PDRectangle.contains``.

        Returns every slot in index order when ``keep_empty`` is set (as
        upstream iterates them), otherwise only the non-empty ones; an empty
        list when the page has no thread beads.
        """
        page = self._active_page
        if page is None:
            return []
        rects = self._bead_rectangles_java(page)
        if not rects:
            return []
        slots = self._partition_into_slots(positions, rects, len(rects) * 2 + 1)
        if keep_empty:
            return slots
        return [s for s in slots if s]

    @staticmethod
    def _bead_rectangles_java(page: PDPage) -> list[tuple[float, float, float, float] | None]:
        """Upstream ``fillBeadRectangles``: each bead rectangle flipped into
        the glyphs' upper-left frame against the media box height and shifted
        by the cropbox corner; ``None`` for a bead without a rectangle."""
        try:
            beads = page.get_thread_beads()
        except Exception:  # defensive: malformed /B
            return []
        if not beads:
            return []
        try:
            media_ury = _f32(float(page.get_media_box().get_upper_right_y()))
        except Exception:  # defensive
            media_ury = 0.0
        try:
            crop = page.get_crop_box()
            crop_llx = _f32(float(crop.get_lower_left_x()))
            crop_lly = _f32(float(crop.get_lower_left_y()))
        except Exception:  # defensive: missing/odd CropBox
            crop_llx = 0.0
            crop_lly = 0.0
        rects: list[tuple[float, float, float, float] | None] = []
        for bead in beads:
            if bead is None:
                rects.append(None)
                continue
            try:
                r = bead.get_rectangle()
            except Exception:
                rects.append(None)
                continue
            if r is None:
                rects.append(None)
                continue
            llx = _f32(float(r.get_lower_left_x()))
            urx = _f32(float(r.get_upper_right_x()))
            ury = _f32(media_ury - _f32(float(r.get_lower_left_y())))
            lly = _f32(media_ury - _f32(float(r.get_upper_right_y())))
            if crop_llx != 0 or crop_lly != 0:
                llx = _f32(llx - crop_llx)
                lly = _f32(lly - crop_lly)
                urx = _f32(urx - crop_llx)
                ury = _f32(ury - crop_lly)
            rects.append((llx, lly, urx, ury))
        return rects

    @staticmethod
    def _partition_into_slots(
        positions: list[TextPosition],
        rects: list[tuple[float, float, float, float] | None],
        slot_count: int,
    ) -> list[list[TextPosition]]:
        """Upstream ``processTextPosition``'s article choice for each glyph."""
        slots: list[list[TextPosition]] = [[] for _ in range(slot_count)]
        last_index = len(slots) - 1
        if not rects:
            # No bead: every glyph falls through to the last slot.
            slots[last_index].extend(positions)
            return slots
        for pos in positions:
            g = _java_geometry(pos)
            x = g.x
            y = g.y
            found = -1
            left_above = -1
            left = -1
            above = -1
            for i, rect in enumerate(rects):
                if found != -1:
                    break
                if rect is None:
                    # Upstream: a null bead rectangle sends the glyph to slot 0.
                    found = 0
                    continue
                llx, lly, urx, ury = rect
                if llx <= x <= urx and lly <= y <= ury:
                    found = i * 2 + 1
                elif (x < llx or y < ury) and left_above == -1:
                    left_above = i * 2
                elif x < llx and left == -1:
                    left = i * 2
                elif y < ury and above == -1:
                    above = i * 2
            if found != -1:
                idx = found
            elif left_above != -1:
                idx = left_above
            elif left != -1:
                idx = left
            elif above != -1:
                idx = above
            else:
                idx = last_index
            slots[idx].append(pos)
        return slots

    @staticmethod
    def _drop_overlapping_duplicates(
        positions: list[TextPosition],
    ) -> list[TextPosition]:
        """Drop runs that re-paint an earlier same-text run at (nearly)
        the same origin — the fake-bold / drop-shadow double strike.

        Faithful port of the ``suppressDuplicateOverlappingText`` filter in
        upstream ``PDFTextStripper.processTextPosition`` (PDFBox 3.0.7),
        adapted to the lite stripper's run-level positions:

        - The dedup map is PAGE-global and keyed on the decoded text
          (upstream ``characterListMapping``, cleared per page), so a
          re-paint of a run *anywhere* later in the page's content stream
          is still recognised — not just one painted immediately after its
          original.
        - ``tolerance = width / len(text) / 3`` — upstream divides the
          position's width by its unicode length; for the lite run-level
          position that is the run's average glyph advance over three. The
          SAME tolerance applies on both axes (upstream reuses ``tolerance``
          for the ``subMap`` x-window and the ``subSet`` y-window).
        - The match window is half-open — ``[v - tol, v + tol)`` — because
          Java's two-argument ``TreeMap.subMap`` / ``TreeSet.subSet`` are
          from-inclusive, to-exclusive: a recorded origin exactly at
          ``v - tol`` matches, one exactly at ``v + tol`` does not.
        - Only a SHOWN run records its origin; a suppressed run never
          extends the map (upstream adds to ``sameTextCharacters`` only
          when ``!suppressCharacter``).
        - Runs emitted inside an ``/ActualText`` span bypass the filter
          entirely (upstream guards the whole block with
          ``this.actualText == null``): they are always shown and are never
          recorded in the map.
        - An empty decoded text mirrors Java float arithmetic: with a
          positive width, ``width / 0`` is ``+Infinity`` — any earlier
          empty-text run on the page suppresses; with width 0 the tolerance
          is ``NaN`` and nothing ever matches (the run is always shown).

        Coordinates and width are upstream's page-rotation-adjusted
        ``getX()`` / ``getY()`` / ``getWidth()`` (see :class:`_JavaGeometry`),
        so the half-open windows apply in upstream's upper-left frame.
        """
        result: list[TextPosition] = []
        # Page-global dedup map keyed on decoded text (upstream
        # ``characterListMapping``). Each bucket carries a spatial hash grid
        # of recorded run origins so a re-paint is located in O(1) expected
        # time rather than by scanning every prior same-text origin — the
        # former inner loop was O(n^2) per page and turned quadratic on pages
        # that stamp thousands of same-text runs (fake bold / drop shadow).
        #
        # The grid is *only* a candidate index: the exact half-open
        # ``[v - tol, v + tol)`` predicate (:func:`_dup_window_hit_flat`) is still
        # evaluated on every candidate, and because ``floor(v / cell)`` is
        # monotonic in ``v`` for a fixed positive ``cell`` the probed 2x2
        # (grown when a run's tolerance exceeds the cell) neighbourhood always
        # contains every origin the window could match. The suppression
        # decision is therefore byte-for-byte identical to the linear scan for
        # every input. Each bucket is ``[cell, grid, overflow, last width,
        # last tolerance]``:
        #   * ``cell``     — grid cell size, fixed to four times the first
        #                    finite positive tolerance recorded for the text
        #                    (constant in the common fake-bold case → at
        #                    most 2x2 probes);
        #   * ``grid``     — ``{cx * _GRID_ROW + cy: [x0, y0, x1, y1, ...]}``
        #                    cell buckets (flat, so no per-origin tuple);
        #   * ``overflow`` — origins that predate a grid cell (empty-text
        #                    buckets, whose tolerance is always inf/NaN) or
        #                    carry a non-finite coordinate; always scanned so
        #                    the result stays exact for those edge cases.
        seen: dict[str, list] = {}
        floor = math.floor
        inf = math.inf
        append = result.append
        pack1 = _f32_pack
        unpack1 = _f32_unpack
        pack4 = _f32x4_pack
        unpack4 = _f32x4_unpack
        row_stride = _GRID_ROW
        window_hit = _dup_window_hit_flat
        fast = _USE_FAST_PATHS
        # ``floor(v / cell)`` raises one of these for a zero cell or a
        # non-finite ``v``: the cases the grid cannot index.
        not_indexable = (ZeroDivisionError, OverflowError, ValueError)
        for pos in positions:
            if pos.from_actual_text:
                append(pos)
                continue
            text = pos.text
            try:
                geometry = pos._java_geometry or _java_geometry(pos)
            except AttributeError:
                geometry = _java_geometry(pos)
            pos_x = geometry.x
            pos_y = geometry.y
            width = geometry.width
            bucket = seen.get(text)
            # The tolerance is a function of the width and the text length
            # alone; each bucket remembers the last one it computed.
            if fast and bucket is not None and width == bucket[3]:
                tol = bucket[4]
            else:
                # Java: text.getWidth() / textCharacter.length() / 3.0f —
                # float division, so length 0 yields +Infinity (or NaN for a
                # zero width, which never matches). A non-finite value packs
                # as is.
                char_count = len(text)
                if char_count:
                    tol = width / char_count / 3.0
                    try:
                        tol = unpack1(pack1(tol))[0]
                    except OverflowError:
                        tol = f32(tol)
                else:
                    tol = _fdiv(_fdiv(width, 0.0), 3.0)
                if bucket is not None:
                    bucket[3] = width
                    bucket[4] = tol
            # Grid column of this origin when the probe already pinned it.
            known_cx = None
            known_cy = None
            if bucket is None:
                # First run of this text on the page: nothing to match.
                # ``[cell, grid, overflow, last width, last tolerance]``.
                bucket = seen[text] = [0.0, {}, [], width, tol]
                cell = 0.0
                grid = bucket[1]
                overflow = bucket[2]
            else:
                cell, grid, overflow = bucket[0], bucket[1], bucket[2]
                try:
                    x_lo, x_hi, y_lo, y_hi = unpack4(
                        pack4(pos_x - tol, pos_x + tol, pos_y - tol, pos_y + tol)
                    )
                except OverflowError:
                    x_lo, x_hi = _f32x2(pos_x - tol, pos_x + tol)
                    y_lo, y_hi = _f32x2(pos_y - tol, pos_y + tol)
                if overflow and window_hit(overflow, x_lo, x_hi, y_lo, y_hi):
                    continue
                if grid:
                    try:
                        cx0 = floor(x_lo / cell)
                        cx1 = floor(x_hi / cell)
                        cy0 = floor(y_lo / cell)
                        cy1 = floor(y_hi / cell)
                    except not_indexable:
                        cx0 = None
                        cx1 = cy0 = cy1 = 0
                    if fast and cx0 is not None and cx1 - cx0 <= 1 and cy1 - cy0 <= 1:
                        # The common case: the window spans at most two
                        # cells per axis (the cell is four times the first
                        # tolerance), probed without loops. ``floor(v /
                        # cell)`` is monotonic, so a one-cell span also pins
                        # the origin's own cell for the insertion below.
                        row = cx0 * row_stride
                        key = row + cy0
                        if key in grid and window_hit(grid[key], x_lo, x_hi, y_lo, y_hi):
                            continue
                        if cy1 != cy0:
                            key = row + cy1
                            if key in grid and window_hit(grid[key], x_lo, x_hi, y_lo, y_hi):
                                continue
                        elif y_lo <= pos_y <= y_hi:
                            known_cy = cy0
                        if cx1 != cx0:
                            row = cx1 * row_stride
                            key = row + cy0
                            if key in grid and window_hit(grid[key], x_lo, x_hi, y_lo, y_hi):
                                continue
                            if cy1 != cy0:
                                key = row + cy1
                                if key in grid and window_hit(
                                    grid[key], x_lo, x_hi, y_lo, y_hi
                                ):
                                    continue
                        elif x_lo <= pos_x <= x_hi:
                            known_cx = cx0
                    elif _dup_grid_hit(grid, cx0, cx1, cy0, cy1, x_lo, x_hi, y_lo, y_hi):
                        continue
            if cell <= 0.0 and 0.0 < tol < inf:
                # Four times the tolerance: a ``2 * tol`` wide window then
                # usually stays inside one cell per axis.
                cell = bucket[0] = 4.0 * tol
            try:
                key = (floor(pos_x / cell) if known_cx is None else known_cx) * row_stride + (
                    floor(pos_y / cell) if known_cy is None else known_cy
                )
            except not_indexable:
                overflow.append(pos_x)
                overflow.append(pos_y)
            else:
                cell_pts = grid.get(key)
                if cell_pts is None:
                    grid[key] = [pos_x, pos_y]
                else:
                    cell_pts.append(pos_x)
                    cell_pts.append(pos_y)
            append(pos)
        return result

    # ---------- emission hooks (subclasses may override) ----------
    #
    # These mirror upstream PDFBox's ``writeString`` /
    # ``writeWordSeparator`` / ``writeLineSeparator`` /
    # ``writeParagraphStart`` / ``writeParagraphEnd`` /
    # ``writePageStart`` / ``writePageEnd`` / ``writeArticleStart`` /
    # ``writeArticleEnd`` overrides. Upstream writes to a Java
    # ``Writer``; we accept a callable sink so subclasses don't need
    # to thread a buffer through the call chain.

    def process_text_position(self, text: TextPosition) -> None:
        """Per-glyph hook invoked for every emitted ``TextPosition``.

        The base implementation is a no-op; subclasses override to
        collect or filter individual glyphs (the
        :class:`FilteredTextStripper` ``-rotationMagic`` collector is
        the canonical use case). Upstream PDFBox calls this from its
        showText path; pypdfbox invokes it for each glyph as the word it
        belongs to is written (see :meth:`write_string`).
        """
        return

    def should_skip_glyph(self, text: TextPosition) -> bool:
        """Return ``True`` to drop ``text`` from the formatted output.

        Mirrors upstream PDFBox's ``shouldSkipGlyph`` filter hook
        (added on the 3.x branch alongside ``setIgnoreContentStreamSpaceGlyphs``).
        The base implementation always returns ``False`` — every glyph
        is kept. Subclasses override to filter, e.g. by rotation,
        position, or font.
        """
        return False

    def write_string(
        self,
        text: str,
        text_positions: list[TextPosition],
        sink: Callable[[str], None],
    ) -> None:
        """Hook for emitting a decoded text run. Default writes
        ``text`` to ``sink``. Subclasses may inspect ``text_positions``
        to filter or transform the run before writing."""
        if (
            not _USE_FAST_PATHS
            or type(self).process_text_position is not _BASE_PROCESS_TEXT_POSITION
        ):
            # (The base hook is a no-op.)
            for tp in text_positions:
                self.process_text_position(tp)
        sink(text)

    def write_string_with_positions(
        self,
        text: str,
        text_positions: list[TextPosition],
        sink: Callable[[str], None],
    ) -> None:
        """Position-aware emission hook with the same signature as
        :meth:`write_string`. Mirrors upstream's
        ``writeString(String, List<TextPosition>)`` overload.

        Invariants enforced here for subclasses:

        - From the format path ``text`` is one word and ``text_positions``
          its glyphs (upstream ``writeLine`` calls it once per word).
        - Each position is dispatched through :meth:`process_text_position`
          *before* anything is written to ``sink``, so collectors can
          inspect the glyph geometry before the text materialises.

        Upstream's ``writeString(String, List<TextPosition>)`` unconditionally
        delegates to ``writeString(String)`` — it writes ``text`` regardless
        of how many positions accompany it (the default overload ignores the
        position list entirely). The lite stripper mirrors that: a word's
        ``text`` is written whenever it is non-empty, even when its position
        list is empty (e.g. a caller-built :class:`WordWithTextPositions`
        with no backing glyphs, as ``write_line`` may receive). Dropping the
        run on an empty position list — the pre-wave-1588 behaviour — silently
        swallowed such words while still emitting the word separators around
        them, diverging from Java's ``writeLine``. Writing an *empty* ``text``
        stays a no-op (``writeString("")`` writes nothing), so it is skipped.

        The default delegates to :meth:`write_string` (the upstream-
        compatible single-arg name); subclasses can override either.
        """
        if not text:
            return
        self.write_string(text, text_positions, sink)

    def write_word_separator(self, sink: Callable[[str], None]) -> None:
        sink(self._word_separator)

    def write_line_separator(self, sink: Callable[[str], None]) -> None:
        sink(self._line_separator)

    def write_paragraph_start(self, sink: Callable[[str], None]) -> None:
        """Upstream ``writeParagraphStart``: an open paragraph is ended
        first, so starts and ends always pair up."""
        if self._in_paragraph:
            self.write_paragraph_end(sink)
            self._in_paragraph = False
        sink(self._paragraph_start)
        self._in_paragraph = True

    def write_paragraph_end(self, sink: Callable[[str], None]) -> None:
        """Upstream ``writeParagraphEnd``: a paragraph that was never
        started is started first."""
        if not self._in_paragraph:
            self.write_paragraph_start(sink)
        sink(self._paragraph_end)
        self._in_paragraph = False

    def write_page_start(self, sink: Callable[[str], None]) -> None:
        sink(self._page_start)

    def write_page_end(self, sink: Callable[[str], None]) -> None:
        sink(self._page_end)

    def write_article_start(self, sink: Callable[[str], None]) -> None:
        sink(self._article_start)

    def write_article_end(self, sink: Callable[[str], None]) -> None:
        sink(self._article_end)

    def write_characters(self, text: TextPosition) -> None:
        """Per-glyph character-write hook.

        Mirrors upstream PDFBox's protected ``writeCharacters(TextPosition)``
        — the lowest-level emission hook, called for the unicode payload
        of a single ``TextPosition``. The default is a no-op because text
        is written word by word through :meth:`write_string`; subclasses
        that want to capture or transform per-glyph output can override.
        """
        return

    def start_document(self, document: PDDocument) -> None:
        """Hook invoked once at the start of every ``get_text`` walk.

        Mirrors upstream's protected ``startDocument(PDDocument)``. The
        base implementation is a no-op; subclasses override to install
        per-document state (e.g. a streaming writer).
        """
        return

    def end_document(self, document: PDDocument) -> None:
        """Hook invoked once at the end of every ``get_text`` walk.

        Mirrors upstream's protected ``endDocument(PDDocument)``. The
        base implementation is a no-op; subclasses override to flush
        per-document state.
        """
        return

    def start_page(self, page: PDPage) -> None:
        """Hook invoked at the start of every page in the walk, before
        ``process_page`` runs and before ``write_page_start`` emits the
        page-start separator.

        Mirrors upstream's protected ``startPage(PDPage)``. Distinct
        from :meth:`write_page_start`: this hook does not write to the
        sink — it lets subclasses observe the page boundary without
        committing characters.
        """
        return

    def end_page(self, page: PDPage) -> None:
        """Hook invoked at the end of every page in the walk, after
        ``write_page_end`` has emitted the page-end separator.

        Mirrors upstream's protected ``endPage(PDPage)``.
        """
        return

    def start_article(self, is_ltr: bool = True) -> None:
        """Hook invoked at the start of an article (bead-bounded
        column). Mirrors upstream's protected ``startArticle(boolean)``;
        ``is_ltr`` tracks whether the article's primary text direction
        is left-to-right (the default).

        The lite stripper treats the page as a single article, so this
        hook is observable but not actively dispatched by the page loop
        — callers and subclass tests can drive it directly. The base
        implementation is a no-op for parity with upstream.
        """
        return

    def end_article(self) -> None:
        """Hook invoked at the end of an article. Mirrors upstream's
        protected ``endArticle``."""
        return

    # ---------- additional upstream helpers (1:1 parity) ----------

    @staticmethod
    def within(first: float, second: float, variance: float) -> bool:
        """Return ``True`` when ``second`` lies within ``variance`` of
        ``first`` (i.e. ``|second - first| < variance``).

        Mirrors upstream's private ``within(float, float, float)`` helper
        (PDFTextStripper.java:857). Note: upstream is strict ``<`` not
        ``<=`` — preserve that.
        """
        return first - variance < second < first + variance

    @staticmethod
    def overlap(y1: float, height1: float, y2: float, height2: float) -> bool:
        """Return ``True`` when two vertical glyph spans overlap.

        Mirrors upstream's private ``overlap`` helper
        (PDFTextStripper.java:762):
            within(y1, y2, .1f)
            || y2 <= y1 && y2 >= y1 - height1
            || y1 <= y2 && y1 >= y2 - height2
        """
        if PDFTextStripper.within(y1, y2, 0.1):
            return True
        if y2 <= y1 and y2 >= y1 - height1:
            return True
        return y1 <= y2 and y1 >= y2 - height2

    @staticmethod
    def multiply_float(value1: float, value2: float) -> float:
        """Multiply two floats and truncate the result to 3 decimal
        places (in thousandths) to avoid float-comparison drift.

        Mirrors upstream's ``multiplyFloat`` (PDFTextStripper.java:1685):
        ``Math.round(value1 * value2 * 1000) / 1000f``.
        """
        return round(value1 * value2 * 1000) / 1000.0

    @staticmethod
    def has_font_or_size_changed(
        current: TextPosition, last: TextPosition | None
    ) -> bool:
        """Return ``True`` when ``current`` differs from ``last`` in
        either font instance, font name, or font size.

        Mirrors upstream's private ``hasFontOrSizeChanged``
        (PDFTextStripper.java:730). The comparison falls back to font
        identity / hash when both wrappers expose no name — matching
        upstream's last-resort branch.
        """
        if last is None:
            return False
        if current.get_font_size() != last.get_font_size():
            return True
        cur_font = current.get_font()
        last_font = last.get_font()
        if cur_font is last_font:
            return False
        cur_name = cur_font.get_name() if cur_font is not None else None
        last_name = last_font.get_name() if last_font is not None else None
        if cur_name is not None:
            return cur_name != last_name
        if last_name is not None:
            return True
        # Both fonts have no name — compare identities (Python equivalent
        # of upstream's hashCode fallback).
        return id(cur_font) != id(last_font)

    @staticmethod
    def remove_contained_spaces(text_list: list[TextPosition]) -> None:
        """Remove space characters whose bounding box is fully contained
        in the previous run's bounding box (a fake-space artefact left
        over by some PDF producers — see PDFBOX-5487).

        Mirrors upstream's private ``removeContainedSpaces``
        (PDFTextStripper.java:771); mutates the supplied list in place.
        """
        if not text_list:
            return
        previous_position = text_list[0]
        idx = 1
        while idx < len(text_list):
            position = text_list[idx]
            if (
                position.get_unicode() == " "
                and previous_position.completely_contains(position)
            ):
                del text_list[idx]
                continue
            previous_position = position
            idx += 1

    def fill_bead_rectangles(self, page: PDPage) -> list[tuple[float, float, float, float]]:
        """Collect the rectangles of every thread bead on ``page``.

        Mirrors upstream's private ``fillBeadRectangles``
        (PDFTextStripper.java:386). Upstream stores the result on the
        protected ``beadRectangles`` field; the lite stripper exposes it
        via the return value (and refreshes the cached
        ``_bead_rectangles`` attribute) so subclasses can inspect the
        same shape upstream callers see.
        """
        rects: list[tuple[float, float, float, float]] = []
        try:
            beads = page.get_thread_beads()
        except Exception:  # defensive: malformed /B
            beads = []
        for bead in beads or []:
            if bead is None:
                continue
            try:
                r = bead.get_rectangle()
            except Exception:
                continue
            if r is None:
                continue
            rects.append(
                (
                    float(r.get_lower_left_x()),
                    float(r.get_lower_left_y()),
                    float(r.get_upper_right_x()),
                    float(r.get_upper_right_y()),
                )
            )
        self._bead_rectangles = rects
        return rects

    def reset_engine(self) -> None:
        """Clear per-walk state. Mirrors upstream's private
        ``resetEngine`` (PDFTextStripper.java:223): resets the
        ``charactersByArticle`` accumulator, the per-page bead rectangle
        cache, and the bookmark page resolution cache so back-to-back
        ``get_text`` walks don't leak state from each other."""
        self._characters_by_article = []
        self._article_slot_count = 0
        self._bead_rectangles = []
        self._start_bookmark_page_number = -1
        self._end_bookmark_page_number = -1
        self._current_page_no = 0

    def process_pages(self, pages: list[PDPage]) -> str:
        """Walk every page in ``pages`` invoking
        :meth:`process_page` and return the concatenated text.

        Mirrors upstream's protected ``processPages(PDPageTree)``
        (PDFTextStripper.java:263). Bookmark resolution is cached on the
        instance (``_start_bookmark_page_number`` /
        ``_end_bookmark_page_number``) for the duration of the call so
        ``process_page`` can consult it without re-walking the outline
        tree per page.
        """
        chunks: list[str] = []
        # Resolve bookmarks against the page list — when neither bookmark
        # resolves but both were set and point to the same outline item,
        # upstream forces an empty range (start=0, end=0).
        start_pg = -1
        end_pg = -1
        if self._start_bookmark is not None:
            for idx, page in enumerate(pages, start=1):
                tgt = self._start_bookmark.find_destination_page(self._active_document)
                if tgt is not None and page.get_cos_object() is tgt:
                    start_pg = idx
                    break
        if self._end_bookmark is not None:
            for idx, page in enumerate(pages, start=1):
                tgt = self._end_bookmark.find_destination_page(self._active_document)
                if tgt is not None and page.get_cos_object() is tgt:
                    end_pg = idx
                    break
        if (
            start_pg == -1
            and self._start_bookmark is not None
            and end_pg == -1
            and self._end_bookmark is not None
            and self._start_bookmark.get_cos_object()
            is self._end_bookmark.get_cos_object()
        ):
            start_pg = 0
            end_pg = 0
        self._start_bookmark_page_number = start_pg
        self._end_bookmark_page_number = end_pg
        for page in pages:
            # PDFBOX-6145: upstream dropped the ``if (page.hasContents())``
            # gate here. ``hasContents()`` resolves ``/Contents`` — an
            # indirect reference, sometimes an array of them — for *every*
            # page in the tree, which for a large document is the dominant
            # cost of extracting a single page ("extremely slow text
            # extraction of single page of large PDF"). ``process_page``
            # already short-circuits a contentless page to the empty-article
            # wrap, and ``PDFStreamEngine.processPage`` keeps its own
            # ``hasContents()`` guard, so the only observable change is that
            # the per-page hooks now fire for contentless pages too — which
            # is exactly what upstream now does.
            chunks.append(self.process_page(page))
            self._current_page_no += 1
        return "".join(chunks)

    def write_page(self) -> str:
        """Render ``get_characters_by_article`` through the line, word and
        paragraph hooks and return the text.

        Mirrors upstream's protected ``writePage``: the page start (when
        there is at least one article), every article, then the page end.
        """
        chunks: list[str] = []

        def sink(piece: str) -> None:
            chunks.append(piece)

        if self._characters_by_article:
            self.write_page_start(sink)
        self._write_articles(self._characters_by_article, sink)
        self.write_page_end(sink)
        return "".join(chunks)

    def write_line(
        self,
        line: list[WordWithTextPositions],
        sink: Callable[[str], None],
    ) -> None:
        """Write a list of normalized words for a single line, inserting
        the configured word separator between them.

        Mirrors upstream's private ``writeLine`` (PDFTextStripper.java:1853);
        exposed as a public method here so lite-mode subclasses that
        compose their own line list can plug into the same hook surface.
        """
        n = len(line)
        cls = type(self)
        if (
            _USE_FAST_PATHS
            and cls.write_string_with_positions is _BASE_WRITE_STRING_WITH_POSITIONS
            and cls.write_string is _BASE_WRITE_STRING
            and cls.process_text_position is _BASE_PROCESS_TEXT_POSITION
            and cls.write_word_separator is _BASE_WRITE_WORD_SEPARATOR
        ):
            # The stock hooks write a non-empty word and the separator.
            separator = self._word_separator
            last = n - 1
            for i, word in enumerate(line):
                if type(word) is WordWithTextPositions:
                    text = word.text
                else:
                    text = word.get_text()
                    word.get_text_positions()
                if text:
                    sink(text)
                if i < last:
                    sink(separator)
            return
        for i, word in enumerate(line):
            self.write_string_with_positions(
                word.get_text(), word.get_text_positions(), sink
            )
            if i < n - 1:
                self.write_word_separator(sink)

    def write_paragraph_separator(self, sink: Callable[[str], None]) -> None:
        """Emit ``paragraph_end`` followed by ``paragraph_start``.

        Mirrors upstream's protected ``writeParagraphSeparator``
        (PDFTextStripper.java:1697)."""
        self.write_paragraph_end(sink)
        self.write_paragraph_start(sink)

    def match_list_item_pattern(
        self, pw: PositionWrapper
    ) -> re.Pattern[str] | None:
        """Return the list-item regex matching the wrapped position's
        decoded text, or ``None`` when none match.

        Mirrors upstream's private ``matchListItemPattern``
        (PDFTextStripper.java:1763). Public here because Python lacks
        Java's package-private visibility distinction — subclasses may
        want to call it directly."""
        tp = pw.get_text_position()
        return self.match_pattern(tp.get_unicode(), self.get_list_item_patterns())

    def create_word(
        self,
        word: str,
        word_positions: list[TextPosition],
    ) -> WordWithTextPositions:
        """Build a :class:`WordWithTextPositions` for ``word`` after
        running it through :meth:`normalize_word`.

        Mirrors upstream's private ``createWord``
        (PDFTextStripper.java:2035)."""
        if (
            _USE_FAST_PATHS
            and word.isascii()
            and type(self).normalize_word is _BASE_NORMALIZE_WORD
            and type(self).handle_direction is _BASE_HANDLE_DIRECTION
        ):
            # The stock hooks return an ASCII word unchanged.
            return WordWithTextPositions(word, word_positions)
        return WordWithTextPositions(self.normalize_word(word), word_positions)

    def normalize_word(self, word: str) -> str:
        """Normalise Unicode presentation forms in ``word`` and apply the
        bidi reordering performed by :meth:`handle_direction`.

        Mirrors upstream's private ``normalizeWord``
        (PDFTextStripper.java:2047). Decomposes Unicode Alphabetic
        Presentation Forms (FB00–FDFF) and Arabic Presentation Forms-B
        (FE70–FEFF) via NFKC, with the upstream-specific quirks for
        U+FDF2 (the ``Allah`` ligature) and reversed Hebrew/Arabic
        decompositions preserved."""
        if _USE_FAST_PATHS and (word.isascii() or _PRESENTATION_FORM.search(word) is None):
            # No presentation form to decompose.
            return self.handle_direction(word)
        builder: list[str] = []
        p = 0
        q = 0
        str_length = len(word)
        had_change = False
        while q < str_length:
            c = word[q]
            cp = ord(c)
            if (0xFB00 <= cp <= 0xFDFF) or (0xFE70 <= cp <= 0xFEFF):
                if not had_change:
                    builder = []
                    had_change = True
                builder.append(word[p:q])
                if cp == 0xFDF2 and q > 0 and ord(word[q - 1]) in (0x0627, 0xFE8D):
                    # Compensate for fonts that map U+FDF2 with a leading
                    # alif by inserting the canonical Allah-without-alif
                    # decomposition.
                    builder.append("لله")
                else:
                    normalized = unicodedata.normalize("NFKC", word[q : q + 1]).strip()
                    if cp >= 0xFB1D and len(normalized) > 1:
                        normalized = normalized[::-1]
                    builder.append(normalized)
                p = q + 1
            q += 1
        if not had_change:
            return self.handle_direction(word)
        builder.append(word[p:q])
        return self.handle_direction("".join(builder))

    def handle_direction(self, word: str) -> str:
        """Reorder a string from logical to visual order for mixed bidi
        text. Mirrors upstream's private ``handleDirection``
        (PDFTextStripper.java:1903).

        Wave 1387 closes the long-standing ICU-bidi divergence by
        routing through :class:`pypdfbox.text.bidi.BidiResolver` — a
        stdlib-only port of UAX #9 (paragraph-direction detection +
        explicit embedding/override/isolate stack + weak/neutral/
        implicit resolution + L1-L4 reorder). The pure-LTR fast path
        from upstream is preserved (`Bidi.isMixed() == false &&
        baseLevel == LTR` → return unchanged); otherwise the resolver
        produces per-codepoint embedding levels and we reorder via the
        standard reverse-runs algorithm, applying Unicode mirroring
        (`L4`) on every RTL-level codepoint that declares
        :func:`unicodedata.mirrored`.
        """
        if not word or (_USE_FAST_PATHS and word.isascii()):
            # (No ASCII character has a right-to-left or explicit-embedding
            # bidi class.)
            return word
        # Fast-path: scan for any strong-RTL character or explicit
        # formatting; if absent, the paragraph is pure LTR and the bidi
        # algorithm is the identity (matches upstream's
        # ``!bidi.isMixed() && baseLevel == DIRECTION_LEFT_TO_RIGHT``
        # short-circuit at PDFTextStripper.java:1911).
        needs_resolve = False
        for ch in word:
            cls = unicodedata.bidirectional(ch)
            if cls in ("R", "AL", "AN", "RLE", "RLO", "RLI", "FSI", "LRE", "LRO", "LRI"):
                needs_resolve = True
                break
        if not needs_resolve:
            return word
        paragraph_dir = get_paragraph_direction(word)
        resolver = BidiResolver()
        levels = resolver.resolve(word, paragraph_direction=paragraph_dir)
        # If the resolver agrees the paragraph is pure LTR (every level
        # 0), nothing to reorder.
        if all(level == 0 for level in levels):
            return word
        # L2 — reverse all level runs from highest level down to the
        # lowest odd level. Then apply L4 mirroring on every RTL-level
        # codepoint.
        indices = _bidi_reorder_indices(levels)
        out: list[str] = []
        for i in indices:
            ch = word[i]
            level = levels[i]
            if level % 2 == 1 and unicodedata.mirrored(ch):
                mirror = _BIDI_MIRROR_MAP.get(ch)
                out.append(mirror if mirror is not None else ch)
            else:
                out.append(ch)
        return "".join(out)

    def normalize(
        self, line: list[_LineItem]
    ) -> list[WordWithTextPositions]:
        """Walk a list of :class:`_LineItem` entries and produce a list
        of normalized :class:`WordWithTextPositions`.

        Mirrors upstream's private ``normalize(List<LineItem>)``
        (PDFTextStripper.java:1874). The ``LineItem`` sentinel pattern is
        ported as :class:`_LineItem`."""
        normalized: list[WordWithTextPositions] = []
        line_builder: list[str] = []
        word_positions: list[TextPosition] = []
        if not _USE_FAST_PATHS or type(self).normalize_add is not _BASE_NORMALIZE_ADD:
            for item in line:
                self.normalize_add(normalized, line_builder, word_positions, item)
        else:
            # :meth:`normalize_add` inline for the stock line items and
            # positions (a one-character text is its own visual order).
            create_word = self.create_word
            add_piece = line_builder.append
            add_position = word_positions.append
            for item in line:
                if type(item) is not _LineItem:
                    self.normalize_add(normalized, line_builder, word_positions, item)
                    continue
                text = item._text_position
                if text is None:
                    normalized.append(create_word("".join(line_builder), list(word_positions)))
                    line_builder.clear()
                    word_positions.clear()
                    continue
                if type(text) is TextPosition and len(piece := text.text) <= 1:
                    add_piece(piece)
                else:
                    add_piece(text.get_visually_ordered_unicode())
                add_position(text)
        # Upstream tests the builder's *length*: trailing empty-unicode glyphs
        # (e.g. the tail of an ``/ActualText`` span) do not form a word.
        last_word = "".join(line_builder)
        if last_word:
            normalized.append(self.create_word(last_word, list(word_positions)))
        return normalized

    def _normalize_positions(
        self, line: list[TextPosition | None]
    ) -> list[WordWithTextPositions]:
        """The stock :meth:`normalize` for a line queued as positions, with
        ``None`` for each word separator item."""
        normalized: list[WordWithTextPositions] = []
        line_builder: list[str] = []
        word_positions: list[TextPosition] = []
        create_word = self.create_word
        add_piece = line_builder.append
        add_position = word_positions.append
        for text in line:
            if text is None:
                normalized.append(create_word("".join(line_builder), list(word_positions)))
                line_builder.clear()
                word_positions.clear()
                continue
            # (A one-character text is its own visual order.)
            if type(text) is TextPosition and len(piece := text.text) <= 1:
                add_piece(piece)
            else:
                add_piece(text.get_visually_ordered_unicode())
            add_position(text)
        # Upstream tests the builder's *length*: trailing empty-unicode glyphs
        # (e.g. the tail of an ``/ActualText`` span) do not form a word.
        last_word = "".join(line_builder)
        if last_word:
            normalized.append(create_word(last_word, list(word_positions)))
        return normalized

    def _write_bare_line(
        self, line: list[TextPosition | None], sink: Callable[[str], None]
    ) -> None:
        """``write_line(normalize(line))`` with the stock hooks, for a line
        queued as positions (``None`` for each word separator item): each
        word's normalized text is written when not empty, with the word
        separator between consecutive words."""
        words: list[str] = []
        add_word = words.append
        line_builder: list[str] = []
        add_piece = line_builder.append
        normalize_word = self.normalize_word
        stock_word = (
            type(self).normalize_word is _BASE_NORMALIZE_WORD
            and type(self).handle_direction is _BASE_HANDLE_DIRECTION
        )
        for text in line:
            if text is None:
                word = "".join(line_builder)
                line_builder.clear()
                # ``create_word``: the stock hooks return an ASCII word as is.
                add_word(word if stock_word and word.isascii() else normalize_word(word))
                continue
            # (A one-character text is its own visual order.)
            if type(text) is TextPosition and len(piece := text.text) <= 1:
                add_piece(piece)
            else:
                add_piece(text.get_visually_ordered_unicode())
        word = "".join(line_builder)
        if word:
            add_word(word if stock_word and word.isascii() else normalize_word(word))
        separator = self._word_separator
        last = len(words) - 1
        for i, word in enumerate(words):
            if word:
                sink(word)
            if i < last:
                sink(separator)

    def normalize_add(
        self,
        normalized: list[WordWithTextPositions],
        line_builder: list[str],
        word_positions: list[TextPosition],
        item: _LineItem,
    ) -> None:
        """Append a :class:`_LineItem` to the normalized line buffers.

        Mirrors upstream's private ``normalizeAdd``
        (PDFTextStripper.java:2111). Upstream returns a
        ``StringBuilder`` (a freshly allocated one when the item is a
        word separator) — we mutate ``line_builder`` and
        ``word_positions`` in place to match Python conventions while
        preserving the same caller contract."""
        if item.is_word_separator():
            normalized.append(
                self.create_word("".join(line_builder), list(word_positions))
            )
            line_builder.clear()
            word_positions.clear()
            return
        text = item.get_text_position()
        if text is not None:
            line_builder.append(text.get_visually_ordered_unicode())
            word_positions.append(text)

    @staticmethod
    def parse_bidi_file(input_stream: object) -> dict[str, str]:
        """Parse the upstream ``BidiMirroring.txt`` resource format and
        return a ``{char: mirrored_char}`` map.

        Mirrors upstream's private static ``parseBidiFile(InputStream)``
        (PDFTextStripper.java:1992). Lite mode keeps the parser as a
        utility — the actual mirroring map is supplied by Unicode's
        bidi data inside :func:`unicodedata.mirrored` plus the system
        font metrics, so the result is informational rather than
        load-bearing for layout."""
        mirroring: dict[str, str] = {}
        if input_stream is None:
            return mirroring
        # Accept both file-like and bytes/str inputs.
        data = input_stream.read() if hasattr(input_stream, "read") else input_stream
        text = (
            data.decode("ascii", errors="replace")
            if isinstance(data, bytes)
            else str(data)
        )
        for raw_line in text.splitlines():
            line = raw_line
            comment_at = line.find("#")
            if comment_at != -1:
                line = line[:comment_at]
            if len(line) < 2:
                continue
            tokens = [t.strip() for t in line.split(";") if t.strip()]
            if len(tokens) == 2:
                try:
                    a = chr(int(tokens[0], 16))
                    b = chr(int(tokens[1], 16))
                except ValueError:
                    continue
                mirroring[a] = b
        return mirroring

    def handle_line_separation(
        self,
        current: PositionWrapper,
        last_position: PositionWrapper | None,
        last_line_start: PositionWrapper | None,
        max_height_for_line: float,
    ) -> PositionWrapper:
        """Mark ``current`` as a line start and (when the heuristic
        agrees) a paragraph start.

        Mirrors upstream's private ``handleLineSeparation``
        (PDFTextStripper.java around the writePage paragraph block).
        Returns the wrapper that should be remembered as the new
        ``last_line_start_position``.
        """
        current.set_line_start()
        if last_position is not None:
            prev = last_position.get_text_position()
            cur_tp = current.get_text_position()
            if self.is_paragraph_separation(cur_tp, prev):
                current.set_paragraph_start()
        return current

    @staticmethod
    def word_with_text_positions(
        word: str, positions: list[TextPosition]
    ) -> WordWithTextPositions:
        """Lite-mode factory matching the upstream inner-class
        constructor signature ``new WordWithTextPositions(word, positions)``.
        Provided so ports of upstream code can call the same name without
        having to import the standalone class."""
        return WordWithTextPositions(word, positions)

    # ---------- /ActualText substitution ----------

    def _actual_text_for_run(self, text: str) -> str | None:
        """Decide what a show-text run contributes under an active
        ``/ActualText`` span.

        Returns:
          * ``text`` unchanged when no ``/ActualText`` is in effect;
          * the ``/ActualText`` replacement string for the **first**
            show-text run of the span (consuming the first-position flag);
          * ``None`` for every later run in the span (its glyph text is
            suppressed — the cursor still advances).

        Mirrors Apache PDFBox's ``PDFTextStripper``, which emits the
        ``/ActualText`` once at the span's first glyph and drops the
        glyph-derived text for the rest of the span (PDF §14.9.4).
        """
        if self._actual_text is None:
            return text
        if self._first_actual_text_position:
            self._first_actual_text_position = False
            return self._actual_text
        return None

    # ---------- marked-content hooks ----------

    def begin_marked_content_sequence(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        """Hook invoked at every ``BMC`` / ``BDC`` operator. Tracks the
        current span's ``/ActualText`` so subsequent show-text runs emit
        the replacement instead of their raw glyph text (PDF §14.9.4).

        Mirrors upstream's overridden
        ``beginMarkedContentSequence(COSName, COSDictionary)``
        (PDFTextStripper.java): the current ``actualText`` field is set
        **unconditionally** to this span's ``/ActualText`` — so entering a
        nested span *without* one clears any inherited replacement, exactly
        as PDFBox does (verified against the live oracle, wave 1445). When
        the span carries an ``/ActualText`` the soft hyphen (U+00AD) is
        stripped and the first-position flag is armed so the replacement is
        emitted once, at the span's first glyph."""
        actual: str | None = None
        if properties is not None:
            try:
                raw = properties.get_string("ActualText")
            except Exception:  # defensive
                raw = None
            if raw is not None:
                actual = raw.replace("­", "")
        self._marked_content_stack.append((tag, properties, actual))
        # Upstream sets the field unconditionally; ``None`` here means a
        # nested span without /ActualText turns substitution back off.
        self._actual_text = actual
        if actual is not None:
            self._first_actual_text_position = True

    def end_marked_content_sequence(self) -> None:
        """Hook invoked at every ``EMC`` operator. Pops the marked-content
        stack and clears the current ``actual_text`` when the popped span
        contributed one.

        Mirrors upstream's overridden ``endMarkedContentSequence``
        (PDFTextStripper.java), which peeks the top span, nulls
        ``actualText`` if that span had an ``/ActualText``, then pops."""
        if not self._marked_content_stack:
            return
        _, _, actual = self._marked_content_stack[-1]
        if actual is not None:
            self._actual_text = None
        self._marked_content_stack.pop()


class _LineItem:
    """Marker class used as a placeholder in a list of
    :class:`TextPosition` runs being normalised into words.

    Mirrors upstream's private inner class
    ``PDFTextStripper.LineItem`` (PDFTextStripper.java:2133): a singleton
    sentinel signals a word boundary; otherwise the entry carries a
    single ``TextPosition``. Promoted to a top-level (module-private)
    class so the ``normalize`` / ``normalize_add`` hooks can be invoked
    without nested-class gymnastics."""

    WORD_SEPARATOR: _LineItem  # set after the class body

    __slots__ = ("_text_position",)

    def __init__(self, text_position: TextPosition | None = None) -> None:
        self._text_position = text_position

    @classmethod
    def get_word_separator(cls) -> _LineItem:
        """Return the singleton word-separator sentinel."""
        return cls.WORD_SEPARATOR

    def get_text_position(self) -> TextPosition | None:
        return self._text_position

    def is_word_separator(self) -> bool:
        return self._text_position is None


_LineItem.WORD_SEPARATOR = _LineItem()

# The stock hooks, so the hot paths can tell when a subclass (or a patch)
# replaced one.
_BASE_PROCESS_TEXT_POSITION = PDFTextStripper.process_text_position
_BASE_NORMALIZE_ADD = PDFTextStripper.normalize_add
_BASE_NORMALIZE = PDFTextStripper.normalize
_BASE_WRITE_LINE = PDFTextStripper.write_line
_BASE_CREATE_WORD = PDFTextStripper.create_word
_BASE_SHOULD_SKIP_GLYPH = PDFTextStripper.should_skip_glyph
_BASE_WRITE_STRING = PDFTextStripper.write_string
_BASE_WRITE_STRING_WITH_POSITIONS = PDFTextStripper.write_string_with_positions
_BASE_WRITE_WORD_SEPARATOR = PDFTextStripper.write_word_separator
_BASE_NORMALIZE_WORD = PDFTextStripper.normalize_word
_BASE_HANDLE_DIRECTION = PDFTextStripper.handle_direction


class _TextState:
    """Mutable text-state bag shared by the dispatcher and emitters."""

    __slots__ = (
        "text_x",
        "text_y",
        "line_x",
        "line_y",
        "leading",
        "font_size",
        "font_name",
        "char_spacing",
        "word_spacing",
        "horizontal_scaling",
        "text_rise",
        "tm_a",
        "tm_b",
        "tm_c",
        "tm_d",
        "ctm",
        "gs_stack",
        "in_text_object",
        "_trm_cache",
        "_run_ctx",
    )

    def __init__(self) -> None:
        self.text_x: float = 0.0
        self.text_y: float = 0.0
        self.line_x: float = 0.0
        self.line_y: float = 0.0
        self.leading: float = 0.0
        self.font_size: float = 0.0
        self.font_name: str | None = None
        self.char_spacing: float = 0.0
        self.word_spacing: float = 0.0
        # Horizontal text scaling (``Tz``), as a fraction (``Tz/100``). PDF
        # 32000-1 §9.3.4: ``Tz`` is a *percentage* that scales the horizontal
        # component of every glyph displacement — and of ``Tc`` / ``Tw`` — by
        # ``Tz/100``. Default 1.0 (i.e. 100%) per ``BT`` text-state reset.
        # A non-1.0 value condenses (<1) or expands (>1) the horizontal
        # advance the word-gap heuristic measures, so word segmentation in
        # ``getText`` is ``Tz``-dependent.
        self.horizontal_scaling: float = 1.0
        # Text rise (``Ts``), in unscaled text-space units. PDF 32000-1
        # §9.3.7: ``Ts`` raises (positive) or lowers (negative) the baseline
        # of subsequent glyphs by shifting the text-rendering matrix origin
        # vertically — upstream folds it into the f-translation of the
        # font-parameter matrix (``[fontSize·Th, 0, 0, fontSize, 0, rise]``),
        # so it moves the glyph origin without changing the glyph scale or
        # direction. A superscript run (``4 Ts``) sits above the baseline; a
        # subscript run sits below. Default 0.0 per the ``BT`` text-state
        # reset. The rise is *not* part of the cursor advance — it is applied
        # only to the rendered origin and reset to 0 by a later ``0 Ts``.
        self.text_rise: float = 0.0
        # Text-matrix scale/shear components — only ``Tm`` mutates these
        # (Td/TD/T*/'/" affect translation only, leaving a/b/c/d alone),
        # so tracking them here is enough to recover the run's rotation
        # at emit time. Identity by default per PDF 1.7 §9.4.1 ``BT``.
        self.tm_a: float = 1.0
        self.tm_b: float = 0.0
        self.tm_c: float = 0.0
        self.tm_d: float = 1.0
        # Current transformation matrix (CTM). The ``cm`` operator
        # concatenates onto it; ``q`` / ``Q`` push / pop it. Tracking the
        # CTM lets the emitter compute the full text-rendering matrix
        # (textMatrix × CTM) the way upstream ``PDFStreamEngine.showText``
        # does, so producers that fold the point size into ``Tm`` and
        # position each line via a per-line ``cm`` are scaled and placed
        # correctly instead of collapsing to a single baseline at size 1.
        self.ctm: Matrix = Matrix()
        self.gs_stack: list[tuple[Matrix, tuple]] = []
        # Whether a text object (``BT`` … ``ET``) is currently open. Upstream
        # gates the text-showing and text-positioning operators on a non-null
        # text matrix / text-line matrix (both set to identity by ``BT`` and
        # to ``null`` by ``ET`` and at stream start): ``Tj`` / ``TJ`` skip when
        # ``getTextMatrix() == null`` (``ShowText`` / ``ShowTextAdjusted``) and
        # ``Td`` / ``TD`` / ``T*`` skip when ``getTextLineMatrix() == null``
        # (``MoveText``). A single open/closed flag captures both, since ``BT``
        # sets both matrices and ``ET`` clears both. Without this gate the lite
        # stripper would extract glyphs from text operators stranded outside a
        # ``BT`` … ``ET`` pair (e.g. after a truncated stream drops the ``BT``),
        # diverging from Apache PDFBox which silently ignores them.
        self.in_text_object: bool = False
        # Cache of the text-rendering matrix's *derived* run-invariant values
        # ``(x_scale, y_scale, text_dir)`` — see
        # ``PDFTextStripper._scale_and_dir``. These depend only on the text
        # matrix scale/shear (``tm_a``..``tm_d``), the CTM and (conservatively)
        # the text rise, none of which change on the frequent show-text /
        # ``Td`` path; the cursor translation (``text_x``/``text_y``) does not
        # affect them. Dropped to ``None`` by the dispatcher whenever
        # ``BT``/``Tm``/``Ts``/``Q``/``cm`` mutate an input, so a stale value
        # can never be observed. ``q`` needs no invalidation: it clones the CTM
        # onto the stack without reassigning ``self.ctm``.
        self._trm_cache: tuple[float, float, float] | None = None
        # ``PDFTextStripper._emit_glyphs``'s run-invariant inputs and the
        # values derived from them (see ``PDFTextStripper._run_context``).
        self._run_ctx: tuple[object, ...] | None = None


def _move_text_line(state: _TextState, tx: float, ty: float) -> None:
    """Upstream ``MoveText``: ``textLineMatrix.concatenate(translate(tx, ty))``
    in float, which moves the line origin by ``(tx, ty)`` through the text
    matrix's scale and shear."""
    tx = _f32(tx)
    ty = _f32(ty)
    x_part, y_part = _f32x2(tx * state.tm_a, tx * state.tm_b)
    x_shear, y_shear = _f32x2(ty * state.tm_c, ty * state.tm_d)
    x_sum, y_sum = _f32x2(x_part + x_shear, y_part + y_shear)
    state.line_x, state.line_y = _f32x2(x_sum + state.line_x, y_sum + state.line_y)


def _two_numbers(operands: list[COSBase]) -> tuple[float, float]:
    """Pull two numeric operands; default to 0.0 on malformed input."""
    if len(operands) < 2:
        return 0.0, 0.0
    a, b = operands[0], operands[1]
    if not (isinstance(a, COSNumber) and isinstance(b, COSNumber)):
        return 0.0, 0.0
    return a.float_value(), b.float_value()


def _six_numbers(operands: list[COSBase]) -> tuple[float, float, float, float, float, float] | None:
    """Pull six numeric operands; return ``None`` on malformed input."""
    if len(operands) < 6:
        return None
    a, b, c, d, e, f = operands[:6]
    if not isinstance(a, COSNumber):
        return None
    if not isinstance(b, COSNumber):
        return None
    if not isinstance(c, COSNumber):
        return None
    if not isinstance(d, COSNumber):
        return None
    if not isinstance(e, COSNumber):
        return None
    if not isinstance(f, COSNumber):
        return None
    return (
        a.float_value(),
        b.float_value(),
        c.float_value(),
        d.float_value(),
        e.float_value(),
        f.float_value(),
    )


__all__ = ["PDFTextStripper"]
