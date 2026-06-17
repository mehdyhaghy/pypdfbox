"""Live PDFBox differential parity for the OpenType (sfnt-wrapped CFF) LOADING
surface: an OTF font whose scaler type is ``OTTO`` and whose PostScript outlines
live in a ``CFF `` table, parsed through ``OTFParser`` into an ``OpenTypeFont``.

This pins the OTF *loading* path that the flat-``.cff`` CFF probes never touch:

  * ``OTFParser().parse(bytes)`` returns an ``OpenTypeFont``;
  * ``is_post_script()`` is true (the ``OTTO`` magic + ``CFF `` table);
  * ``is_supported_otf()`` is true (CFF v1, not CFF2);
  * the SFNT table directory carries the expected tags (``CFF `` / ``cmap`` /
    ``head`` / ``name`` / ...);
  * ``get_cff().get_name()`` exposes the embedded ``CFFFont``;
  * a glyph fetched *through the CFF* (name → gid → Type 2 charstring → path)
    matches Apache PDFBox's assembled ``GeneralPath``.

The oracle output is produced by ``oracle/probes/OtfCffLoadProbe.java`` driving
Apache FontBox's ``OTFParser`` on the same bytes. The glyph-path fingerprint is
the same coordinate-tolerant / structurally-strict shape used by
``test_glyph_path_oracle.py`` — rounded curve bounding box, segment count, and
M/L/Q/C/Z type sequence (see that module's docstring for the rationale and the
CFF closeCharString1Path / consecutive-moveTo normalisation).

No OTF is bundled in the repo, so the fixture is synthesised at test time with
fontTools' ``FontBuilder`` (a permissive-licensed dependency already present):
a tiny CFF-flavoured OTF with two drawn glyphs (``A``/``B``), ``.notdef`` and
``space``. The bytes feed *both* sides, so the comparison is exact regardless of
the synthetic font's internals.
"""

from __future__ import annotations

import io
from typing import Any

from pypdfbox.fontbox.ttf.open_type_font import OpenTypeFont
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from tests.fontbox.ttf.oracle.test_glyph_path_oracle import _cff_fingerprint
from tests.oracle.harness import requires_oracle, run_probe_text

# Glyph names probed for outlines — must match OtfCffLoadProbe.GLYPH_NAMES.
_GLYPH_NAMES = (".notdef", "A", "B", "space")

# Per-edge bbox epsilon (font units) — same rounding allowance as the glyph-path
# oracle (Math.round half-up vs Python round half-even at an exact .5).
_BBOX_EPS = 1


def _build_otf_bytes() -> bytes:
    """Synthesise a minimal CFF-flavoured (``OTTO``) OpenType font.

    Two drawn glyphs (``A`` a closed triangle, ``B`` a closed quad), plus
    ``.notdef`` and a blank ``space``. ``FontBuilder(isTTF=False)`` emits the
    ``CFF `` table and the ``OTTO`` sfnt header, exactly the loading surface
    under test.
    """
    from fontTools.fontBuilder import FontBuilder  # noqa: PLC0415
    from fontTools.pens.t2CharStringPen import T2CharStringPen  # noqa: PLC0415

    glyph_order = [".notdef", "A", "B", "space"]
    upm = 1000

    fb = FontBuilder(upm, isTTF=False)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x41: "A", 0x42: "B", 0x20: "space"})

    def _charstring(draw: Any) -> Any:
        pen = T2CharStringPen(0, None)
        draw(pen)
        return pen.getCharString()

    def _notdef(pen: Any) -> None:
        pen.moveTo((0, 0))
        pen.closePath()

    def _triangle(pen: Any) -> None:
        pen.moveTo((100, 0))
        pen.lineTo((400, 0))
        pen.lineTo((250, 700))
        pen.closePath()

    def _curved(pen: Any) -> None:
        pen.moveTo((100, 0))
        pen.curveTo((150, 400), (350, 400), (400, 0))
        pen.lineTo((100, 0))
        pen.closePath()

    def _space(pen: Any) -> None:
        pen.moveTo((0, 0))
        pen.closePath()

    charstrings = {
        ".notdef": _charstring(_notdef),
        "A": _charstring(_triangle),
        "B": _charstring(_curved),
        "space": _charstring(_space),
    }
    fb.setupCFF(
        "OtfCffLoadProbeFont",
        {"FullName": "OtfCffLoadProbeFont"},
        charstrings,
        {},
    )

    metrics = {n: (upm, 0) for n in glyph_order}
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "OtfCffLoadProbeFont", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()

    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _py_load(otf_bytes: bytes) -> str:
    """Reconstruct OtfCffLoadProbe output from pypdfbox (line-for-line)."""
    otf = OTFParser().parse(otf_bytes)
    assert isinstance(otf, OpenTypeFont)

    cff = otf.get_cff()
    cff_name = "null" if cff is None else cff.get_name()

    lines: list[str] = []
    lines.append(
        f"META\t{str(otf.is_post_script()).lower()}\t"
        f"{str(otf.is_supported_otf()).lower()}\t"
        f"{otf.get_number_of_glyphs()}\t{otf.get_units_per_em()}\t{cff_name}"
    )

    tags = sorted(t.get_tag() for t in otf.get_tables())
    lines.append("TABLES\t" + ",".join(tags))

    for name in _GLYPH_NAMES:
        lines.append(_py_glyph(otf, cff, name))

    # Direct-GID outlines straight through the embedded CFF — exercises the
    # CFF glyph-assembly path independent of name resolution.
    for gid in range(otf.get_number_of_glyphs()):
        lines.append(_py_gid(cff, gid))
    return "\n".join(lines) + "\n"


def _py_gid(cff: Any, gid: int) -> str:
    name = f"GID:{gid}"
    try:
        cs = None if cff is None else cff.get_type2_char_string(gid)
        if cs is None:
            from tests.fontbox.ttf.oracle.test_glyph_path_oracle import (
                _Fingerprint,  # noqa: PLC0415
            )

            fp = _Fingerprint()
        else:
            fp = _cff_fingerprint(cs.get_path())
    except Exception:
        return f"GLYPH\t{name}\t{gid}\t0\tERR\tERR\tERR\tERR\tERR\tERR"
    return f"GLYPH\t{name}\t{gid}\t0\t{fp.as_line()}"


def _py_glyph(otf: OpenTypeFont, cff: Any, name: str) -> str:
    gid = otf.name_to_gid(name)
    advance = otf.get_advance_width(gid)
    try:
        cs = None if cff is None else cff.get_type2_char_string(gid)
        if cs is None:
            from tests.fontbox.ttf.oracle.test_glyph_path_oracle import (
                _Fingerprint,  # noqa: PLC0415
            )

            fp = _Fingerprint()
        else:
            fp = _cff_fingerprint(cs.get_path())
    except Exception:
        return f"GLYPH\t{name}\t{gid}\t{advance}\tERR\tERR\tERR\tERR\tERR\tERR"
    return f"GLYPH\t{name}\t{gid}\t{advance}\t{fp.as_line()}"


def _parse_glyph_line(line: str) -> tuple[str, str, str, tuple[int, ...] | None, str, str]:
    """Split a ``GLYPH`` line into (name, gid, advance, bbox|None, nseg, typeseq)."""
    p = line.split("\t")
    # GLYPH name gid advance minX minY maxX maxY nseg typeSeq
    name, gid, advance = p[1], p[2], p[3]
    if p[4] == "ERR":
        return name, gid, advance, None, "ERR", "ERR"
    bbox = (int(p[4]), int(p[5]), int(p[6]), int(p[7]))
    nseg = p[8]
    typeseq = p[9] if len(p) > 9 else ""
    return name, gid, advance, bbox, nseg, typeseq


@requires_oracle
def test_otf_cff_load_matches_pdfbox() -> None:
    """OTF/CFF loading metadata + table directory + per-glyph CFF outline must
    match Apache PDFBox 3.0.7.

    META and TABLES lines must match exactly. GLYPH lines must match exactly on
    name / gid / advance / segment-count / type-sequence; the curve bounding box
    may differ by at most ``_BBOX_EPS`` per edge (rounding only).
    """
    otf_bytes = _build_otf_bytes()

    import os  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    # mkstemp (not NamedTemporaryFile) so the handle is closed before the Java
    # probe opens the path — Windows can't reopen a still-open temp file by name.
    fd, tmp_path = tempfile.mkstemp(suffix=".otf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(otf_bytes)
        java = run_probe_text("OtfCffLoadProbe", "read", tmp_path).splitlines()
    finally:
        Path(tmp_path).unlink()

    py = _py_load(otf_bytes).splitlines()

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"java: {java}\npy:   {py}"
    )

    diffs: list[str] = []
    for i, (j, p) in enumerate(zip(java, py, strict=True)):
        if j.startswith(("META", "TABLES")):
            if j != p:
                diffs.append(f"  line {i}: java={j!r} py={p!r}")
            continue
        # GLYPH line — structurally strict, bbox tolerant.
        jn, jg, ja, jb, jns, jt = _parse_glyph_line(j)
        pn, pg, pa, pb, pns, pt = _parse_glyph_line(p)
        if (jn, jg, ja, jns, jt) != (pn, pg, pa, pns, pt):
            diffs.append(f"  line {i} (GLYPH {jn}): java={j!r} py={p!r}")
            continue
        if jb is None or pb is None:
            if jb is not pb:
                diffs.append(f"  line {i} (GLYPH {jn}): java={j!r} py={p!r}")
            continue
        if any(abs(a - b) > _BBOX_EPS for a, b in zip(jb, pb, strict=True)):
            diffs.append(f"  line {i} (GLYPH {jn}) bbox>{_BBOX_EPS}: java={jb} py={pb}")

    assert not diffs, "OTF/CFF load parity broken:\n" + "\n".join(diffs)
