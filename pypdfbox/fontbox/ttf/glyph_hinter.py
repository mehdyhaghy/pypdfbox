"""Applies TrueType bytecode hinting (grid-fitting) to a font's glyphs, producing grid-fitted paths.

One hinter is created per :class:`TrueTypeFont`. It lazily builds a
:class:`TrueTypeInterpreter` from the font's ``maxp``/``head``/``cvt``/``fpgm``/
``prep`` tables, runs the font program once, and re-runs the control value
program whenever the ppem changes. For each glyph it scales the outline into
the pixel grid (appending the phantom points), runs the glyph's instructions
and scales the grid-fitted result back into font units, so the rest of the
rendering pipeline - which scales font units to device pixels at exactly this
ppem - reproduces the grid-fitting.

Hinting is best-effort: anything malformed, unsupported, or not applicable (an
empty glyph, a simple glyph with no instructions, a ppem below
``head.lowestRecPPEM`` or excluded by the ``gasp`` table, or a ``prep`` that
switches hinting off with INSTCTRL) falls back to ``None``, and the caller
renders the raw outline. Composite glyphs are hinted: each component with its
own instructions, then the composite's. One bad glyph never disables hinting
for the rest of the font. Whether to hint at all is the caller's decision
(``PDFRenderer.set_hinting_enabled``, off by default); this class always
grid-fits when asked.

The interpreter carries a great deal of mutable state - the storage area, the
twilight zone, the post-``prep`` template, the active ppem - so every entry
point here holds the hinter's re-entrant lock (upstream's ``synchronized``)
and one font hints one glyph at a time. A font substituted from the system is
held in a process-wide cache, so several rendering threads can share one
instance and queue on this lock; embedded fonts are per-document and
unaffected. ``HintingConcurrencyTest`` pins the behavior.

Implementation note: pypdfbox decodes ``glyf`` with fontTools rather than
upstream's ``GlyfSimpleDescript``/``GlyfCompositeDescript`` readers, so the
hinter keeps its own per-glyph :class:`_HintDescription` built from the
decoded glyph. It reproduces the upstream descriptions point for point (the
``(short)(lsb - xMin)`` x-shift of a simple glyph, a composite's
``(short)(scaleX(x, y) + xTranslate)`` points, ``resolve()``'s point and
contour offsets and its ``maxComponentDepth`` limit) and flattens them into
arrays once per glyph, so a glyph hinted at several sizes is decoded once.
"""

from __future__ import annotations

import logging
import threading
from typing import IO, TYPE_CHECKING, Any

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.execution_context import ExecutionContext
from pypdfbox.fontbox.ttf.execution_tracer import ExecutionTracer
from pypdfbox.fontbox.ttf.fixed import ONE, round_, scale, to_int32
from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyph_renderer import GlyphRenderer
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.hinting_exception import HintingException
from pypdfbox.fontbox.ttf.true_type_interpreter import TrueTypeInterpreter
from pypdfbox.fontbox.ttf.zone import Zone

if TYPE_CHECKING:
    from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont

_LOG = logging.getLogger(__name__)

_INT_MIN = -0x80000000
_INT_MAX = 0x7FFFFFFF
_ON_CURVE = GlyfDescript.ON_CURVE
_ROUND_XY_TO_GRID = GlyfCompositeComp.ROUND_XY_TO_GRID
_SHORT_MAX_VALUE = 32767
# Hard stop for composite nesting while building descriptions, in case a font declares an absurd
# maxComponentDepth: upstream's limit is maxp.maxComponentDepth alone, which Java's deeper stack
# tolerates; a reference cycle in such a font would exhaust Python's recursion limit first.
_MAX_DESCRIPTION_LEVEL = 64


def _short(value: int) -> int:
    """Java ``(short)`` cast: the low 16 bits, sign-extended."""
    return ((value + 0x8000) & 0xFFFF) - 0x8000


def _scale_all(values: list[int], ppem: int, units_per_em: int) -> list[int]:
    """``[Fixed.scale(v, ppem, unitsPerEm) for v in values]``, with the per-call setup hoisted."""
    if units_per_em <= 0 or ppem <= 0:
        return [scale(v, ppem, units_per_em) for v in values]
    m = ppem * ONE
    half = units_per_em >> 1
    out = [
        (v * m + half) // units_per_em if v >= 0 else -((half - v * m) // units_per_em)
        for v in values
    ]
    if out and (min(out) < _INT_MIN or max(out) > _INT_MAX):
        out = [to_int32(v) for v in out]
    return out


def _component(component: Any, glyph_index: int) -> GlyfCompositeComp:
    """Upstream's ``GlyfCompositeComp`` for a fontTools ``GlyphComponent``.

    fontTools keeps only the flags it cannot recompute (ROUND_XY_TO_GRID,
    USE_MY_METRICS, ...), so whether the arguments are an x/y offset or a
    pair of anchor points is read from which attributes it set. A
    point-anchored component gets no translation, as upstream does.
    """
    comp = GlyfCompositeComp()
    comp._flags = int(getattr(component, "flags", 0))
    comp._glyph_index = glyph_index
    if hasattr(component, "firstPt"):
        comp._point1 = comp._argument1 = int(component.firstPt)
        comp._point2 = comp._argument2 = int(component.secondPt)
    else:
        comp._flags |= GlyfCompositeComp.ARGS_ARE_XY_VALUES
        comp._xtranslate = comp._argument1 = int(getattr(component, "x", 0))
        comp._ytranslate = comp._argument2 = int(getattr(component, "y", 0))
    transform = getattr(component, "transform", None)
    if transform is not None:
        comp._xscale = float(transform[0][0])
        comp._scale01 = float(transform[0][1])
        comp._scale10 = float(transform[1][0])
        comp._yscale = float(transform[1][1])
    return comp


def _is_identity(comp: GlyfCompositeComp) -> bool:
    """Whether the component has no scale, so ``scaleX(x, y) == x`` and ``scaleY(x, y) == y``
    (``Math.round`` of an integer-valued float)."""
    return (
        comp._xscale == 1.0
        and comp._yscale == 1.0
        and comp._scale01 == 0.0
        and comp._scale10 == 0.0
    )


class _HintDescription:
    """A glyph's outline as upstream's ``GlyfDescript`` reports it, flattened into arrays.

    Exposes the ``GlyphDescription`` accessor surface (``get_point_count``,
    ``get_contour_count``, ``get_end_pt_of_contours``, ``get_flags``,
    ``get_x_coordinate``, ``get_y_coordinate``, ``is_composite``, ``resolve``,
    ``get_instructions``) so :class:`GlyphRenderer` can draw it, plus a
    composite's ``get_components``.
    """

    __slots__ = (
        "_contour_end_flags",
        "_on_curve_flags",
        "advance_width",
        "components",
        "composite",
        "contour_count",
        "end_pts",
        "flags",
        "instructions",
        "left_side_bearing",
        "point_count",
        "program",
        "unshifted_x",
        "x_minimum",
        "xs",
        "y_maximum",
        "ys",
    )

    def __init__(self) -> None:
        self.composite = False
        self.point_count = 0
        self.contour_count = 0
        self.end_pts: list[int] = []
        self.flags: list[int] = []
        self.xs: list[int] = []
        self.ys: list[int] = []
        # simple glyph: x without the (short)(lsb - xMin) parse shift, as FreeType hints it
        self.unshifted_x: list[int] = []
        self.instructions: list[int] | None = None
        # the instructions as bytes, ready for a BytecodeStream (upstream's toByteArray)
        self.program: bytes | None = None
        self.components: tuple[GlyfCompositeComp, ...] = ()
        self.x_minimum = 0
        self.y_maximum = 0
        self.left_side_bearing = 0
        self.advance_width = 0
        self._on_curve_flags: list[bool] | None = None
        self._contour_end_flags: list[bool] | None = None

    @property
    def on_curve_flags(self) -> list[bool]:
        """Per-point on-curve flags, for :class:`GlyphRenderer`."""
        if self._on_curve_flags is None:
            self._compute_point_flags()
        assert self._on_curve_flags is not None
        return self._on_curve_flags

    @property
    def contour_end_flags(self) -> list[bool]:
        """Per-point end-of-contour flags as ``GlyphRenderer.describe`` derives them."""
        if self._contour_end_flags is None:
            self._compute_point_flags()
        assert self._contour_end_flags is not None
        return self._contour_end_flags

    def _compute_point_flags(self) -> None:
        self._on_curve_flags, self._contour_end_flags = GlyphRenderer._point_flags(
            self, self.point_count
        )

    # --- GlyphDescription surface ---

    def is_composite(self) -> bool:
        return self.composite

    def resolve(self) -> None:
        """Composite offsets are resolved when the description is built."""

    def get_point_count(self) -> int:
        return self.point_count

    def get_contour_count(self) -> int:
        return self.contour_count

    def get_end_pt_of_contours(self, i: int) -> int:
        return self.end_pts[i]

    def get_flags(self, i: int) -> int:
        return self.flags[i]

    def get_x_coordinate(self, i: int) -> int:
        return self.xs[i]

    def get_y_coordinate(self, i: int) -> int:
        return self.ys[i]

    def get_instructions(self) -> list[int] | None:
        return self.instructions

    def get_components(self) -> tuple[GlyfCompositeComp, ...]:
        return self.components


class _Hinted:
    """The result of grid-fitting one glyph: its description, the executed zone, and its point
    count (without the appended phantom points)."""

    __slots__ = ("gd", "point_count", "zone")

    def __init__(self, gd: _HintDescription, zone: Zone, point_count: int) -> None:
        self.gd = gd
        self.zone = zone
        self.point_count = point_count


class GlyphHinter:
    """Mirrors upstream package-private ``org.apache.fontbox.ttf.GlyphHinter``."""

    PROBE_PPEM = 32
    """The ppem the full-control probe hints its sample glyphs at."""
    PROBE_SAMPLE = 32
    """At most this many glyphs with instructions are sampled by the probe."""
    PROBE_CANDIDATES = 512
    """Glyphs examined while looking for the sample, to bound the cost on huge CJK fonts."""
    PROBE_TOLERANCE = 5 * 64
    """A sampled glyph "moves" if some point is displaced by more than this (5px at PROBE_PPEM)."""
    PROBE_MIN_MOVING = 2
    """The number of moving glyphs that marks a font as needing full control."""
    MAX_ASSEMBLY_PPEM = 64
    """Upper bound on the size a full-control font is assembled at (see assembly_ppem)."""
    MAX_COMPONENT_DEPTH = 8
    """Maximum composite nesting depth, to bound recursion on pathological fonts."""

    def __init__(self, font: TrueTypeFont) -> None:
        self._font = font
        self._lock = threading.RLock()
        self._initialized = False
        self._available = False
        self._warned = False
        self._failure_count = 0
        self._first_failure: str | None = None
        self._interpreter: TrueTypeInterpreter | None = None
        self._gasp: Any = None
        self._lowest_rec_ppem = 0
        self._units_per_em = 0
        self._current_ppem = -1
        # None until probed: whether the font's bytecode builds glyph geometry (see
        # _needs_full_control)
        self._full_control: bool | None = None
        # while probing, overrides the backward-compatibility decision for glyph programs
        self._forced_backward_compatibility: bool | None = None
        # glyph descriptions, built on first use (see _HintDescription)
        self._descriptions: dict[int, _HintDescription | None] = {}
        self._glyf: Any = None
        self._glyph_order: list[str] = []
        self._glyph_ids: dict[str, int] | None = None
        self._num_glyphs = 0
        self._hmtx: Any = None
        self._max_component_depth = 0

    def _initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            self._initialized = True
            self._available = False

            font = self._font
            maxp = font.get_maximum_profile()
            fpgm = font.get_font_program()
            prep = font.get_control_value_program()
            cvt = font.get_control_values()

            # hinting is only meaningful if the font carries a bytecode program
            if maxp is None or (fpgm is None and prep is None):
                return

            self._units_per_em = font.get_units_per_em()
            self._gasp = font.get_gasp()
            header = font.get_header()
            self._lowest_rec_ppem = header.get_lowest_rec_ppem() if header is not None else 0
            self._max_component_depth = maxp.get_max_component_depth()
            self._hmtx = font.get_horizontal_metrics()
            glyph_table = font.get_glyph_table()
            if glyph_table is not None:
                self._glyf = glyph_table._glyf_table
                self._glyph_order = glyph_table._glyph_order
                self._num_glyphs = glyph_table._num_glyphs

            interpreter = TrueTypeInterpreter(
                maxp.get_max_stack_elements(),
                maxp.get_max_storage(),
                maxp.get_max_twilight_points(),
                self._units_per_em,
            )
            interpreter.set_font_program(bytes(fpgm.get_program()) if fpgm is not None else None)
            interpreter.set_control_value_program(
                bytes(prep.get_program()) if prep is not None else None
            )
            interpreter.set_control_values(cvt.get_values() if cvt is not None else None)
            self._interpreter = interpreter
            interpreter.prepare_font_program()
            self._available = True

    def get_path(self, gid: int, requested_ppem: int) -> Any:
        """Returns the grid-fitted path of the glyph at the given ppem, or ``None`` if hinting
        does not apply and the caller should render the raw outline.

        The path is in font units, as a fontTools ``RecordingPen`` (the shape
        :meth:`GlyphData.get_path` returns).

        One deliberate departure from FreeType: a font whose bytecode builds
        its glyphs (see :meth:`_needs_full_control`) is, below its
        ``head.lowestRecPPEM``, hinted at that size and the result scaled
        down (see :meth:`assembly_ppem`). Such fonts - MingLiU and its
        relatives all declare 25 - need the bytecode to put their glyphs
        together, but at small sizes the same program also forces every
        stroke to a whole pixel in both directions, making antialiased text
        roughly 1.7 times as heavy as the design. Assembling at the smallest
        size the vendor recommends for the outlines keeps the glyphs correct
        at their designed weight. :meth:`get_hinted_points_f26_dot6` is
        unaffected and still hints at the requested size.
        """
        with self._lock:
            ppem = requested_ppem
            try:
                self._initialize()
                if self._available:
                    ppem = GlyphHinter.assembly_ppem(
                        requested_ppem, self._needs_full_control(), self._lowest_rec_ppem
                    )
            except OSError:
                # _hint() below reports the failure and falls back
                pass
            hinted = self._hint(gid, ppem)
            if hinted is None:
                return None
            # scale the grid-fitted coordinates back into font units (drop the phantom points)
            n = hinted.point_count
            zone = hinted.zone
            upem = self._units_per_em
            denominator = ppem * ONE
            half = denominator // 2
            hinted_x = [
                (v * upem + half) // denominator
                if v >= 0
                else -((half - v * upem) // denominator)
                for v in zone._current_x[:n]
            ]
            hinted_y = [
                (v * upem + half) // denominator
                if v >= 0
                else -((half - v * upem) // denominator)
                for v in zone._current_y[:n]
            ]
            return GlyphRenderer(hinted.gd, hinted_x, hinted_y).get_path()

    def get_hinted_points_f26_dot6(self, gid: int, ppem: int) -> list[list[int]] | None:
        """Returns the grid-fitted glyph points in F26Dot6 device coordinates (the raw
        interpreter output, before scaling back to font units, and excluding the phantom points),
        or ``None`` if hinting does not apply. This is the form compared against a FreeType
        reference dump by the golden tests.
        """
        with self._lock:
            hinted = self._hint(gid, ppem)
            if hinted is None:
                return None
            n = hinted.point_count
            return [hinted.zone._current_x[:n], hinted.zone._current_y[:n]]

    def trace_glyph(self, gid: int, ppem: int, out: IO[str], trace_point: int) -> None:
        """Runs the control value program untraced, then grid-fits the glyph with an execution
        tracer attached, so the per-instruction trace can be diffed against FreeType's
        ``ttinterp`` trace. For development/debugging only.

        :raises OSError: if the font could not be read.
        """
        with self._lock:
            self._initialize()
            if not self._available:
                return
            self._set_active_ppem(ppem)
            interpreter = self._interpreter
            assert interpreter is not None
            interpreter.set_tracer(ExecutionTracer(out, trace_point))
            try:
                self._hint_glyph(gid, ppem, 0)
            finally:
                interpreter.set_tracer(None)

    def _hint(self, gid: int, ppem: int) -> _Hinted | None:
        """Runs all gating, then grid-fits the glyph, returning the executed zone or ``None``
        on fallback."""
        if ppem <= 0:
            return None
        try:
            self._initialize()
            if not self._available:
                return None
            # fonts whose bytecode builds the glyphs are hinted at every size: FreeType likewise
            # exempts its "tricky" fonts from both size gates
            full = self._needs_full_control()
            # head.lowestRecPPEM is the vendor's "smallest readable size in pixels" for the
            # outlines. Fonts that ship bitmap strikes for small sizes (MS Mincho/Gothic say 25)
            # set it above the sizes the bitmaps cover; their instructions were never meant to
            # run there, and doing so under grayscale forces every thin stroke to a full pixel.
            # Text fonts without strikes sit at 6-9, so this never fires for them.
            if not full and ppem < self._lowest_rec_ppem:
                return None
            # gasp gate: if a gasp table is present and does not request grid-fitting here,
            # skip. (GRIDFIT without DOGRAY is deliberately NOT treated as "do not hint": Arial
            # and Liberation flag 9-17ppem that way, so it would switch hinting off for body
            # text.)
            gasp = self._gasp
            if not full and gasp is not None and not gasp.is_grid_fit(ppem):
                return None
            self._set_active_ppem(ppem)
            # INSTCTRL bit 1: prep switched hinting off at this size (fonts do this above a ppem
            # threshold); render the raw outline, as FreeType does in tt_loader_init
            interpreter = self._interpreter
            assert interpreter is not None
            saved = interpreter.get_saved_state()
            assert saved is not None
            if saved._instruct_control & 1:
                return None
            return self._hint_glyph(gid, ppem, 0)
        except (OSError, HintingException) as e:
            self._log_failure(gid, ppem, e)
            return None

    def _log_failure(self, gid: int, ppem: int, e: BaseException) -> None:
        """Reports a glyph that could not be hinted.

        Only the first failure in a font is a warning carrying the traceback;
        the rest go to debug. Hinting is attempted per ``(glyph, ppem)`` pair,
        so a font whose bytecode never runs would otherwise emit thousands of
        identical tracebacks for a page of CJK text.
        """
        self._failure_count += 1
        if self._first_failure is None:
            self._first_failure = f"glyph {gid} at {ppem}ppem: {type(e).__name__}: {e}"
        if self._warned:
            _LOG.debug(
                "hinting failed for glyph %d at %dppem, using raw outline", gid, ppem, exc_info=e
            )
            return
        self._warned = True
        _LOG.warning(
            "hinting failed for glyph %d at %dppem in font %s, using raw outline; further "
            "failures in this font are logged at debug level",
            gid,
            ppem,
            self._font_name(),
            exc_info=e,
        )

    def get_failure_count(self) -> int:
        """How many (glyph, ppem) hinting attempts failed and fell back to the raw outline, as
        opposed to not applying (no instructions, gasp, lowestRecPPEM); for tests."""
        with self._lock:
            return self._failure_count

    def get_first_failure(self) -> str | None:
        """The first failure, ``"glyph <gid> at <ppem>ppem: <exception>"``, or ``None``."""
        with self._lock:
            return self._first_failure

    def _font_name(self) -> str:
        """The font's PostScript name for the warning above, best-effort."""
        try:
            return str(self._font.get_name())
        except Exception:
            return "<unknown>"

    @staticmethod
    def assembly_ppem(ppem: int, full_control: bool, lowest_rec_ppem: int) -> int:
        """The ppem to run a glyph program at when the glyph is drawn at ``ppem``: the same,
        except that a full-control font below its ``lowestRecPPEM`` is assembled at
        ``lowestRecPPEM`` (capped at :attr:`MAX_ASSEMBLY_PPEM`), and the result scaled down (see
        :meth:`get_path`)."""
        if not full_control or ppem <= 0 or ppem >= lowest_rec_ppem:
            return ppem
        return max(ppem, min(lowest_rec_ppem, GlyphHinter.MAX_ASSEMBLY_PPEM))

    def _needs_full_control(self) -> bool:
        """Whether the font's bytecode builds its glyph geometry rather than just fitting
        outlines to the pixel grid.

        A small set of fonts - DynaLab CJK faces such as MingLiU and
        DFKai-SB, which FreeType calls "tricky" - position and scale glyph
        components with their instructions, in x as well as y, so they only
        render correctly with full bytecode control: no v40 backward
        compatibility (which suppresses x moves) and no size gates.

        Rather than recognise such fonts by name, this measures the behaviour
        itself, once per font: it hints a spread of up to
        :attr:`PROBE_SAMPLE` glyphs that carry instructions at
        :attr:`PROBE_PPEM` ppem with backward compatibility on and with it
        off (full control), and compares them point by point with each other
        and with the raw outline. A glyph counts when both comparisons exceed
        5px (see :meth:`builds_geometry`), and :attr:`PROBE_MIN_MOVING` such
        glyphs mark the font.

        :raises OSError: if the glyph table cannot be read.
        """
        if self._full_control is None:
            self._full_control = self._probe_full_control()
            # the probe ran prep at its own size
            self._current_ppem = -1
        return self._full_control

    def _probe_full_control(self) -> bool:
        moving = 0
        for gid in self._probe_sample():
            try:
                compatible = self._probe_hinted_points(gid, True)
                full = self._probe_hinted_points(gid, False)
                if compatible is None or full is None:
                    continue
                raw = self._probe_raw_points(gid, len(full[0]))
                if raw is not None and GlyphHinter.builds_geometry(raw, compatible, full):
                    moving += 1
                    if moving >= GlyphHinter.PROBE_MIN_MOVING:
                        return True
            except (OSError, HintingException) as e:
                # a glyph that cannot be hinted says nothing about the font
                _LOG.debug("full-control probe could not hint glyph %d", gid, exc_info=e)
        return False

    def _probe_sample(self) -> list[int]:
        """Up to PROBE_SAMPLE glyphs with instructions, spread evenly over the font's non-empty
        glyphs.

        Non-empty glyphs are found from the loca offsets without parsing them
        - an embedded CID subset keeps its full glyph count with only a
        handful of glyphs present - and at most PROBE_CANDIDATES of them,
        spread evenly, are parsed.
        """
        loca = self._font.get_index_to_location()
        offsets = loca.get_offsets() if loca is not None else None
        if not offsets:
            return []
        present = [gid for gid in range(len(offsets) - 1) if offsets[gid + 1] > offsets[gid]]
        present_count = len(present)
        candidates = min(present_count, GlyphHinter.PROBE_CANDIDATES)
        instructed: list[int] = []
        for i in range(candidates):
            gid = present[i * present_count // candidates]
            gd = self._description(gid)
            if gd is None:
                continue
            if gd.point_count > 0 and (gd.composite or gd.instructions):
                instructed.append(gid)
        # spread the sample over the whole font: the glyphs whose programs build geometry are
        # the ideographs, not the Latin and punctuation at the low glyph ids
        count = len(instructed)
        size = min(count, GlyphHinter.PROBE_SAMPLE)
        return [instructed[i * count // size] for i in range(size)]

    def _probe_hinted_points(
        self, gid: int, backward_compatibility: bool
    ) -> list[list[int]] | None:
        """Hints one glyph at PROBE_PPEM with backward compatibility forced, ignoring the size
        gates."""
        self._set_active_ppem(GlyphHinter.PROBE_PPEM)
        self._forced_backward_compatibility = backward_compatibility
        try:
            hinted = self._hint_glyph(gid, GlyphHinter.PROBE_PPEM, 0)
            if hinted is None:
                return None
            n = hinted.point_count
            return [hinted.zone._current_x[:n], hinted.zone._current_y[:n]]
        finally:
            self._forced_backward_compatibility = None

    def _probe_raw_points(self, gid: int, point_count: int) -> list[list[int]] | None:
        """The glyph's scaled, unhinted outline at PROBE_PPEM, in the frame of the hinted points
        (origin at x = 0, as the parsed description has it), or ``None`` if its point count
        differs."""
        gd = self._description(gid)
        if gd is None or gd.point_count != point_count:
            return None
        upem = self._units_per_em
        return [
            _scale_all(gd.xs, GlyphHinter.PROBE_PPEM, upem),
            _scale_all(gd.ys, GlyphHinter.PROBE_PPEM, upem),
        ]

    @staticmethod
    def builds_geometry(
        raw: list[list[int]], compatible: list[list[int]], full: list[list[int]]
    ) -> bool:
        """Whether a glyph's program builds its geometry rather than fitting it to the grid:
        backward compatibility changes the result by more than PROBE_TOLERANCE, *and* even with
        backward compatibility on the result is that far from the raw outline.

        The second condition tells a font that needs full control (MingLiU:
        at least 7px from raw with it on) from one whose x instructions are
        merely broken and are hidden by backward compatibility (Giovanni
        Book: about 1px from raw with it on, 90px with it off) - giving the
        latter full control would wreck it.
        """
        return (
            GlyphHinter.point_delta(compatible, full) > GlyphHinter.PROBE_TOLERANCE
            and GlyphHinter.point_delta(raw, compatible) > GlyphHinter.PROBE_TOLERANCE
        )

    @staticmethod
    def point_delta(a: list[list[int]], b: list[list[int]]) -> int:
        """The largest displacement of any point between two outlines of the same glyph, on
        either axis."""
        delta = 0
        ax, ay = a[0], a[1]
        bx, by = b[0], b[1]
        for i in range(len(ax)):
            delta = max(delta, abs(ax[i] - bx[i]), abs(ay[i] - by[i]))
        return delta

    def is_full_control(self) -> bool:
        """Whether the probe found that this font's bytecode builds its glyphs; for tests.

        :raises OSError: if the glyph table cannot be read.
        """
        with self._lock:
            self._initialize()
            return self._available and self._needs_full_control()

    def _set_active_ppem(self, ppem: int) -> None:
        """Re-runs the control value program if the ppem changed.

        The guard is load-bearing, not just an optimization: ``set_ppem``
        clears the storage area and twilight zone before running ``prep``,
        so re-running it per glyph would wipe the values ``prep`` seeded for
        the glyph programs to read.
        """
        if ppem != self._current_ppem:
            # set_ppem rescales the CVT and clears storage before running prep; if prep raises,
            # the interpreter no longer holds current_ppem's state, so force the next call to
            # re-run it
            self._current_ppem = -1
            interpreter = self._interpreter
            assert interpreter is not None
            interpreter.set_ppem(ppem, ppem)
            self._current_ppem = ppem

    # --- glyph descriptions -------------------------------------------------------------------

    def _description(self, gid: int, level: int = 0) -> _HintDescription | None:
        """The glyph's description (upstream ``font.getGlyph().getGlyph(gid).getDescription()``),
        or ``None`` for a glyph id out of range.

        A glyph is decoded once; like upstream's glyph cache, a description
        already built is returned whatever the composite level.

        :raises OSError: when a composite nests deeper than
            ``maxp.maxComponentDepth`` (upstream ``GlyphTable.getGlyphData``).
        """
        descriptions = self._descriptions
        if gid in descriptions:
            return descriptions[gid]
        if gid < 0 or gid >= self._num_glyphs or self._glyf is None:
            return None
        try:
            glyph = self._glyf[self._glyph_order[gid]]
        except Exception as e:
            # upstream's glyph reader reports malformed glyph data as an IOException
            raise OSError(f"cannot read glyph {gid}: {e}") from e
        n_contours = int(getattr(glyph, "numberOfContours", 0))
        if n_contours != 0 and (
            level > self._max_component_depth or level > _MAX_DESCRIPTION_LEVEL
        ):
            raise OSError(
                f"composite glyph maximum level ({self._max_component_depth}) reached"
            )
        gd = _HintDescription()
        hmtx = self._hmtx
        lsb = hmtx.get_left_side_bearing(gid) if hmtx is not None else 0
        gd.left_side_bearing = lsb
        gd.advance_width = (
            hmtx.get_advance_width(gid) if hmtx is not None else self._units_per_em
        )
        if n_contours != 0 and getattr(glyph, "xMin", None) is not None:
            gd.x_minimum = int(glyph.xMin)
            gd.y_maximum = int(glyph.yMax)
        if n_contours > 0:
            self._init_simple(gd, glyph, lsb)
        elif n_contours < 0:
            self._init_composite(gd, glyph, level + 1)
        program = getattr(glyph, "program", None)
        if program is not None:
            code = bytes(program.getBytecode())
            if code:
                gd.program = code
                gd.instructions = list(code)
        descriptions[gid] = gd
        return gd

    @staticmethod
    def _init_simple(gd: _HintDescription, glyph: Any, lsb: int) -> None:
        """A simple glyph as upstream's ``GlyfSimpleDescript`` reads it: x accumulated from
        ``(short)(lsb - xMin)``."""
        x0 = _short(lsb - gd.x_minimum)
        coords = glyph.coordinates
        gd.point_count = len(coords)
        gd.contour_count = int(glyph.numberOfContours)
        gd.end_pts = [int(e) for e in glyph.endPtsOfContours]
        gd.flags = [f & 0xFF for f in glyph.flags]
        # GlyphCoordinates keeps x0, y0, x1, y1, ... in one flat array; reading it directly skips
        # a Python-level __getitem__ per point
        flat = getattr(coords, "_a", None)
        if flat is not None:
            raw_x = list(map(int, flat[0::2]))
            raw_y = list(map(int, flat[1::2]))
        else:
            raw_x = [int(p[0]) for p in coords]
            raw_y = [int(p[1]) for p in coords]
        # upstream accumulates the absolute coordinates in Java shorts
        xs = [x + x0 for x in raw_x] if x0 else raw_x
        if xs and (min(xs) < -0x8000 or max(xs) > 0x7FFF):
            xs = [_short(x) for x in xs]
        if raw_y and (min(raw_y) < -0x8000 or max(raw_y) > 0x7FFF):
            raw_y = [_short(y) for y in raw_y]
        gd.xs = xs
        gd.ys = raw_y
        # GlyphData shifts a simple glyph's x coordinates by lsb - xMin so its origin is at 0.
        # FreeType hints the unshifted outline, with the origin phantom point at xMin - lsb, and
        # moves the origin afterwards; undo the shift so rounding and phantom-point positions
        # match (upstream buildZone's parseShift)
        gd.unshifted_x = [x - x0 for x in gd.xs]

    def _init_composite(self, gd: _HintDescription, glyph: Any, level: int) -> None:
        """A composite glyph as upstream's ``GlyfCompositeDescript`` resolves it."""
        gd.composite = True
        components: list[GlyfCompositeComp] = []
        get_glyph_id = self._glyph_id
        for component in getattr(glyph, "components", None) or ():
            components.append(_component(component, get_glyph_id(component.glyphName)))
        gd.components = tuple(components)
        # initDescriptions: each component's description, keyed by glyph index
        descriptions: dict[int, _HintDescription] = {}
        for comp in components:
            index = comp.get_glyph_index()
            try:
                sub = self._description(index, level)
            except OSError as e:
                _LOG.error("%s", e)
                continue
            if sub is not None:
                descriptions[index] = sub
        # resolve: each component's first point and contour
        first_index = 0
        first_contour = 0
        for comp in components:
            if first_index > _SHORT_MAX_VALUE:
                # PDFBOX-6231: protect against wide nested composite glyphs
                _LOG.error("firstIndex is %d, aborting resolve", first_index)
                break
            comp.set_first_index(first_index)
            comp.set_first_contour(first_contour)
            sub = descriptions.get(comp.get_glyph_index())
            if sub is not None:
                first_index += sub.point_count
                first_contour += sub.contour_count
        if not components:
            return
        last = components[-1]
        last_sub = descriptions.get(last.get_glyph_index())
        if last_sub is None:
            _LOG.error(
                "GlyphDescription for index %d is null, returning 0", last.get_glyph_index()
            )
            return
        point_count = last.get_first_index() + last_sub.point_count
        contour_count = last.get_first_contour() + last_sub.contour_count
        # the per-point accessors find the first component whose point (contour) range holds the
        # index, as upstream's getCompositeComp / getCompositeCompEndPt do
        flags = [0] * point_count
        xs = [0] * point_count
        ys = [0] * point_count
        filled = [False] * point_count
        for comp in components:
            sub = descriptions.get(comp.get_glyph_index())
            if sub is None:
                continue
            first = comp.get_first_index()
            tx = comp.get_x_translate()
            ty = comp.get_y_translate()
            sxs = sub.xs
            sys_ = sub.ys
            sflags = sub.flags
            identity = _is_identity(comp)
            for k in range(sub.point_count):
                i = first + k
                if i >= point_count or filled[i]:
                    continue
                filled[i] = True
                x = sxs[k]
                y = sys_[k]
                flags[i] = sflags[k]
                if identity:
                    xs[i] = _short(x + tx)
                    ys[i] = _short(y + ty)
                else:
                    xs[i] = _short(comp.scale_x(x, y) + tx)
                    ys[i] = _short(comp.scale_y(x, y) + ty)
        end_pts = [0] * contour_count
        filled = [False] * contour_count
        for comp in components:
            sub = descriptions.get(comp.get_glyph_index())
            if sub is None:
                continue
            first_c = comp.get_first_contour()
            first = comp.get_first_index()
            for k in range(sub.contour_count):
                c = first_c + k
                if c >= contour_count or filled[c]:
                    continue
                filled[c] = True
                end_pts[c] = sub.end_pts[k] + first
        gd.point_count = point_count
        gd.contour_count = contour_count
        gd.flags = flags
        gd.xs = xs
        gd.ys = ys
        gd.end_pts = end_pts

    def _glyph_id(self, name: str) -> int:
        """The glyph id of a component, by the name fontTools refers to it with."""
        ids = self._glyph_ids
        if ids is None:
            ids = self._glyph_ids = {n: i for i, n in enumerate(self._glyph_order)}
        return ids.get(name, 0)

    # --- grid-fitting -------------------------------------------------------------------------

    def _hint_glyph(self, gid: int, ppem: int, depth: int) -> _Hinted | None:
        """Grid-fits one glyph (simple or composite), recursing into components.

        Upstream ``hint(int, int, int)``.
        """
        if depth > GlyphHinter.MAX_COMPONENT_DEPTH:
            return None
        gd = self._description(gid)
        if gd is None:
            return None
        if gd.composite:
            if gd.point_count == 0:
                return None
            return self._hint_composite(gd, gid, ppem, depth)
        n = gd.point_count
        if gd.contour_count == 0 or n == 0:
            # empty glyph (e.g. space, newline): nothing to hint
            return None
        program = gd.program
        if program is None:
            return None
        zone = self._build_zone(gd, ppem)
        ctx = self._run_program(zone, program, ppem, False)
        # move the origin to x = 0, as FreeType does after hinting (TT_Load_Glyph translates by
        # -pp1.x). Under backward compatibility FreeType keeps the unhinted phantom points
        # (TT_Hint_Glyph), otherwise the hinted ones
        cur_x = zone._current_x
        origin_x = zone._original_x[n] if ctx._backward_compatibility else cur_x[n]
        if origin_x:
            cur_x[:] = [v - origin_x for v in cur_x]
        return _Hinted(gd, zone, n)

    def _hint_composite(
        self, composite: _HintDescription, gid: int, ppem: int, depth: int
    ) -> _Hinted:
        """Grid-fits a composite glyph the way FreeType does: each component is hinted on its
        own, then transformed and offset into the composite's coordinate space, the phantom
        points appended, and finally the composite's own instructions (if any) run over the
        assembled outline."""
        n = composite.point_count
        zone = Zone(n + 4, composite.contour_count)
        for comp in composite.components:
            self._assemble_component(comp, ppem, depth, zone)
        zone._contour_ends[:] = composite.end_pts
        self._append_phantom_points(composite, ppem, n, zone)
        # A composite's own program works on its components as already hinted and assembled, so
        # its unscaled coordinates are those assembled positions (the originals) at a scale of
        # 1, as in FreeType's TT_Hint_Glyph (see ExecutionContext.is_composite)
        zone._unscaled_x[:] = zone._original_x
        zone._unscaled_y[:] = zone._original_y
        if composite.program is not None:
            self._run_program(zone, composite.program, ppem, True)
        return _Hinted(composite, zone, n)

    def _assemble_component(
        self, comp: GlyfCompositeComp, ppem: int, depth: int, zone: Zone
    ) -> None:
        """Hints one component glyph and writes its transformed/offset points into the
        composite's zone arrays. The component's grid-fitted outline goes to both the current
        and the original arrays, as FreeType bakes hinted components into the composite before
        running its instructions."""
        component_gid = comp.get_glyph_index()
        first = comp.get_first_index()
        cgd = self._description(component_gid)
        if cgd is None:
            return
        count = cgd.point_count
        upem = self._units_per_em
        if first + count > len(zone._on_curve):
            # cannot happen for a resolved composite; upstream would fail with an index out of
            # bounds here, this falls back to the raw outline instead
            raise HintingException(
                f"component {component_gid} points {first}..{first + count - 1} out of range"
            )
        end = first + count
        zone._on_curve[first:end] = [(f & _ON_CURVE) != 0 for f in cgd.flags[:count]]

        # grid-fitted component points (its own instructions executed); fall back to the
        # scaled-but-unhinted component points
        hinted_component = self._hint_glyph(component_gid, ppem, depth + 1)
        if hinted_component is not None and hinted_component.point_count == count:
            c_cur_x = hinted_component.zone._current_x[:count]
            c_cur_y = hinted_component.zone._current_y[:count]
        else:
            c_cur_x = _scale_all(cgd.xs, ppem, upem)
            c_cur_y = _scale_all(cgd.ys, ppem, upem)

        # device-space offset. With ROUND_XY_TO_GRID FreeType's v40 interpreter rounds only the y
        # offset to the grid, leaving x unrounded to approximate ClearType's fine horizontal grid
        # (TT_Process_Composite_Component)
        offset_x = scale(comp.get_x_translate(), ppem, upem)
        offset_y = scale(comp.get_y_translate(), ppem, upem)
        if comp.get_flags() & _ROUND_XY_TO_GRID:
            offset_y = round_(offset_y)

        if _is_identity(comp):
            px = [x + offset_x for x in c_cur_x]
            py = [y + offset_y for y in c_cur_y]
        else:
            scale_x = comp.scale_x
            scale_y = comp.scale_y
            px = [scale_x(x, y) + offset_x for x, y in zip(c_cur_x, c_cur_y, strict=True)]
            py = [scale_y(x, y) + offset_y for x, y in zip(c_cur_x, c_cur_y, strict=True)]
        # Java int arithmetic
        if px and (min(px) < _INT_MIN or max(px) > _INT_MAX):
            px = [to_int32(v) for v in px]
        if py and (min(py) < _INT_MIN or max(py) > _INT_MAX):
            py = [to_int32(v) for v in py]
        # FreeType bakes each hinted component into the composite and copies cur -> org before
        # running the composite program, so the original equals the assembled hinted position (a
        # SHC/MDRP in the composite then measures zero movement for an unmoved component point)
        zone._current_x[first:end] = px
        zone._current_y[first:end] = py
        zone._original_x[first:end] = px
        zone._original_y[first:end] = py

    def _run_program(
        self, zone: Zone, program: bytes, ppem: int, composite: bool
    ) -> ExecutionContext:
        """Clones the saved post-prep state, resets it for the glyph, and runs the program over
        the zone."""
        interpreter = self._interpreter
        assert interpreter is not None
        saved = interpreter.get_saved_state()
        assert saved is not None
        # INSTCTRL bit 2: glyph programs start from the default graphics state rather than
        # prep's
        gs = GraphicsState() if saved._instruct_control & 2 else saved.copy()
        gs.reset_for_glyph()
        ctx = interpreter.new_context(gs)
        ctx.set_ppem(ppem)
        ctx.set_glyph_zone(zone)
        # v40 grayscale "backward compatibility" applies to the glyph program only, never
        # fpgm/prep, which build control values via twilight-zone x/y moves that must not be
        # suppressed. A native-ClearType font waives it from prep with INSTCTRL bit 4; read from
        # gs, so a bit-2 reset to the default state also clears the waiver, as in FreeType's
        # tt_loader_init. A font whose bytecode builds the glyph geometry gets full control, as
        # FreeType gives its "tricky" fonts; the probe forces the mode while it measures.
        forced = self._forced_backward_compatibility
        if forced is not None:
            ctx.set_backward_compatibility(forced)
        else:
            ctx.set_backward_compatibility(
                self._full_control is not True and (gs._instruct_control & 4) == 0
            )
        ctx.set_composite(composite)
        interpreter.run(ctx, BytecodeStream(program))
        return ctx

    def _build_zone(self, gd: _HintDescription, ppem: int) -> Zone:
        n = gd.point_count
        upem = self._units_per_em
        # four phantom points are appended after the glyph's own points
        zone = Zone(n + 4, gd.contour_count)
        unscaled_x = gd.unshifted_x
        unscaled_y = gd.ys
        x = _scale_all(unscaled_x, ppem, upem)
        y = _scale_all(unscaled_y, ppem, upem)
        zone._unscaled_x[:n] = unscaled_x
        zone._unscaled_y[:n] = unscaled_y
        zone._original_x[:n] = x
        zone._original_y[:n] = y
        zone._current_x[:n] = x
        zone._current_y[:n] = y
        zone._on_curve[:n] = [(f & _ON_CURVE) != 0 for f in gd.flags]
        zone._contour_ends[:] = gd.end_pts
        self._append_phantom_points(gd, ppem, n, zone)
        return zone

    def _append_phantom_points(
        self, gd: _HintDescription, ppem: int, point_count: int, zone: Zone
    ) -> None:
        upem = self._units_per_em
        origin_x = gd.x_minimum - gd.left_side_bearing
        y_max = gd.y_maximum
        # pp1 = origin, pp2 = origin + advance (horizontal); pp3/pp4 are the vertical pair
        px = [origin_x, origin_x + gd.advance_width, 0, 0]
        py = [0, 0, y_max, y_max - upem]
        ox = _scale_all(px, ppem, upem)
        oy = _scale_all(py, ppem, upem)
        end = point_count + 4
        zone._unscaled_x[point_count:end] = px
        zone._unscaled_y[point_count:end] = py
        zone._original_x[point_count:end] = ox
        zone._original_y[point_count:end] = oy
        # FreeType rounds the phantom points to the grid before running the glyph program
        zone._current_x[point_count:end] = [round_(v) for v in ox]
        zone._current_y[point_count:end] = [round_(v) for v in oy]


__all__ = ["GlyphHinter"]
