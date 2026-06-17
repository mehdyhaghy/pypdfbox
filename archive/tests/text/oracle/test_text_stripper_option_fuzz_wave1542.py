"""Live Apache PDFBox differential parity for ``PDFTextStripper``'s extraction
*option* surface — page-range bounds, separators/markers, and the boolean
toggles — over a small synthetic multi-page document (wave 1542).

Sibling oracle files pin specific facets: ``test_text_separator_oracle.py``
pins separator *placement* with sentinel tokens on a real outline fixture,
``test_sort_by_position_oracle.py`` / ``test_text_sort_inline_oracle.py`` pin
the position-sort re-ordering, and ``test_text_stripper_basic_fuzz_wave1533.py``
pins baseline word/line segmentation on single-page streams. This file's
distinct angle is the *configuration matrix* itself: ~33 option/edge
combinations driving ``set_start_page`` / ``set_end_page`` with out-of-range,
zero, negative, and ``start > end`` values (the RAW value, not the
``min(end, page_count)`` clamp ``ExtractTextRangeProbe`` mirrors from the CLI),
``set_sort_by_position`` over reverse-ordered text, every separator/marker
override, ``set_should_separate_by_beads``, ``set_add_more_formatting``,
``set_suppress_duplicate_overlapping_text``, and isolating a final
whitespace-only page.

The companion :class:`TextStripperOptionFuzzProbe` Java probe emits one
escaped line per case (``CASE:<name>:<escaped-text>``) so newlines / word
breaks round-trip exactly. Each case constructs a FRESH ``PDFTextStripper`` —
a stripper run mutates per-page parser state that a second stripper on the
same document would inherit.

The synthetic document is built once by pypdfbox and handed to both engines:
- page 1: two flush lines (baseline horizontal extraction);
- page 2: a single line (page-range isolation target);
- page 3: two words drawn right-then-left on one baseline (out of reading
  order — exercises the sort toggle);
- page 4: whitespace-only positioning, no glyphs (empty-slice target).

All cases are pinned byte-for-byte against PDFBox 3.0.7. ``@requires_oracle``
so it skips cleanly without Java + the jar. Hand-written (not ported from
upstream JUnit).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "TextStripperOptionFuzzProbe"

# Each page's raw content stream. ``/F1`` is rewritten per page to the key the
# page resources allocate for the embedded Helvetica font. Pages are US Letter
# (612x792) so the coordinates are comfortably inside the media box.
_PAGE_1 = b"BT /F1 24 Tf 72 700 Td (Alpha) Tj 0 -40 Td (Beta) Tj ET"
_PAGE_2 = b"BT /F1 24 Tf 72 700 Td (Gamma) Tj ET"
# Two words on one baseline drawn right-then-left (out of reading order).
_PAGE_3 = b"BT /F1 24 Tf 300 700 Td (Right) Tj -250 0 Td (Left) Tj ET"
# Whitespace-only positioning: no show-text operators, so no glyphs.
_PAGE_4 = b"BT /F1 24 Tf 72 700 Td 200 0 Td 0 -40 Td ET"

_PAGES = (_PAGE_1, _PAGE_2, _PAGE_3, _PAGE_4)


def _build_pdf(path: str) -> None:
    """Build the 4-page synthetic document at ``path``.

    Every page gets its own embedded Helvetica font and its ``/F1`` token is
    rewritten to whatever key that page's resources allocate.
    """
    doc = PDDocument()
    try:
        for content in _PAGES:
            page = PDPage(PDRectangle(0, 0, 612, 792))
            doc.add_page(page)
            font = PDFontFactory.create_default_font(
                Standard14Fonts.FontName.HELVETICA.value
            )
            resources = page.get_or_create_resources()
            font_key = resources.add(font)
            page.set_resources(resources)
            rewritten = content.replace(
                b"/F1", b"/" + font_key.get_name().encode("ascii")
            )
            stream = COSStream()
            with stream.create_output_stream() as out:
                out.write(rewritten)
            page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()


def _unesc(s: str) -> str:
    """Reverse the probe's escape (``\\n`` / ``\\r`` / ``\\\\``)."""
    result: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                result.append("\n")
                i += 2
                continue
            if nxt == "r":
                result.append("\r")
                i += 2
                continue
            if nxt == "\\":
                result.append("\\")
                i += 2
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def _java_cases(path: str) -> dict[str, str]:
    """Run the probe; return ``{case_name: unescaped_text}``.

    The case name is the segment between the first and second ``:`` — the
    payload may itself contain ``:`` so we split only twice.
    """
    out = run_probe_text(_PROBE, path)
    cases: dict[str, str] = {}
    for line in out.split("\n"):
        if not line.startswith("CASE:"):
            continue
        _, name, payload = line.split(":", 2)
        cases[name] = _unesc(payload)
    return cases


def _py(path: str, configure) -> str:
    """Extract with pypdfbox after applying ``configure(stripper)``.

    The document is closed in a ``finally`` so a Windows file lock is always
    released before the temp dir is removed.
    """
    doc = PDDocument.load(path)
    try:
        stripper = PDFTextStripper()
        configure(stripper)
        return stripper.get_text(doc)
    finally:
        doc.close()


# ``configure`` callables mirroring each Java probe case one-for-one. Total
# page count of the fixture is 4.
_PAGE_COUNT = len(_PAGES)


def _cfg_default(s: PDFTextStripper) -> None:
    pass


_CONFIGS = {
    "default_full": _cfg_default,
    "start_zero": lambda s: s.set_start_page(0),
    "start_negative": lambda s: s.set_start_page(-5),
    "end_zero": lambda s: s.set_end_page(0),
    "end_negative": lambda s: s.set_end_page(-3),
    "end_beyond": lambda s: s.set_end_page(_PAGE_COUNT + 100),
    "start_beyond": lambda s: s.set_start_page(_PAGE_COUNT + 50),
    "start_gt_end": lambda s: (s.set_start_page(3), s.set_end_page(1)),
    "single_page_2": lambda s: (s.set_start_page(2), s.set_end_page(2)),
    "range_2_3": lambda s: (s.set_start_page(2), s.set_end_page(3)),
    "start_zero_end_beyond": lambda s: (
        s.set_start_page(0),
        s.set_end_page(_PAGE_COUNT + 9),
    ),
    "sort_true": lambda s: s.set_sort_by_position(True),
    "sort_false": lambda s: s.set_sort_by_position(False),
    "sort_true_page3": lambda s: (
        s.set_sort_by_position(True),
        s.set_start_page(3),
        s.set_end_page(3),
    ),
    "sort_false_page3": lambda s: (
        s.set_sort_by_position(False),
        s.set_start_page(3),
        s.set_end_page(3),
    ),
    "word_sep": lambda s: s.set_word_separator("_WS_"),
    "line_sep": lambda s: s.set_line_separator("_LS_\n"),
    "word_line_sep_p1": lambda s: (
        s.set_word_separator("~"),
        s.set_line_separator("#\n"),
        s.set_start_page(1),
        s.set_end_page(1),
    ),
    "para_markers": lambda s: (
        s.set_paragraph_start("[PS]"),
        s.set_paragraph_end("[PE]"),
    ),
    "page_markers": lambda s: (
        s.set_page_start("<S>"),
        s.set_page_end("<E>\n"),
    ),
    "all_separators": lambda s: (
        s.set_word_separator("|w|"),
        s.set_line_separator("|l|\n"),
        s.set_paragraph_start("|ps|"),
        s.set_paragraph_end("|pe|"),
        s.set_page_start("|S|"),
        s.set_page_end("|E|\n"),
    ),
    "empty_word_sep": lambda s: s.set_word_separator(""),
    "beads_true": lambda s: s.set_should_separate_by_beads(True),
    "beads_false": lambda s: s.set_should_separate_by_beads(False),
    "more_formatting": lambda s: s.set_add_more_formatting(True),
    "more_formatting_lsep": lambda s: (
        s.set_add_more_formatting(True),
        s.set_line_separator("/N/\n"),
    ),
    "suppress_dup_true": lambda s: s.set_suppress_duplicate_overlapping_text(True),
    "suppress_dup_false": lambda s: s.set_suppress_duplicate_overlapping_text(False),
    "suppress_dup_sorted": lambda s: (
        s.set_suppress_duplicate_overlapping_text(True),
        s.set_sort_by_position(True),
    ),
    "last_page_only": lambda s: (
        s.set_start_page(_PAGE_COUNT),
        s.set_end_page(_PAGE_COUNT),
    ),
    "last_page_sorted": lambda s: (
        s.set_start_page(_PAGE_COUNT),
        s.set_end_page(_PAGE_COUNT),
        s.set_sort_by_position(True),
    ),
}


@requires_oracle
def test_option_matrix_matches_pdfbox() -> None:
    """Every option/edge combination extracts byte-for-byte identically to
    Java PDFBox 3.0.7 across the 4-page synthetic document."""
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "doc.pdf")
        _build_pdf(path)
        java = _java_cases(path)
        # Sanity: the probe emitted every case we model.
        assert set(java) == set(_CONFIGS), (
            f"probe/test case-name drift: "
            f"java-only={set(java) - set(_CONFIGS)} "
            f"py-only={set(_CONFIGS) - set(java)}"
        )
        mismatches: list[str] = []
        for name, configure in _CONFIGS.items():
            py = _py(path, configure)
            if py != java[name]:
                mismatches.append(
                    f"{name}: py={py!r} java={java[name]!r}"
                )
        assert not mismatches, "option-matrix divergences:\n" + "\n".join(mismatches)


# ---------------------------------------------------------------------------
# Literal-shape assertions so a regression that silently changes BOTH engines
# (e.g. a probe that stopped emitting newlines) is still caught against a
# concrete expectation, independent of the live oracle.
# ---------------------------------------------------------------------------


@requires_oracle
def test_out_of_range_start_yields_empty() -> None:
    """A start page past the last page selects nothing -> empty string, no
    exception (PDFTextStripper.processPages just never enters a page)."""
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "doc.pdf")
        _build_pdf(path)
        java = _java_cases(path)
        assert java["start_beyond"] == ""
        assert _py(path, _CONFIGS["start_beyond"]) == ""
        # start > end is likewise empty.
        assert java["start_gt_end"] == ""
        assert _py(path, _CONFIGS["start_gt_end"]) == ""


@requires_oracle
def test_zero_and_negative_bounds_behave_like_full_or_empty() -> None:
    """A 0 / negative *start* clamps to the first page (full doc); a 0 /
    negative *end* selects nothing (empty)."""
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "doc.pdf")
        _build_pdf(path)
        java = _java_cases(path)
        assert java["start_zero"] == java["default_full"]
        assert java["start_negative"] == java["default_full"]
        assert java["end_zero"] == ""
        assert java["end_negative"] == ""
        for name in ("start_zero", "start_negative", "end_zero", "end_negative"):
            assert _py(path, _CONFIGS[name]) == java[name]


@requires_oracle
def test_whitespace_only_last_page_yields_only_page_separator() -> None:
    """Isolating the glyph-free final page yields just the page separator
    (one newline) in both engines."""
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "doc.pdf")
        _build_pdf(path)
        java = _java_cases(path)
        assert java["last_page_only"] == "\n"
        assert _py(path, _CONFIGS["last_page_only"]) == "\n"
