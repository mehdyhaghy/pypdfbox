"""Fuzz / branch-coverage hammer for :class:`PDFTextStripperByArea`.

Wave 1571 (Agent D). Targets the ~18% of
``pypdfbox/text/pdf_text_stripper_by_area.py`` left uncovered by the
hand-written + clipping suites: region-lifecycle edge cases, glyphs on /
straddling / outside a region boundary, two overlapping regions, the
Java ``Rectangle2D.contains`` half-open boundary semantics (x inclusive
on min / exclusive on max; y EXCLUSIVE on min / inclusive on max after
the user-space y-flip), rotated-page device folding (``_glyph_device_origin``
/ ``_region_device_bounds`` for /Rotate 90/180/270), the ligature
``individual_widths``-length-mismatch uniform-split fallback, the
duck-typed PDRectangle ``_normalize_rect`` path, unknown-region lookup,
and extract-twice reset.

Behaviour is cross-checked against Apache PDFBox 3.0.7
``org.apache.pdfbox.text.PDFTextStripperByArea`` semantics: each glyph
is tested with ``Rectangle2D.contains(text.getX(), text.getY())`` against
each region; a glyph inside multiple regions is recorded by the first
region in HashMap order and suppressed (as a coincident duplicate) for
the rest when ``suppressDuplicateOverlappingText`` is on.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, PDFTextStripperByArea
from pypdfbox.text.pdf_text_stripper_by_area import (
    _glyph_device_origin,
    _hashmap_order,
    _normalize_rect,
    _region_device_bounds,
)
from pypdfbox.text.text_position import TextPosition

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_page(doc: PDDocument, content: bytes, rotation: int = 0) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    if rotation:
        page.set_rotation(rotation)
    doc.add_page(page)
    return page


def _single_glyph_page(doc: PDDocument, x: float, y: float, text: bytes) -> PDPage:
    return _make_page(
        doc, b"BT /F0 12 Tf %d %d Td (%s) Tj ET" % (int(x), int(y), text)
    )


# ---------------------------------------------------------------------------
# region lifecycle
# ---------------------------------------------------------------------------


def test_is_subclass() -> None:
    assert isinstance(PDFTextStripperByArea(), PDFTextStripper)


def test_get_regions_empty_initially() -> None:
    assert PDFTextStripperByArea().get_regions() == []


def test_add_remove_re_add_cycle() -> None:
    s = PDFTextStripperByArea()
    s.add_region("a", (0.0, 0.0, 10.0, 10.0))
    s.add_region("b", (0.0, 0.0, 10.0, 10.0))
    s.add_region("c", (0.0, 0.0, 10.0, 10.0))
    s.remove_region("b")
    assert s.get_regions() == ["a", "c"]
    s.add_region("b", (1.0, 1.0, 5.0, 5.0))
    assert s.get_regions() == ["a", "c", "b"]


def test_remove_region_unknown_noop() -> None:
    s = PDFTextStripperByArea()
    s.add_region("a", (0.0, 0.0, 10.0, 10.0))
    s.remove_region("ghost")
    s.remove_region("")
    assert s.get_regions() == ["a"]


def test_remove_one_of_duplicate_names_removes_first() -> None:
    """``add_region`` appends the name unconditionally (upstream ArrayList),
    so a duplicate name yields two list entries but one map entry. Removing
    it once drops the FIRST list entry (``list.remove`` semantics) and the
    single map entry — matching upstream ``regions.remove`` / ``regionArea``
    delete."""
    s = PDFTextStripperByArea()
    s.add_region("dup", (0.0, 0.0, 10.0, 10.0))
    s.add_region("dup", (5.0, 5.0, 50.0, 50.0))
    assert s.get_regions() == ["dup", "dup"]
    s.remove_region("dup")
    # Map key gone, so only the remaining list entry survives the next
    # remove's membership guard.
    assert s.get_regions() == ["dup"]
    s.remove_region("dup")
    assert s.get_regions() == ["dup"]  # map no longer has it -> list untouched


def test_get_text_for_region_unknown_returns_empty_string() -> None:
    s = PDFTextStripperByArea()
    assert s.get_text_for_region("nope") == ""


def test_get_text_for_region_unknown_after_extract() -> None:
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"hi")
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s.extract_regions(page)
    assert s.get_text_for_region("totally-unknown") == ""


# ---------------------------------------------------------------------------
# add_region input coercion
# ---------------------------------------------------------------------------


def test_add_region_pdrectangle() -> None:
    s = PDFTextStripperByArea()
    s.add_region("r", PDRectangle(10.0, 20.0, 30.0, 40.0))
    assert s.get_regions() == ["r"]


def test_add_region_list_form() -> None:
    s = PDFTextStripperByArea()
    s.add_region("r", [0.0, 0.0, 100.0, 100.0])
    assert s.get_regions() == ["r"]


def test_add_region_rejects_string() -> None:
    s = PDFTextStripperByArea()
    with pytest.raises(TypeError):
        s.add_region("r", "garbage")  # type: ignore[arg-type]


def test_add_region_rejects_short_tuple() -> None:
    s = PDFTextStripperByArea()
    with pytest.raises(TypeError):
        s.add_region("r", (1.0, 2.0, 3.0))  # type: ignore[arg-type]


def test_normalize_rect_duck_typed_object() -> None:
    """A non-PDRectangle object exposing ``get_lower_left_x`` &c is accepted
    via duck typing (forward-compat with PDRectangle subclasses)."""

    class DuckRect:
        def get_lower_left_x(self) -> float:
            return 1.0

        def get_lower_left_y(self) -> float:
            return 2.0

        def get_upper_right_x(self) -> float:
            return 3.0

        def get_upper_right_y(self) -> float:
            return 4.0

    assert _normalize_rect(DuckRect()) == (1.0, 2.0, 3.0, 4.0)


def test_normalize_rect_negative_dims_flipped() -> None:
    assert _normalize_rect((100.0, 100.0, -40.0, -20.0)) == (60.0, 80.0, 100.0, 100.0)


# ---------------------------------------------------------------------------
# boundary semantics (Java Rectangle2D.contains, half-open, after y-flip)
# ---------------------------------------------------------------------------
#
# Region (min_x, min_y, max_x, max_y); unrotated test in _bin_glyph is
#   min_x <= x < max_x  and  min_y < y <= max_y
# i.e. x: left inclusive / right exclusive; y: bottom EXCLUSIVE / top inclusive.


def _glyph_captured(rect_xywh, gx: float, gy: float) -> bool:
    doc = PDDocument()
    page = _single_glyph_page(doc, gx, gy, b"X")
    s = PDFTextStripperByArea()
    s.add_region("r", rect_xywh)
    s.extract_regions(page)
    return "X" in s.get_text_for_region("r")


def test_glyph_fully_inside() -> None:
    assert _glyph_captured((50.0, 690.0, 200.0, 40.0), 100.0, 700.0)


def test_glyph_fully_outside() -> None:
    assert not _glyph_captured((50.0, 690.0, 200.0, 40.0), 400.0, 100.0)


def test_glyph_on_left_edge_inclusive() -> None:
    # min_x is inclusive: x == min_x captured.
    assert _glyph_captured((100.0, 690.0, 200.0, 40.0), 100.0, 700.0)


def test_glyph_on_right_edge_exclusive() -> None:
    # max_x is exclusive: x == max_x rejected.  Region x in [100,300).
    assert not _glyph_captured((100.0, 690.0, 200.0, 40.0), 300.0, 700.0)


def test_glyph_on_top_edge_inclusive() -> None:
    # After the y-flip, max_y (the user-space TOP) is INCLUSIVE.
    assert _glyph_captured((50.0, 600.0, 500.0, 100.0), 100.0, 700.0)


def test_glyph_on_bottom_edge_exclusive() -> None:
    # After the y-flip, min_y (the user-space BOTTOM) is EXCLUSIVE.
    assert not _glyph_captured((50.0, 700.0, 500.0, 92.0), 100.0, 700.0)


def test_glyph_just_above_top_rejected() -> None:
    assert not _glyph_captured((50.0, 600.0, 500.0, 99.0), 100.0, 700.0)


def test_glyph_just_inside_bottom() -> None:
    assert _glyph_captured((50.0, 699.0, 500.0, 50.0), 100.0, 700.0)


# ---------------------------------------------------------------------------
# straddling a region boundary (per-glyph split)
# ---------------------------------------------------------------------------


def test_run_straddling_left_boundary_splits_per_glyph() -> None:
    """A multi-glyph run whose first glyphs fall left of a region and whose
    tail falls inside must contribute only the tail glyphs — upstream emits
    one TextPosition per glyph and tests each origin separately, and the
    lite stripper reproduces that by splitting the run."""
    doc = PDDocument()
    # "ABCDEF" starting at x=100; default 12pt glyphs advance ~6-7 units.
    page = _single_glyph_page(doc, 100, 700, b"ABCDEF")
    s = PDFTextStripperByArea()
    # Region whose left edge sits partway through the run; capture only the
    # right portion. Region x in [130, 600).
    s.add_region("right", (130.0, 690.0, 470.0, 20.0))
    s.extract_regions(page)
    captured = s.get_text_for_region("right").strip()
    # Some prefix must be dropped and some tail kept.
    assert captured != "ABCDEF"
    assert captured != ""
    assert "F" in captured  # the rightmost glyph is well inside


def test_run_entirely_inside_keeps_all_glyphs() -> None:
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"hello")
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s.extract_regions(page)
    assert s.get_text_for_region("r").strip() == "hello"
    # one bin entry per glyph, no double-count from the format-walk re-fire.
    assert len(s._region_character_list["r"]) == 5


# ---------------------------------------------------------------------------
# overlapping regions
# ---------------------------------------------------------------------------


def test_overlap_suppress_on_one_region_wins() -> None:
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"ov")
    s = PDFTextStripperByArea()
    s.add_region("a", (50.0, 690.0, 300.0, 20.0))
    s.add_region("b", (60.0, 695.0, 300.0, 10.0))
    s.extract_regions(page)
    a = s.get_text_for_region("a").strip()
    b = s.get_text_for_region("b").strip()
    # Exactly one region keeps the glyphs; the other is empty.
    assert {a, b} == {"ov", ""}


def test_overlap_suppress_off_both_capture() -> None:
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"ov")
    s = PDFTextStripperByArea()
    s.set_suppress_duplicate_overlapping_text(False)
    s.add_region("a", (50.0, 690.0, 300.0, 20.0))
    s.add_region("b", (60.0, 695.0, 300.0, 10.0))
    s.extract_regions(page)
    assert s.get_text_for_region("a").strip() == "ov"
    assert s.get_text_for_region("b").strip() == "ov"


def test_three_overlapping_regions_suppress_on_one_winner() -> None:
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"z")
    s = PDFTextStripperByArea()
    s.add_region("p", (50.0, 690.0, 300.0, 20.0))
    s.add_region("q", (55.0, 692.0, 300.0, 16.0))
    s.add_region("r", (60.0, 694.0, 300.0, 12.0))
    s.extract_regions(page)
    captures = [
        s.get_text_for_region(n).strip() for n in ("p", "q", "r")
    ]
    assert captures.count("z") == 1
    assert captures.count("") == 2


# ---------------------------------------------------------------------------
# empty region / no text
# ---------------------------------------------------------------------------


def test_extracted_empty_region_returns_line_separator_only() -> None:
    """An extracted region that matched no glyphs returns exactly the
    trailing line separator (upstream's per-region writePage terminates the
    page with getLineSeparator() even when empty), NOT ''."""
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"top")
    s = PDFTextStripperByArea()
    # Region far from any text.
    s.add_region("empty", (0.0, 0.0, 50.0, 50.0))
    s.extract_regions(page)
    assert s.get_text_for_region("empty") == s.get_line_separator()
    assert s.get_text_for_region("empty").strip() == ""


def test_blank_page_no_contents_region_stays_empty() -> None:
    doc = PDDocument()
    blank = PDPage()
    doc.add_page(blank)
    s = PDFTextStripperByArea()
    s.add_region("r", (0.0, 0.0, 612.0, 792.0))
    s.extract_regions(blank)
    # hasContents() guard returns before any binning/formatting -> never
    # written, so the empty-string default comes back (no trailing sep).
    assert s.get_text_for_region("r") == ""


def test_no_regions_extract_is_noop() -> None:
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"x")
    s = PDFTextStripperByArea()
    s.extract_regions(page)  # must not raise
    assert s.get_regions() == []


# ---------------------------------------------------------------------------
# extract_regions reset / reuse
# ---------------------------------------------------------------------------


def test_extract_twice_same_page_idempotent() -> None:
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"same")
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s.extract_regions(page)
    first = s.get_text_for_region("r")
    s.extract_regions(page)
    second = s.get_text_for_region("r")
    # No accumulation across calls — the bin + dedup map reset each run.
    assert first == second == "same" + s.get_line_separator()
    assert len(s._region_character_list["r"]) == 4


def test_extract_twice_different_pages_no_carryover() -> None:
    doc = PDDocument()
    p1 = _single_glyph_page(doc, 100, 700, b"one")
    p2 = _single_glyph_page(doc, 100, 700, b"two")
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s.extract_regions(p1)
    assert s.get_text_for_region("r").strip() == "one"
    s.extract_regions(p2)
    assert s.get_text_for_region("r").strip() == "two"


def test_region_added_after_first_extract_is_picked_up() -> None:
    """Regions registered after a prior extract are reset + binned on the
    next extract (the reset loop walks the live ``_regions`` list)."""
    doc = PDDocument()
    page = _make_page(
        doc,
        b"BT /F0 12 Tf 100 700 Td (top) Tj ET "
        b"BT /F0 12 Tf 100 500 Td (bot) Tj ET ",
    )
    s = PDFTextStripperByArea()
    s.add_region("top", (50.0, 690.0, 500.0, 20.0))
    s.extract_regions(page)
    assert s.get_text_for_region("top").strip() == "top"
    # Add a second region and re-extract.
    s.add_region("bot", (50.0, 490.0, 500.0, 20.0))
    s.extract_regions(page)
    assert s.get_text_for_region("top").strip() == "top"
    assert s.get_text_for_region("bot").strip() == "bot"


def test_remove_region_clears_cached_text() -> None:
    doc = PDDocument()
    page = _single_glyph_page(doc, 100, 700, b"hi")
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s.extract_regions(page)
    assert s.get_text_for_region("r").strip() == "hi"
    s.remove_region("r")
    assert s.get_text_for_region("r") == ""


# ---------------------------------------------------------------------------
# bead override + sort
# ---------------------------------------------------------------------------


def test_set_should_separate_by_beads_is_noop() -> None:
    s = PDFTextStripperByArea()
    assert s.is_should_separate_by_beads() is False
    s.set_should_separate_by_beads(True)
    assert s.is_should_separate_by_beads() is False


def test_sort_by_position_orders_within_region() -> None:
    doc = PDDocument()
    page = _make_page(
        doc,
        b"BT /F0 12 Tf 100 500 Td (bottom) Tj ET "
        b"BT /F0 12 Tf 100 700 Td (top) Tj ET ",
    )
    s = PDFTextStripperByArea()
    s.set_sort_by_position(True)
    s.add_region("all", (50.0, 490.0, 500.0, 230.0))
    s.extract_regions(page)
    captured = s.get_text_for_region("all")
    assert captured.find("top") < captured.find("bottom")


# ---------------------------------------------------------------------------
# rotated pages: device folding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_page_user_region_captures_glyph(rotation: int) -> None:
    """A user-space region around the user-space glyph origin captures the
    glyph on every page rotation — the stripper folds BOTH the glyph origin
    and the region rectangle into the same device frame, so the binary
    'is it inside' answer is rotation-invariant for a centred glyph."""
    doc = PDDocument()
    page = _single_glyph_page(doc, 200, 400, b"R")
    page.set_rotation(rotation)
    s = PDFTextStripperByArea()
    # Generous region well around (200, 400) so corner-edge half-openness
    # under the device fold doesn't flip the result.
    s.add_region("r", (150.0, 350.0, 120.0, 120.0))
    s.extract_regions(page)
    assert s.get_text_for_region("r").strip() == "R"


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [
        (0, (100.0, 700.0)),
        (90, (700.0, 100.0)),
        (180, (612.0 - 100.0, 700.0)),
        (270, (792.0 - 700.0, 612.0 - 100.0)),
    ],
)
def test_glyph_device_origin_transforms(rotation, expected) -> None:
    assert _glyph_device_origin(100.0, 700.0, rotation, 612.0, 792.0) == expected


def test_region_device_bounds_renormalizes() -> None:
    # /Rotate 90 swaps axes; result must stay (min_x, min_y, max_x, max_y).
    b = _region_device_bounds((50.0, 690.0, 550.0, 710.0), 90, 612.0, 792.0)
    assert b[0] <= b[2] and b[1] <= b[3]
    assert b == (690.0, 50.0, 710.0, 550.0)


def test_region_device_bounds_rotate_zero_identity() -> None:
    assert _region_device_bounds((1.0, 2.0, 3.0, 4.0), 0, 612.0, 792.0) == (
        1.0,
        2.0,
        3.0,
        4.0,
    )


# ---------------------------------------------------------------------------
# ligature uniform-split fallback (individual_widths length != char count)
# ---------------------------------------------------------------------------


def test_process_text_position_ligature_uniform_split() -> None:
    """When a run's ``individual_widths`` length does not match its decoded
    char count (a ligature code mapping to multiple chars), the splitter
    falls back to the uniform ``width / n`` per-glyph estimate rather than
    indexing a mismatched widths array."""
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    # Prime the per-region buffer + binning state the way extract_regions does.
    s._region_character_list["r"] = []
    s._character_list_mapping = {}
    s._page_rotation = 0
    s._binning_active = True
    # 'fi' ligature: 2 decoded chars but a single advance in individual_widths.
    tp = TextPosition(
        text="fi", x=100.0, y=700.0, font_size=12.0, width=12.0,
        individual_widths=[12.0],
    )
    s.process_text_position(tp)
    s._binning_active = False
    captured = "".join(p.get_unicode() for p in s._region_character_list["r"])
    assert captured == "fi"
    # Each glyph routed as its own one-char position.
    assert [p.get_unicode() for p in s._region_character_list["r"]] == ["f", "i"]


def test_process_text_position_real_widths_split() -> None:
    """When ``individual_widths`` length matches the char count the splitter
    uses the real per-glyph advances (not the uniform estimate)."""
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s._region_character_list["r"] = []
    s._character_list_mapping = {}
    s._page_rotation = 0
    s._binning_active = True
    tp = TextPosition(
        text="AB", x=100.0, y=700.0, font_size=12.0, width=20.0,
        individual_widths=[8.0, 12.0],
    )
    s.process_text_position(tp)
    s._binning_active = False
    assert [p.get_unicode() for p in s._region_character_list["r"]] == ["A", "B"]
    # Second glyph placed at x + first width.
    assert s._region_character_list["r"][1].get_x() == 108.0


def test_process_text_position_single_char_no_split() -> None:
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s._region_character_list["r"] = []
    s._character_list_mapping = {}
    s._page_rotation = 0
    s._binning_active = True
    tp = TextPosition(text="Q", x=100.0, y=700.0, font_size=12.0, width=8.0)
    s.process_text_position(tp)
    s._binning_active = False
    assert [p.get_unicode() for p in s._region_character_list["r"]] == ["Q"]


def test_process_text_position_dropped_when_not_binning() -> None:
    """The ``_binning_active`` guard drops a hook invocation from the
    format-walk so positions are not double-counted in their own bin."""
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s._region_character_list["r"] = []
    s._binning_active = False  # simulate the format-walk re-entry
    tp = TextPosition(text="x", x=100.0, y=700.0, font_size=12.0, width=8.0)
    s.process_text_position(tp)
    assert s._region_character_list["r"] == []


# ---------------------------------------------------------------------------
# _hashmap_order determinism (overlap-winner selection)
# ---------------------------------------------------------------------------


def test_hashmap_order_insertion_independent() -> None:
    assert _hashmap_order(["a", "b"]) == _hashmap_order(["b", "a"])
    assert _hashmap_order(["r1", "r2"]) == ["r2", "r1"]
    assert _hashmap_order(["tl", "tr", "bl", "br"]) == ["br", "tl", "bl", "tr"]


def test_hashmap_order_single_and_empty() -> None:
    assert _hashmap_order([]) == []
    assert _hashmap_order(["only"]) == ["only"]
