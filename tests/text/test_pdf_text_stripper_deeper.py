"""Wave 41 deeper-edge coverage for :class:`PDFTextStripper`.

Pins behaviour added on top of the basic single-page extractor:

  - ``set_should_separate_by_beads`` actually buckets glyphs by the
    page's thread-bead rectangles when at least one bead is present.
  - ``set_should_flip_axes`` transposes the role of X and Y in the
    line-break / word-gap heuristic.
  - ``should_skip_glyph`` filters individual glyphs out of the output
    before sorting / formatting.
  - ``is_paragraph_separation`` / ``start_of_paragraph`` /
    ``is_para_break_indented`` agree on the indent + drop heuristic.
  - ``write_string_with_positions`` enforces its non-empty invariants
    and delegates to ``write_string``.
  - ``set_sort_by_position`` + ``set_should_flip_axes`` together produce
    the rotated reading-order traversal.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.text import PDFTextStripper, TextPosition

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _attach_bead(page: PDPage, rect: PDRectangle) -> PDThreadBead:
    bead = PDThreadBead()
    bead.set_page(page)
    bead.set_rectangle(rect)
    page.set_thread_beads([bead])
    return bead


def _attach_beads(page: PDPage, rects: list[PDRectangle]) -> list[PDThreadBead]:
    beads = []
    for r in rects:
        b = PDThreadBead()
        b.set_page(page)
        b.set_rectangle(r)
        beads.append(b)
    page.set_thread_beads(beads)
    return beads


# ---------------------------------------------------------------------------
# flip_axes
# ---------------------------------------------------------------------------


def test_default_should_flip_axes_is_false() -> None:
    s = PDFTextStripper()
    assert s.is_should_flip_axes() is False
    assert s.get_should_flip_axes() is False


def test_round_trip_should_flip_axes() -> None:
    s = PDFTextStripper()
    s.set_should_flip_axes(True)
    assert s.is_should_flip_axes() is True
    assert s.get_should_flip_axes() is True
    s.set_should_flip_axes(False)
    assert s.is_should_flip_axes() is False


def test_flip_axes_transposes_line_break_axis() -> None:
    """With flip-axes on, two runs sharing a Y but with very different X
    are treated as different *lines* (X is the line-stepping axis)."""
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (alpha) Tj "
            b"1 0 0 1 400 700 Tm (beta) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_should_flip_axes(True)
    out = s.get_text(doc)
    # In the rotated frame the two runs are on different "lines" so a
    # line separator (newline) sits between them — no word separator.
    assert "alpha" in out and "beta" in out
    assert "\n" in out[out.index("alpha") + len("alpha") : out.index("beta")]
    # And no word separator (space) at the boundary.
    assert "alpha beta" not in out


# ---------------------------------------------------------------------------
# should_skip_glyph
# ---------------------------------------------------------------------------


def test_should_skip_glyph_default_keeps_everything() -> None:
    s = PDFTextStripper()
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=10.0)
    assert s.should_skip_glyph(pos) is False


def test_should_skip_glyph_override_filters_runs() -> None:
    """A subclass that returns True for runs containing ``z`` should see
    those runs absent from the formatted output."""

    class FilteringStripper(PDFTextStripper):
        def should_skip_glyph(self, text: TextPosition) -> bool:  # type: ignore[override]
            return "z" in text.text

    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"100 700 Td (foo) Tj "
            b"50 0 Td (zap) Tj "
            b"50 0 Td (bar) Tj "
            b"ET"
        ),
    )
    out = FilteringStripper().get_text(doc)
    assert "foo" in out
    assert "bar" in out
    assert "zap" not in out


# ---------------------------------------------------------------------------
# bead-aware separation
# ---------------------------------------------------------------------------


def test_should_separate_by_beads_groups_runs_into_bead_buckets() -> None:
    """Two runs in two distinct bead rectangles should appear in
    bead-chain order, separated by a line break."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            # In bead 2 (right column) — emitted first by stream order.
            b"1 0 0 1 400 700 Tm (right) Tj "
            # In bead 1 (left column).
            b"1 0 0 1 100 700 Tm (left) Tj "
            b"ET"
        ),
    )
    _attach_beads(
        page,
        [
            PDRectangle(50.0, 600.0, 250.0, 750.0),  # left column
            PDRectangle(350.0, 600.0, 550.0, 750.0),  # right column
        ],
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    # Bead-1 (left column) bucket emits before bead-2 (right column).
    assert out.index("left") < out.index("right")


def test_should_separate_by_beads_disabled_preserves_stream_order() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 400 700 Tm (right) Tj "
            b"1 0 0 1 100 700 Tm (left) Tj "
            b"ET"
        ),
    )
    _attach_beads(
        page,
        [
            PDRectangle(50.0, 600.0, 250.0, 750.0),
            PDRectangle(350.0, 600.0, 550.0, 750.0),
        ],
    )
    s = PDFTextStripper()
    s.set_should_separate_by_beads(False)
    out = s.get_text(doc)
    # No bead bucketing — order tracks the content stream.
    assert out.index("right") < out.index("left")


def test_bead_separation_no_beads_means_no_bucketing() -> None:
    """A page without ``/B`` should fall through to a single all-positions
    group even with bead-separation enabled (parity with upstream)."""
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (only) Tj ET",
    )
    s = PDFTextStripper()
    assert s.is_should_separate_by_beads() is True
    assert s.get_text(doc) == "only\n"


def test_bead_separation_out_of_bead_run_lands_in_upstream_gap_slot() -> None:
    """A run outside every bead lands in the first gap slot it is left-of /
    above, per upstream's ``2*N + 1`` ``charactersByArticle`` layout (slot
    ``i*2`` is the gap before bead ``i``). Here ``out`` (x=10, far left of the
    bead) is left-of the bead -> gap slot 0 (before bead 0), so it emits
    *before* the in-bead run ``in`` (slot 1) — matching upstream
    ``processTextPosition`` (PDFTextStripper.java:954-1020), not a trailing
    residual bucket."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            # Outside any bead, left of the column.
            b"1 0 0 1 10 10 Tm (out) Tj "
            # Inside the bead.
            b"1 0 0 1 100 700 Tm (in) Tj "
            b"ET"
        ),
    )
    _attach_bead(page, PDRectangle(50.0, 600.0, 250.0, 750.0))
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out.index("out") < out.index("in")


def test_bead_partition_two_beads_uses_2n_plus_1_slots() -> None:
    """``_partition_by_beads`` allocates ``2*N + 1`` slots for ``N`` beads and
    assigns each glyph to slot ``i*2+1`` (inside bead ``i``) or to the first
    gap slot ``i*2`` it is left-of / above — the upstream
    ``charactersByArticle`` layout (PDFTextStripper.java:954-1020). A run
    between two beads lands in the gap slot, so non-empty slots emit in index
    order: gap-before-bead-0, bead-0, bead-1."""
    s = PDFTextStripper()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    _attach_beads(
        page,
        [
            PDRectangle(50.0, 600.0, 250.0, 750.0),  # bead 0 (left)
            PDRectangle(350.0, 600.0, 550.0, 750.0),  # bead 1 (right)
        ],
    )
    s._active_page = page  # noqa: SLF001
    in0 = TextPosition(text="A", x=100.0, y=700.0, font_size=12.0)
    in1 = TextPosition(text="B", x=400.0, y=700.0, font_size=12.0)
    # x between the two beads, above their bottom edge -> gap slot before
    # bead 1 (it is left of bead 1). It is NOT left of bead 0 (x>250) but IS
    # above bead 0 -> qualifies for bead 0's gap slot (slot 0) first.
    between = TextPosition(text="C", x=300.0, y=700.0, font_size=12.0)
    buckets = s._partition_by_beads([in0, in1, between])  # noqa: SLF001
    assert buckets == [[between], [in0], [in1]]


def test_bead_separation_inter_article_line_break_into_residual() -> None:
    """A run that falls just *below* the only bead (outside it) lands in the
    trailing residual slot and, because the running line state carries across
    article boundaries (upstream declares it outside the ``writePage`` article
    loop, lines 497-503), a one-row vertical drop between the in-bead run and
    the residual run emits a single line separator — not a silent
    concatenation."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            # Inside the bead, lower line.
            b"1 0 0 1 60 610 Tm (inbead) Tj "
            # Just below the bead's bottom edge (y < 600), one row down.
            b"1 0 0 1 60 596 Tm (below) Tj "
            b"ET"
        ),
    )
    _attach_bead(page, PDRectangle(50.0, 600.0, 550.0, 760.0))
    s = PDFTextStripper()
    out = s.get_text(doc)
    try:
        assert out.index("inbead") < out.index("below")
        between = out[out.index("inbead") + len("inbead") : out.index("below")]
        assert "\n" in between
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# paragraph-separation heuristic
# ---------------------------------------------------------------------------


def test_is_paragraph_separation_detects_drop() -> None:
    s = PDFTextStripper()
    prev = TextPosition(text="x", x=100.0, y=700.0, font_size=12.0)
    pos = TextPosition(text="y", x=100.0, y=600.0, font_size=12.0)  # 100u drop
    assert s.is_paragraph_separation(pos, prev) is True


def test_is_paragraph_separation_negative_for_tight_run() -> None:
    """Two runs at almost the same origin should not trip either prong
    of the heuristic — no drop, no indent."""
    s = PDFTextStripper()
    prev = TextPosition(
        text="x", x=100.0, y=700.0, font_size=12.0, width_of_space=4.0
    )
    pos = TextPosition(
        text="y", x=101.0, y=700.0, font_size=12.0, width_of_space=4.0
    )
    assert s.is_paragraph_separation(pos, prev) is False


def test_is_paragraph_separation_detects_indent() -> None:
    """A new line that starts noticeably to the right of the previous
    line should fire the indent prong of the heuristic."""
    s = PDFTextStripper()
    prev = TextPosition(
        text="x", x=100.0, y=700.0, font_size=12.0, width_of_space=4.0
    )
    # Same-ish y, indent of 20 user units > 2 × space-width (4) = 8.
    pos = TextPosition(
        text="y", x=120.0, y=700.0, font_size=12.0, width_of_space=4.0
    )
    assert s.is_paragraph_separation(pos, prev) is True


def test_is_para_break_indented_only_indent() -> None:
    """``is_para_break_indented`` ignores the drop prong — only fires
    on indents."""
    s = PDFTextStripper()
    prev = TextPosition(
        text="x", x=100.0, y=700.0, font_size=12.0, width_of_space=4.0
    )
    # Big drop, no indent: drop-prong-only ⇒ indent helper says no.
    drop_pos = TextPosition(
        text="y", x=100.0, y=300.0, font_size=12.0, width_of_space=4.0
    )
    assert s.is_para_break_indented(drop_pos, prev) is False
    # Indent only.
    indent_pos = TextPosition(
        text="y", x=200.0, y=700.0, font_size=12.0, width_of_space=4.0
    )
    assert s.is_para_break_indented(indent_pos, prev) is True


def test_start_of_paragraph_alias_matches_is_paragraph_separation() -> None:
    s = PDFTextStripper()
    prev = TextPosition(text="x", x=100.0, y=700.0, font_size=12.0)
    pos = TextPosition(text="y", x=100.0, y=300.0, font_size=12.0)
    assert s.start_of_paragraph(pos, prev) is s.is_paragraph_separation(pos, prev)


def test_paragraph_break_emits_paragraph_markers() -> None:
    """When a paragraph break is detected mid-page, the configured
    ``paragraph_start`` / ``paragraph_end`` markers should fire."""
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (line1) Tj "
            # Big y drop — paragraph break
            b"1 0 0 1 100 500 Tm (line2) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_paragraph_start("<P>")
    s.set_paragraph_end("</P>")
    out = s.get_text(doc)
    assert "</P>" in out and "<P>" in out
    # Upstream ``writePage`` opens a leading page-body paragraph (``<P>`` on
    # the first glyph) and closes a trailing one (``</P>`` after the last
    # line). The mid-page break emits ``writeParagraphEnd`` +
    # ``writeParagraphStart`` (PDFTextStripper.java:700-724, 1697-1700), so the
    # break shows up as a ``</P>...<P>`` pair between the two lines.
    assert out.startswith("<P>")
    assert out.rstrip("\n").endswith("</P>")
    # The mid-page paragraph separator wraps the break: a close then a reopen.
    assert "</P>" in out
    assert out.index("</P>") < out.rindex("<P>")


# ---------------------------------------------------------------------------
# write_string_with_positions
# ---------------------------------------------------------------------------


def test_write_string_with_positions_delegates_to_write_string() -> None:
    """Default ``write_string_with_positions`` calls ``write_string``."""
    seen: list[tuple[str, int]] = []

    class Capturing(PDFTextStripper):
        def write_string(self, text, text_positions, sink) -> None:  # type: ignore[override]
            seen.append((text, len(text_positions)))
            sink(text)

    s = Capturing()
    out: list[str] = []
    pos = TextPosition(text="hi", x=0.0, y=0.0, font_size=10.0)
    s.write_string_with_positions("hi", [pos], out.append)
    assert seen == [("hi", 1)]
    assert out == ["hi"]


def test_write_string_with_positions_skips_empty_text() -> None:
    """Empty text ⇒ no-op (``writeString("")`` writes nothing). A non-empty
    text with an empty position list is still written, matching upstream's
    ``writeString(String, List<TextPosition>)``, which ignores the position
    list and always delegates to ``writeString(String)``."""
    seen: list[str] = []
    s = PDFTextStripper()
    s.write_string_with_positions("", [TextPosition(text="", x=0, y=0, font_size=10)], seen.append)
    assert seen == []
    s.write_string_with_positions("hi", [], seen.append)
    assert seen == ["hi"]


# ---------------------------------------------------------------------------
# sort + flip_axes interaction
# ---------------------------------------------------------------------------


def test_sort_by_position_with_flip_axes_walks_rotated_reading_order() -> None:
    """sort_by_position + flip_axes should walk the rotated frame:
    ascending X is "top-down" in the rotated view, ascending Y is
    "left-to-right" within a column."""
    doc = PDDocument()
    # Stream order is scrambled. Geometric reading in flipped frame
    # (X ascending → Y ascending):
    #   (100, 100) "A"
    #   (100, 700) "B"
    #   (400, 100) "C"
    #   (400, 700) "D"
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 400 700 Tm (D) Tj "
            b"1 0 0 1 100 700 Tm (B) Tj "
            b"1 0 0 1 400 100 Tm (C) Tj "
            b"1 0 0 1 100 100 Tm (A) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    s.set_should_flip_axes(True)
    out = s.get_text(doc)
    assert out.index("A") < out.index("B") < out.index("C") < out.index("D")
