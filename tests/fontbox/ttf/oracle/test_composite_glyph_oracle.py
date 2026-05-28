"""Live PDFBox differential parity for the ``glyf`` COMPOSITE-GLYPH path.

A composite glyph (an accented letter such as ``Agrave`` / ``Eacute``) is not
stored as its own outline. It references one or more component sub-glyphs (the
base letter + the diacritic) by index, each carrying an ``ARGS_ARE_XY_VALUES``
offset and an optional component transform (``WE_HAVE_A_SCALE`` /
``WE_HAVE_AN_X_AND_Y_SCALE`` / ``WE_HAVE_A_TWO_BY_TWO``), chained by the
``MORE_COMPONENTS`` flag. FontBox flattens that chain in
``GlyfCompositeDescript`` / ``GlyfCompositeComp``, applying each component's
2x2 scale + translate to every borrowed point.

This is the surface ``oracle/probes/CompositeGlyphProbe.java`` fingerprints: it
loads a RAW bundled TrueType font directly through ``TTFParser`` (not via a
PDF) and, for a curated set of composite GIDs, emits — from
``ttf.getGlyph().getGlyph(gid).getDescription()`` (after ``resolve()``):

  * the RESOLVED outline contour count + total point count + glyph bbox;
  * one row per ASSEMBLED point: its post-transform ``(x, y)`` and on-curve bit.

Both sides start from the same integer font-unit coordinates and the composite
transform uses ``Math.round``, so the assembled coordinates are bit-identical —
this is an EXACT-match parity test (no epsilon).

The fixture is the permissively-licensed bundled ``DejaVuSans.ttf`` (Bitstream
Vera / public-domain-equivalent), whose accented Latin letters are composites
with a base + diacritic component (some carrying scales, e.g. the fraction and
superscript glyphs). Only bundled fonts are used so the outline is
deterministic across machines.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_FONT = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)

# Curated composite GIDs in DejaVuSans:
#   - 126/127/128 onequarter/onehalf/threequarters: fraction composites that
#     carry SCALED superscript/subscript digit components (WE_HAVE_A_SCALE /
#     WE_HAVE_AN_X_AND_Y_SCALE) -> exercises the component transform.
#   - 130-141 Agrave..Edieresis: accented letters = base glyph + a translated
#     diacritic component (ARGS_ARE_XY_VALUES offset, MORE_COMPONENTS chain).
#   - 137 Ccedilla, 134 Adieresis: multi-contour assembled outlines.
_GIDS = [126, 127, 128, 130, 131, 132, 133, 134, 137, 138, 139, 140, 141]


def _py_lines(font_path: Path, gids: list[int]) -> list[str]:
    """Reconstruct ``CompositeGlyphProbe`` output from pypdfbox, line-for-line."""
    ttf = TTFParser().parse(font_path)
    try:
        glyf = ttf.get_glyph_table()
        assert glyf is not None
        post = ttf.get_post_script()
        glyph_names = post.get_glyph_names() if post is not None else None
        num_glyphs = ttf.get_number_of_glyphs()

        def name_for(gid: int) -> str:
            if glyph_names is not None and 0 <= gid < len(glyph_names):
                return str(glyph_names[gid])
            return f"gid{gid}"

        lines: list[str] = []
        for gid in gids:
            name = name_for(gid) if 0 <= gid < num_glyphs else "?"
            gd = glyf.get_glyph(gid)
            if gd is None:
                lines.append(f"GLYPH\t{gid}\t{name}\tNULL\tNULL\tNULL")
                continue
            desc = gd.get_description()
            desc.resolve()
            contours = desc.get_contour_count()
            points = desc.get_point_count()
            bbox = gd.get_bounding_box()
            lines.append(
                f"GLYPH\t{gid}\t{name}\t{contours}\t{points}\t"
                f"{int(bbox.get_lower_left_x())} {int(bbox.get_lower_left_y())} "
                f"{int(bbox.get_upper_right_x())} {int(bbox.get_upper_right_y())}"
            )
            for i in range(points):
                x = desc.get_x_coordinate(i)
                y = desc.get_y_coordinate(i)
                on_curve = 1 if (desc.get_flags(i) & 0x01) != 0 else 0
                lines.append(f"PT\t{gid}\t{i}\t{x}\t{y}\t{on_curve}")
        return lines
    finally:
        ttf.close()


@requires_oracle
def test_composite_glyph_outline_matches_pdfbox() -> None:
    """The assembled composite-glyph outline (resolved contour/point counts,
    bbox, and every post-transform point coordinate + on-curve flag) read from
    the bundled DejaVuSans composites must match Apache PDFBox 3.0.7 exactly.

    Coordinates are integer font units and the composite scale+translate uses
    ``Math.round`` on both sides, so the match is exact (no tolerance).
    """
    gid_arg = ",".join(str(g) for g in _GIDS)
    java = run_probe_text("CompositeGlyphProbe", str(_FONT), gid_arg).splitlines()
    py = _py_lines(_FONT, _GIDS)

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"first java: {java[:4]}\nfirst py:   {py[:4]}"
    )

    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "composite-glyph parity broken:\n" + "\n".join(diffs[:40])
