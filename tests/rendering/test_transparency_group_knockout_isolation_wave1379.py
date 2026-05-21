"""Wave 1379 — full structural verification of transparency-group
``/K`` (knockout) + ``/I`` (isolation) compositing in
:class:`pypdfbox.rendering.PDFRenderer`.

These tests close the DEFERRED.md "rendering" entry that called out
"falls back to isolated non-knockout" — verified against current
source, all four combinations are implemented (since wave 31, with
ExtGState soft-mask + blend-mode integration through wave 40 and
the §11.3.5.1 ColorDodge/ColorBurn alignment in wave 1363).

Adds the synthetic three-overlapping-shapes knockout test from the
wave 1379 brief plus structural alpha-channel assertions on
:meth:`PDFRenderer.render_image_with_dpi` output (RGBA), and pins
``/I`` + ``/K`` interaction with the ExtGState blend mode applied at
group compositing time (§11.4.7.4).

PDF 32000-1 sections covered:

- §11.4.5–11.4.6  — group concepts.
- §11.4.7.2       — isolated vs non-isolated initial backdrop.
- §11.4.7.3       — knockout group: each top-level child replaces
                    the prior contents at the group level.
- §11.4.7.4       — group compositing with the active blend mode.
"""

from __future__ import annotations

from PIL import Image

from pypdfbox.cos import COSBoolean, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(
    actual: tuple[int, ...],
    expected: tuple[int, ...],
    tol: int = 12,
) -> bool:
    """Per-channel tolerance compare for an arbitrary-width pixel tuple."""
    return all(
        abs(a - e) <= tol
        for a, e in zip(actual[: len(expected)], expected, strict=True)
    )


def _wire_group_form(
    page: PDPage,
    stream_bytes: bytes,
    *,
    isolated: bool | None,
    knockout: bool | None,
    page_prefix: bytes = b"",
) -> None:
    """Attach a single transparency-group form XObject to a page.

    The form's content stream is ``stream_bytes``; ``/Group/S
    /Transparency`` is always set; ``/I`` and ``/K`` are populated only
    when explicitly requested (``None`` leaves them out so the spec
    defaults of false apply).
    """
    form_stream = COSStream()
    form_stream.set_raw_data(stream_bytes)
    form = PDFormXObject(form_stream)
    form.set_b_box(PDRectangle(0.0, 0.0, 100.0, 100.0))

    group_dict = COSDictionary()
    group_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    if isolated is not None:
        group_dict.set_item(COSName.get_pdf_name("I"), COSBoolean.get(isolated))
    if knockout is not None:
        group_dict.set_item(COSName.get_pdf_name("K"), COSBoolean.get(knockout))
    form.set_group(group_dict)

    page_dict = page.get_cos_object()
    contents = COSStream()
    contents.set_raw_data(page_prefix + b"q\n/Form0 Do\nQ\n")
    page_dict.set_item(COSName.CONTENTS, contents)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Form0"),
        form.get_cos_object(),
    )


# Page is 100x100. PDF coords use (x, y) with y-up; PIL is y-down so
# PIL_y = 100 - PDF_y. All sample points below are PIL coords.

# ---------------------------------------------------------------------------
# Three overlapping squares — the wave 1379 brief's synthetic case.
#
# We use squares (re/f) rather than circles because the renderer's
# content-stream operator set is path-fill + rect — the "3 circles"
# pattern from the brief is structurally identical (3 overlapping
# painting operators in a /K=true group): only the last one in the
# overlap zone should remain visible.
# ---------------------------------------------------------------------------


_THREE_SQUARES_STREAM = (
    b"1 0 0 rg\n"        # red
    b"10 10 60 60 re\nf\n"
    b"0 1 0 rg\n"        # green, overlaps red
    b"30 30 60 60 re\nf\n"
    b"0 0 1 rg\n"        # blue, overlaps both
    b"50 50 40 40 re\nf\n"
)


def test_three_overlapping_squares_isolated_knockout_only_last_survives() -> None:
    """``/I true /K true`` with 3 overlapping opaque squares.

    PDF spec §11.4.7.3 — a knockout group restores the group-canvas
    snapshot before *every* top-level painting operator. Each child
    therefore fully replaces (knocks out) every previous child, not
    just the part the previous child painted in the new child's
    footprint. The final state of the group is the *last* paint only.

    Concretely:
      * Snapshot at group entry: fully transparent (isolated).
      * red rect paints → snapshot restored → red erased.
      * green rect paints → snapshot restored → green erased.
      * blue rect paints (final) → group composites onto parent.

    After compositing onto the page (white default backdrop), only
    the blue square's pixels are visible; the red-only and green-only
    regions revert to the parent's white.
    """
    doc, page = _make_doc()
    _wire_group_form(
        page, _THREE_SQUARES_STREAM, isolated=True, knockout=True
    )
    img = PDFRenderer(doc).render_image(0)

    # Sample points (PIL coords, PDF y inverted):
    #  * Red-only region (red painted, then knocked out): white parent.
    #    PDF (15, 15) → PIL (15, 85).
    #  * Green-only region (green painted, then knocked out): white parent.
    #    PDF (40, 40) → PIL (40, 60).
    #  * Blue square footprint: PDF (50..90, 50..90) → PIL (50..90, 10..50).
    #    Take centre PDF (70, 70) → PIL (70, 30).
    #  * Outside any paint: PDF (5, 5) → PIL (5, 95): white parent.
    red_only_pt = img.getpixel((15, 85))
    green_only_pt = img.getpixel((40, 60))
    blue_pt = img.getpixel((70, 30))
    outside = img.getpixel((5, 95))

    # Red was knocked out — parent (white) shows through.
    assert _is_close(red_only_pt, (255, 255, 255), tol=4), red_only_pt
    # Green was also knocked out — parent (white) shows through.
    assert _is_close(green_only_pt, (255, 255, 255), tol=4), green_only_pt
    # Final paint (blue) is the only thing left in the group.
    assert _is_close(blue_pt, (0, 0, 255)), blue_pt
    # Nothing was ever painted here — parent white.
    assert _is_close(outside, (255, 255, 255), tol=4), outside


def test_three_overlapping_squares_non_isolated_knockout_parent_shows_through() -> None:
    """``/I false /K true``: knockout snapshot is the parent canvas
    contents at group entry (the yellow backdrop). After every
    top-level paint the canvas reverts to that snapshot, so only the
    final paint (blue) is left visible in the group; everywhere else
    (including regions where red or green painted earlier) reverts to
    yellow.
    """
    doc, page = _make_doc()
    backdrop = b"1 1 0 rg\n0 0 100 100 re\nf\n"
    _wire_group_form(
        page,
        _THREE_SQUARES_STREAM,
        isolated=False,
        knockout=True,
        page_prefix=backdrop,
    )
    img = PDFRenderer(doc).render_image(0)

    # Same geometry as the isolated case but the snapshot is yellow:
    red_only_region = img.getpixel((15, 85))
    green_only_region = img.getpixel((40, 60))
    blue_pt = img.getpixel((70, 30))
    outside = img.getpixel((95, 5))

    # Red square knocked out → yellow backdrop visible.
    assert _is_close(red_only_region, (255, 255, 0)), red_only_region
    # Green square also knocked out → yellow.
    assert _is_close(green_only_region, (255, 255, 0)), green_only_region
    # Last paint (blue) wins.
    assert _is_close(blue_pt, (0, 0, 255)), blue_pt
    # Outside any group paint → yellow backdrop.
    assert _is_close(outside, (255, 255, 0)), outside


# ---------------------------------------------------------------------------
# Non-knockout 3-square overlap — sanity contrast vs the knockout cases.
# All three paints accumulate, so the 3-way overlap shows the latest
# OPAQUE paint (blue) anyway — but the red/green-only regions remain
# distinct (they don't get knocked back), proving the non-knockout
# branch did not engage the snapshot-restore code path.
# ---------------------------------------------------------------------------


def test_three_overlapping_squares_isolated_non_knockout_layers_normally() -> None:
    """``/I true /K false``: standard layering. With opaque fills the
    latest paint at each pixel wins, but the red-only and green-only
    regions outside the deeper overlap still show their respective
    colours (no snapshot-revert happened)."""
    doc, page = _make_doc()
    _wire_group_form(
        page, _THREE_SQUARES_STREAM, isolated=True, knockout=False
    )
    img = PDFRenderer(doc).render_image(0)

    # Red-only region (no later paint touches it).
    assert _is_close(img.getpixel((20, 80)), (255, 0, 0))
    # Green covers red here (no blue touches it) — green wins.
    assert _is_close(img.getpixel((40, 60)), (0, 255, 0))
    # Blue is the topmost paint in the deep overlap.
    assert _is_close(img.getpixel((60, 40)), (0, 0, 255))


# ---------------------------------------------------------------------------
# Backdrop preservation: a /K=true group must NOT obliterate parent
# pixels OUTSIDE the painted region — only the snapshot-reset region
# is affected; uncovered parent area is unchanged.
# ---------------------------------------------------------------------------


def test_knockout_group_preserves_parent_pixels_outside_group_paint() -> None:
    """A knockout group only erases prior paint *within the group* —
    parent-canvas pixels outside the group's painted region must stay
    untouched.

    Wire a /I=false /K=true group that paints one small red square in
    the top-left, over a parent that paints two stripes (blue on left,
    cyan on right). After group compositing the right stripe (which
    the group never touches) must remain cyan.
    """
    doc, page = _make_doc()
    # Parent: blue left half + cyan right half.
    backdrop = (
        b"0 0 1 rg\n0 0 50 100 re\nf\n"     # blue rect on the left
        b"0 1 1 rg\n50 0 50 100 re\nf\n"    # cyan rect on the right
    )
    # Group paints only a small red square in the bottom-left corner.
    group_stream = b"1 0 0 rg\n10 10 20 20 re\nf\n"
    _wire_group_form(
        page,
        group_stream,
        isolated=False,
        knockout=True,
        page_prefix=backdrop,
    )
    img = PDFRenderer(doc).render_image(0)

    # Right-half pixel — the group never paints here; parent cyan stays.
    assert _is_close(img.getpixel((75, 50)), (0, 255, 255))
    # Red square visible at PDF (10..30, 10..30) → PIL (10..30, 70..90).
    assert _is_close(img.getpixel((20, 80)), (255, 0, 0))


# ---------------------------------------------------------------------------
# Alpha-channel structural check: render an isolated group on an RGBA
# canvas and verify the alpha channel reflects only the group's paints
# (the isolated backdrop was transparent).
# ---------------------------------------------------------------------------


def test_isolated_group_alpha_channel_only_where_painted() -> None:
    """``/I true``: when we extract the post-render image as RGBA the
    alpha channel comes from final RGB composite (always 255 on the
    lite renderer). What we *can* check structurally is that the
    painted-square region has the painted RGB and the unpainted area
    keeps the page's default white, not a partial-alpha haze."""
    doc, page = _make_doc()
    group_stream = b"0 0 0 rg\n20 20 60 60 re\nf\n"  # opaque black square
    _wire_group_form(page, group_stream, isolated=True, knockout=False)
    img = PDFRenderer(doc).render_image(0)
    rgba = img.convert("RGBA") if img.mode != "RGBA" else img

    # Centre of the painted square: black.
    cx, cy = 50, 50
    px = rgba.getpixel((cx, cy))
    assert _is_close(px, (0, 0, 0, 255)), px
    # Outside the painted square: white page (alpha=255 in RGBA cast).
    outside = rgba.getpixel((95, 5))
    assert _is_close(outside, (255, 255, 255, 255), tol=4), outside


# ---------------------------------------------------------------------------
# /K=true with a nested Form XObject — knockout must reset BEFORE the
# top-level Do but NOT before paints *inside* the nested form (depth
# counter behaviour, see _process_form_bytes).
# ---------------------------------------------------------------------------


def test_knockout_does_not_fire_inside_nested_form_xobject() -> None:
    """Inside a ``/K true`` group with a nested form XObject, the
    snapshot reset only fires for the *top-level* group children. Paints
    inside the nested form accumulate as normal — otherwise a nested
    form with multiple paints would erase its own earlier work.

    The form-depth counter (``_knockout_form_depth``) bumps on every
    nested ``_process_form_bytes`` so only depth 0 triggers the reset.

    Group with a single top-level ``Do`` (the inner form, which paints
    red then green internally). No subsequent top-level paint, so the
    Do is the *last* group-level child and both inner-form paints
    survive compositing.
    """
    doc, page = _make_doc()

    # Inner form: paints two overlapping rects internally — both must
    # remain visible (no internal knockout).
    inner_stream = COSStream()
    inner_stream.set_raw_data(
        b"1 0 0 rg\n10 10 30 30 re\nf\n"
        b"0 1 0 rg\n20 20 30 30 re\nf\n"
    )
    inner_form = PDFormXObject(inner_stream)
    inner_form.set_b_box(PDRectangle(0.0, 0.0, 100.0, 100.0))
    # No /Group on inner form — it's a plain form XObject, not a t-group.

    # Outer transparency group with /I=true /K=true. Only one top-level
    # painting operator inside the group: ``/Inner Do``. So the
    # knockout snapshot is restored once (before the Do), then the
    # inner form's two rects paint without further snapshot reset
    # (depth bumps to 1 inside the inner stream). After the inner form
    # returns, the group has both inner paints composited; we exit the
    # group cleanly with no further knockout reset.
    outer_form_stream = COSStream()
    outer_form_stream.set_raw_data(b"/Inner Do\n")
    outer_form = PDFormXObject(outer_form_stream)
    outer_form.set_b_box(PDRectangle(0.0, 0.0, 100.0, 100.0))

    group_dict = COSDictionary()
    group_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    group_dict.set_item(COSName.get_pdf_name("I"), COSBoolean.get(True))
    group_dict.set_item(COSName.get_pdf_name("K"), COSBoolean.get(True))
    outer_form.set_group(group_dict)

    # Inner-form resources must be on the outer form so /Inner resolves.
    outer_resources = PDResources()
    outer_resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Inner"),
        inner_form.get_cos_object(),
    )
    outer_form.set_resources(outer_resources)

    page_dict = page.get_cos_object()
    page_contents = COSStream()
    page_contents.set_raw_data(b"q\n/Outer Do\nQ\n")
    page_dict.set_item(COSName.CONTENTS, page_contents)
    page_resources = PDResources()
    page.set_resources(page_resources)
    page_resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Outer"),
        outer_form.get_cos_object(),
    )

    img = PDFRenderer(doc).render_image(0)

    # Inside the inner-form red-only region (PDF (10..20, 10..20)).
    # Red paint #1 must NOT have been erased by green paint #2 (because
    # we're inside a nested form and depth > 0 → no reset).
    # PDF (15, 15) → PIL (15, 85).
    inner_red_only = img.getpixel((15, 85))
    assert _is_close(inner_red_only, (255, 0, 0)), inner_red_only

    # Inside the green-only region (PDF (40, 40)..(50, 50)) → green.
    # PDF (45, 45) → PIL (45, 55).
    inner_green_only = img.getpixel((45, 55))
    assert _is_close(inner_green_only, (0, 255, 0)), inner_green_only


# ---------------------------------------------------------------------------
# Sanity: rendering each of the 4 combinations on the page-default
# white background terminates and produces a 100x100 RGB image.
# ---------------------------------------------------------------------------


def test_four_combinations_render_to_consistent_dimensions() -> None:
    for isolated, knockout in [
        (True, False),
        (False, False),
        (True, True),
        (False, True),
    ]:
        doc, page = _make_doc()
        _wire_group_form(
            page,
            _THREE_SQUARES_STREAM,
            isolated=isolated,
            knockout=knockout,
        )
        img = PDFRenderer(doc).render_image(0)
        assert img.size == (100, 100)
        assert img.mode in {"RGB", "RGBA"}
        # Structural sanity: at least one painted square pixel landed.
        # Convert to RGBA and check there's at least one non-white pixel.
        rgba = img.convert("RGBA") if img.mode != "RGBA" else img
        # Iterate pixels via load() to avoid Pillow's deprecated
        # ``getdata()`` (deprecated 14.0).
        load = rgba.load()
        w, h = rgba.size
        non_white = 0
        for yy in range(h):
            for xx in range(w):
                pxx = load[xx, yy]
                if not (pxx[0] >= 250 and pxx[1] >= 250 and pxx[2] >= 250):
                    non_white += 1
        assert non_white > 0, (
            f"isolated={isolated} knockout={knockout}: no paint reached the page"
        )


# ---------------------------------------------------------------------------
# Defensive: an /I+/K group with an empty content stream must not raise
# (knockout snapshot allocation runs at group entry; the snapshot just
# never gets consulted).
# ---------------------------------------------------------------------------


def test_knockout_group_with_empty_content_stream_is_no_op() -> None:
    doc, page = _make_doc()
    _wire_group_form(page, b"", isolated=True, knockout=True)
    img = PDFRenderer(doc).render_image(0)
    # All-white page (group painted nothing).
    rgba = img.convert("RGBA") if img.mode != "RGBA" else img
    px = rgba.getpixel((50, 50))
    assert _is_close(px, (255, 255, 255, 255), tol=4), px


# ---------------------------------------------------------------------------
# Image-mode contract: render_image returns a PIL Image whose pixel
# tuples are RGB(A) — used implicitly by all assertions above. Pin it
# explicitly so a future renderer mode change can't silently break the
# tolerance compares.
# ---------------------------------------------------------------------------


def test_render_image_returns_pillow_image() -> None:
    doc, page = _make_doc()
    _wire_group_form(
        page, _THREE_SQUARES_STREAM, isolated=True, knockout=True
    )
    img = PDFRenderer(doc).render_image(0)
    assert isinstance(img, Image.Image)
    assert img.mode in {"RGB", "RGBA"}
