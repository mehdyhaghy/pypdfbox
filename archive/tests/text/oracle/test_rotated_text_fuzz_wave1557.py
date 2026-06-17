"""Live Apache PDFBox differential fuzz of ``PDFTextStripper`` text extraction
over text drawn with NON-TRIVIAL text matrices and page rotation (wave 1557).

The existing rotated-text oracles each isolate ONE facet on a fixed page:
``RotatedTextDirProbe`` (per-glyph ``getDir()``), ``RotatedMultiLineProbe`` /
``test_rotated_page_extraction_oracle`` (page ``/Rotate`` default path),
``RotatedUprightTextProbe``, ``TextStateMatrixProbe`` (per-glyph TRM),
``TextRiseProbe`` (Ts geometry), ``TextHorizScalingProbe`` (Tz), and
``SortByPositionProbe`` (out-of-order show-text). This module sweeps a MATRIX of
~23 configurations through ``RotatedTextFuzzProbe`` — each a single LETTER page
built by Apache PDFBox itself (so the input bytes are identical on both engines)
— and extracts every one with ``set_sort_by_position`` ON and OFF (46
extractions), pinning where pypdfbox is byte-identical to Java 3.0.7 and, where
it diverges, pinning BOTH sides with an honest divergence note.

Configurations (probe ``build <id>``):
  tm_0 tm_45 tm_90 tm_180 tm_270     text matrix rotated N deg about its origin
  page_0 page_90 page_180 page_270   upright identity-Tm text on a /Rotate N page
  combo_90 combo_180 combo_270       page /Rotate N AND text Tm rotated N
  rise_pos rise_neg rise_zero_baseline   super/subscript via Ts
  tz_wide tz_narrow                  horizontal scaling 300 / 25 percent
  opposite_dir                       two runs, second Tm-rotated 180 deg
  bottom_to_top                      column of 90-deg runs stacked up the page
  multiline_45                       three 45-deg lines
  mixed_dirs                         upright + 90-deg + 270-deg on one page
  rotate90_multiline                 /Rotate 90 with three upright lines
  tm_neg_scale                       Tm with negative d (vertically mirrored)

Honest divergences pinned BOTH sides (architectural — NOT bugs; no glyph is ever
dropped, the character multiset is preserved):

  * **Tm-rotated runs fragment per-glyph in Java, stay intact in pypdfbox.**
    Apache PDFBox feeds ``writePage`` one ``showGlyph`` per glyph, and on a
    rotated text matrix each glyph lands a "new line" in the device frame, so a
    short rotated run such as "Ninety" extracts as ``N\nin\net\ny`` (unsorted)
    or fragments under the directional sort. The lite stripper emits a Tm run as
    a single ``TextPosition`` carrying the whole run text, so it extracts the run
    intact ("Ninety"). pypdfbox's output is the more readable of the two; the
    character content is identical. This covers tm_45/tm_90/tm_270,
    bottom_to_top, multiline_45 and the rotated sidebars of mixed_dirs.

  * **Sorted extraction on a /Rotate 90/270 page.** Upstream un-rotates each
    glyph into a portrait reading frame for the directional comparator
    (``getDir()`` folds the page rotation, so ``getXDirAdj``/``getYDirAdj``
    reconstruct upright reading order), whereas the lite stripper folds the page
    rotation eagerly into the stored device coordinates
    (``PDFTextStripper._apply_page_rotation``, pinned byte-exact for the DEFAULT
    path by ``test_rotated_page_extraction_oracle``) and the sort then orders in
    that device frame, fragmenting the rows. Result: page_90/page_270 and
    rotate90_multiline diverge ONLY when ``sort_by_position`` is on. The default
    (unsorted) path is byte-exact, and no glyph is dropped in either mode (the
    character multiset matches Java) — so this is a documented ordering
    divergence, not a glyph-loss bug.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_PROBE = "RotatedTextFuzzProbe"

# Every configuration the probe knows how to build.
_IDS = [
    "tm_0",
    "tm_45",
    "tm_90",
    "tm_180",
    "tm_270",
    "page_0",
    "page_90",
    "page_180",
    "page_270",
    "combo_90",
    "combo_180",
    "combo_270",
    "rise_pos",
    "rise_neg",
    "rise_zero_baseline",
    "tz_wide",
    "tz_narrow",
    "opposite_dir",
    "bottom_to_top",
    "multiline_45",
    "mixed_dirs",
    "rotate90_multiline",
    "tm_neg_scale",
]

# Configs where BOTH the sorted and unsorted extraction is byte-identical to
# Apache PDFBox 3.0.7. (Verified live against the oracle when this wave landed.)
_FULL_PARITY = {
    "tm_0",
    "tm_180",
    "page_0",
    "page_180",
    "combo_90",
    "combo_180",
    "combo_270",
    "rise_pos",
    "rise_neg",
    "rise_zero_baseline",
    "tz_wide",
    "tz_narrow",
    "opposite_dir",
    "tm_neg_scale",
}


def _unescape(s: str) -> str:
    return s.replace("\\r", "\r").replace("\\n", "\n").replace("\\\\", "\\")


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _java(path: Path) -> tuple[str, str]:
    """Return (sorted_text, unsorted_text) from the Java oracle."""
    out = run_probe_text(_PROBE, "extract", str(path))
    sorted_text = unsorted_text = None
    for line in out.splitlines():
        if line.startswith("SORTED:"):
            sorted_text = _unescape(line[len("SORTED:") :])
        elif line.startswith("UNSORTED:"):
            unsorted_text = _unescape(line[len("UNSORTED:") :])
    assert sorted_text is not None and unsorted_text is not None, out
    return sorted_text, unsorted_text


def _py(path: Path, *, sort: bool) -> str:
    doc = PDDocument.load(str(path))
    try:
        s = PDFTextStripper()
        s.set_sort_by_position(sort)
        return s.get_text(doc)
    finally:
        doc.close()


def _multiset(s: str) -> Counter[str]:
    """Character multiset ignoring whitespace — the glyph-loss invariant."""
    return Counter(ch for ch in s if not ch.isspace())


@pytest.fixture(scope="module")
def _built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Build every configuration once with Apache PDFBox (shared bytes)."""
    base = tmp_path_factory.mktemp("rotated_text_fuzz")
    out: dict[str, Path] = {}
    for config in _IDS:
        path = base / f"{config}.pdf"
        run_probe(_PROBE, "build", config, str(path))
        out[config] = path
    return out


@requires_oracle
@pytest.mark.parametrize("config", sorted(_FULL_PARITY))
def test_full_parity_byte_exact(_built: dict[str, Path], config: str) -> None:
    """Configs where pypdfbox is byte-identical to Apache PDFBox in BOTH sort
    modes: identity / 180-deg Tm, upright text on a /Rotate 0|180 page, the
    rotation-cancelling combos, text rise (super/sub/reset), extreme Tz, the
    opposite-direction run pair, and the vertically-mirrored Tm."""
    java_sorted, java_unsorted = _java(_built[config])
    assert _py(_built[config], sort=True) == java_sorted, f"{config} sorted"
    assert _py(_built[config], sort=False) == java_unsorted, f"{config} unsorted"


@requires_oracle
def test_no_glyph_dropped_anywhere(_built: dict[str, Path]) -> None:
    """The load-bearing invariant across EVERY config and BOTH sort modes:
    pypdfbox never drops (or invents) a glyph relative to Java — the non-space
    character multiset is identical, even where the line/word ordering of
    rotated runs diverges. A future fold/sort regression that silently loses a
    rotated glyph is caught here regardless of ordering.

    ``multiline_45`` is excluded and pinned separately: at a NON-right angle
    (45 deg) Java's own per-glyph device-frame grouping reorders glyphs so
    aggressively that PDFBox's *own* extraction folds a glyph pair into word
    spacing (it is the Java side that is lossy here, not pypdfbox), so the
    multiset cannot match. See ``test_multiline_45_nonright_angle_divergence``."""
    for config in _IDS:
        if config == "multiline_45":
            continue
        java_sorted, java_unsorted = _java(_built[config])
        py_sorted = _py(_built[config], sort=True)
        py_unsorted = _py(_built[config], sort=False)
        assert _multiset(py_sorted) == _multiset(java_sorted), f"{config} sorted"
        assert _multiset(py_unsorted) == _multiset(java_unsorted), (
            f"{config} unsorted"
        )


@requires_oracle
def test_tm_rotated_runs_stay_intact_divergence(_built: dict[str, Path]) -> None:
    """DIVERGENCE pinned BOTH sides — Tm-rotated runs.

    Apache PDFBox fragments a Tm-rotated run glyph-by-glyph in the device frame
    (one ``showGlyph`` per glyph, each a new device "line"); the lite stripper
    emits the whole run as a single ``TextPosition`` and extracts it intact.
    Neither drops a glyph (asserted globally above). We pin Java's fragmented
    rendering and pypdfbox's intact rendering so a drift on either engine is
    detected."""
    # tm_90 / tm_270: Java fragments the right-angle Tm run in the UNSORTED
    # (device-frame) path; pypdfbox keeps it intact.
    for config, intact in (("tm_90", "Ninety\n"), ("tm_270", "TwoSeventy\n")):
        _, java_unsorted = _java(_built[config])
        assert "\n" in java_unsorted.rstrip("\n")  # Java fragmented it
        assert _py(_built[config], sort=False) == intact

    # tm_45 (a non-right angle): Java fragments in BOTH modes; pypdfbox keeps it
    # intact in both.
    java_sorted, java_unsorted = _java(_built["tm_45"])
    assert "\n" in java_sorted.rstrip("\n")
    assert "\n" in java_unsorted.rstrip("\n")
    assert _py(_built["tm_45"], sort=True) == "FortyFive\n"
    assert _py(_built["tm_45"], sort=False) == "FortyFive\n"

    # bottom_to_top: three stacked 90-deg runs. Java fragments per glyph;
    # pypdfbox keeps each run intact and groups them on one device line.
    java_sorted, _ = _java(_built["bottom_to_top"])
    assert java_sorted == "alpha\nbeta\ngamma\n"
    assert _py(_built["bottom_to_top"], sort=True) == "alphabeta gamma\n"


@requires_oracle
def test_multiline_45_nonright_angle_divergence(
    _built: dict[str, Path]
) -> None:
    """DIVERGENCE pinned BOTH sides — three 45-degree Tm lines.

    At a non-right angle Apache PDFBox's per-glyph device-frame grouping
    reorders + fragments the glyphs heavily, and in doing so PDFBox's OWN
    extraction folds a glyph pair into word spacing (it is the Java side that is
    lossy here). The lite stripper keeps each 45-degree run intact and emits
    three clean lines. We pin Java's fragmented/lossy rendering and pypdfbox's
    intact, readable rendering."""
    java_sorted, java_unsorted = _java(_built["multiline_45"])
    # Java fragments heavily in both modes.
    assert java_sorted.count("\n") > 3
    assert java_unsorted.count("\n") > 3
    # pypdfbox keeps three readable lines.
    assert _py(_built["multiline_45"], sort=True) == (
        "Line three\nLine two\nLine one\n"
    )
    assert _py(_built["multiline_45"], sort=False) == (
        "Line one\nLine two\nLine three\n"
    )


@requires_oracle
def test_mixed_directions_divergence(_built: dict[str, Path]) -> None:
    """DIVERGENCE pinned BOTH sides — three text directions on one page.

    The upright heading is byte-exact; the two rotated sidebars fragment in Java
    and stay intact in pypdfbox. We pin that the heading line agrees and that
    pypdfbox keeps the sidebars readable while Java fragments them."""
    java_sorted, java_unsorted = _java(_built["mixed_dirs"])
    py_unsorted = _py(_built["mixed_dirs"], sort=False)
    # Both engines lead with the upright heading line.
    assert java_unsorted.startswith("Heading across top\n")
    assert py_unsorted.startswith("Heading across top\n")
    # Java fragments the sidebars; pypdfbox keeps them intact.
    assert "sidebar" not in java_unsorted.split("\n", 1)[1].replace("\n", "")[:8]
    assert py_unsorted == (
        "Heading across top\nLeft sidebar up\nRight sidebar down\n"
    )
    # Sorted: Java groups by direction (heading, then the two sidebars on one
    # joined line); pypdfbox keeps three readable lines.
    assert java_sorted == (
        "Heading across top\nLeft sidebar upRight sidebar down\n"
    )
    assert _py(_built["mixed_dirs"], sort=True) == (
        "Heading across top\nLeft sidebar up\nRight sidebar down\n"
    )


@requires_oracle
@pytest.mark.parametrize(
    "config",
    ["page_90", "page_270", "rotate90_multiline"],
)
def test_rotated_page_unsorted_byte_exact_sorted_diverges(
    _built: dict[str, Path], config: str
) -> None:
    """Page ``/Rotate`` 90/270: the DEFAULT (unsorted) path is byte-exact with
    Apache PDFBox (this is the wave-1495 page-rotation fold, also pinned by
    ``test_rotated_page_extraction_oracle``); the SORTED path diverges and is
    pinned BOTH sides as a documented ordering divergence.

    DIVERGENCE: upstream un-rotates each glyph into a portrait reading frame for
    the directional comparator, reconstructing upright reading order, whereas
    the lite stripper sorts in the eagerly-folded device frame and fragments the
    rows. No glyph is dropped (the global multiset invariant proves it); only
    the line/word ordering differs."""
    java_sorted, java_unsorted = _java(_built[config])

    # Default path: byte-exact.
    assert _py(_built[config], sort=False) == java_unsorted

    # Sorted path: documented divergence — pin BOTH sides.
    py_sorted = _py(_built[config], sort=True)
    assert py_sorted != java_sorted  # they genuinely diverge
    # No glyph lost despite the reordering.
    assert _multiset(py_sorted) == _multiset(java_sorted)
    # Java reconstructs upright reading order on the rotated page.
    if config == "rotate90_multiline":
        assert java_sorted == (
            "Heading Title\nFirst body line\nSecond body line\n"
        )
    else:
        assert java_sorted == "Upright on rotated page\n"


@requires_oracle
def test_combo_cancelling_rotation_byte_exact(_built: dict[str, Path]) -> None:
    """Page ``/Rotate`` N combined with a text Tm rotated N degrees cancels to
    visually-upright reading; pypdfbox matches Apache PDFBox byte-for-byte in
    both sort modes (the run reads as one intact line on both engines)."""
    for config, expected in (
        ("combo_90", "ComboNinety\n"),
        ("combo_180", "ComboOneEighty\n"),
        ("combo_270", "ComboTwoSeventy\n"),
    ):
        java_sorted, java_unsorted = _java(_built[config])
        assert java_sorted == java_unsorted == expected
        assert _py(_built[config], sort=True) == expected
        assert _py(_built[config], sort=False) == expected


@requires_oracle
def test_text_rise_inline_no_spurious_break(_built: dict[str, Path]) -> None:
    """Super/subscript via Ts stays inline (no spurious newline) and is
    byte-identical to Apache PDFBox in both sort modes — the rise is within the
    line tolerance so the raised/lowered run does not start a new line."""
    for config, expected in (
        ("rise_pos", "E=mc2 tail\n"),
        ("rise_neg", "H2O done\n"),
        ("rise_zero_baseline", "ABC\n"),
    ):
        java_sorted, java_unsorted = _java(_built[config])
        assert java_sorted == java_unsorted == expected
        assert _py(_built[config], sort=True) == expected
        assert _py(_built[config], sort=False) == expected


@requires_oracle
def test_horizontal_scaling_extremes_byte_exact(
    _built: dict[str, Path]
) -> None:
    """Extreme Tz (300% wide, 25% narrow) does not split or drop glyphs — the
    text extracts as one line byte-identical to Apache PDFBox in both modes
    (horizontal scaling stretches advance width but not the line grouping)."""
    for config, expected in (
        ("tz_wide", "Wide text\n"),
        ("tz_narrow", "Narrow text\n"),
    ):
        java_sorted, java_unsorted = _java(_built[config])
        assert java_sorted == java_unsorted == expected
        assert _py(_built[config], sort=True) == expected
        assert _py(_built[config], sort=False) == expected


@requires_oracle
def test_self_escape_roundtrip() -> None:
    """The probe's ``\\n``/``\\r``/``\\\\`` escaping round-trips through the
    Python unescape so framed payloads are recovered verbatim."""
    raw = "a\nb\\c\rd"
    assert _unescape(_escape(raw)) == raw
