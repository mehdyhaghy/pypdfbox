"""Live PDFBox differential fuzz for the OTF/CFF *integration boundary* of a
CFF-flavoured (``OTTO``) :class:`OpenTypeFont` — the seam between the SFNT
wrapper and the embedded :class:`CFFFont`.

The sibling oracle modules pin the happy path:

  * ``test_otf_cff_load_oracle`` — load metadata, table directory, per-glyph
    CFF outline through ``get_cff().get_type2_char_string(gid)``;
  * ``test_otf_cff_glyph_access_oracle`` — the renderer glyph-access trio
    (``get_path`` / ``get_width`` / ``has_glyph`` name-keyed) and ``get_glyph``
    rejection.

This module fuzzes the *boundary* those probes do not stress (wave 1557):

  * ``numberOfGlyphs`` (from ``maxp``) vs the CFF charstring count
    (``CFFFont.get_num_char_strings()``) — for a well-formed font they agree;
  * a GID at exactly the charstring count, GIDs far past it (count+50, 1000),
    and a negative GID — upstream ``CFFFont.getType2CharString`` clamps an
    out-of-range *positive* GID to the ``.notdef`` glyph (GID 0) rather than
    throwing, and throws on a *negative* GID;
  * the ``CFF `` table presence + the embedded ``CFFFont`` name;
  * name resolution for a ``uniXXXX`` cmap name, an unknown name, and the empty
    string (all back through the CFF);
  * a *truncated* ``CFF `` table file — the parser's degrade-vs-throw behaviour.

The oracle output is produced by ``oracle/probes/OtfCffFuzzProbe.java`` driving
Apache FontBox's ``OTFParser`` on the same bytes. The path fingerprint reuses
the coordinate-tolerant / structurally-strict shape from
``test_glyph_path_oracle.py`` (rounded curve bounding box, segment count, and
M/L/Q/C/Z type sequence).

Honest divergences pinned here (see in-line comments):

  * **Glyph *name* representation.** Apache PDFBox re-parses the embedded CFF
    bytes with its own ``CFFParser`` and labels the synthetic ``FontBuilder``
    glyphs ``GID+N`` (no charset string), whereas pypdfbox surfaces fontTools'
    real glyph names (``.notdef`` / ``A`` / ``B`` / ``space``). Both sides draw
    the *same* outline; only the human-readable name field differs. The strict
    comparison therefore excludes the name *string* but keeps the GID and the
    full path fingerprint — the rendering-relevant contract.
  * **Negative GID.** Java throws ``ArrayIndexOutOfBoundsException`` (probe
    emits ``ERR``); pypdfbox returns an empty wrapper (the documented ergonomic
    divergence already recorded for ``get_type2_char_string``). Pinned as an
    asymmetry, not asserted equal.

The fixture is the same synthesised CFF-flavoured OTF used by the sibling
modules (``_build_otf_bytes`` via fontTools' ``FontBuilder``); the bytes feed
*both* sides, so the comparison is exact regardless of the font's internals.
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

# Names probed for name->gid->CFF resolution — must match OtfCffFuzzProbe.NAMES.
_NAMES = ("uni0041", "uni0042", "uni0020", ".notdef", "bogusName", "")

# Per-edge bbox epsilon (font units) — same rounding allowance as the glyph-path
# oracle (Math.round half-up vs Python round half-even at an exact .5).
_BBOX_EPS = 1


def _py_gid_path_line(cff: Any, gid: int) -> tuple[int, str | None, tuple[int, ...] | None]:
    """Return (gid, typeseq|None, bbox|None) for a GID through the embedded CFF.

    ``typeseq`` is ``None`` (and bbox ``None``) when pypdfbox would emit the
    Java probe's ``ERR`` shape — i.e. a negative GID returns an empty wrapper
    here whose path is empty, but Java *throws*. The caller treats that as the
    documented asymmetry.
    """
    if cff is None:
        return gid, "", (0, 0, 0, 0)
    cs = cff.get_type2_char_string(gid)
    if cs is None:
        return gid, "", (0, 0, 0, 0)
    fp = _cff_fingerprint(cs.get_path())
    parts = fp.as_line().split("\t")
    # as_line(): minX minY maxX maxY nseg typeSeq (typeSeq may be empty -> 6).
    bbox = (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
    typeseq = parts[5] if len(parts) > 5 else ""
    return gid, typeseq, bbox


def _parse_java_gid_path(line: str) -> tuple[int, str | None, tuple[int, ...] | None]:
    """Split a Java ``GIDPATH`` line into (gid, typeseq|None, bbox|None)."""
    p = line.split("\t")
    # GIDPATH gid name nseg typeSeq minX minY maxX maxY
    gid = int(p[1])
    if p[3] == "ERR":  # nseg == ERR -> the whole tail is ERR (exception)
        return gid, None, None
    typeseq = p[4]
    bbox = (int(p[5]), int(p[6]), int(p[7]), int(p[8]))
    return gid, typeseq, bbox


@requires_oracle
def test_otf_cff_fuzz_read_matches_pdfbox() -> None:
    """OTF/CFF integration metadata + GID-clamping + name resolution must match
    Apache PDFBox 3.0.7 on the rendering-relevant fields.

    META: ``isPostScript`` / ``isSupportedOTF`` / ``numGlyphs`` /
    ``numCharStrings`` / ``cffName`` / ``hasCFF`` must match exactly — this pins
    the maxp-vs-CFF glyph-count agreement and the CFF table presence.

    GIDPATH: every probed GID (0, last, count, count+50, 1000) must match
    exactly on segment count + type sequence, with a bbox tolerance of
    ``_BBOX_EPS`` per edge. The glyph *name* string is excluded (Java labels the
    synthetic CFF glyphs ``GID+N`` while pypdfbox keeps fontTools' real names —
    same outline, different label). The negative GID (-1) is the documented
    asymmetry: Java throws, pypdfbox returns an empty path; assert that exact
    pairing rather than equality.

    NAME: every probed name must resolve to the same GID. The resolved CFF name
    string is excluded for the same representation reason as GIDPATH.
    """
    otf_bytes = _build_otf_bytes()

    fd, tmp_path = tempfile.mkstemp(suffix=".otf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(otf_bytes)
        java = run_probe_text("OtfCffFuzzProbe", "read", tmp_path).splitlines()
    finally:
        Path(tmp_path).unlink()

    otf = OTFParser().parse(otf_bytes)
    assert isinstance(otf, OpenTypeFont)
    cff = otf.get_cff()

    java_meta = next(line for line in java if line.startswith("META"))
    num_glyphs = otf.get_number_of_glyphs()
    num_char = -1 if cff is None else cff.get_num_char_strings()
    cff_name = "null" if cff is None else cff.get_name()
    py_meta = (
        f"META\t{str(otf.is_post_script()).lower()}\t"
        f"{str(otf.is_supported_otf()).lower()}\t"
        f"{num_glyphs}\t{num_char}\t{cff_name}\t"
        f"{str(cff is not None).lower()}"
    )
    assert java_meta == py_meta, f"META mismatch:\n java={java_meta!r}\n py  ={py_meta!r}"

    # The well-formed font: maxp count and CFF charstring count must agree.
    assert num_glyphs == num_char, (
        f"numberOfGlyphs ({num_glyphs}) != CFF charstring count ({num_char})"
    )

    # GIDPATH lines — probe order: 0, last, count, count+50, 1000, -1.
    java_gid = [_parse_java_gid_path(line) for line in java if line.startswith("GIDPATH")]
    probe_gids = [0, num_glyphs - 1, num_glyphs, num_glyphs + 50, 1000, -1]
    assert [g for g, _, _ in java_gid] == probe_gids, (
        f"GID order mismatch: {[g for g, _, _ in java_gid]} != {probe_gids}"
    )

    diffs: list[str] = []
    for jgid, jtypes, jbbox in java_gid:
        py_gid, py_types, py_bbox = _py_gid_path_line(cff, jgid)
        if jgid < 0:
            # Documented asymmetry: Java throws (None), pypdfbox returns empty.
            if jtypes is not None:
                diffs.append(f"  GID {jgid}: expected Java ERR, got {jtypes!r}")
            if py_types != "":
                diffs.append(f"  GID {jgid}: expected py empty path, got {py_types!r}")
            continue
        if jtypes != py_types:
            diffs.append(f"  GID {jgid}: typeseq java={jtypes!r} py={py_types!r}")
            continue
        assert jbbox is not None and py_bbox is not None
        if any(abs(a - b) > _BBOX_EPS for a, b in zip(jbbox, py_bbox, strict=True)):
            diffs.append(f"  GID {jgid}: bbox>{_BBOX_EPS} java={jbbox} py={py_bbox}")

    # NAME lines — name must resolve to the same GID (resolved-name string
    # excluded for the representation reason documented above).
    java_name = [line.split("\t") for line in java if line.startswith("NAME")]
    assert len(java_name) == len(_NAMES), f"NAME line count: {len(java_name)} != {len(_NAMES)}"
    for parts, expected_name in zip(java_name, _NAMES, strict=True):
        # NAME name gid resolvedName  (name may be empty -> 4 cols, or 3 if "")
        jname = parts[1]
        jgid = int(parts[2])
        assert jname == expected_name, f"NAME order: java {jname!r} != {expected_name!r}"
        py_resolved_gid = otf.name_to_gid(expected_name)
        if jgid != py_resolved_gid:
            diffs.append(f"  NAME {expected_name!r}: gid java={jgid} py={py_resolved_gid}")

    assert not diffs, "OTF/CFF integration parity broken:\n" + "\n".join(diffs)


@requires_oracle
def test_otf_cff_fuzz_truncated_matches_pdfbox() -> None:
    """A truncated OTF (``CFF `` table offset past the file size) must fail to
    parse on both sides.

    Apache PDFBox skips every over-long table and then raises because the font
    has no usable outline table; the probe emits ``TRUNC\\tPARSE_ERR``. pypdfbox
    (fontTools-backed ``OTFParser``) likewise raises on the truncated bytes.
    Pinned at two truncation lengths: a mid-directory cut (100 bytes) and a
    header-only cut (12 bytes).
    """
    otf_bytes = _build_otf_bytes()

    for keep in (100, 12):
        fd, tmp_path = tempfile.mkstemp(suffix=".otf")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(otf_bytes)
            java = run_probe_text("OtfCffFuzzProbe", "truncated", tmp_path, str(keep)).strip()
        finally:
            Path(tmp_path).unlink()

        assert java == "TRUNC\tPARSE_ERR", f"keep={keep}: unexpected Java {java!r}"

        # pypdfbox must also reject the truncated bytes.
        truncated = otf_bytes[:keep]
        raised = False
        try:
            OTFParser().parse(truncated)
        except Exception:  # noqa: BLE001
            raised = True
        assert raised, f"keep={keep}: pypdfbox parsed a truncated OTF that PDFBox rejects"
