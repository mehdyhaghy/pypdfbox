"""Wave 1483 — PDType3CharProc glyph-metric edge cases pinned to live PDFBox.

Oracle-confirmed against Apache PDFBox 3.0.7 (probe
``oracle/probes/Type3CharProcEdgeProbe.java``). Covers the malformed /
boundary char-proc shapes the well-formed accessor oracle never exercises:

* ``getGlyphBBox()`` returns a bbox **only** when the leading operator is
  ``d1`` with *exactly six* operands — upstream's ``arguments.size() == 6``.
  A ``d1`` with seven or more operands falls into the ``else`` branch and
  returns ``null``. Before this wave the port used ``len(operands) < 6``,
  so a 7-operand ``d1`` wrongly computed a bbox (BUG fixed this wave).
* ``getWidth()`` reads the first operand of the leading ``d0`` / ``d1``
  operator; leading comments / whitespace are skipped; a ``d1`` with too
  few operands still yields its first operand as the width (or ``0`` when
  the first operand is itself ``0``).

The pypdfbox port is intentionally *more lenient* than upstream for the
truly broken streams (non-numeric first operand, missing ``d0``/``d1``
operator, empty stream): upstream raises ``IOException`` there, pypdfbox
returns ``0.0`` so font-wide bbox/width scans don't abort on one bad glyph.
Those leniency cases are pinned in the existing char-proc tests and are NOT
re-asserted differentially here (the probe omits them).
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from tests.oracle.harness import requires_oracle, run_probe_text


def _proc(body: bytes) -> PDType3CharProc:
    glyph = COSStream()
    glyph.set_data(body)
    return PDType3CharProc(PDType3Font(), glyph)


def _bbox_str(proc: PDType3CharProc) -> str:
    r = proc.get_glyph_bbox()
    if r is None:
        return "NULL"
    return (
        f"{r.get_lower_left_x():.4f},{r.get_lower_left_y():.4f},"
        f"{r.get_upper_right_x():.4f},{r.get_upper_right_y():.4f}"
    )


# (label, body, expected_width, expected_bbox) — literals confirmed by the
# Java probe so these tests pass WITHOUT the oracle.
_CASES = [
    ("d1_normal", b"750 0 0 0 500 700 d1\n0 0 500 700 re f",
     750.0, "0.0000,0.0000,500.0000,700.0000"),
    ("d0_normal", b"640 0 d0\n0 0 500 700 re f", 640.0, "NULL"),
    ("d1_leading_comment", b"% comment line\n750 0 0 0 500 700 d1\nf",
     750.0, "0.0000,0.0000,500.0000,700.0000"),
    ("d1_leading_ws", b"   \n\t 750 0 0 0 500 700 d1\nf",
     750.0, "0.0000,0.0000,500.0000,700.0000"),
    ("d1_5args", b"750 0 0 0 500 d1\nf", 750.0, "NULL"),
    # The fix: a d1 with seven operands must return NULL (upstream == 6).
    ("d1_7args", b"750 0 0 0 500 700 900 d1\nf", 750.0, "NULL"),
    ("d1_4args", b"0 0 500 700 d1\nf", 0.0, "NULL"),
    ("d0_only_wx", b"640 d0\nf", 640.0, "NULL"),
    ("d1_realnums", b"750.5 0 10.25 20.5 510.75 720.0 d1\nf",
     750.5, "10.2500,20.5000,510.7500,720.0000"),
    ("d1_negative", b"750 0 -10 -20 500 700 d1\nf",
     750.0, "-10.0000,-20.0000,500.0000,700.0000"),
    # Trailing garbage after a valid 6-operand d1 is ignored — only the
    # first operator is read.
    ("d1_then_garbage", b"750 0 0 0 500 700 d1 extra 99 d0\nf",
     750.0, "0.0000,0.0000,500.0000,700.0000"),
]


def test_d1_with_seven_operands_returns_no_bbox() -> None:
    """A ``d1`` with more than six operands must yield ``None`` from
    ``get_glyph_bbox`` (upstream requires ``arguments.size() == 6``)."""
    proc = _proc(b"750 0 0 0 500 700 900 d1\nf")
    assert proc.get_glyph_bbox() is None
    # ...while the width is still the first operand.
    assert proc.get_width() == 750.0


def test_d1_with_exactly_six_operands_yields_bbox() -> None:
    proc = _proc(b"750 0 10 20 500 700 d1\nf")
    r = proc.get_glyph_bbox()
    assert r is not None
    assert (
        r.get_lower_left_x(),
        r.get_lower_left_y(),
        r.get_upper_right_x(),
        r.get_upper_right_y(),
    ) == (10.0, 20.0, 500.0, 700.0)


def test_leading_comment_and_whitespace_skipped() -> None:
    proc = _proc(b"% glyph header\n   \t750 0 0 0 500 700 d1\nf")
    assert proc.get_width() == 750.0
    r = proc.get_glyph_bbox()
    assert r is not None
    assert r.get_upper_right_x() == 500.0


def test_all_edge_literals_match_pinned_values() -> None:
    """Every probed case matches the PDFBox-confirmed width + bbox."""
    for label, body, exp_w, exp_bbox in _CASES:
        proc = _proc(body)
        assert proc.get_width() == exp_w, f"{label}: width"
        assert _bbox_str(proc) == exp_bbox, f"{label}: bbox"


@requires_oracle
def test_char_proc_metric_edges_match_pdfbox() -> None:
    """Differential: the synthetic char-proc edge cases line up with live
    Apache PDFBox 3.0.7 for every case the port does not deliberately
    diverge on (the probe omits the lenient IOException-vs-0.0 cases)."""
    java = run_probe_text("Type3CharProcEdgeProbe")
    java_lines = {
        line.split("\t", 1)[0]: line
        for line in java.rstrip().splitlines()
    }
    for label, body, _exp_w, _exp_bbox in _CASES:
        proc = _proc(body)
        py = f"{label}\tWIDTH={proc.get_width():.6f}\tBBOX={_bbox_str(proc)}"
        assert label in java_lines, f"probe missing case {label}"
        assert py == java_lines[label], (
            f"divergence for {label}:\n  java={java_lines[label]!r}\n"
            f"  py  ={py!r}"
        )
