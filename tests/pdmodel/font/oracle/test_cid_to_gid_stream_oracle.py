"""Live PDFBox differential parity for the CIDFontType2 ``/CIDToGIDMap``
**stream** branch (the non-``/Identity`` case).

Wave 1444. When a CIDFontType2's ``/CIDToGIDMap`` is a *stream* rather than
the name ``/Identity``, the stream is a packed big-endian array of 2-byte GIDs
indexed by CID: ``gid = stream[2*cid : 2*cid+2]`` decoded big-endian, with a
CID at or beyond the stream length resolving to GID 0. This is a distinct code
path from the ``/Identity`` shortcut (where ``cid == gid``, bounded by the
embedded program's glyph count) — the stream path must (a) take the stream
branch rather than the Identity branch, (b) decode the GIDs big-endian, and (c)
clamp out-of-range CIDs to GID 0.

pypdfbox's embedder always writes ``/CIDToGIDMap /Identity`` for a full (non
subset) embed, so the fixture here is hand-authored: after
:meth:`PDType0Font.load` (subset OFF, which leaves ``/Identity``) the descendant
dict's ``/CIDToGIDMap`` is replaced with an explicit stream that maps a handful
of CIDs to *non-identity* GIDs (e.g. CID 3 -> GID 36 = ``A``, CID 5 -> GID 43 =
``H``, CID 7 -> GID 48 = ``M``, CID 9 -> GID 58 = ``W`` in the bundled
``DejaVuSans.ttf``), with an in-range CID 4 deliberately left at GID 0 and
several CIDs beyond the stream length. The content stream then shows
``<00030005000700090>`` under Identity-H (code == CID), so the glyphs that paint
are exactly the *mapped* GIDs, not the identity ones.

The content-stream CIDs (3, 5, 7, 9) are chosen so their descendant ``/W``
advance widths are non-zero: the *advance* a Type0 font reports for display is
``/W``[CID] (the displacement, independent of which GID the CID maps to), so the
render is decoupled from the remapped glyph's own hmtx advance. This keeps the
render fingerprint a clean test of *which glyph paints* (the CIDToGIDMap-stream
surface) rather than of advance-width policy.

Two engines, two assertions:

* ``CidToGidStreamProbe.java`` emits PDFBox's ``codeToGID(cid)`` for a set of
  CIDs (mapped, in-range-zero, and out-of-range) plus whether ``/CIDToGIDMap``
  is a stream and the embedded glyph count. pypdfbox's
  :meth:`PDCIDFontType2.cid_to_gid` / :meth:`code_to_gid` must match every line.
* ``RenderProbe.java`` (16x16 luminance grid) confirms the *mapped* glyphs
  actually paint where PDFBox paints them — a stream-not-read regression (glyphs
  treated as Identity) would paint the wrong glyphs and blow the grid gate.

Render gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured
against PDFBox 3.0.7 the fixture lands at MAD ~0.07 / MAXDIFF ~4 (the remapped
glyphs paint exactly where PDFBox paints them).
"""

from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FONT = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)

# CID -> GID remapping written into the /CIDToGIDMap stream. The four mapped
# CIDs (3, 5, 7, 9) are the content-stream codes; they point at visible glyphs
# A / H / M / W. CID 4 sits *inside* the stream but holds GID 0 (an explicit
# in-range zero). Every CID at or beyond the stream length (the stream covers
# indices 0..9) resolves to GID 0.
_CID_TO_GID = {3: 36, 5: 43, 7: 48, 9: 58}
_STREAM_LEN_CIDS = 10  # stream holds entries for CID 0..9 inclusive.

# CIDs the probe + python helper resolve, covering every branch:
#   mapped (3,5,7,9) -> non-identity GID,
#   in-range explicit zero (4) -> 0,
#   out-of-range (10, 60000, 65535) -> 0,
#   .notdef (0) -> 0.
_PROBE_CIDS = (0, 3, 4, 5, 7, 9, 10, 60000, 65535)
_EXPECTED_GID = {
    0: 0,
    3: 36,
    4: 0,
    5: 43,
    7: 48,
    9: 58,
    10: 0,
    60000: 0,
    65535: 0,
}

# Content-stream codes (Identity-H => code == CID); the mapped CIDs, in order.
_CONTENT_CIDS = (3, 5, 7, 9)


def _build(out: Path) -> Path:
    """Embed ``DejaVuSans.ttf`` (subset OFF) as a Type0/CIDFontType2, replace
    the descendant's ``/CIDToGIDMap`` with a hand-authored *stream* that maps a
    few CIDs to non-identity GIDs, and show the mapped CIDs under Identity-H."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 200.0, 60.0))
        doc.add_page(page)

        # subset OFF keeps the full glyph set so the remapped GIDs (36/43/48/58)
        # address real glyphs, and leaves /CIDToGIDMap as /Identity for us to
        # override below.
        font = PDType0Font.load(doc, str(_FONT), embed_subset=False)
        descendant = font.get_descendant_font()
        assert isinstance(descendant, PDCIDFontType2)

        # Pack the big-endian uint16 GID array, indexed by CID.
        gids = [0] * _STREAM_LEN_CIDS
        for cid, gid in _CID_TO_GID.items():
            gids[cid] = gid
        data = b"".join(struct.pack(">H", g) for g in gids)
        cid_to_gid_stream = COSStream()
        cid_to_gid_stream.set_data(data)
        descendant._dict.set_item(
            COSName.get_pdf_name("CIDToGIDMap"), cid_to_gid_stream
        )
        descendant.clear_cid_to_gid_map_cache()

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        # Identity-H: each 2-byte code IS the CID. Show the mapped CIDs.
        codes = b"".join(struct.pack(">H", c) for c in _CONTENT_CIDS)
        cs = COSStream()
        cs.set_data(
            b"BT\n/F1 24 Tf\n10 20 Td\n<%s> Tj\nET\n" % codes.hex().encode("ascii")
        )
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


# ---------------------------------------------------------------------------
# fingerprint helper — mirrors RenderProbe.java's cell mapping exactly
# ---------------------------------------------------------------------------


def _grid_from_image(img: Image.Image) -> list[int]:
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255
        for i in range(_GRID * _GRID)
    ]


def _reload_descendant(pdf_path: Path) -> tuple[PDDocument, PDCIDFontType2]:
    """Reload ``pdf_path`` and return (doc, the CIDFontType2 descendant).

    Caller owns the returned doc and must close it.
    """
    doc = PDDocument.load(pdf_path)
    for page in doc.get_pages():
        res = page.get_resources()
        if res is None:
            continue
        for name in res.get_font_names():
            font = res.get_font(name)
            if not isinstance(font, PDType0Font):
                continue
            descendant = font.get_descendant_font()
            if isinstance(descendant, PDCIDFontType2):
                return doc, descendant
    doc.close()
    raise AssertionError("no CIDFontType2 descendant in fixture")


# ---------------------------------------------------------------------------
# fixture proof: the authored map really is a stream, not /Identity
# ---------------------------------------------------------------------------


def test_authored_map_is_a_stream_not_identity(tmp_path: Path) -> None:
    """Prove the fixture exercises the *stream* branch: the reloaded
    descendant's ``/CIDToGIDMap`` must be a stream (not the name ``/Identity``),
    and its decoded bytes must be the big-endian GID array we wrote. If the
    save path ever collapsed the stream to ``/Identity`` this test would catch
    it before the parity assertions ran against the wrong branch."""
    fixture = _build(tmp_path / "cid_to_gid_stream.pdf")
    doc, descendant = _reload_descendant(fixture)
    try:
        assert not descendant.is_identity_cid_to_gid_map()
        assert descendant.has_cid_to_gid_map()
        raw = descendant.get_cid_to_gid_map_bytes()
        assert raw is not None
        expected = [0] * _STREAM_LEN_CIDS
        for cid, gid in _CID_TO_GID.items():
            expected[cid] = gid
        decoded = [
            int.from_bytes(raw[i : i + 2], "big") for i in range(0, len(raw), 2)
        ]
        assert decoded == expected
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# differential test (a): code -> GID through the stream matches PDFBox
# ---------------------------------------------------------------------------


@requires_oracle
def test_cid_to_gid_stream_matches_pdfbox(tmp_path: Path) -> None:
    """Every ``cid -> gid`` resolved through the ``/CIDToGIDMap`` stream must
    match Apache PDFBox's ``codeToGID``, including:

    * mapped CIDs -> their non-identity GIDs (the 2-byte big-endian decode),
    * an in-range CID holding an explicit 0 -> GID 0,
    * out-of-range CIDs (beyond the stream length) -> GID 0,
    * the stream-vs-Identity branch + glyph count reported identically.
    """
    fixture = _build(tmp_path / "cid_to_gid_stream.pdf")

    args = ["CidToGidStreamProbe", str(fixture), *(str(c) for c in _PROBE_CIDS)]
    java = run_probe_text(*args).splitlines()

    # Header: KIND \t <kind> \t <numGlyphs>
    assert java[0].startswith("KIND\t")
    _kw, kind, num_glyphs_s = java[0].split("\t")
    assert kind == "stream", f"PDFBox did not see a stream /CIDToGIDMap: {kind}"
    java_num_glyphs = int(num_glyphs_s)

    # Python reproduction: stream kind + glyph count + per-CID GID.
    doc, descendant = _reload_descendant(fixture)
    try:
        assert not descendant.is_identity_cid_to_gid_map()
        ttf = descendant.get_true_type_font()
        assert ttf is not None
        py_num_glyphs = ttf.get_number_of_glyphs()
        assert py_num_glyphs == java_num_glyphs

        java_gids = {}
        for line in java[1:]:
            tag, cid_s, gid_s = line.split("\t")
            assert tag == "GID"
            java_gids[int(cid_s)] = gid_s

        for cid in _PROBE_CIDS:
            py_gid = descendant.cid_to_gid(cid)
            # code_to_gid is the descendant-facing alias the renderer uses; it
            # must agree with cid_to_gid for a CIDFontType2.
            assert descendant.code_to_gid(cid) == py_gid
            assert str(py_gid) == java_gids[cid], (
                f"cid {cid}: pypdfbox gid {py_gid} != PDFBox {java_gids[cid]}"
            )
            # Pin the absolute expectation too, so a future PDFBox bump that
            # also regressed the same way wouldn't slip through.
            assert py_gid == _EXPECTED_GID[cid]
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# differential test (b): the mapped glyphs render where PDFBox renders them
# ---------------------------------------------------------------------------


@requires_oracle
def test_cid_to_gid_stream_render_matches_pdfbox(tmp_path: Path) -> None:
    """The glyphs that paint are the *mapped* GIDs (A/H/M/W via the stream),
    not the identity ones. A stream-not-read regression (CID treated as GID)
    would paint different glyphs and blow the grid gate."""
    fixture = _build(tmp_path / "cid_to_gid_stream.pdf")

    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    java_w, java_h = (int(v) for v in lines[0].split())
    java_grid = [int(v) for v in lines[1].split()]
    assert len(java_grid) == _GRID * _GRID

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"rendered dimensions diverge: pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} (maxdiff={maxdiff}) "
        f"— mapped-glyph render grossly divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} (mad={mad:.2f}) "
        f"— a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_blank_page_far_from_stream_reference(tmp_path: Path) -> None:
    """Guard the gate: a blank-white page is far outside tolerance versus
    PDFBox's actual (mapped-glyph) render — proving the mapped glyphs really
    paint and the gate discriminates a correct stream read from a blank
    (dropped) render."""
    fixture = _build(tmp_path / "cid_to_gid_stream.pdf")
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    java_grid = [int(v) for v in lines[1].split()]
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"tolerance too loose — a blank page passes the MAD gate (blank MAD "
        f"{mad:.2f}); a dropped-glyph render would not be caught"
    )


# ---------------------------------------------------------------------------
# value pin (no oracle): the 2-byte big-endian decode + out-of-range -> 0
# ---------------------------------------------------------------------------


def test_stream_decode_and_out_of_range(tmp_path: Path) -> None:
    """Regression pin for the stream branch with no oracle needed.

    Exercises directly: stream-vs-Identity branch, 2-byte big-endian indexing,
    in-range explicit zero, and out-of-range CID -> GID 0.
    """
    fixture = _build(tmp_path / "cid_to_gid_stream.pdf")
    doc, descendant = _reload_descendant(fixture)
    try:
        # Branch: a stream, not Identity.
        assert not descendant.is_identity_cid_to_gid_map()
        assert descendant.has_cid_to_gid_map()
        # 2-byte big-endian decode of mapped CIDs.
        for cid, gid in _CID_TO_GID.items():
            assert descendant.cid_to_gid(cid) == gid
        # In-range explicit zero.
        assert descendant.cid_to_gid(4) == 0
        # Out-of-range CIDs (beyond the stream length) -> 0.
        assert descendant.cid_to_gid(_STREAM_LEN_CIDS) == 0
        assert descendant.cid_to_gid(_STREAM_LEN_CIDS + 5) == 0
        assert descendant.cid_to_gid(65535) == 0
        # Negative CID -> 0 (defensive guard).
        assert descendant.cid_to_gid(-1) == 0
    finally:
        doc.close()
