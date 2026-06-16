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
        # Shared page-wide duplicate-suppression map, mirroring upstream's
        # private ``Map<String, TreeMap<Float, TreeSet<Float>>>
        # characterListMapping`` in ``PDFTextStripper``. Upstream's
        # ``PDFTextStripperByArea.processTextPosition`` (Java L137-147)
        # repoints ``charactersByArticle`` per matching region and delegates
        # to the base ``PDFTextStripper.processTextPosition`` (Java L897-951),
        # which dedups every offered glyph against this ONE page-wide map
        # before binning. A glyph inside two overlapping regions is therefore
        # recorded by the FIRST region iterated (in ``regionArea``'s HashMap
        # order) and SUPPRESSED as a coincident duplicate when offered to the
        # second — so an overlap glyph lands in exactly one region. We
        # reproduce that here: the map is keyed by the glyph's unicode string,
        # value maps x -> set of recorded y's for that character. Reset per
        # ``extract_regions`` run. See ``CHANGES.md`` (wave 1492 convergence).
        self._character_list_mapping: dict[str, dict[float, set[float]]] = {}

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
        lower-left edge in user space.

        Adding the same name twice **appends the name again** to the
        :meth:`get_regions` list while overwriting the rectangle in the
        backing area map — byte-for-byte upstream parity. Upstream's
        ``addRegion`` (PDFTextStripperByArea.java) unconditionally calls
        ``regions.add(regionName)`` *and* ``regionArea.put(regionName,
        rect)``, so a name added N times appears N times in
        ``getRegions()`` (an ``ArrayList``) but only once in
        ``regionArea`` (a ``HashMap``, last rect wins). Verified against
        the live PDFBox 3.0.7 oracle: ``add("r"); add("r")`` yields
        ``getRegions() == ["r", "r"]``. See ``CHANGES.md``.
        """
        bounds = _normalize_rect(rect)
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
        # Reset the shared page-wide dedup map so a prior page's recorded
        # glyphs can't suppress this page's. Mirrors upstream's
        # ``characterListMapping.clear()`` at the top of each
        # ``processPage`` (PDFTextStripper.java L378).
        self._character_list_mapping = {}

        contents = page.get_contents()
        if not contents:
            return

        # Run the parser exactly the way ``PDFTextStripper.process_page``
        # does so font/CMap resolution stays consistent. We can't just
        # call ``super().process_page(page)`` because that returns
        # already-formatted text — we need the raw position list to bin
        # by region first, then format each region separately.
        self._active_page = page
        # Snapshot the page rotation + cropbox extents so ``_apply_page_rotation``
        # can fold the page ``/Rotate`` into each glyph's stored coordinates,
        # exactly the way the base ``PDFTextStripper.process_page`` does. On a
        # rotated page upstream's ``PDFTextStripperByArea.processTextPosition``
        # (Java L141) tests ``Rectangle2D.contains(text.getX(), text.getY())``
        # against the page-rotation-adjusted *device* coordinates; folding here
        # puts the lite glyph origins in that same device frame so ``_bin_glyph``
        # can reproduce the native ``Rectangle2D.contains`` half-open test. The
        # unrotated path (``/Rotate 0``) is a verbatim no-op fold, so the proven
        # y-up user-frame half-open parity is unaffected.
        try:
            self._page_rotation = int(page.get_rotation()) % 360
        except Exception:  # noqa: BLE001 — defensive: bad /Rotate
            self._page_rotation = 0
        try:
            crop = page.get_crop_box()
            self._page_width = float(crop.get_width())
            self._page_height = float(crop.get_height())
        except Exception:  # noqa: BLE001 — defensive: missing/odd CropBox
            self._page_width = 0.0
            self._page_height = 0.0
        self._cmap_cache = {}
        self._font_cache = {}
        self._active_cmap = None
        self._active_font = None
        self._active_avg_advance = None
        try:
            positions = self._extract_positions(contents)
            # NOTE: we do NOT run ``_apply_page_rotation`` over the whole list
            # here. On a rotated page the fold collapses a horizontal run's
            # ``width`` to a zero device-axis extent, which would break the
            # per-glyph straddle split in ``process_text_position`` (it steps the
            # glyph origin by the run's user-space advance). Instead the split
            # stays in the user frame and ``_bin_glyph`` folds each individual
            # glyph origin into the device frame just before the boundary test
            # (see ``_glyph_device_origin``), so binning matches upstream's
            # page-rotation-adjusted ``Rectangle2D.contains`` test per glyph.
            # Record page geometry on the positions for API parity regardless.
            for pos in positions:
                pos.rotation = float(self._page_rotation)
                pos.page_width = self._page_width
                pos.page_height = self._page_height
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
            # Upstream's per-region ``writePage`` (PDFTextStripperByArea.java
            # L156-164) calls the base ``writePage`` once per region but does
            # NOT re-run duplicate suppression — the dedup already happened in
            # ``processTextPosition`` against the shared ``characterListMapping``
            # while binning (above). The lite ``_format_positions`` would
            # otherwise dedup each bin a SECOND time (per-bin), which both
            # double-counts the work and, with independent per-bin maps, can
            # drop a legitimately-distinct same-text glyph differently than
            # upstream. Suppress the format-time dedup for the byArea path so
            # the bins flow through verbatim; the bin-time shared dedup in
            # ``_bin_glyph`` is the single source of truth.
            saved_suppress = self._suppress_duplicate_overlapping_text
            self._suppress_duplicate_overlapping_text = False
            try:
                self._format_region_text()
            finally:
                self._suppress_duplicate_overlapping_text = saved_suppress
        finally:
            self._active_page = None
            self._active_cmap = None
            self._active_font = None
            self._active_avg_advance = None

    def _format_region_text(self) -> None:
        """Format each region's binned positions into its output string.

        Mirrors upstream's ``writePage`` override which iterates
        ``regionArea.keySet()`` and re-runs the base formatter per region.
        The active page / font caches stay valid here so any decode work the
        formatter triggers (word-gap font widths) sees the same state the
        parser walk used.
        """
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
        # Prefer the real per-glyph advances threaded from the font's
        # ``/Widths`` (wave 1488) so a run straddling a region boundary is
        # split at the true glyph position Java would test — not at the
        # uniform ``width / n`` estimate. ``get_individual_widths`` returns
        # the real list when present, falling back to the even split. We only
        # use it when its length matches the decoded character count (a 1:1
        # code↔char run); ligature/multi-char codes fall back to uniform so
        # the per-character routing stays well-defined.
        widths = text.get_individual_widths()
        if len(widths) == n:
            offset = 0.0
            for i, ch in enumerate(run_text):
                glyph_x = base_x + offset
                glyph = replace(
                    text, text=ch, x=glyph_x, width=widths[i],
                    individual_widths=None,
                )
                self._bin_glyph(glyph, glyph_x, y)
                offset += widths[i]
            return
        # ``width`` is the run's full advance in the same units as ``x``.
        per_glyph = text.get_width() / n
        for i, ch in enumerate(run_text):
            glyph_x = base_x + per_glyph * i
            glyph = replace(
                text, text=ch, x=glyph_x, width=per_glyph, individual_widths=None
            )
            self._bin_glyph(glyph, glyph_x, y)

    def _bin_glyph(self, text: TextPosition, x: float, y: float) -> None:
        """Bin ``text`` into the matching region(s), reproducing upstream's
        shared duplicate-suppression so an overlap glyph lands in exactly
        one region.

        Upstream's ``PDFTextStripperByArea.processTextPosition`` (Java
        L137-147) walks ``regionArea`` in ``HashMap`` iteration order and,
        for each region whose ``Rectangle2D.contains(x, y)`` is true,
        repoints ``charactersByArticle`` to that region's list and delegates
        to the base ``PDFTextStripper.processTextPosition`` (Java L897-951).
        The base method dedups the glyph against the ONE page-wide
        ``characterListMapping``: the first region to be offered the glyph
        records it (text, x, y) and bins it; when the SAME glyph is offered
        to a later overlapping region, ``suppressDuplicateOverlappingText``
        finds the coincident (text, x, y) in the shared map and drops it —
        so it never reaches the later region's bin. We reproduce that here:
        iterate matching regions in Java-HashMap order (:func:`_hashmap_order`),
        and bin a glyph only if it survives the shared dedup.

        Boundary semantics reproduce Java ``Rectangle2D.contains`` exactly.
        On an **unrotated** page the glyph origin ``(x, y)`` is in the lite
        y-up user frame and the region rectangle is stored y-up, so the y-flip
        into Java device space turns the half-open test into ``min_x`` inclusive
        / ``max_x`` exclusive and ``min_y`` *exclusive* / ``max_y`` inclusive
        (see the ``process_text_position`` docstring).

        On a **rotated** page (``/Rotate 90/180/270``) the user-space glyph
        origin ``(x, y)`` is folded into the page-rotation-adjusted *device*
        frame (y-down, upper-left origin) via :func:`_glyph_device_origin` — the
        exact coordinates upstream's ``processTextPosition`` tests
        ``Rectangle2D.contains`` against (Java L141: ``text.getX()`` /
        ``text.getY()``). The user-space region rectangle is mapped into that
        same device frame via :func:`_region_device_bounds`, and we apply
        ``Rectangle2D.contains``'s native ``min_x <= x < max_x &&
        min_y <= y < max_y`` directly.
        """
        suppress = self._suppress_duplicate_overlapping_text
        rotation = self._page_rotation
        if rotation != 0:
            dev_x, dev_y = _glyph_device_origin(
                x, y, rotation, self._page_width, self._page_height
            )
        for name in _hashmap_order(self._region_area.keys()):
            if rotation == 0:
                min_x, min_y, max_x, max_y = self._region_area[name]
                if not (min_x <= x < max_x and min_y < y <= max_y):
                    continue
            else:
                min_x, min_y, max_x, max_y = _region_device_bounds(
                    self._region_area[name],
                    rotation,
                    self._page_width,
                    self._page_height,
                )
                if not (min_x <= dev_x < max_x and min_y <= dev_y < max_y):
                    continue
            if suppress and self._is_suppressed_duplicate(text, x, y):
                # The shared page-wide map already recorded a coincident
                # same-text glyph (from an earlier region in HashMap order or
                # an earlier glyph). Drop it for THIS region — upstream's
                # base ``processTextPosition`` returns without binning.
                continue
            self._region_character_list[name].append(text)

    def _is_suppressed_duplicate(
        self, text: TextPosition, x: float, y: float
    ) -> bool:
        """Port of the ``suppressDuplicateOverlappingText`` block in
        ``PDFTextStripper.processTextPosition`` (Java L913-950).

        Consults the shared ``self._character_list_mapping``. Returns
        ``True`` when a previously-recorded same-text glyph lies within the
        coincidence tolerance (``width / len / 3.0`` per Java L932) of
        ``(x, y)`` — meaning upstream would suppress this offer. Otherwise
        records ``(x, y)`` under the glyph's unicode and returns ``False``.
        """
        text_character = text.get_unicode()
        same_text = self._character_list_mapping.setdefault(text_character, {})
        # Java L932: tolerance = width / textCharacter.length() / 3.0f.
        char_len = max(len(text_character), 1)
        tolerance = text.get_width() / char_len / 3.0
        # Java L934-944: scan the x-submap within [x-tol, x+tol) for any
        # recorded y within [y-tol, y+tol). subMap/subSet are half-open on
        # the upper bound; we match that with ``< x + tolerance`` etc.
        for rec_x, rec_ys in same_text.items():
            if not (x - tolerance <= rec_x < x + tolerance):
                continue
            for rec_y in rec_ys:
                if y - tolerance <= rec_y < y + tolerance:
                    return True
        # Java L945-950: not suppressed — record (x, y) and show.
        same_text.setdefault(x, set()).add(y)
        return False


def _glyph_device_origin(
    x: float,
    y: float,
    rotation: int,
    page_width: float,
    page_height: float,
) -> tuple[float, float]:
    """Fold a user-space glyph origin into the page-rotation-adjusted device
    frame, matching upstream ``TextPosition.getX()`` / ``getY()``.

    Mirrors the per-position transform ``PDFTextStripper._apply_page_rotation``
    applies for a rotated page: ``getX() == getXRot(rotation)`` and
    ``getY() == pageDim - getYLowerLeftRot(rotation)``. For a user point
    ``(x, y)`` (y-up) this resolves to

      * ``/Rotate 90``  -> ``(y, x)``
      * ``/Rotate 180`` -> ``(pw - x, y)``
      * ``/Rotate 270`` -> ``(ph - y, pw - x)``

    so a glyph lands at the same device coordinate the region rectangle is
    mapped to by :func:`_region_device_bounds`. The ``/Rotate 180`` Y is the
    user-space ``y`` unchanged: upstream's ``getY() = pageHeight -
    getYLowerLeftRot(180)`` and ``getYLowerLeftRot(180) = pageHeight - y``, so
    the two ``pageHeight`` terms cancel (the only rotation where the device Y is
    not a flip of the user Y).
    """
    if rotation == 90:
        return (y, x)
    if rotation == 180:
        return (page_width - x, y)
    if rotation == 270:
        return (page_height - y, page_width - x)
    return (x, y)


def _region_device_bounds(
    bounds: tuple[float, float, float, float],
    rotation: int,
    page_width: float,
    page_height: float,
) -> tuple[float, float, float, float]:
    """Map a user-space region rectangle into the page-rotation-adjusted
    *device* frame so it can be tested against folded glyph coordinates.

    ``bounds`` is ``(min_x, min_y, max_x, max_y)`` in PDF user space (y-up).
    The folded glyph frame matches upstream's ``TextPosition.getX()`` /
    ``getY()`` for the given page ``rotation`` (see
    ``PDFTextStripper._apply_page_rotation``): a user point ``(ux, uy)`` maps to

      * ``/Rotate 90``  -> ``(uy, ux)``
      * ``/Rotate 180`` -> ``(pw - ux, uy)``
      * ``/Rotate 270`` -> ``(ph - uy, pw - ux)``

    (matching :func:`_glyph_device_origin` exactly, including the ``/Rotate 180``
    Y that stays ``uy`` because upstream's two ``pageHeight`` flips cancel.)

    We transform the rectangle's two opposite corners and renormalize so the
    result is ``(min_x, min_y, max_x, max_y)`` in the device frame. The caller
    then applies ``Rectangle2D.contains``'s native half-open test directly.
    """
    min_x, min_y, max_x, max_y = bounds

    def _to_device(ux: float, uy: float) -> tuple[float, float]:
        if rotation == 90:
            return (uy, ux)
        if rotation == 180:
            return (page_width - ux, uy)
        if rotation == 270:
            return (page_height - uy, page_width - ux)
        return (ux, uy)

    dx0, dy0 = _to_device(min_x, min_y)
    dx1, dy1 = _to_device(max_x, max_y)
    return (min(dx0, dx1), min(dy0, dy1), max(dx0, dx1), max(dy0, dy1))


def _java_string_hash_code(s: str) -> int:
    """Compute ``java.lang.String.hashCode()`` for ``s``.

    JLS-specified (stable across all JVMs):
    ``h = s[0]*31^(n-1) + s[1]*31^(n-2) + ... + s[n-1]`` evaluated in 32-bit
    signed ``int`` arithmetic (overflow wraps). The result is returned as a
    Python int in the signed 32-bit range. Java iterates UTF-16 code units;
    for the BMP region names this loop matches by iterating Python code
    points (a non-BMP name would need surrogate-pair expansion, but region
    names are short ASCII identifiers in practice).
    """
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    # Reinterpret as signed 32-bit.
    if h >= 0x80000000:
        h -= 0x100000000
    return h


def _java_hashmap_index(key: str, capacity: int) -> int:
    """Bucket index for ``key`` in a ``java.util.HashMap`` of the given
    table ``capacity``.

    HashMap spreads the hash with ``h ^ (h >>> 16)`` (Java 8+ ``HashMap.hash``)
    then masks with ``capacity - 1`` (capacity is always a power of two).
    The ``>>> 16`` is an unsigned shift, so operate on the unsigned 32-bit
    form of the hash.
    """
    h = _java_string_hash_code(key) & 0xFFFFFFFF
    h ^= h >> 16
    return h & (capacity - 1)


def _java_hashmap_capacity(count: int) -> int:
    """Table capacity a default ``java.util.HashMap`` settles at after
    ``count`` distinct ``put`` calls.

    Default initial capacity is 16, load factor 0.75 — the table doubles
    when ``size > capacity * 0.75``. ``regionArea`` is ``new HashMap<>()``
    (PDFTextStripperByArea.java L36) and filled by ``addRegion`` puts, so
    its capacity is determined solely by the region count. For the realistic
    region counts (<= 12) capacity stays 16; the loop below handles larger
    sets faithfully so a future many-region caller still matches.
    """
    capacity = 16
    # Resize threshold is capacity*0.75; HashMap resizes when size EXCEEDS it
    # (size > threshold) after the put that crosses the boundary.
    while count > capacity * 3 // 4:
        capacity <<= 1
    return capacity


def _hashmap_order(keys) -> list[str]:  # noqa: ANN001 - keys is a str iterable
    """Return ``keys`` in ``java.util.HashMap`` iteration order.

    HashMap iterates buckets ``0 .. capacity-1``; within a bucket, entries are
    a linked list in insertion order (no treeification below 8 colliding
    entries, which region-name sets never reach). We therefore sort by
    ``(bucket_index, insertion_position)``. This reproduces the *non-spec but
    deterministic* order upstream's ``regionArea.forEach`` (and ``keySet``)
    walks — verified empirically against the live PDFBox oracle for several
    region-name sets (wave 1492): the surviving overlap region is fixed by the
    region name's ``String.hashCode`` bucket, independent of insertion order.

    NOTE: this is a deliberate Java-emulation. We accept the brittleness
    (it assumes default HashMap capacity growth and no treeification) because
    it is the only faithful way to pick the surviving region for an
    overlap glyph; the alternative is a documented divergence (rejected in
    favour of convergence — see ``CHANGES.md``).
    """
    key_list = list(keys)
    capacity = _java_hashmap_capacity(len(key_list))
    return sorted(
        key_list,
        key=lambda k: (_java_hashmap_index(k, capacity), key_list.index(k)),
    )


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
