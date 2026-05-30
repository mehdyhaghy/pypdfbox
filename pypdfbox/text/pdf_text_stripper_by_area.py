from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from .pdf_text_stripper import PDFTextStripper
from .text_position import TextPosition

if TYPE_CHECKING:
    from pypdfbox.pdmodel import PDPage, PDRectangle


# Public alias for callers who want to pass a tuple/list-style rectangle.
# Upstream takes ``java.awt.geom.Rectangle2D`` whose constructor signature
# is ``(x, y, width, height)`` and whose y axis points DOWN (Java AWT
# convention). pypdfbox accepts either a ``PDRectangle`` (PDF user space,
# y-up) or a 4-tuple ``(x, y, width, height)`` interpreted as a
# user-space rectangle whose ``y`` is the LOWER-LEFT edge — this is a
# documented divergence from upstream's Java-coords convention. See
# CHANGES.md.
RegionRect = "PDRectangle | tuple[float, float, float, float]"


class PDFTextStripperByArea(PDFTextStripper):
    """Extract text limited to one or more named rectangular regions.

    Mirrors ``org.apache.pdfbox.text.PDFTextStripperByArea``:

    - :meth:`add_region` registers a named rectangle.
    - :meth:`remove_region` drops a previously-registered region.
    - :meth:`get_regions` returns the live list of registered region names
      in insertion order.
    - :meth:`extract_regions` walks the page's content stream once and
      bins each :class:`TextPosition` into the regions whose rectangles
      contain the position's origin.
    - :meth:`get_text_for_region` returns the formatted text for a single
      region, computed by :meth:`extract_regions`.

    Beads / article threads are incompatible with region clipping and
    are unconditionally disabled (the constructor calls
    ``super().set_should_separate_by_beads(False)`` and the override of
    :meth:`set_should_separate_by_beads` is a no-op, matching upstream).

    Coordinate system divergence from upstream
    -----------------------------------------
    Upstream's ``addRegion(String, Rectangle2D)`` takes a Java AWT
    rectangle whose y axis points downward (``y == 0`` is the top).
    pypdfbox uses PDF user-space rectangles natively (``y == 0`` is the
    bottom). Pass a :class:`PDRectangle` or a ``(x, y, width, height)``
    tuple where ``y`` is the LOWER-LEFT edge in user space. See
    ``CHANGES.md``.
    """

    def __init__(self) -> None:
        super().__init__()
        # Beads + regions are incompatible upstream — disable here too.
        # Bypass our own override (which is a no-op for parity) and write
        # the underlying flag directly.
        self._should_separate_by_beads = False
        # Insertion-ordered list of region names (mirrors upstream's
        # ``ArrayList<String> regions``). Kept separate from the rect map
        # so iteration order is deterministic regardless of dict order.
        self._regions: list[str] = []
        # name -> normalized bounding box ``(min_x, min_y, max_x, max_y)``
        # in PDF user space. Mirrors upstream's
        # ``Map<String, Rectangle2D> regionArea``.
        self._region_area: dict[str, tuple[float, float, float, float]] = {}
        # name -> list of decoded ``TextPosition`` objects whose origin
        # falls inside the region. Refilled on each
        # :meth:`extract_regions` call. Mirrors upstream's
        # ``Map<String, ArrayList<List<TextPosition>>> regionCharacterList``
        # collapsed to one article per region (lite-mode has no bead /
        # article splitting).
        self._region_character_list: dict[str, list[TextPosition]] = {}
        # name -> formatted text for the region (output of
        # :meth:`get_text_for_region`). Refilled on each
        # :meth:`extract_regions` call. Mirrors upstream's
        # ``Map<String, StringWriter> regionText``.
        self._region_text: dict[str, str] = {}
        # Guard flag — set while ``extract_regions`` is binning positions
        # so the ``process_text_position`` override only routes during
        # the binning pass (and not during the per-region
        # ``_format_positions`` invocation, which calls the hook a second
        # time via ``write_string`` and would otherwise double-bin).
        self._binning_active: bool = False

    # ---------- bead override ----------

    def set_should_separate_by_beads(self, value: bool) -> None:
        """No-op override.

        Upstream documents this as: "Beads are ignored when stripping by
        area." We keep the same contract — calling this with any value
        leaves the underlying flag at ``False``.
        """
        # Intentionally drop the value on the floor. Mirrors upstream's
        # empty-bodied override.

    # ---------- region management ----------

    def add_region(
        self,
        region_name: str,
        rect: PDRectangle | tuple[float, float, float, float] | list[float],
    ) -> None:
        """Register ``region_name`` covering the given rectangle.

        ``rect`` may be a :class:`PDRectangle` (PDF user space) or a
        ``(x, y, width, height)`` tuple/list where ``y`` is the
        lower-left edge in user space. Adding the same name twice
        overwrites the rectangle but keeps the name's first position in
        :meth:`get_regions`.
        """
        bounds = _normalize_rect(rect)
        if region_name not in self._region_area:
            self._regions.append(region_name)
        self._region_area[region_name] = bounds

    def remove_region(self, region_name: str) -> None:
        """Drop a previously-registered region. No-op if not present.

        Mirrors upstream's ``removeRegion`` which silently ignores
        unknown names.
        """
        if region_name in self._region_area:
            self._regions.remove(region_name)
            del self._region_area[region_name]
        # Also clear any cached extraction state so a later
        # ``get_text_for_region`` on a re-added name doesn't return stale
        # text from before the removal.
        self._region_character_list.pop(region_name, None)
        self._region_text.pop(region_name, None)

    def get_regions(self) -> list[str]:
        """Return the live list of region names in insertion order.

        Upstream returns the backing ``ArrayList`` directly; we mirror
        that aliasing so callers who mutate the list (e.g. clear it) see
        the change reflected in subsequent :meth:`extract_regions`
        calls.
        """
        return self._regions

    def get_text_for_region(self, region_name: str) -> str:
        """Return the formatted text for ``region_name``.

        Should be called after :meth:`extract_regions`. Returns an empty
        string when the region was never extracted (mirrors upstream's
        ``StringWriter.toString()`` on a freshly-created writer rather
        than raising).
        """
        return self._region_text.get(region_name, "")

    # ---------- extraction ----------

    def extract_regions(self, page: PDPage) -> None:
        """Walk ``page`` once and bin each text position into the regions
        whose rectangles contain its origin.

        Resets the per-region buffers so the same instance can be reused
        across multiple pages — mirrors upstream's
        ``regionCharacterList.put(name, …)`` / ``regionText.put(name, new
        StringWriter())`` reset at the top of ``extractRegions``.

        Pages with no ``/Contents`` are silently skipped (matches
        upstream's ``if (page.hasContents())`` guard).
        """
        # Reset per-region state for every registered region — even ones
        # we never observed before — so a stale prior extraction can't
        # leak into the new run.
        for name in self._regions:
            self._region_character_list[name] = []
            self._region_text[name] = ""

        contents = page.get_contents()
        if not contents:
            return

        # Run the parser exactly the way ``PDFTextStripper.process_page``
        # does so font/CMap resolution stays consistent. We can't just
        # call ``super().process_page(page)`` because that returns
        # already-formatted text — we need the raw position list to bin
        # by region first, then format each region separately.
        self._active_page = page
        self._cmap_cache = {}
        self._font_cache = {}
        self._active_cmap = None
        self._active_font = None
        self._active_avg_advance = None
        try:
            positions = self._extract_positions(contents)
            # Bin positions into regions through the public hook so a
            # subclass that overrides ``process_text_position`` can still
            # extend the routing decision (e.g. drop watermarks). The
            # guard flag below stops the per-region ``_format_positions``
            # call from re-entering the bin loop via ``write_string``.
            self._binning_active = True
            try:
                for position in positions:
                    self.process_text_position(position)
            finally:
                self._binning_active = False

            # Format each region's bin into a string with the configured
            # separators. Mirrors upstream's ``writePage`` override which
            # iterates ``regionArea.keySet()`` and re-runs the formatter
            # per region. The active page / font caches stay valid here
            # so any decode work the formatter triggers (word-gap font
            # widths, suppress-duplicate threshold) sees the same state
            # the parser walk used.
            for name in self._regions:
                bin_positions = self._region_character_list.get(name, [])
                formatted = self._format_positions(bin_positions)
                # Upstream's region writer runs the standard ``writePage``
                # loop once per region, which terminates the page with
                # ``getLineSeparator()`` whether or not the region captured
                # any glyphs. The Java oracle therefore returns exactly one
                # trailing ``"\n"`` for an *extracted* region — including an
                # empty one (``getTextForRegion`` over a region that matched
                # nothing returns ``"\n"``, not ``""``; verified against the
                # live PDFBox oracle, wave 1439). ``_format_positions`` only
                # writes separators *between* lines, so append the trailing
                # separator unconditionally here to match.
                formatted += self.get_line_separator()
                self._region_text[name] = formatted
        finally:
            self._active_page = None
            self._active_cmap = None
            self._active_font = None
            self._active_avg_advance = None

    def process_text_position(self, text: TextPosition) -> None:
        """Route a single text position into every region that contains
        its origin.

        Mirrors upstream's ``processTextPosition`` override: a position
        whose ``(x, y)`` falls inside multiple regions is added to all
        of them (regions can overlap). Positions outside every region
        are dropped.

        Boundary semantics (Java ``Rectangle2D.contains`` parity)
        --------------------------------------------------------
        Upstream tests each ``TextPosition`` with
        ``Rectangle2D.contains(x, y)``, which is *half-open*:
        ``rx <= x < rx + rw`` and ``ry <= y < ry + rh`` in Java AWT
        device space (y-down, origin top-left). A glyph sitting exactly on
        the left/top edge is inside; one on the right/bottom edge is
        outside. pypdfbox stores regions in PDF user space (y-up), so the
        Java y-flip turns the y half-openness inside out: the user-space
        ``min_y`` becomes exclusive and ``max_y`` inclusive, while x keeps
        ``min_x`` inclusive / ``max_x`` exclusive. The asymmetric bounds
        below reproduce ``Rectangle2D.contains`` exactly (verified against
        the live PDFBox oracle — see
        ``tests/text/oracle/test_text_sort_area_oracle.py``).

        Lite-stripper subtlety
        ----------------------
        The base :class:`PDFTextStripper` invokes
        ``process_text_position`` from two places — the parser walk
        (upstream parity) and the formatting walk (lite-mode-only;
        upstream's ``writeString`` doesn't re-emit the hook). The
        ``_binning_active`` guard ensures we only bin during the parser
        walk; a re-entry from ``write_string`` during per-region
        formatting is dropped on the floor so we don't double-count
        positions in their own region's bin.
        """
        if not self._binning_active:
            return
        # Upstream's ``PDFTextStripper`` emits one ``TextPosition`` per glyph,
        # so ``PDFTextStripperByArea.processTextPosition`` tests each glyph's
        # own origin against every region's ``Rectangle2D`` — a single
        # show-text run that straddles a region boundary is split per glyph
        # across the regions it crosses. pypdfbox's lite stripper emits one
        # ``TextPosition`` per *run* (see ``PDFTextStripper._emit``), so binning
        # the run by its start origin alone would route the whole run into the
        # region containing its first glyph and drop the tail glyphs that
        # actually fall in a neighbouring region. To match upstream's per-glyph
        # routing we split the run here: each glyph ``i`` of an ``n``-character
        # run is placed at ``x + (width / n) * i`` (the lite stripper models a
        # run's advance as a uniform ``width / n`` per glyph — see the
        # monospace-average ``run_width`` in ``_emit``), and that per-glyph
        # origin is what gets tested against each region. A glyph routed into a
        # region contributes its single character to that region's bin via a
        # one-character ``TextPosition`` so the formatter reassembles the
        # captured slice in order.
        run_text = text.get_unicode()
        n = len(run_text)
        if n <= 1:
            self._bin_glyph(text, text.get_x(), text.get_y())
            return
        base_x = text.get_x()
        y = text.get_y()
        # ``width`` is the run's full advance in the same units as ``x``.
        per_glyph = text.get_width() / n
        for i, ch in enumerate(run_text):
            glyph_x = base_x + per_glyph * i
            glyph = replace(text, text=ch, x=glyph_x, width=per_glyph)
            self._bin_glyph(glyph, glyph_x, y)

    def _bin_glyph(self, text: TextPosition, x: float, y: float) -> None:
        """Append ``text`` to every region whose rectangle contains ``(x, y)``.

        Boundary semantics reproduce Java ``Rectangle2D.contains`` exactly:
        half-open in Java device space (y-down), which the y-flip into PDF
        user space turns into ``min_x`` inclusive / ``max_x`` exclusive and
        ``min_y`` *exclusive* / ``max_y`` inclusive. See the
        ``process_text_position`` docstring.
        """
        for name, (min_x, min_y, max_x, max_y) in self._region_area.items():
            if min_x <= x < max_x and min_y < y <= max_y:
                self._region_character_list[name].append(text)


def _normalize_rect(
    rect: object,
) -> tuple[float, float, float, float]:
    """Coerce ``rect`` into ``(min_x, min_y, max_x, max_y)`` user space.

    Accepts:
      - :class:`PDRectangle` (uses ``lower_left_*`` / ``upper_right_*``).
      - A 4-tuple/list ``(x, y, width, height)`` — y is the lower-left
        edge in user space (PDF convention). Width/height may be
        negative; the result is normalized so ``min`` < ``max``.
      - Anything else with ``get_lower_left_x`` etc. accessors (duck
        typing for forward-compat with PDRectangle subclasses).
    """
    # Local import to break the pdmodel ↔ text cycle at module-load time.
    from pypdfbox.pdmodel import PDRectangle  # noqa: PLC0415

    if isinstance(rect, PDRectangle):
        return (
            rect.lower_left_x,
            rect.lower_left_y,
            rect.upper_right_x,
            rect.upper_right_y,
        )
    if isinstance(rect, (tuple, list)) and len(rect) == 4:
        x, y, w, h = (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))
        x0, x1 = (x, x + w) if w >= 0 else (x + w, x)
        y0, y1 = (y, y + h) if h >= 0 else (y + h, y)
        return (x0, y0, x1, y1)
    # Duck-typed PDRectangle-ish object.
    get_llx = getattr(rect, "get_lower_left_x", None)
    get_lly = getattr(rect, "get_lower_left_y", None)
    get_urx = getattr(rect, "get_upper_right_x", None)
    get_ury = getattr(rect, "get_upper_right_y", None)
    if all(callable(g) for g in (get_llx, get_lly, get_urx, get_ury)):
        return (
            float(get_llx()),  # type: ignore[misc]
            float(get_lly()),  # type: ignore[misc]
            float(get_urx()),  # type: ignore[misc]
            float(get_ury()),  # type: ignore[misc]
        )
    raise TypeError(
        f"add_region expects a PDRectangle or (x, y, w, h) tuple, "
        f"got {type(rect).__name__}"
    )


__all__ = ["PDFTextStripperByArea"]
