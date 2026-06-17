"""Live PDFBox differential parity for the TrueType cmap format-14 (Unicode
Variation Sequence) subtable surface.

Format 14 maps a (base codepoint, variation selector) pair to a glyph id, via
default-UVS ranges and non-default-UVS records. The decisive parity fact is
that Apache FontBox's ``CmapSubtable`` exposes **no** variation-selector lookup
API — the only public glyph accessor is ``getGlyphId(int)``, which takes a
single codepoint. A format-14 subtable therefore cannot contribute to the
single-codepoint glyph lookup at all: through the shared API it is inert, and
``CmapSubtable#processSubtype14`` in PDFBox 3.0.7 is a no-op that merely logs
"Format 14 cmap table is not supported and will be ignored".

This test pins that observable contract. It synthesizes (deterministically, via
fontTools; nothing committed) a font whose ``cmap`` carries a format-14 (0,5)
Unicode-Variation-Sequence subtable — with both non-default UVS records
(``0x0041``/``0x0042`` under selector ``0xFE00``) and default-UVS records
(``0x4E00``/``0x6F22`` under selector ``0xE0100``) — alongside the font's
normal Unicode subtables. The same file is fed to ``CmapFormat14Probe`` (Java
FontBox) and to the pypdfbox reproducer; both enumerate every subtable via
``get_cmaps()`` and emit ``get_glyph_id(codepoint)`` for a fixed codepoint set.

Parity assertions verified by this test:

  * the format-14 (0,5) subtable returns glyph id 0 for *every* probed
    codepoint (it never populates the single-codepoint forward map), exactly as
    upstream's ignored format-14 does; and
  * the presence of a format-14 subtable does not corrupt the parse of its
    neighbours — the (3,1)/(0,3)/(3,10)/... subtables still resolve the base
    codepoints to the same glyph ids PDFBox produces.

pypdfbox additionally parses the UVS records into ``get_glyph_id_uvs`` /
``has_uvs`` helpers (an additive extension upstream lacks); those are not part
of the shared, oracle-comparable surface and so do not affect this parity
check.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.cmap_table import CmapTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf"

# Mirror the probe's CODEPOINTS exactly (UVS bases + the FE00/E0100 selectors
# themselves treated as plain codepoints + a control).
_CODEPOINTS = [0x0041, 0x0042, 0x4E00, 0x6F22, 0xFE00, 0xE0100, 0x20]


def _make_uvs_font(djv_bytes: bytes) -> bytes:
    """Append a format-14 (0,5) UVS subtable to DejaVuSans's ``cmap``.

    Records (deterministic):

      * selector ``0xFE00`` (non-default UVS): ``0x0041`` -> glyph of ``B`` and
        ``0x0042`` -> glyph of ``A`` (deliberately swapped so a hypothetical
        UVS-aware ``getGlyphId`` would differ from the plain BMP mapping —
        proving the format-14 subtable is genuinely inert under the shared API).
      * selector ``0xE0100`` (default UVS): ``0x4E00`` and ``0x6F22`` recorded
        with a ``None`` glyph (i.e. "use the base glyph").
    """
    from fontTools.ttLib import TTFont  # noqa: PLC0415
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable as FTSub  # noqa: PLC0415

    tt = TTFont(io.BytesIO(djv_bytes))
    try:
        bmp = tt["cmap"].getcmap(3, 1).cmap  # codepoint -> glyphName
        sub14 = FTSub.getSubtableClass(14)(14)
        sub14.platformID = 0
        sub14.platEncID = 5  # Unicode Variation Sequences
        sub14.format = 14
        sub14.language = 0
        # fontTools touches `.cmap` on every subtable during compile dedup;
        # format 14 has none, so give it an empty dict.
        sub14.cmap = {}
        sub14.uvsDict = {
            0xFE00: [(0x0041, bmp[0x0042]), (0x0042, bmp[0x0041])],
            0xE0100: [(0x4E00, None), (0x6F22, None)],
        }
        tt["cmap"].tables.append(sub14)
        buf = io.BytesIO()
        tt.save(buf)
        return buf.getvalue()
    finally:
        tt.close()


def _py_lines(ttf_path: Path) -> str:
    """Reconstruct ``CmapFormat14Probe`` output from pypdfbox."""
    lines: list[str] = []
    ttf = TrueTypeFont.from_bytes(ttf_path.read_bytes())
    try:
        num_glyphs = ttf.get_number_of_glyphs()
        raw = ttf.get_table_bytes("cmap")
        assert raw is not None

        class _Font:
            def get_number_of_glyphs(self) -> int:
                return num_glyphs

        cmap = CmapTable()
        cmap.read(_Font(), MemoryTTFDataStream(raw))
        for i, sub in enumerate(cmap.get_cmaps()):
            lines.append(
                f"SUB\t{i}\t{sub.get_platform_id()}\t{sub.get_platform_encoding_id()}"
            )
            for cp in _CODEPOINTS:
                lines.append(f"GID\t{i}\t{cp}\t{sub.get_glyph_id(cp)}")
    finally:
        ttf.close()
    return "\n".join(lines) + "\n"


def _assert_parity(java: str, py: str) -> None:
    j = java.splitlines()
    p = py.splitlines()
    assert len(j) == len(p), (
        f"line-count mismatch: java={len(j)} py={len(p)}\n"
        f"first java: {j[:3]}\nfirst py:   {p[:3]}"
    )
    diffs = [
        f"  line {i}: java={a!r} py={b!r}"
        for i, (a, b) in enumerate(zip(j, p, strict=True))
        if a != b
    ]
    assert not diffs, "cmap format-14 parity broken:\n" + "\n".join(diffs[:40])


@requires_oracle
def test_format14_subtable_is_inert_under_shared_api_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """A format-14 (0,5) UVS subtable must return glyph id 0 for every
    single-codepoint ``get_glyph_id`` (upstream ignores format 14), and its
    presence must not corrupt the parse of the neighbouring Unicode subtables —
    all enumerated exactly as Apache PDFBox 3.0.7 does.
    """
    djv = (_TTF_DIR / "DejaVuSans.ttf").read_bytes()
    uvs_path = tmp_path / "Uvs14.ttf"
    uvs_path.write_bytes(_make_uvs_font(djv))
    java = run_probe_text("CmapFormat14Probe", str(uvs_path))
    py = _py_lines(uvs_path)
    _assert_parity(java, py)


@requires_oracle
def test_format14_subtable_present_and_emits_zero_only(tmp_path: Path) -> None:
    """Sanity-pin: the synthesized font really does carry a (0,5) format-14
    subtable, and that subtable's GID lines are all zero on both sides.
    """
    djv = (_TTF_DIR / "DejaVuSans.ttf").read_bytes()
    uvs_path = tmp_path / "Uvs14.ttf"
    uvs_path.write_bytes(_make_uvs_font(djv))
    java = run_probe_text("CmapFormat14Probe", str(uvs_path)).splitlines()

    # Locate the (0,5) subtable header line and assert every GID line that
    # follows (until the next SUB) is zero.
    sub_index = None
    for line in java:
        parts = line.split("\t")
        if parts[0] == "SUB" and parts[2] == "0" and parts[3] == "5":
            sub_index = parts[1]
            break
    assert sub_index is not None, "no (0,5) format-14 subtable enumerated"

    gid_lines = [
        line
        for line in java
        if line.startswith(f"GID\t{sub_index}\t")
    ]
    assert gid_lines, "format-14 subtable emitted no GID lines"
    for line in gid_lines:
        assert line.split("\t")[-1] == "0", f"format-14 GID line not zero: {line}"
