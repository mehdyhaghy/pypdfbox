"""Live PDFBox differential parity for the renderer-facing GLYPH-ACCESS surface
of a CFF-flavoured (``OTTO``) :class:`OpenTypeFont`.

Where ``test_otf_cff_load_oracle`` reaches into the embedded CFF directly
(``get_cff().get_type2_char_string(gid).get_path()``), this module pins the
public FontBox glyph-access API a renderer actually drives:

  * :meth:`OpenTypeFont.get_path` (name-keyed) — the OTF override that routes
    through the CFF when the font is PostScript-flavoured;
  * :meth:`TrueTypeFont.get_width` (name-keyed) — upstream
    ``TrueTypeFont.getWidth(String)`` is *unconditionally*
    ``getAdvanceWidth(nameToGID(name))`` cast to float, with NO special-case
    for an unresolved (gid 0) name, so a name that falls back to ``.notdef``
    reports gid 0's advance, not ``0.0``;
  * :meth:`TrueTypeFont.has_glyph` — name resolves to a non-zero gid;
  * :meth:`OpenTypeFont.get_glyph_table` — must raise on a PostScript font (no
    ``glyf`` table) where upstream throws ``UnsupportedOperationException``.

The oracle output is produced by ``oracle/probes/OtfCffGlyphAccessProbe.java``
driving Apache FontBox's ``OTFParser`` on the same bytes. The glyph-path
fingerprint reuses the coordinate-tolerant / structurally-strict shape from
``test_glyph_path_oracle.py`` (rounded curve bounding box, segment count, and
M/L/Q/C/Z type sequence — see that module's docstring for the
closeCharString1Path / consecutive-moveTo normalisation rationale).

The fixture is the same synthesised CFF-flavoured OTF used by
``test_otf_cff_load_oracle`` (built with fontTools' ``FontBuilder``); it ships a
format-3.0 ``post`` table, so PostScript glyph names do not resolve and the
probe addresses glyphs by their ``uniXXXX`` cmap form (matching how a real
subset-embedded OTF/CFF font is keyed). ``.notdef`` and an unknown name both
fall back to gid 0 — the case that distinguishes the corrected ``get_width``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from pypdfbox.fontbox.ttf.open_type_font import OpenTypeFont
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from tests.fontbox.ttf.oracle.test_glyph_path_oracle import _cff_fingerprint
from tests.fontbox.ttf.oracle.test_otf_cff_load_oracle import _build_otf_bytes
from tests.oracle.harness import requires_oracle, run_probe_text

# Names probed — must match OtfCffGlyphAccessProbe.NAMES (order preserved).
_NAMES = ("uni0041", "uni0042", "uni0020", ".notdef", "bogusName")

# Per-edge bbox epsilon (font units) — same rounding allowance as the glyph-path
# oracle (Math.round half-up vs Python round half-even at an exact .5).
_BBOX_EPS = 1


def _py_glyph_table_state(otf: OpenTypeFont) -> str:
    """Mirror the probe's ``getGlyph()`` THROWS/ok/null fingerprint.

    pypdfbox raises :class:`NotImplementedError` (the Python analogue of
    upstream's ``UnsupportedOperationException``) for a PostScript-flavoured
    OTF; map that to ``THROWS`` to compare against the Java probe.
    """
    try:
        table = otf.get_glyph_table()
    except NotImplementedError:
        return "THROWS"
    return "null" if table is None else "ok"


def _py_access_line(otf: OpenTypeFont, cff: Any, name: str) -> str:
    """Reconstruct one ``ACCESS`` line from pypdfbox (probe format)."""
    has_glyph = otf.has_glyph(name)
    width = otf.get_width(name)

    # Drive the public name-keyed get_path override (routes through the CFF for
    # a supported PostScript font), then fingerprint exactly like the probe.
    gid = otf.name_to_gid(name)
    cs = None if cff is None else cff.get_type2_char_string(gid)
    if cs is None:
        from tests.fontbox.ttf.oracle.test_glyph_path_oracle import (
            _Fingerprint,  # noqa: PLC0415
        )

        fp = _Fingerprint()
    else:
        fp = _cff_fingerprint(cs.get_path())

    # _Fingerprint.as_line() emits "minX minY maxX maxY nseg typeSeq"; the probe
    # ACCESS line emits "nseg typeSeq minX minY maxX maxY" — re-order to match.
    min_x, min_y, max_x, max_y, nseg, typeseq = _fp_fields(fp)
    return (
        f"ACCESS\t{name}\t{str(has_glyph).lower()}\t{round(width)}\t"
        f"{nseg}\t{typeseq}\t{min_x}\t{min_y}\t{max_x}\t{max_y}"
    )


def _fp_fields(fp: Any) -> tuple[str, str, str, str, str, str]:
    """Split ``_Fingerprint.as_line()`` into its six tab fields."""
    parts = fp.as_line().split("\t")
    # as_line(): minX minY maxX maxY nseg typeSeq (typeSeq may be empty -> 6 cols)
    min_x, min_y, max_x, max_y, nseg = parts[0], parts[1], parts[2], parts[3], parts[4]
    typeseq = parts[5] if len(parts) > 5 else ""
    return min_x, min_y, max_x, max_y, nseg, typeseq


def _py_output(otf_bytes: bytes) -> list[str]:
    otf = OTFParser().parse(otf_bytes)
    assert isinstance(otf, OpenTypeFont)
    cff = otf.get_cff()
    lines = [f"GLYPHTABLE\t{_py_glyph_table_state(otf)}"]
    lines.extend(_py_access_line(otf, cff, name) for name in _NAMES)
    return lines


def _parse_access(line: str) -> tuple[tuple[str, str, str, str, str], tuple[int, ...]]:
    """Split an ``ACCESS`` line into (strict fields, bbox)."""
    p = line.split("\t")
    # ACCESS name hasGlyph width nseg typeSeq minX minY maxX maxY
    name, has_glyph, width, nseg = p[1], p[2], p[3], p[4]
    typeseq = p[5]
    bbox = (int(p[6]), int(p[7]), int(p[8]), int(p[9]))
    return (name, has_glyph, width, nseg, typeseq), bbox


@requires_oracle
def test_otf_cff_glyph_access_matches_pdfbox() -> None:
    """OTF/CFF renderer-facing glyph access (get_path / get_width / has_glyph
    name-keyed, plus get_glyph rejection) must match Apache PDFBox 3.0.7.

    GLYPHTABLE must match exactly. ACCESS lines must match exactly on name /
    hasGlyph / width / segment-count / type-sequence; the curve bounding box may
    differ by at most ``_BBOX_EPS`` per edge (rounding only).
    """
    otf_bytes = _build_otf_bytes()

    # mkstemp (not NamedTemporaryFile) so the handle is closed before the Java
    # probe opens the path — Windows can't reopen a still-open temp file by name.
    fd, tmp_path = tempfile.mkstemp(suffix=".otf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(otf_bytes)
        java = run_probe_text("OtfCffGlyphAccessProbe", "read", tmp_path).splitlines()
    finally:
        Path(tmp_path).unlink()

    py = _py_output(otf_bytes)

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\njava: {java}\npy:   {py}"
    )

    diffs: list[str] = []
    for i, (j, p) in enumerate(zip(java, py, strict=True)):
        if j.startswith("GLYPHTABLE"):
            if j != p:
                diffs.append(f"  line {i}: java={j!r} py={p!r}")
            continue
        jstrict, jb = _parse_access(j)
        pstrict, pb = _parse_access(p)
        if jstrict != pstrict:
            diffs.append(f"  line {i} (ACCESS {jstrict[0]}): java={j!r} py={p!r}")
            continue
        if any(abs(a - b) > _BBOX_EPS for a, b in zip(jb, pb, strict=True)):
            diffs.append(f"  line {i} (ACCESS {jstrict[0]}) bbox>{_BBOX_EPS}: java={jb} py={pb}")

    assert not diffs, "OTF/CFF glyph-access parity broken:\n" + "\n".join(diffs)
