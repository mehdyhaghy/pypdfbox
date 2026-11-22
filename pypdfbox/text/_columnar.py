"""Columnar text layout for :class:`PDFTextStripper` (default ``get_text`` path).

The object pipeline builds one :class:`TextPosition` per glyph and runs the
duplicate filter and ``writePage``'s line / word / paragraph logic over those
objects. For the common page (upright text on an unrotated page, stock hooks,
no ``/ActualText``) this module keeps the glyphs of :meth:`_emit_plain`'s
upright branch as columns instead (cursor, end offset, text, run record) and
lays the page out from arrays: the geometry is derived with numpy in float32
(IEEE single, the same values as the per-value narrowing of the object path),
the duplicate filter and the word metrics are vectorized, and only the line
state machine and the word-average recurrence run as tight loops over floats.

Positions built by the object path on the same page (a string whose bytes
the glyph memo has not seen yet, a non-plain text matrix, ...) are taken over
as they are. Anything the columnar layout does not handle makes
:func:`format_page` return ``None``; the caller then materializes every
position (:meth:`PageColumns.merge`) and runs the object pipeline, so the
output is the same either way. :class:`TextPosition` objects for columnar
glyphs are only built when something asks for them
(``get_characters_by_article`` and friends).
"""

from __future__ import annotations

from array import array
from typing import TYPE_CHECKING

import numpy as np

from .text_position import _IS_DIACRITIC, TextPosition

if TYPE_CHECKING:
    from .pdf_text_stripper import PDFTextStripper

_FLT_MAX = 3.4028234663852886e38
_F32 = np.float32
_F64 = np.float64


def _n32(values: np.ndarray) -> np.ndarray:
    """Narrow float64 values to float32 and back (the C ``(float)`` cast)."""
    return values.astype(_F32).astype(_F64)


class PageColumns:
    """The glyphs of one page that :meth:`_emit_plain` kept as columns.

    ``x`` holds each glyph's text-space cursor (float32 values), ``e`` the
    cursor-independent end offset ``f32(dx * tm_a)``, ``p`` the unicode
    piece. ``segs`` has one ``(first glyph, positions before it, run id,
    glyph_y, record)`` entry per string, ``recs`` the per-call run records
    ``(ctx, font_name, font, resolved_font_name, page_width_raw)``.
    """

    __slots__ = ("x", "e", "p", "segs", "recs", "_last", "_geometry")

    def __init__(self) -> None:
        self.x: list[float] = []
        self.e: list[float] = []
        self.p: list[str] = []
        self.segs: list[tuple[int, int, int, float, int]] = []
        self.recs: list[tuple] = []
        self._last: tuple | None = None
        self._geometry: tuple | None = None

    def record(self, ctx: tuple, font_name, font, resolved_font_name, page_width_raw) -> int:
        """The index of the run record for these values (the last one when
        they are the very same objects)."""
        last = self._last
        if (
            last is not None
            and last[0] is ctx
            and last[1] is font_name
            and last[3] is resolved_font_name
            and last[4] is page_width_raw
        ):
            return len(self.recs) - 1
        rec = (ctx, font_name, font, resolved_font_name, page_width_raw)
        self.recs.append(rec)
        self._last = rec
        return len(self.recs) - 1

    # ------------------------------------------------------------------

    def geometry(self) -> tuple:
        """Per-glyph arrays: ``(seg index, origin_x, origin_y, end_x,
        dx_display, device_x, device_y, device_end_x, geometry_y,
        geometry_width, finite)``, all float64 holding float32 values."""
        if self._geometry is not None:
            return self._geometry
        n = len(self.x)
        segs = self.segs
        starts = np.fromiter((s[0] for s in segs), dtype=np.int64, count=len(segs))
        counts = np.diff(np.append(starts, n))
        seg_of = np.repeat(np.arange(len(segs)), counts)
        x = np.asarray(self.x, dtype=_F64)
        e = np.asarray(self.e, dtype=_F64)
        gy_seg = np.fromiter((s[3] for s in segs), dtype=_F64, count=len(segs))
        rec_seg = np.fromiter((s[4] for s in segs), dtype=np.int64, count=len(segs))
        recs = self.recs
        crop_llx = np.fromiter((r[0][13] for r in recs), dtype=_F64, count=len(recs))
        crop_lly = np.fromiter((r[0][14] for r in recs), dtype=_F64, count=len(recs))
        page_h = np.fromiter((r[0][30] for r in recs), dtype=_F64, count=len(recs))
        rec_of = rec_seg[seg_of]
        llx = crop_llx[rec_of]
        lly = crop_lly[rec_of]
        with np.errstate(all="ignore"):
            # ``origin = glyph * c0 + c6`` with the identity CTM of a plain
            # context (the ``+ 0.0`` turns a negative zero positive).
            origin_x = x + 0.0
            origin_y = gy_seg[seg_of] + 0.0
            end_x = _n32(e + x) + 0.0
            dx_display = _n32(end_x - origin_x)
            has_llx = llx != 0.0
            device_x = np.where(has_llx, _n32(origin_x - llx), origin_x)
            device_end_x = np.where(has_llx, _n32(end_x - llx), end_x)
            device_y = np.where(lly != 0.0, _n32(origin_y - lly), origin_y)
            geometry_y = _n32(page_h[rec_of] - device_y)
            geometry_width = np.abs(np.where(has_llx, _n32(device_end_x - device_x), dx_display))
            finite = bool(
                np.isfinite(device_x).all()
                and np.isfinite(device_end_x).all()
                and np.isfinite(geometry_y).all()
                and np.isfinite(dx_display).all()
            )
        self._geometry = (
            seg_of,
            origin_x,
            origin_y,
            end_x,
            dx_display,
            device_x,
            device_y,
            device_end_x,
            geometry_y,
            geometry_width,
            finite,
        )
        return self._geometry

    def materialize(self, indices: list[int] | None = None) -> list[TextPosition]:
        """The :class:`TextPosition` objects :meth:`_emit_plain` would have
        built for the columnar glyphs ``indices`` (all when ``None``)."""
        (
            seg_of,
            origin_x,
            origin_y,
            _end_x,
            dx_display,
            device_x,
            device_y,
            device_end_x,
            geometry_y,
            geometry_width,
            _finite,
        ) = self.geometry()
        if indices is None:
            indices = range(len(self.x))
        seg_l = seg_of.tolist()
        ox = origin_x.tolist()
        oy = origin_y.tolist()
        dxd = dx_display.tolist()
        dvx = device_x.tolist()
        dvy = device_y.tolist()
        dvex = device_end_x.tolist()
        gyl = geometry_y.tolist()
        gwl = geometry_width.tolist()
        xs = self.x
        pieces = self.p
        segs = self.segs
        recs = self.recs
        out: list[TextPosition] = []
        append = out.append
        for i in indices:
            seg = segs[seg_l[i]]
            ctx, font_name, font, resolved_font_name, page_width_raw = recs[seg[4]]
            glyph_y = seg[3]
            gw = gwl[i]
            gy = gyl[i]
            dx = dvx[i]
            position = TextPosition(
                pieces[i],
                ox[i],
                oy[i],
                ctx[20],
                font_name,
                font,
                resolved_font_name,
                gw,
                ctx[22],
                ctx[3],
                ctx[4],
                ctx[19],
                0.0,
                page_width_raw,
                ctx[15],
                [ctx[11], ctx[12], ctx[16], ctx[17], xs[i], glyph_y],
                ctx[28],
                ctx[21],
                [dxd[i]],
                False,
                dx,
                dvy[i],
                dvex[i],
                # ``end_y`` equals ``origin_y`` in a plain context.
                oy[i] if not ctx[14] else dvy[i],
                ctx[1],
            )
            position._run_id = seg[2]
            position._java_geometry = (0.0, dx, gy, gw, dx, gy, gw, ctx[31], ctx[32])
            append(position)
        return out

    def order(self, n_objects: int) -> tuple[np.ndarray, np.ndarray]:
        """Page-order slots of the columnar glyphs and of the ``n_objects``
        positions the object path appended, as two index arrays."""
        n = len(self.x)
        segs = self.segs
        starts = np.fromiter((s[0] for s in segs), dtype=np.int64, count=len(segs))
        before = np.fromiter((s[1] for s in segs), dtype=np.int64, count=len(segs))
        counts = np.diff(np.append(starts, n))
        before_g = np.repeat(before, counts)
        col_slot = np.arange(n, dtype=np.int64) + before_g
        objs = np.arange(n_objects, dtype=np.int64)
        obj_slot = objs + np.searchsorted(before_g, objs, side="right")
        return col_slot, obj_slot

    def merge(self, objects: list[TextPosition]) -> list[TextPosition]:
        """Every position of the page in emission order, the columnar ones
        materialized."""
        built = self.materialize()
        if not objects:
            return built
        col_slot, obj_slot = self.order(len(objects))
        merged: list = [None] * (len(built) + len(objects))
        for slot, pos in zip(col_slot.tolist(), built, strict=True):
            merged[slot] = pos
        for slot, pos in zip(obj_slot.tolist(), objects, strict=True):
            merged[slot] = pos
        return merged


class LazyArticles:
    """``charactersByArticle`` of a columnar page, built on first use."""

    __slots__ = ("cols", "objects", "slots", "value")

    def __init__(self, cols: PageColumns, objects: list, slots: list) -> None:
        self.cols = cols
        self.objects = objects
        # Per article: page-order sources (``>= 0`` a columnar glyph,
        # ``< 0`` the object ``~i``).
        self.slots = slots
        self.value: list[list[TextPosition]] | None = None

    def get(self) -> list[list[TextPosition]]:
        if self.value is None:
            cols = self.cols
            objects = self.objects
            groups = []
            for sources in self.slots:
                col_ids = [s for s in sources if s >= 0]
                built = iter(cols.materialize(col_ids)) if col_ids else iter(())
                groups.append([next(built) if s >= 0 else objects[~s] for s in sources])
            self.value = groups
            self.cols = None
            self.objects = None
        return self.value


# ----------------------------------------------------------------------
# Page layout
# ----------------------------------------------------------------------


def _font_or_size_changed(tf1, font1, tf2, font2) -> bool:
    """``PDFTextStripper._java_font_or_size_changed`` for ``Tf`` sizes that
    are set (current ``tf1`` / ``font1``, last ``tf2`` / ``font2``)."""
    if tf1 != tf2:
        return True
    if font1 is font2:
        return False
    name1 = font1.get_name() if font1 is not None else None
    name2 = font2.get_name() if font2 is not None else None
    if name1 is not None:
        return name1 != name2
    if name2 is not None:
        return True
    return hash(font1) != hash(font2)


def _visual_piece(piece: str) -> str:
    """``TextPosition.get_visually_ordered_unicode`` of a piece."""
    if len(piece) <= 1:
        return piece
    return TextPosition(piece, 0.0, 0.0, 0.0).get_visually_ordered_unicode()


def _is_diacritic(piece: str) -> bool:
    if len(piece) != 1:
        return False
    known = _IS_DIACRITIC.get(piece)
    if known is None:
        known = TextPosition(piece, 0.0, 0.0, 0.0).is_diacritic()
    return known


def _dedup_keep(ids: np.ndarray, x: np.ndarray, y: np.ndarray, w: np.ndarray, lengths: np.ndarray):
    """Indices of the glyphs the duplicate filter shows, in page order, or
    ``None`` when the page needs the object filter.

    Upstream suppresses a glyph when an earlier *shown* glyph with the same
    text lies in the half-open window ``[v - tol, v + tol)`` on both axes,
    ``tol = f32(width / len(text) / 3)``. A grid with cells wider than every
    window pairs each glyph with the earlier same-text glyphs of the
    neighbouring cells; the exact window test runs on those pairs,
    vectorized, and only glyphs with a hit are decided one by one (a hit
    counts only while its glyph is shown).
    """
    n = len(ids)
    if n == 0:
        return np.arange(0)
    if (lengths == 0).any():
        return None
    with np.errstate(all="ignore"):
        tol = _n32(w / lengths / 3.0)
    if not np.isfinite(tol).all():
        return None
    max_tol = float(tol.max())
    idx = np.arange(n)
    if max_tol <= 0.0:
        # Every window is empty.
        return idx
    with np.errstate(all="ignore"):
        x_lo = _n32(x - tol)
        x_hi = _n32(x + tol)
        y_lo = _n32(y - tol)
        y_hi = _n32(y + tol)
    # Cells at least as wide as every window: a window then overlaps one or
    # two cells per axis, and an origin inside it lies in one of those
    # (``floor(v / cell)`` is monotonic).
    cell = 2.5 * max_tol
    cx = np.floor(x / cell)
    cy = np.floor(y / cell)
    cx_lo = np.floor(x_lo / cell)
    cx_hi = np.floor(x_hi / cell)
    cy_lo = np.floor(y_lo / cell)
    cy_hi = np.floor(y_hi / cell)
    base_x = float(cx_lo.min()) - 1.0
    base_y = float(cy_lo.min()) - 1.0
    sx = int(cx_hi.max() - base_x) + 2
    sy = int(cy_hi.max() - base_y) + 2
    if float(ids.max() + 1) * sx * sy >= 2.0**62:
        return None
    id_base = ids.astype(np.int64) * sy
    key = (id_base + (cy - base_y).astype(np.int64)) * sx + (cx - base_x).astype(np.int64)
    k_lo_lo = (id_base + (cy_lo - base_y).astype(np.int64)) * sx + (cx_lo - base_x).astype(np.int64)
    x_two = cx_hi != cx_lo
    y_two = cy_hi != cy_lo
    order = np.argsort(key, kind="stable")
    sorted_key = key[order]
    hit_i = []
    hit_j = []
    budget = 64 * n + 4096
    for which, nk in (
        (None, k_lo_lo),
        (x_two, k_lo_lo + 1),
        (y_two, k_lo_lo + sx),
        (x_two & y_two, k_lo_lo + sx + 1),
    ):
        if which is None:
            qi = idx
        else:
            qi = np.flatnonzero(which)
            if not len(qi):
                continue
            nk = nk[qi]
        lo = np.searchsorted(sorted_key, nk, "left")
        cnt = np.searchsorted(sorted_key, nk, "right") - lo
        total = int(cnt.sum())
        if not total:
            continue
        budget -= total
        if budget < 0:
            return None
        ii = np.repeat(qi, cnt)
        jj = order[np.repeat(lo - (np.cumsum(cnt) - cnt), cnt) + np.arange(total)]
        earlier = jj < ii
        ii = ii[earlier]
        jj = jj[earlier]
        xj = x[jj]
        yj = y[jj]
        hit = (x_lo[ii] <= xj) & (xj < x_hi[ii]) & (y_lo[ii] <= yj) & (yj < y_hi[ii])
        if hit.any():
            hit_i.append(ii[hit])
            hit_j.append(jj[hit])
    if not hit_i:
        return idx
    hi = np.concatenate(hit_i)
    hj = np.concatenate(hit_j)
    by_i = np.lexsort((hj, hi))
    shown = np.ones(n, dtype=bool)
    current = -1
    suppressed = False
    for i, j in zip(hi[by_i].tolist(), hj[by_i].tolist(), strict=True):
        if i != current:
            if suppressed:
                shown[current] = False
            current = i
            suppressed = False
        if not suppressed and shown[j]:
            suppressed = True
    if suppressed:
        shown[current] = False
    return np.flatnonzero(shown)


def format_page(
    stripper: PDFTextStripper, cols: PageColumns, objects: list[TextPosition]
) -> str | None:
    """The page text :meth:`PDFTextStripper._format_positions` would write,
    or ``None`` when the page needs the object pipeline."""
    s = stripper
    if s._sort_by_position or s._flip_axes:
        return None
    n_col = len(cols.x)
    (
        _seg_of,
        _ox,
        _oy,
        _ex,
        _dxd,
        device_x,
        _dvy,
        _dvex,
        geometry_y,
        geometry_width,
        finite,
    ) = cols.geometry()
    if not finite:
        return None
    seg_of = _seg_of
    recs = cols.recs
    segs = cols.segs
    rec_seg = np.fromiter((sg[4] for sg in segs), dtype=np.int64, count=len(segs))
    rec_of = rec_seg[seg_of]
    rec_h = np.fromiter((r[0][31] for r in recs), dtype=_F64, count=len(recs))
    rec_ws = np.fromiter((r[0][32] for r in recs), dtype=_F64, count=len(recs))
    # Font / size groups: ``(Tf size, font)`` per record.
    group_of_key: dict = {}
    group_info: list[tuple] = []
    rec_group = []
    for r in recs:
        tf = r[0][1]
        if tf != tf:
            return None
        k = (tf, id(r[2]))
        g = group_of_key.get(k)
        if g is None:
            g = group_of_key[k] = len(group_info)
            group_info.append((tf, r[2]))
        rec_group.append(g)
    rec_group_a = np.asarray(rec_group, dtype=np.int64)
    n_obj = len(objects)
    pieces: list[str] = cols.p
    if n_obj:
        # Take the object path's positions over, when they fit.
        ox_l = []
        oy_l = []
        ow_l = []
        oh_l = []
        ows_l = []
        on_l = []
        og_l = []
        op_l = []
        for pos in objects:
            if (
                type(pos) is not TextPosition
                or pos.in_actual_text_span
                or pos.from_actual_text
                or pos.tf_font_size is None
                or pos.tf_font_size != pos.tf_font_size
            ):
                return None
            g = pos._java_geometry
            if g is None:
                return None
            if g[0] != 0.0 or g[4] != g[1] or g[5] != g[2] or g[6] != g[3]:
                return None
            widths = pos.individual_widths
            if widths is None:
                return None
            k = (pos.tf_font_size, id(pos.font))
            grp = group_of_key.get(k)
            if grp is None:
                grp = group_of_key[k] = len(group_info)
                group_info.append((pos.tf_font_size, pos.font))
            ox_l.append(g[1])
            oy_l.append(g[2])
            ow_l.append(g[3])
            oh_l.append(g[7])
            ows_l.append(g[8])
            on_l.append(len(widths) or 1)
            og_l.append(grp)
            op_l.append(pos.text)
        col_slot, obj_slot = cols.order(n_obj)
        n = n_col + n_obj
        gx = np.empty(n)
        gy = np.empty(n)
        gw = np.empty(n)
        gh = np.empty(n)
        gws = np.empty(n)
        gnw = np.empty(n)
        grp_of = np.empty(n, dtype=np.int64)
        src = np.empty(n, dtype=np.int64)
        gx[col_slot] = device_x
        gx[obj_slot] = ox_l
        gy[col_slot] = geometry_y
        gy[obj_slot] = oy_l
        gw[col_slot] = geometry_width
        gw[obj_slot] = ow_l
        gh[col_slot] = rec_h[rec_of]
        gh[obj_slot] = oh_l
        gws[col_slot] = rec_ws[rec_of]
        gws[obj_slot] = ows_l
        gnw[col_slot] = 1.0
        gnw[obj_slot] = on_l
        grp_of[col_slot] = rec_group_a[rec_of]
        grp_of[obj_slot] = og_l
        src[col_slot] = np.arange(n_col)
        src[obj_slot] = ~np.arange(n_obj)
        merged_p = np.empty(n, dtype=object)
        merged_p[col_slot] = pieces
        merged_p[obj_slot] = op_l
        pieces = merged_p.tolist()
        if not (np.isfinite(gx).all() and np.isfinite(gy).all() and np.isfinite(gw).all()):
            return None
    else:
        n = n_col
        gx = device_x
        gy = geometry_y
        gw = geometry_width
        gh = rec_h[rec_of]
        gws = rec_ws[rec_of]
        gnw = None
        grp_of = rec_group_a[rec_of]
        src = None
    if not (np.isfinite(gh).all() and np.isfinite(gws).all()):
        return None

    # Text ids (the index of each text's first glyph).
    first_of: dict[str, int] = {}
    ids_l = list(map(first_of.setdefault, pieces, range(n), strict=True))
    ids = np.asarray(ids_l, dtype=np.int64)

    # Duplicate filter.
    if s._suppress_duplicate_overlapping_text:
        lengths = np.asarray([len(pieces[i]) for i in first_of.values()], dtype=_F64)
        # Per glyph: length of its text.
        id_rank = np.zeros(n, dtype=np.int64)
        uniq_first = np.fromiter(first_of.values(), dtype=np.int64, count=len(first_of))
        id_rank[uniq_first] = np.arange(len(uniq_first))
        glyph_len = lengths[id_rank[ids]]
        keep = _dedup_keep(ids, gx, gy, gw, glyph_len)
        if keep is None:
            return None
    else:
        keep = np.arange(n)

    # Articles: beads need the object partition.
    rects: list = []
    if s._should_separate_by_beads and s._active_page is not None:
        rects = s._bead_rectangles_java(s._active_page)
    if rects:
        return None

    # Diacritics need the object merge.
    diacritic_texts = [t for t in first_of if _is_diacritic(t)]
    if diacritic_texts:
        flagged = np.zeros(n, dtype=bool)
        for t in diacritic_texts:
            flagged |= ids == first_of[t]
        if flagged[keep].any():
            return None

    # The glyphs ``writePage`` walks.
    seq = keep
    if s._ignore_content_stream_space_glyphs and " " in first_of:
        seq = seq[ids[seq] != first_of[" "]]
    text = _write_page(s, seq, pieces, ids, first_of, gx, gy, gw, gh, gws, gnw, grp_of, group_info)
    if text is None:
        return None

    # ``charactersByArticle``: one slot, or the last of the bead slots.
    slot_count = max(1, s._article_slot_count)
    s._article_slot_count = slot_count
    keep_l = keep.tolist() if src is None else src[keep].tolist()
    slots: list[list[int]] = [[] for _ in range(slot_count)]
    slots[slot_count - 1 if s._should_separate_by_beads else 0] = keep_l
    s._set_lazy_articles(LazyArticles(cols, objects, slots))
    return text


def _write_page(s, seq, pieces, ids, first_of, gx, gy, gw, gh, gws, gnw, grp_of, group_info):
    """``PDFTextStripper._write_articles`` for one non-empty article (the
    others empty) over the glyph columns ``seq``."""
    from .pdf_text_stripper import _F32_TENTH

    slot_count = max(1, s._article_slot_count)
    chunks: list[str] = []
    sink = chunks.append
    m = len(seq)

    def write_empty_articles(count: int) -> None:
        for _ in range(count):
            if s._article_start:
                s.write_article_start(sink)
            if s._article_end:
                s.write_article_end(sink)

    # Empty slots before the glyph slot.
    glyph_slot = slot_count - 1 if s._should_separate_by_beads else 0
    write_empty_articles(glyph_slot)
    if s._article_start:
        s.write_article_start(sink)
    if m:
        whole = m == len(gx)
        x32 = (gx if whole else gx[seq]).astype(_F32)
        y32 = (gy if whole else gy[seq]).astype(_F32)
        w32 = (gw if whole else gw[seq]).astype(_F32)
        h32 = (gh if whole else gh[seq]).astype(_F32)
        ws32 = (gws if whole else gws[seq]).astype(_F32)
        grp = grp_of if whole else grp_of[seq]
        seq_ids = ids if whole else ids[seq]
        spacing_tolerance = _F32(s._spacing_tolerance)
        average_char_tolerance = _F32(s._average_char_tolerance)
        tenth = _F32(_F32_TENTH)
        with np.errstate(all="ignore"):
            if gnw is None:
                cw32 = w32
            else:
                cw32 = ((gw if whole else gw[seq]) / (gnw if whole else gnw[seq])).astype(_F32)
            # ``deltaSpace`` per glyph, from its and the last glyph's
            # ``widthOfSpace`` (the page's first glyph has none).
            lws32 = np.empty(m, dtype=_F32)
            lws32[0] = -1.0
            lws32[1:] = ws32[:-1]
            delta_space = np.where(
                (ws32 == 0) | np.isnan(ws32),
                _F32(_FLT_MAX),
                np.where(
                    lws32 < 0,
                    ws32 * spacing_tolerance,
                    ((ws32 + lws32) / _F32(2.0)) * spacing_tolerance,
                ),
            )
            space_limit = ws32 + delta_space
            x_distance = np.empty(m, dtype=_F32)
            x_distance[0] = 0.0
            x_distance[1:] = x32[1:] - x32[:-1]
            x_reset = (x_distance > space_limit) | (-x_distance > space_limit)
            x_reset[0] = False
            new_end = x32 + w32
        if (new_end == -1.0).any():
            return None
        # Average character width: reset at a font or size change.
        resets: list[int] = []
        if m > 1:
            changed = np.flatnonzero(grp[1:] != grp[:-1]) + 1
            if len(changed):
                memo: dict = {}
                g_l = grp.tolist()
                for i in changed.tolist():
                    pair = (g_l[i], g_l[i - 1])
                    r = memo.get(pair)
                    if r is None:
                        tf1, f1 = group_info[pair[0]]
                        tf2, f2 = group_info[pair[1]]
                        r = memo[pair] = _font_or_size_changed(tf1, f1, tf2, f2)
                    if r:
                        resets.append(i)
        avg32 = _average_widths(cw32, resets)
        with np.errstate(all="ignore"):
            delta_cw = avg32 * average_char_tolerance
            prev_end = np.empty(m, dtype=_F32)
            prev_end[0] = -1.0
            prev_end[1:] = new_end[:-1]
            expected = prev_end + np.where(delta_cw < delta_space, delta_cw, delta_space)
            sep = (expected != _F32(-_FLT_MAX)) & (expected < x32)
        sep[0] = False
        # Line breaks (and the line height at each).
        breaks, break_heights = _line_breaks(y32, h32, tenth, x_reset)
        separator = s._word_separator
        firsts = np.fromiter(first_of.values(), dtype=np.int64, count=len(first_of))
        if separator:
            ends_ok = np.zeros(len(gx), dtype=bool)
            ends_ok[firsts] = [not t.endswith(separator) for t in first_of]
            sep[1:] &= ends_ok[seq_ids[:-1]]
        if breaks:
            sep[np.asarray(breaks)] = False
        # Line text.
        if all(len(t) <= 1 for t in first_of):
            toks = pieces if whole else list(map(pieces.__getitem__, seq.tolist()))
        else:
            visual = {first: _visual_piece(t) for t, first in first_of.items()}
            toks = list(map(visual.__getitem__, seq_ids.tolist()))
        lines = _line_texts(s, toks, np.flatnonzero(sep).tolist(), [0, *breaks, m], separator)
        # Paragraph start of the page.
        s.write_paragraph_start(sink)
        if breaks:
            _write_breaks(s, sink, lines, breaks, break_heights, seq, pieces, x32, y32, w32, ws32)
        sink(lines[-1])
        s.write_paragraph_end(sink)
    if s._article_end:
        s.write_article_end(sink)
    write_empty_articles(slot_count - 1 - glyph_slot)
    return "".join(chunks)


def _write_breaks(s, sink, lines, breaks, break_heights, seq, pieces, x32, y32, w32, ws32):
    """Each line but the last, then the separators ``handleLineSeparation``
    writes after it (``_java_is_paragraph_separation`` on the break glyph)."""
    drop = float(_F32(s.get_drop_threshold()))
    indent = float(_F32(s.get_indent_threshold()))
    multiply = s._java_multiply_float
    patterns = None
    bi = np.asarray(breaks)
    starts = np.empty(len(bi), dtype=np.int64)
    starts[0] = 0
    starts[1:] = bi[:-1]
    with np.errstate(all="ignore"):
        y_gaps = np.abs(y32[bi] - y32[bi - 1]).astype(_F64).tolist()
        x_gaps = (x32[bi] - x32[starts]).astype(_F64).tolist()
    wsl = ws32[bi].astype(_F64).tolist()
    wl = w32[bi].astype(_F64).tolist()
    # The last line start's ``PositionWrapper`` flags.
    ls_paragraph = True
    ls_hanging = False
    line_start = 0
    for li, i in enumerate(breaks):
        sink(lines[li])
        result = False
        hanging = False
        x_gap = x_gaps[li]
        ws = wsl[li]
        if y_gaps[li] > multiply(drop, break_heights[li]):
            result = True
        elif x_gap > multiply(indent, ws):
            if not ls_paragraph:
                result = True
            else:
                hanging = True
        elif x_gap < -ws:
            if not ls_paragraph:
                result = True
        elif abs(x_gap) < multiply(0.25, wl[li]):
            if ls_hanging:
                hanging = True
            elif ls_paragraph:
                if patterns is None:
                    patterns = s.get_list_item_patterns()
                li_pattern = s.match_pattern(pieces[int(seq[line_start])], patterns)
                if li_pattern is not None:
                    current_pattern = s.match_pattern(pieces[int(seq[i])], patterns)
                    if li_pattern is current_pattern:
                        result = True
        s.write_line_separator(sink)
        if result:
            s.write_paragraph_separator(sink)
        line_start = i
        ls_paragraph = result
        ls_hanging = hanging


_MIN_NORMAL = 2.0**-126


def _average_widths(cw32: np.ndarray, resets: list[int]) -> np.ndarray:
    """``averageCharWidth`` per glyph: the running float32 mean
    ``f32(previous + width) / 2``, restarting at the article start and at
    ``resets``.

    Halving the narrowed sum is exact unless it is subnormal; the result is
    checked for that and recomputed narrowing the halves too.
    """
    cw = cw32.astype(_F64).tolist()
    bounds = [0, *resets, len(cw)]
    out: list[float] = []
    append = out.append
    scratch = array("f", bytes(8))
    for k in range(len(bounds) - 1):
        it = iter(cw[bounds[k] : bounds[k + 1]])
        a = next(it)
        append(a)
        for c in it:
            scratch[0] = a + c
            a = scratch[0] * 0.5
            append(a)
    avg = np.asarray(out, dtype=_F32)
    if ((avg != 0) & (np.abs(avg) < _MIN_NORMAL)).any():
        out = []
        append = out.append
        for k in range(len(bounds) - 1):
            it = iter(cw[bounds[k] : bounds[k + 1]])
            a = next(it)
            append(a)
            for c in it:
                scratch[0] = a + c
                scratch[0] = scratch[0] / 2
                a = scratch[0]
                append(a)
        avg = np.asarray(out, dtype=_F32)
    return avg


def _line_breaks(y32: np.ndarray, h32: np.ndarray, tenth, x_reset: np.ndarray):
    """The glyphs that start a new line in ``writePage``, and the line
    height (``maxHeightForLine``) each break closes.

    The line state is ``(maxYForLine, maxHeightForLine)``, running maxima
    reset at a break and where the ``x`` jump exceeds the space limit. In a
    run of glyphs with the same ``y`` and height ``(y, h)``, only the first
    two can break: the later ones see a state at least as overlapping as the
    second did (both maxima are at least ``y`` and ``h`` by then), and they
    leave it unchanged. A jump resets the state to ``(y, h)``, after which
    jumps change nothing, so of the later glyphs only the first jump is
    visited.
    """
    m = len(y32)
    with np.errstate(all="ignore"):
        low = (y32 - tenth).astype(_F64)
        high = (y32 + tenth).astype(_F64)
        y_minus_h = (y32 - h32).astype(_F64)
    run_start = np.empty(m, dtype=bool)
    run_start[0] = True
    run_start[1:] = (y32[1:] != y32[:-1]) | (h32[1:] != h32[:-1])
    visit = run_start.copy()
    visit[1:] |= run_start[:-1]
    later_jump = np.flatnonzero(x_reset & ~visit)
    if len(later_jump):
        run_of = np.cumsum(run_start)
        _runs, first = np.unique(run_of[later_jump], return_index=True)
        visit[later_jump[first]] = True
    idx = np.flatnonzero(visit)
    breaks: list[int] = []
    heights: list[float] = []
    scratch = array("f", bytes(8))
    neg = -_FLT_MAX
    it = zip(
        idx.tolist(),
        y32[idx].astype(_F64).tolist(),
        h32[idx].astype(_F64).tolist(),
        low[idx].tolist(),
        high[idx].tolist(),
        y_minus_h[idx].tolist(),
        x_reset[idx].tolist(),
        strict=True,
    )
    # The first glyph only starts the state.
    _i, max_y, max_h, _lo, _hi, _ymh, _xr = next(it)
    if max_h < -1.0:
        max_h = -1.0
    scratch[0] = max_y - max_h
    max_y_minus_h = scratch[0]
    for i, yi, hi, lo, hi_b, ymh, xr in it:
        if not (lo < max_y < hi_b) and not (
            (max_y <= yi and max_y >= ymh) or (yi <= max_y and yi >= max_y_minus_h)
        ):
            breaks.append(i)
            heights.append(max_h)
            max_y = neg
            max_h = -1.0
        if xr:
            max_y = neg
            max_h = -1.0
        changed = False
        if yi > max_y:
            changed = True
            max_y = yi
        if hi > max_h:
            max_h = hi
            changed = True
        if changed:
            scratch[0] = max_y - max_h
            max_y_minus_h = scratch[0]
    return breaks, heights


def _line_texts(
    s, toks: list[str], sep_idx: list[int], bounds: list[int], separator: str
) -> list[str]:
    """Each line's text as ``_write_bare_line`` writes it."""
    lines: list[str] = []
    si = 0
    n_sep = len(sep_idx)
    normalize_word = s.normalize_word
    join = "".join
    for li in range(len(bounds) - 1):
        a = bounds[li]
        b = bounds[li + 1]
        words: list[str] = []
        start = a
        while si < n_sep and sep_idx[si] < b:
            j = sep_idx[si]
            words.append(join(toks[start:j]))
            start = j
            si += 1
        last = join(toks[start:b])
        if last:
            words.append(last)
        line = separator.join(words)
        if not line.isascii():
            line = separator.join([w if w.isascii() else normalize_word(w) for w in words])
        lines.append(line)
    return lines
