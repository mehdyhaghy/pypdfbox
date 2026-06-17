"""Live Apache PDFBox differential FUZZING of the high-level
``PDPageContentStream`` WRITER API (wave 1549).

Sibling to ``test_content_stream_gen_oracle.py`` (fixed drawing script + the
float formatter in isolation). This module drives a *battery* of short
edge-case op sequences through the live PDFBox 3.0.7 oracle
(``ContentStreamGenFuzzProbe``) and through pypdfbox, then asserts each case's
projection agrees:

- **byte-parity cases** — the call sequence is legal in both writers and must
  emit byte-identical content-stream bytes (after collapsing the auto-allocated
  font-resource key ``/F1`` upstream vs ``/F0`` pypdfbox — a resource-slot
  surface, not a formatting difference). Covers: out-of-range-but-valid colour
  boundaries, negative / zero / huge line widths, empty / zero / fractional
  dash patterns with phase, tiny / large / negative-zero float operands
  (number-format precision), extreme transform matrices, multiple BT/ET blocks,
  ``showText`` paren/backslash escaping, fractional font size, save/restore
  nesting, ``setTextMatrix`` extremes, ``newLineAtOffset``.

- **both-raise cases** — the call sequence is rejected by *both* writers
  (out-of-range colour components, non-finite NaN/Inf coordinates, path op
  inside a text block, nested beginText, endText without beginText, newLine
  without beginText). pypdfbox's ``ValueError`` mirrors PDFBox's
  ``IllegalArgumentException`` and ``RuntimeError`` mirrors
  ``IllegalStateException``; the out-of-range-colour and not-a-finite-number
  *messages* are byte-identical to upstream.

- **documented-divergence cases** — the lite ``PDPageContentStream`` surface
  intentionally broadens two behaviours relative to upstream (recorded in
  CHANGES.md):
    1. ``show_text`` does NOT run the font glyph encoder, so control characters
       / non-WinAnsi text that upstream rejects
       (``IllegalArgumentException: U+0009 ... is not available in the font``)
       are emitted by pypdfbox (latin-1 literal, or UTF-16BE hex fallback).
    2. ``show_text_with_positioning`` accepts ``int`` position adjustments,
       whereas upstream's ``showTextWithPositioning(Object[])`` only accepts
       ``Float`` + ``String`` and raises ``IllegalArgumentException`` on an
       ``Integer``.
  These are pinned here as expected divergences so a regression that
  *accidentally* matched upstream (or drifted further) is caught.

Decorated ``@requires_oracle`` — skips without Java + the pinned jar. The
probe is the authority for the upstream side; the byte-parity expectations are
NOT hand-copied. Hand-written.
"""

from __future__ import annotations

import base64
import re

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "ContentStreamGenFuzzProbe"


def _font() -> object:
    return PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)


def _run(script) -> bytes:
    """Drive ``script`` through a fresh pypdfbox PDPageContentStream and
    return the flushed content-stream bytes."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        try:
            script(cs)
        finally:
            cs.close()
        return bytes(cs.get_target_stream().create_input_stream().read())
    finally:
        doc.close()


def _norm_font_key(data: bytes) -> bytes:
    """Collapse ``/F<n>`` resource keys (upstream /F1 vs pypdfbox /F0) — a
    resource-slot surface, not a formatting difference."""
    return re.sub(rb"/F\d+", rb"/F", data)


# ---------------------------------------------------------------------------
# Case scripts. Names MUST match the probe's case names.
# ---------------------------------------------------------------------------

# Cases whose emitted bytes must be byte-identical to upstream.
_BYTE_PARITY: dict[str, object] = {
    "show_text_parens_backslash": lambda cs: (
        cs.begin_text(),
        cs.set_font(_font(), 12),
        cs.show_text("a(b)c\\d"),
        cs.end_text(),
    ),
    "show_text_empty": lambda cs: (
        cs.begin_text(),
        cs.set_font(_font(), 12),
        cs.show_text(""),
        cs.end_text(),
    ),
    "set_font_size_zero": lambda cs: (
        cs.begin_text(),
        cs.set_font(_font(), 0),
        cs.end_text(),
    ),
    "set_font_size_negative": lambda cs: (
        cs.begin_text(),
        cs.set_font(_font(), -12),
        cs.end_text(),
    ),
    "set_font_size_fractional": lambda cs: (
        cs.begin_text(),
        cs.set_font(_font(), 10.333),
        cs.end_text(),
    ),
    "rgb_boundary_zero_one": lambda cs: cs.set_non_stroking_color(0.0, 1.0, 0.5),
    "line_width_negative": lambda cs: cs.set_line_width(-3.5),
    "line_width_zero": lambda cs: cs.set_line_width(0),
    "line_width_huge": lambda cs: cs.set_line_width(1.0e9),
    "dash_empty": lambda cs: cs.set_line_dash_pattern([], 0),
    "dash_zero_elements": lambda cs: cs.set_line_dash_pattern([0, 0], 0),
    "dash_with_phase": lambda cs: cs.set_line_dash_pattern([3, 2], 1.5),
    "dash_fractional": lambda cs: cs.set_line_dash_pattern([1.25, 0.75], 0.5),
    "add_rect_tiny_float": lambda cs: cs.add_rect(
        0.000005, 0.000004, 0.000025, 0.123455
    ),
    "line_to_large_float": lambda cs: (
        cs.move_to(0, 0),
        cs.line_to(12345.6789, 999999.5),
    ),
    "transform_extreme_matrix": lambda cs: cs.transform(
        1.0e6, 0, 0, 1.0e6, -50000.25, 0.000001
    ),
    "transform_negative_scale": lambda cs: cs.transform(-1, 0, 0, -1, 100, 200),
    "new_line_at_offset_negative": lambda cs: (
        cs.begin_text(),
        cs.new_line_at_offset(-72.5, -10),
        cs.end_text(),
    ),
    "multiple_bt_et_blocks": lambda cs: (
        cs.begin_text(),
        cs.set_font(_font(), 12),
        cs.show_text("one"),
        cs.end_text(),
        cs.begin_text(),
        cs.show_text("two"),
        cs.end_text(),
    ),
    "save_restore_pairs": lambda cs: (
        cs.save_graphics_state(),
        cs.save_graphics_state(),
        cs.restore_graphics_state(),
        cs.restore_graphics_state(),
    ),
    "set_leading_and_newline": lambda cs: (
        cs.begin_text(),
        cs.set_font(_font(), 12),
        cs.set_leading(14.5),
        cs.new_line(),
        cs.end_text(),
    ),
    "set_text_matrix_extreme": lambda cs: (
        cs.begin_text(),
        cs.set_text_matrix(2.5, 0, 0, 2.5, 0.000001, 1.0e7),
        cs.end_text(),
    ),
    "negative_zero_operand": lambda cs: cs.move_to(-0.000005, 0),
}

# Cases rejected by BOTH writers. Value = the pypdfbox exception type expected.
_BOTH_RAISE: dict[str, type[Exception]] = {
    "stroking_color_gray_out_of_range_high": ValueError,
    "stroking_color_gray_out_of_range_low": ValueError,
    "non_stroking_rgb_out_of_range": ValueError,
    "stroking_cmyk_out_of_range": ValueError,
    "move_to_nan": ValueError,
    "move_to_pos_inf": ValueError,
    "move_to_neg_inf": ValueError,
    "path_op_inside_text_block": RuntimeError,
    "nested_begin_text": RuntimeError,
    "end_text_without_begin": RuntimeError,
    "new_line_without_begin": RuntimeError,
}

_BOTH_RAISE_SCRIPTS: dict[str, object] = {
    "stroking_color_gray_out_of_range_high": lambda cs: cs.set_stroking_color(
        1.5
    ),
    "stroking_color_gray_out_of_range_low": lambda cs: cs.set_stroking_color(
        -0.1
    ),
    "non_stroking_rgb_out_of_range": lambda cs: cs.set_non_stroking_color(
        0.0, 1.2, 0.0
    ),
    "stroking_cmyk_out_of_range": lambda cs: cs.set_stroking_color(
        0.1, 0.2, 0.3, 2.0
    ),
    "move_to_nan": lambda cs: cs.move_to(float("nan"), 100),
    "move_to_pos_inf": lambda cs: cs.move_to(float("inf"), 100),
    "move_to_neg_inf": lambda cs: cs.line_to(0, float("-inf")),
    "path_op_inside_text_block": lambda cs: (cs.begin_text(), cs.move_to(0, 0)),
    "nested_begin_text": lambda cs: (cs.begin_text(), cs.begin_text()),
    "end_text_without_begin": lambda cs: cs.end_text(),
    "new_line_without_begin": lambda cs: cs.new_line(),
}


def _probe_results() -> dict[str, tuple[str, str]]:
    """Run the probe once; map case-name -> (status, payload).

    For an ``OK`` line payload is the base64 stream bytes; for an ``EXC`` line
    payload is ``"<exception-class>\t<message>"``.
    """
    out = run_probe_text(_PROBE)
    results: dict[str, tuple[str, str]] = {}
    for line in out.splitlines():
        if not line:
            continue
        parts = line.split("\t", 2)
        name, status = parts[0], parts[1]
        payload = parts[2] if len(parts) > 2 else ""
        results[name] = (status, payload)
    return results


@requires_oracle
def test_byte_parity_cases_match_pdfbox() -> None:
    """Each legal edge-case sequence emits byte-identical content bytes."""
    results = _probe_results()
    for name, script in _BYTE_PARITY.items():
        assert name in results, f"probe produced no result for {name!r}"
        status, payload = results[name]
        assert status == "OK", (
            f"{name}: probe reported {status} ({payload!r}); pypdfbox treats "
            "this as a byte-parity case"
        )
        java = base64.b64decode(payload)
        py = _run(script)
        assert _norm_font_key(py) == _norm_font_key(java), (
            f"{name}: content-stream bytes diverge:\n"
            f"  pypdfbox: {py!r}\n  PDFBox:   {java!r}"
        )


@requires_oracle
def test_both_raise_cases_rejected_by_both() -> None:
    """Sequences upstream rejects are also rejected by pypdfbox."""
    results = _probe_results()
    for name, exc_type in _BOTH_RAISE.items():
        assert name in results, f"probe produced no result for {name!r}"
        status, _ = results[name]
        assert status == "EXC", (
            f"{name}: probe reported {status}; expected upstream to raise"
        )
        with pytest.raises(exc_type):
            _run(_BOTH_RAISE_SCRIPTS[name])


@requires_oracle
def test_out_of_range_colour_message_matches_pdfbox() -> None:
    """The DeviceGray/RGB/CMYK out-of-range guard messages are byte-identical
    to upstream's ``IllegalArgumentException`` text."""
    results = _probe_results()
    cases = {
        "stroking_color_gray_out_of_range_high": (
            lambda cs: cs.set_stroking_color(1.5)
        ),
        "non_stroking_rgb_out_of_range": (
            lambda cs: cs.set_non_stroking_color(0.0, 1.2, 0.0)
        ),
        "stroking_cmyk_out_of_range": (
            lambda cs: cs.set_stroking_color(0.1, 0.2, 0.3, 2.0)
        ),
    }
    for name, script in cases.items():
        status, payload = results[name]
        assert status == "EXC"
        # payload is "<ExceptionClass>\t<message>"
        java_msg = payload.split("\t", 1)[1]
        with pytest.raises(ValueError) as exc:
            _run(script)
        assert str(exc.value) == java_msg, (
            f"{name}: message diverges: pypdfbox={str(exc.value)!r} "
            f"PDFBox={java_msg!r}"
        )


# ---------------------------------------------------------------------------
# Documented divergences (lite-surface broadenings). Pin BOTH sides so a
# regression that drifts either direction is named.
# ---------------------------------------------------------------------------


@requires_oracle
def test_show_text_control_char_diverges_from_pdfbox() -> None:
    """Upstream rejects WinAnsi-unavailable chars via the font glyph encoder;
    the lite ``show_text`` skips encoding and emits the bytes (CHANGES.md)."""
    results = _probe_results()
    for name in ("show_text_tab", "show_text_newline", "show_text_carriage_return"):
        status, payload = results[name]
        assert status == "EXC", (
            f"{name}: upstream now {status} ({payload!r}); the divergence note "
            "in CHANGES.md may be stale"
        )
        assert "is not available in the font" in payload

    # pypdfbox emits without raising: tab stays a literal (ASCII-safe),
    # newline / CR fall to the hex form (match upstream COSWriter's
    # is-ASCII break on \\r / \\n).
    tab = _run(
        lambda cs: (
            cs.begin_text(),
            cs.set_font(_font(), 12),
            cs.show_text("a\tb"),
            cs.end_text(),
        )
    )
    assert b"(a\tb) Tj" in tab
    nl = _run(
        lambda cs: (
            cs.begin_text(),
            cs.set_font(_font(), 12),
            cs.show_text("a\nb"),
            cs.end_text(),
        )
    )
    assert b"<610A62> Tj" in nl


@requires_oracle
def test_show_text_with_positioning_int_diverges_from_pdfbox() -> None:
    """Upstream's ``showTextWithPositioning`` accepts only Float + String and
    raises ``IllegalArgumentException`` on an ``Integer``; the lite surface
    accepts ``int`` position adjustments (CHANGES.md)."""
    results = _probe_results()
    status, payload = results["text_with_positioning"]
    assert status == "EXC", (
        "upstream now accepts an int in showTextWithPositioning; the "
        "divergence note in CHANGES.md may be stale"
    )
    assert "array of Float and String" in payload

    # pypdfbox accepts the int and serialises it as a position adjustment.
    out = _run(
        lambda cs: (
            cs.begin_text(),
            cs.set_font(_font(), 12),
            cs.show_text_with_positioning(["A", -120.5, "B", 50, "C"]),
            cs.end_text(),
        )
    )
    assert b"[(A)-120.5 (B)50 (C)] TJ" in out
