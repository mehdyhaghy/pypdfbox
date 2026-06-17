"""Live PDFBox differential parity for the TrueType ``OS/2`` table (FontBox).

Recent fontbox oracle waves covered ``hmtx`` (advance + LSB), ``glyf``
composite components, ``cmap`` lookup (incl. format 14), the legacy ``kern``
table, ``post``, ``name``, and glyph paths. This wave targets the
**``OS/2`` Windows metrics table** —
``org.apache.fontbox.ttf.OS2WindowsMetricsTable``, parsed by
``TrueTypeFont.getOS2Windows()``.

The probe enumerates every public accessor on the upstream table:

* the fixed v0 block — version, average char width, weight/width class,
  fsType, the sub/superscript size+offset quartets, strikeout size+position,
  family class, the 10-byte PANOSE blob, the four unicode-range words, the
  4-char vendor id, fsSelection, first/last char index, the typo
  ascender/descender/line-gap, and the win ascent/descent;
* the v1-gated code-page range words; and
* the v2-gated sxHeight / sCapHeight (``getHeight`` / ``getCapHeight``),
  default/break char and ``usMaxContext``.

FontBox returns ``0`` for any field above the table's declared version, so
the probe also pins that version-gating behaviour: ``LiberationSans-Regular``
carries a full **v3** table (every field populated) while ``DejaVuSansMono``
carries a **v1** table (the v2 fields short-circuit to 0). Both fonts are
already bundled under permissive licenses; no synthetic font is needed.

``Os2MetricsProbe`` output is reconstructed line-for-line on the Python side
and compared verbatim against Apache PDFBox 3.0.7.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXDIR = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "fontbox" / "ttf"
)
_LIBERATION = _FIXDIR / "LiberationSans-Regular.ttf"  # OS/2 version 3
_DEJAVU_MONO = _FIXDIR / "DejaVuSansMono.ttf"  # OS/2 version 1


def _py_os2(font_path: Path) -> str:
    """Reconstruct ``Os2MetricsProbe`` output from pypdfbox (line-for-line)."""
    ttf = TTFParser().parse(font_path)
    try:
        lines: list[str] = []
        os2 = ttf.get_os2_windows()
        if os2 is None:
            lines.append("OS2\tabsent")
            return "\n".join(lines) + "\n"
        lines.append("OS2\tpresent")
        lines.append(f"version\t{os2.get_version()}")
        lines.append(f"averageCharWidth\t{os2.get_average_char_width()}")
        lines.append(f"weightClass\t{os2.get_weight_class()}")
        lines.append(f"widthClass\t{os2.get_width_class()}")
        lines.append(f"fsType\t{os2.get_fs_type()}")
        lines.append(f"subscriptXSize\t{os2.get_subscript_x_size()}")
        lines.append(f"subscriptYSize\t{os2.get_subscript_y_size()}")
        lines.append(f"subscriptXOffset\t{os2.get_subscript_x_offset()}")
        lines.append(f"subscriptYOffset\t{os2.get_subscript_y_offset()}")
        lines.append(f"superscriptXSize\t{os2.get_superscript_x_size()}")
        lines.append(f"superscriptYSize\t{os2.get_superscript_y_size()}")
        lines.append(f"superscriptXOffset\t{os2.get_superscript_x_offset()}")
        lines.append(f"superscriptYOffset\t{os2.get_superscript_y_offset()}")
        lines.append(f"strikeoutSize\t{os2.get_strikeout_size()}")
        lines.append(f"strikeoutPosition\t{os2.get_strikeout_position()}")
        lines.append(f"familyClass\t{os2.get_family_class()}")
        lines.append(f"panose\t{os2.get_panose().hex()}")
        lines.append(f"unicodeRange1\t{os2.get_unicode_range1()}")
        lines.append(f"unicodeRange2\t{os2.get_unicode_range2()}")
        lines.append(f"unicodeRange3\t{os2.get_unicode_range3()}")
        lines.append(f"unicodeRange4\t{os2.get_unicode_range4()}")
        lines.append(f"achVendId\t{os2.get_ach_vend_id()}")
        lines.append(f"fsSelection\t{os2.get_fs_selection()}")
        lines.append(f"firstCharIndex\t{os2.get_first_char_index()}")
        lines.append(f"lastCharIndex\t{os2.get_last_char_index()}")
        lines.append(f"typoAscender\t{os2.get_typo_ascender()}")
        lines.append(f"typoDescender\t{os2.get_typo_descender()}")
        lines.append(f"typoLineGap\t{os2.get_typo_line_gap()}")
        lines.append(f"winAscent\t{os2.get_win_ascent()}")
        lines.append(f"winDescent\t{os2.get_win_descent()}")
        lines.append(f"codePageRange1\t{os2.get_code_page_range1()}")
        lines.append(f"codePageRange2\t{os2.get_code_page_range2()}")
        lines.append(f"height\t{os2.get_height()}")
        lines.append(f"capHeight\t{os2.get_cap_height()}")
        lines.append(f"defaultChar\t{os2.get_default_char()}")
        lines.append(f"breakChar\t{os2.get_break_char()}")
        lines.append(f"maxContext\t{os2.get_max_context()}")
        return "\n".join(lines) + "\n"
    finally:
        ttf.close()


def _assert_parity(font_path: Path) -> None:
    assert font_path.is_file(), f"missing fixture: {font_path}"
    java = run_probe_text("Os2MetricsProbe", str(font_path)).splitlines()
    py = _py_os2(font_path).splitlines()

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"first java: {java[:3]}\nfirst py:   {py[:3]}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "OS/2 parity broken:\n" + "\n".join(diffs[:40])


@requires_oracle
@pytest.mark.parametrize(
    "font_path",
    [_LIBERATION, _DEJAVU_MONO],
    ids=["liberation_sans_v3", "dejavu_sans_mono_v1"],
)
def test_os2_metrics_matches_pdfbox(font_path: Path) -> None:
    """Every ``OS/2`` accessor — including the version-gated v1/v2 fields and
    the PANOSE blob — must match Apache PDFBox 3.0.7 byte-for-byte.
    """
    _assert_parity(font_path)
