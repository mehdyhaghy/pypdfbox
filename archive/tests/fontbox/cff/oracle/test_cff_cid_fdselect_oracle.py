"""Live Apache PDFBox differential parity for CID-keyed CFF (CIDFontType0C)
**/FDSelect + /FDArray** font-dict selection — the per-CID resolution that the
``CffSubsetProbe`` family (subset *structure*) never reaches.

A CID-keyed CFF maps each GID/CID to a font-dict index via /FDSelect (on-disk
format 0 or 3), and each font-dict in /FDArray carries its own Private DICT
(``defaultWidthX`` / ``nominalWidthX`` + a local /Subrs INDEX). A glyph's
charstring must be interpreted against the *selected* font-dict's width
defaults and local subrs. This module pins, against Apache PDFBox 3.0.7's own
fontbox parse of the same bytes:

* the /FDSelect on-disk format (0 / 3) and /FDArray size;
* the per-FD Private DICT width defaults;
* ``FDSelect.getFDIndex(gid)`` for every GID;
* ``getType2CharString(cid).getWidth()`` — the advance the per-FD
  nominalWidthX path computes — for every CID;
* the glyph outline fingerprint (segment count + first segments) for every CID
  — which is what proves the ``callsubr`` operand resolved to the *right*
  font-dict's local /Subrs.

Fixtures
--------
Two synthetic multi-FD CID CFFs (generated deterministically — see
``tests/fixtures/fontbox/cff/make_cid_fd_fixtures.py`` — because PDFBox's own
corpus has no small font where /FDSelect discriminates between several
font-dicts):

* ``cid_multifd_subr.cff`` — 2 font-dicts, FDSelect ``[0,0,1,1]``, each FD with
  its **own local subr**. FD0's subr draws a horizontal line, FD1's a vertical
  one, so the same ``callsubr`` opcode yields a different outline per FD —
  the high-value local-subr-in-the-right-font-dict case.
* ``cid_multifd_3fd.cff`` — 3 font-dicts, FDSelect ``[0,0,0,1,1,2,2,2]``,
  distinct per-FD width defaults; the per-CID width path proves the right FD's
  Private DICT is read.

Plus the real-world ``PDFBOX-3062-005717-p1.pdf`` /FontFile3 /CIDFontType0C
programs (single-FD, **format-3** FDSelect) — exercises the format-3 range
walk on genuine embedded fonts.

Both engines read the *same* CFF bytes, so any divergence is a real
FDSelect/FDArray/charstring-resolution bug, not a byte-layout artifact.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO = Path(__file__).resolve().parents[4]
_CFF_FIXTURES = _REPO / "tests" / "fixtures" / "fontbox" / "cff"
_PDF_FIXTURES = _REPO / "tests" / "fixtures" / "pdmodel" / "font"

_SUBR_CFF = _CFF_FIXTURES / "cid_multifd_subr.cff"
_THREE_FD_CFF = _CFF_FIXTURES / "cid_multifd_3fd.cff"
_LOCALSUBR_BIAS_CFF = _CFF_FIXTURES / "cid_multifd_localsubr_bias.cff"
_CID_PDF = _PDF_FIXTURES / "PDFBOX-3062-005717-p1.pdf"

# pypdfbox draw-command name -> PDFBox java.awt.geom.PathIterator segment type.
_SEG_TYPE = {"moveto": 0, "lineto": 1, "curveto": 3, "closepath": 4}


# --------------------------------------------------------------------------- #
# Probe-line parsing (CffCidFdProbe `read` output).
# --------------------------------------------------------------------------- #


class _FdFacts:
    def __init__(self) -> None:
        self.num_glyphs = 0
        self.is_cid = False
        self.fd_select_format = -1
        self.fd_array_size = 0
        self.fd_widths: dict[int, tuple[float, float]] = {}
        self.fd_index: dict[int, int] = {}
        self.widths: dict[int, float] = {}
        self.outlines: dict[int, tuple[int, str]] = {}


def _parse_probe(text: str) -> _FdFacts:
    f = _FdFacts()
    for line in text.splitlines():
        cols = line.split("\t")
        tag = cols[0]
        if tag == "META" and len(cols) >= 5:
            f.num_glyphs = int(cols[1])
            f.is_cid = cols[2] == "true"
            f.fd_select_format = int(cols[3])
            f.fd_array_size = int(cols[4])
        elif tag == "FDW" and len(cols) >= 4:
            f.fd_widths[int(cols[1])] = (float(cols[2]), float(cols[3]))
        elif tag == "FD" and len(cols) >= 3:
            f.fd_index[int(cols[1])] = int(cols[2])
        elif tag == "WID" and len(cols) >= 3:
            f.widths[int(cols[1])] = float(cols[2])
        elif tag == "OUT" and len(cols) >= 4:
            # OUT \t cid \t cmdCount \t fingerprint
            f.outlines[int(cols[1])] = (int(cols[2]), cols[3])
    return f


# --------------------------------------------------------------------------- #
# pypdfbox-side fact extraction — mirrors the probe field-for-field.
# --------------------------------------------------------------------------- #


def _py_fingerprint(commands: list[tuple]) -> tuple[int, str]:
    """Mirror the probe's GeneralPath fingerprint: ``type:x,y;`` per segment,
    coords rounded to integers. pypdfbox's pen carries no phantom post-close
    moveto, matching the probe's GeneralPath-quirk normalisation."""
    parts: list[str] = []
    for cmd in commands:
        seg = _SEG_TYPE[cmd[0]]
        coords = [str(round(v)) for v in cmd[1:]]
        parts.append(f"{seg}:" + ",".join(coords) + ";")
    return len(commands), "".join(parts)


def _py_facts(cid: CFFCIDFont) -> _FdFacts:
    f = _FdFacts()
    f.num_glyphs = cid.get_num_char_strings()
    f.is_cid = cid.is_cid_font()
    fd_select = cid.get_fd_select()
    fd_array = cid.get_fd_array()
    f.fd_select_format = fd_select.get_format()
    f.fd_array_size = fd_array.size()
    for i in range(fd_array.size()):
        f.fd_widths[i] = (
            fd_array.get_default_width_x(i),
            fd_array.get_nominal_width_x(i),
        )
    for gid in range(f.num_glyphs):
        f.fd_index[gid] = fd_select.get_fd_index(gid)
    # CID == GID for the Identity-ordered fonts these fixtures use; the probe
    # walks CID 0..numGlyphs-1, and CFFCIDFont.get_width/get_path take a CID.
    for c in range(f.num_glyphs):
        f.widths[c] = cid.get_width(c)
        f.outlines[c] = _py_fingerprint(cid.get_path(c))
    return f


def _assert_fd_parity(probe_text: str, cid: CFFCIDFont) -> None:
    java = _parse_probe(probe_text)
    py = _py_facts(cid)

    assert py.is_cid == java.is_cid, ("is_cid", py.is_cid, java.is_cid)
    assert py.num_glyphs == java.num_glyphs, (py.num_glyphs, java.num_glyphs)
    # /FDSelect on-disk format (0 / 3) matches.
    assert py.fd_select_format == java.fd_select_format, (
        "fd_select_format",
        py.fd_select_format,
        java.fd_select_format,
    )
    # /FDArray size matches.
    assert py.fd_array_size == java.fd_array_size, (
        "fd_array_size",
        py.fd_array_size,
        java.fd_array_size,
    )
    # Per-FD Private DICT width defaults match.
    assert set(py.fd_widths) == set(java.fd_widths), "FD width key sets differ"
    for i, (jd, jn) in java.fd_widths.items():
        pd, pn = py.fd_widths[i]
        assert round(pd) == round(jd), ("defaultWidthX", i, pd, jd)
        assert round(pn) == round(jn), ("nominalWidthX", i, pn, jn)
    # FDSelect.getFDIndex(gid) matches for every GID — the FD discrimination.
    assert py.fd_index == java.fd_index, ("fd_index", py.fd_index, java.fd_index)
    # Per-CID advance width matches (per-FD nominalWidthX path).
    assert set(py.widths) == set(java.widths), "width CID sets differ"
    for c, jw in java.widths.items():
        assert round(py.widths[c]) == round(jw), ("width", c, py.widths[c], jw)
    # Per-CID outline fingerprint matches — proves the local /Subrs index was
    # resolved in the GID's own font-dict.
    assert set(py.outlines) == set(java.outlines), "outline CID sets differ"
    for c, (jcnt, jfp) in java.outlines.items():
        pcnt, pfp = py.outlines[c]
        assert pcnt == jcnt, ("outline cmd count", c, pcnt, jcnt)
        assert pfp == jfp, ("outline fingerprint", c, pfp, jfp)


def _load_cid(data: bytes) -> CFFCIDFont:
    base = CFFParser().parse(data)[0]
    assert base.is_cid_font(), "fixture is not a CID-keyed CFF"
    return CFFCIDFont.from_cff_font(base)


# --------------------------------------------------------------------------- #
# Differential tests.
# --------------------------------------------------------------------------- #


@requires_oracle
def test_multifd_subr_fdselect_outline_matches_pdfbox() -> None:
    """2-FD CID CFF where each font-dict has its own local subr: FDSelect
    index, per-FD width defaults, per-CID width, and outline fingerprint all
    match Apache PDFBox 3.0.7. The outline parity is the load-bearing check —
    it proves ``callsubr`` resolved against the *selected* font-dict's /Subrs
    (FD0 draws a horizontal line, FD1 a vertical one)."""
    data = _SUBR_CFF.read_bytes()
    probe = run_probe_text("CffCidFdProbe", "read", str(_SUBR_CFF))
    _assert_fd_parity(probe, _load_cid(data))


@requires_oracle
def test_multifd_localsubr_bias_outline_matches_pdfbox() -> None:
    """2-FD CID CFF whose FDs carry **different-size** local /Subrs INDEXes, so
    each FD has a *different subr bias* (Adobe Technote #5176 §16: 107 for a
    1-entry INDEX, 1131 for a 1300-entry INDEX).

    This is the sharper sibling of
    ``test_multifd_subr_fdselect_outline_matches_pdfbox``: there both FDs have a
    single-entry /Subrs INDEX (shared bias 107), so a wrong-FD lookup still
    lands on *a* valid subr. Here FD0's ``callsubr -107`` must resolve to subr 0
    (bias 107, horizontal line) while FD1's ``callsubr 168`` must resolve to its
    *last* subr (index 1299 under bias 1131, vertical line). The FD1 outline is
    non-empty only if the interpreter computed the **1131 bias from FD1's own
    large /Subrs count** and indexed FD1's INDEX — not FD0's, and not a
    hard-coded 107 bias. A wrong bias or wrong-FD index yields an empty outline
    for the FD1 CIDs, a sharp divergence. Apache PDFBox 3.0.7 and pypdfbox must
    agree segment-for-segment."""
    data = _LOCALSUBR_BIAS_CFF.read_bytes()
    probe = run_probe_text("CffCidFdProbe", "read", str(_LOCALSUBR_BIAS_CFF))
    _assert_fd_parity(probe, _load_cid(data))


@requires_oracle
def test_multifd_three_fd_width_selection_matches_pdfbox() -> None:
    """3-FD CID CFF, FDSelect ``[0,0,0,1,1,2,2,2]``: the per-CID width path
    selects the right font-dict's ``nominalWidthX`` (50 / 80 / 111). FDSelect
    index, FDArray size, widths, and outlines match Apache PDFBox 3.0.7."""
    data = _THREE_FD_CFF.read_bytes()
    probe = run_probe_text("CffCidFdProbe", "read", str(_THREE_FD_CFF))
    _assert_fd_parity(probe, _load_cid(data))


@requires_oracle
def test_real_cidfonttype0c_format3_fdselect_matches_pdfbox() -> None:
    """Real-world embedded /FontFile3 /CIDFontType0C programs (format-3
    FDSelect, single font-dict): the format-3 range walk, per-CID FD index,
    widths, and outline fingerprints match Apache PDFBox 3.0.7 for every
    embedded CID font in PDFBOX-3062-005717-p1.pdf."""
    doc = PDDocument.load(str(_CID_PDF))
    try:
        seen = 0
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                fd = font.get_font_descriptor()
                if fd is None:
                    continue
                ff3 = fd.get_cos_object().get_dictionary_object(
                    COSName.get_pdf_name("FontFile3")
                )
                if ff3 is None:
                    continue
                stream = ff3.create_input_stream()
                try:
                    data = bytes(stream.read())
                finally:
                    stream.close()
                base = CFFParser().parse(data)[0]
                if not base.is_cid_font():
                    continue
                # mkstemp (not NamedTemporaryFile) so the handle is closed
                # before the Java probe reopens the path by name — on Windows
                # a still-open NamedTemporaryFile is locked against re-open.
                fd_handle, tmp_path = tempfile.mkstemp(suffix=".cff")
                try:
                    with os.fdopen(fd_handle, "wb") as tmp:
                        tmp.write(data)
                    probe = run_probe_text("CffCidFdProbe", "read", tmp_path)
                finally:
                    os.unlink(tmp_path)
                _assert_fd_parity(probe, CFFCIDFont.from_cff_font(base))
                seen += 1
        assert seen >= 1, "no CIDFontType0C program found in the fixture"
    finally:
        doc.close()
