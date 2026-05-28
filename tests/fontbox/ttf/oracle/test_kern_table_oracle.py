"""Live PDFBox differential parity for the TrueType ``kern`` table (FontBox).

Recent fontbox oracle waves covered ``hmtx`` (advance + LSB), ``glyf``
composite components, ``cmap`` lookup, Type1/Type2 charstrings and embedded
CMaps. This wave targets the legacy ``kern`` table — specifically the
**format-0 horizontal kerning subtable**:

* ``KerningTable.get_horizontal_kerning_subtable()`` selection (and the
  cross-stream overload), which walks the subtables and returns the first
  inline-progression horizontal one.
* The selected subtable's coverage as observed through the only public
  coverage accessors upstream exposes — ``is_horizontal_kerning()`` and
  ``is_horizontal_kerning(cross=True)``.
* ``KerningSubtable.get_kerning(left, right)`` — the binary-search lookup over
  the sorted ``(left, right, value)`` pair list, returning a signed design-unit
  adjustment on hit and 0 on miss / out-of-range / negative-sentinel GID.
* ``KerningSubtable.get_kerning(glyphs)`` — the sequence overload where the
  Nth adjustment pairs glyph N with the next NON-NEGATIVE glyph (so a -1
  sentinel in the middle of the sequence is skipped).

The fixture is ``LiberationSans-Regular.ttf`` (already bundled; permissive
license), which carries a real ``version 0`` ``kern`` table with a single
format-0 horizontal subtable of 908 Latin/Greek kerning pairs. No synthetic
font is needed.

Output of ``KernTableProbe`` is reconstructed line-for-line on the Python side
and compared verbatim against Apache PDFBox 3.0.7.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _pairs(num_glyphs: int) -> list[tuple[int, int]]:
    """Mirror ``KernTableProbe.pairs`` exactly: a dense grid over low GIDs
    plus boundary / out-of-range / negative-sentinel probes."""
    out: list[tuple[int, int]] = []
    cap = min(num_glyphs, 90)
    for left in range(cap):
        for right in range(cap):
            out.append((left, right))
    out.append((num_glyphs - 1, 0))
    out.append((0, num_glyphs - 1))
    out.append((num_glyphs, 0))
    out.append((-1, 5))
    out.append((5, -1))
    return out


def _sequence(num_glyphs: int) -> list[int]:
    """Mirror ``KernTableProbe.sequence`` exactly."""
    a = min(36, num_glyphs - 1)
    b = min(55, num_glyphs - 1)
    c = min(3, num_glyphs - 1)
    return [c, a, -1, b, a, c]


def _py_kern(font_path: Path) -> str:
    """Reconstruct ``KernTableProbe`` output from pypdfbox (line-for-line)."""
    ttf = TTFParser().parse(font_path)
    try:
        lines: list[str] = []
        kern = ttf.get_kerning()
        if kern is None:
            lines.append("KERN\t0")
            lines.append("HSUB\tabsent\tfalse\tfalse")
            return "\n".join(lines) + "\n"
        num_glyphs = ttf.get_number_of_glyphs()
        hsub = kern.get_horizontal_kerning_subtable()
        lines.append(f"KERN\t{1 if hsub is not None else 0}")
        hk = hsub is not None and hsub.is_horizontal_kerning()
        hkc = hsub is not None and hsub.is_horizontal_kerning(cross=True)
        lines.append(
            "HSUB\t{}\t{}\t{}".format(
                "present" if hsub is not None else "absent",
                "true" if hk else "false",
                "true" if hkc else "false",
            )
        )
        if hsub is None:
            return "\n".join(lines) + "\n"
        for left, right in _pairs(num_glyphs):
            value = hsub.get_kerning(left, right)
            lines.append(f"PAIR\t{left}\t{right}\t{value}")
        adj = hsub.get_kerning(_sequence(num_glyphs))
        for i, value in enumerate(adj):
            lines.append(f"SEQ\t{i}\t{value}")
        return "\n".join(lines) + "\n"
    finally:
        ttf.close()


@requires_oracle
def test_kern_table_matches_pdfbox() -> None:
    """The format-0 horizontal kerning subtable — subtable selection, coverage
    accessors, per-pair binary-search lookup, and the glyph-sequence overload —
    must match Apache PDFBox 3.0.7 byte-for-byte.
    """
    assert _FIXTURE.is_file(), f"missing fixture: {_FIXTURE}"
    java = run_probe_text("KernTableProbe", str(_FIXTURE)).splitlines()
    py = _py_kern(_FIXTURE).splitlines()

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"first java: {java[:3]}\nfirst py:   {py[:3]}"
    )

    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "kern parity broken:\n" + "\n".join(diffs[:40])
