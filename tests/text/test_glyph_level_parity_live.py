"""Live PDFBox 3.0.8 differentials for glyph-level text extraction.

Builds content streams (rotated and 45 degree text, fake bold, accents,
spacing, paragraphs, graphics-state text parameters, ActualText) and
compares ``PDFTextStripper`` with PDFBox through ``StripperOptionsProbe``,
one JVM per option set, and checks the Java ``List.sort`` / PDFBox
``IterativeMergeSort`` ports against Java with ``ListSortProbe``.

Hand-written (not ported from upstream JUnit).
"""

import math
import random
from pathlib import Path

import pytest

from pypdfbox.text._tim_sort import ComparisonContractError, tim_sort
from pypdfbox.util.iterative_merge_sort import IterativeMergeSort
from tests.oracle.harness import requires_oracle, run_probe_text
from tests.text.test_glyph_level_parity import (
    _FIXTURES,
    _build,
    _rock_paper_scissors,
    _strip,
)


@requires_oracle
def test_sorts_match_java_on_random_sequences(tmp_path: Path) -> None:
    rng = random.Random(1605)
    sequences = [
        [rng.randrange(3) for _ in range(rng.choice([5, 31, 32, 33, 64, 100, 300]))]
        for _ in range(120)
    ]
    data = tmp_path / "sequences.txt"
    data.write_text("\n".join(" ".join(map(str, s)) for s in sequences) + "\n", encoding="utf-8")
    java = run_probe_text("ListSortProbe", str(data)).splitlines()
    for sequence, expected in zip(sequences, java, strict=True):
        tim = list(sequence)
        try:
            tim_sort(tim, _rock_paper_scissors)
            tim_text = ",".join(map(str, tim))
        except ComparisonContractError:
            tim_text = "THROW " + ",".join(map(str, tim))
        merged = list(sequence)
        IterativeMergeSort.sort(merged, _rock_paper_scissors)
        assert f"T {tim_text} | I {','.join(map(str, merged))}" == expected



# ---------------------------------------------------------------------------
# live differential
# ---------------------------------------------------------------------------

_LIVE_CONTENTS = [
    # Rotated words, sorted and not.
    b"BT /F1 14 Tf 0 1 -1 0 200 300 Tm (Ninety) Tj ET "
    b"BT /F1 14 Tf 0 -1 1 0 400 600 Tm (TwoSeventy) Tj ET "
    b"BT /F1 14 Tf -1 0 0 -1 500 100 Tm (OneEighty) Tj ET",
    # 45 degree text: direction 0, a non-transitive comparison when sorted.
    b"BT /F1 12 Tf %f %f %f %f 100 500 Tm (diagonal words here and there) Tj ET "
    b"BT /F2 10 Tf 120 480 Td (straight line under it) Tj ET"
    % (math.cos(math.pi / 4), math.sin(math.pi / 4), -math.sin(math.pi / 4), math.cos(math.pi / 4)),
    # Fake bold and repaints.
    b"BT /F1 12 Tf 100 700 Td (bold) Tj 0.5 0 Td (bold) Tj ET "
    b"BT /F2 12 Tf 100 680 Td (Hello) Tj 0 0.9 Td (Hello) Tj ET",
    # Separate accent glyphs merged into their letters.
    b"BT /F1 18 Tf 100 700 Td (e) Tj -8 0 Td (\\264) Tj 20 0 Td (a) Tj -9 0 Td (`) Tj ET",
    # Character / word spacing, horizontal scaling, TJ gaps, rise.
    b"BT /F1 10 Tf 2 Tc 100 700 Td (spaced out) Tj 0 Tc 4 Tw 0 -14 Td (word spacing here) Tj "
    b"150 Tz 0 -14 Td [(scaled) -500 (TJ) 120 (gap)] TJ 100 Tz 3 Ts (rise) Tj ET",
    # Paragraph detection: indents, drops, a bullet list.
    b"BT /F1 11 Tf 72 700 Td (First paragraph line one) Tj 0 -13 Td (line two) Tj "
    b"20 -13 Td (Indented start) Tj -20 -40 Td (After a drop) Tj 0 -13 Td (1. item) Tj "
    b"0 -13 Td (2. item) Tj ET",
    # q / Q around text and a cm.
    b"BT /F2 9 Tf ET q 1 0 0 1 30 -20 cm BT /F1 16 Tf 1 Tc 100 600 Td (inside) Tj ET Q "
    b"BT 100 620 Td (after restore) Tj ET",
    # ActualText spans.
    b"/Span <</ActualText (Replaced)>> BDC BT /F1 12 Tf 100 700 Td (abc def) Tj ET EMC "
    b"BT /F1 12 Tf 200 700 Td (plain) Tj ET",
]

_LIVE_OPTIONS = [
    ({}, "sort=0"),
    ({"sort": True}, "sort=1"),
    ({"suppress": False}, "suppress=0"),
    ({"sort": True, "ignore_spaces": True}, "sort=1,ignoreSpaces=1"),
    ({"add_more": True}, "addMore=1"),
    ({"markers": True}, "markers=1"),
]


@requires_oracle
@pytest.mark.parametrize(
    ("options", "probe_options"), _LIVE_OPTIONS, ids=[o for _, o in _LIVE_OPTIONS]
)
def test_live_differential(tmp_path: Path, options: dict, probe_options: str) -> None:
    paths = [
        _build(tmp_path / f"c{i}.pdf", [content]) for i, content in enumerate(_LIVE_CONTENTS)
    ]
    paths.append(_FIXTURES / "text" / "input" / "eu-001.pdf")
    out = run_probe_text("StripperOptionsProbe", probe_options, *(str(p) for p in paths))
    for i, path in enumerate(paths, start=1):
        start = out.index(f"<<<{i}\n") + len(f"<<<{i}\n")
        java = out[start : out.index(f">>>{i}\n", start)]
        assert _strip(path, **options) == java, path.name


_LIVE_FIXTURES = [
    "multipdf/PDFBOX-6049-ExpectedResult.pdf",
    "multipdf/PDFBOX-6049-Source.pdf",
    "multipdf/PDFBOX-6049-Overlay.pdf",
    "multipdf/Overlayed-with-rot0.pdf",
    "multipdf/Overlayed-with-rot90.pdf",
    "multipdf/Overlayed-with-rot180.pdf",
    "multipdf/Overlayed-with-rot270.pdf",
    "multipdf/PDFBOX-4417-001031.pdf",
    "multipdf/PDFBOX-4417-054080.pdf",
    "multipdf/PDFBOX-5762-722238.pdf",
    "multipdf/rot180.pdf",
    "pdmodel/font/PDFBOX-6249-cns1-nonembedded-latin.pdf",
    "pdmodel/interactive/form/PDFBOX-3656-SF1199AEG (Complete).pdf",
    "pdfwriter/PDFBOX-3110-poems-beads.pdf",
    "text/rotated_text_dir.pdf",
    "text/input/eu-001.pdf",
]


@requires_oracle
@pytest.mark.parametrize(
    ("options", "probe_options"), _LIVE_OPTIONS, ids=[o for _, o in _LIVE_OPTIONS]
)
def test_live_fixture_differential(options: dict, probe_options: str) -> None:
    paths = [_FIXTURES / name for name in _LIVE_FIXTURES]
    out = run_probe_text("StripperOptionsProbe", probe_options, *(str(p) for p in paths))
    for i, path in enumerate(paths, start=1):
        start = out.index(f"<<<{i}\n") + len(f"<<<{i}\n")
        java = out[start : out.index(f">>>{i}\n", start)]
        assert _strip(path, **options) == java, path.name
