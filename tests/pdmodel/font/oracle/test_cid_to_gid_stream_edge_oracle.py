"""Live PDFBox differential parity for the CIDFontType2 ``/CIDToGIDMap`` edge
shapes the wave-1444 stream test did not cover: an **odd-length** stream (a
trailing byte that doesn't complete a 2-byte GID), an **empty** stream, and the
entry set to a **non-Identity name** (``/Foo``).

Wave 1483. Upstream ``PDCIDFont.readCIDToGIDMap`` (PDCIDFont.java:398) reads the
map only when the entry is a *stream* (``dict.getCOSStream``), decoding
``numberOfInts = mapAsBytes.length / 2`` big-endian ``uint16`` GIDs — integer
division **drops a trailing odd byte**. An *empty* stream yields a non-null but
zero-length ``cid2gid`` array, so every CID is out of range -> GID 0 (distinct
from the *absent*/name case where ``cid2gid`` is null and the CID falls through
to the bounded-identity branch). Any *name* (``/Identity`` **or** any other
name like ``/Foo``) is not a stream, so ``getCOSStream`` returns null and
``readCIDToGIDMap`` returns null — upstream then treats the CID as the GID,
bounded by the embedded program's glyph count (``cid < numberOfGlyphs ? cid :
0``). PDFBox does NOT special-case the name's spelling: a stray ``/Foo`` maps
exactly like ``/Identity``.

All three shapes were confirmed against Apache PDFBox 3.0.7 via
``CidToGidStreamProbe`` (reused from wave 1444) — pypdfbox already matches every
literal, so this file pins parity rather than fixing a divergence.

The value pins pass without the oracle; the ``@requires_oracle`` tests run the
live differential when the jar is present.
"""

from __future__ import annotations

import struct
from pathlib import Path

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_FONT = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)

# CIDs probed across every edge shape (mapped, in-range, out-of-range).
_PROBE_CIDS = (0, 1, 2, 3, 100, 60000, 65535)

# Odd-length stream: bytes for GID 36 (CID 0) + GID 43 (CID 1) + one trailing
# byte that does not complete a third 2-byte entry. Upstream's
# ``length / 2`` truncation drops the trailing byte, leaving entries [36, 43].
_ODD_BYTES = struct.pack(">H", 36) + struct.pack(">H", 43) + b"\x30"
_ODD_EXPECTED = {0: 36, 1: 43, 2: 0, 3: 0, 100: 0, 60000: 0, 65535: 0}

# Empty stream: non-null zero-length map -> every CID is out of range -> 0.
_EMPTY_EXPECTED = dict.fromkeys(_PROBE_CIDS, 0)

# Non-Identity name ``/Foo``: not a stream, so the map is null and the CID is
# the GID bounded by the program's glyph count (DejaVuSans = 6253 glyphs), with
# CID 0 (.notdef) staying 0 and out-of-range CIDs clamped to 0.
_OTHER_NAME = "Foo"
_OTHER_NAME_EXPECTED = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    100: 100,
    60000: 0,
    65535: 0,
}


def _build(out: Path, kind: str) -> Path:
    """Embed ``DejaVuSans.ttf`` (subset OFF) as a Type0/CIDFontType2 and set its
    descendant ``/CIDToGIDMap`` to the requested edge shape."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 200.0, 60.0))
        doc.add_page(page)

        font = PDType0Font.load(doc, str(_FONT), embed_subset=False)
        descendant = font.get_descendant_font()
        assert isinstance(descendant, PDCIDFontType2)

        key = COSName.get_pdf_name("CIDToGIDMap")
        if kind == "odd":
            stream = COSStream()
            stream.set_data(_ODD_BYTES)
            descendant._dict.set_item(key, stream)
        elif kind == "empty":
            stream = COSStream()
            stream.set_data(b"")
            descendant._dict.set_item(key, stream)
        elif kind == "othername":
            descendant._dict.set_item(key, COSName.get_pdf_name(_OTHER_NAME))
        else:  # pragma: no cover - guard against typos in callers
            raise AssertionError(f"unknown kind: {kind}")
        descendant.clear_cid_to_gid_map_cache()

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        cs = COSStream()
        cs.set_data(b"BT\n/F1 24 Tf\n10 20 Td\n<0003> Tj\nET\n")
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


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
# value pins (no oracle needed)
# ---------------------------------------------------------------------------


def test_odd_length_stream_drops_trailing_byte(tmp_path: Path) -> None:
    """A 5-byte ``/CIDToGIDMap`` stream decodes exactly two GIDs (the trailing
    odd byte is dropped, mirroring upstream's ``length / 2`` truncation); the
    rest of the CID range resolves to GID 0."""
    fixture = _build(tmp_path / "cid_to_gid_odd.pdf", "odd")
    doc, descendant = _reload_descendant(fixture)
    try:
        assert descendant.has_cid_to_gid_map()
        assert not descendant.is_identity_cid_to_gid_map()
        raw = descendant.get_cid_to_gid_map_bytes()
        assert raw == _ODD_BYTES
        for cid, gid in _ODD_EXPECTED.items():
            assert descendant.cid_to_gid(cid) == gid
            assert descendant.code_to_gid(cid) == gid
    finally:
        doc.close()


def test_empty_stream_maps_every_cid_to_zero(tmp_path: Path) -> None:
    """An empty ``/CIDToGIDMap`` stream is a non-null, zero-length map: every
    CID is out of range, so each resolves to GID 0. ``has_cid_to_gid_map`` is
    still ``True`` (a stream is present, just empty) — distinct from the
    absent/name case which is bounded identity."""
    fixture = _build(tmp_path / "cid_to_gid_empty.pdf", "empty")
    doc, descendant = _reload_descendant(fixture)
    try:
        assert descendant.has_cid_to_gid_map()
        assert not descendant.is_identity_cid_to_gid_map()
        assert descendant.get_cid_to_gid_map_bytes() == b""
        for cid, gid in _EMPTY_EXPECTED.items():
            assert descendant.cid_to_gid(cid) == gid
            assert descendant.code_to_gid(cid) == gid
    finally:
        doc.close()


def test_non_identity_name_is_bounded_identity(tmp_path: Path) -> None:
    """A ``/CIDToGIDMap`` set to a non-Identity name (``/Foo``) is not a stream,
    so upstream's ``getCOSStream`` returns null and the map is null — the CID is
    the GID, bounded by the embedded program's glyph count. PDFBox does not
    special-case the name spelling: ``/Foo`` behaves like ``/Identity``."""
    fixture = _build(tmp_path / "cid_to_gid_othername.pdf", "othername")
    doc, descendant = _reload_descendant(fixture)
    try:
        # Not a stream -> no decoded map; not the literal /Identity name either.
        assert not descendant.has_cid_to_gid_map()
        assert not descendant.is_identity_cid_to_gid_map()
        assert descendant.get_cid_to_gid_map_bytes() is None
        ttf = descendant.get_true_type_font()
        assert ttf is not None
        num_glyphs = ttf.get_number_of_glyphs()
        assert num_glyphs > 100
        for cid, gid in _OTHER_NAME_EXPECTED.items():
            assert descendant.cid_to_gid(cid) == gid
            assert descendant.code_to_gid(cid) == gid
        # The boundary itself: last in-range CID passes, first OOB -> 0.
        assert descendant.cid_to_gid(num_glyphs - 1) == num_glyphs - 1
        assert descendant.cid_to_gid(num_glyphs) == 0
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# live differential (reuses wave 1444's CidToGidStreamProbe)
# ---------------------------------------------------------------------------


def _assert_oracle_parity(
    fixture: Path,
    expected_kind: str,
    expected_gids: dict[int, int],
) -> None:
    args = ["CidToGidStreamProbe", str(fixture), *(str(c) for c in _PROBE_CIDS)]
    java = run_probe_text(*args).splitlines()

    assert java[0].startswith("KIND\t")
    _kw, kind, _num_glyphs = java[0].split("\t")
    assert kind == expected_kind, f"PDFBox saw kind {kind!r}, want {expected_kind!r}"

    java_gids: dict[int, str] = {}
    for line in java[1:]:
        tag, cid_s, gid_s = line.split("\t")
        assert tag == "GID"
        java_gids[int(cid_s)] = gid_s

    doc, descendant = _reload_descendant(fixture)
    try:
        for cid in _PROBE_CIDS:
            py_gid = descendant.cid_to_gid(cid)
            assert str(py_gid) == java_gids[cid], (
                f"cid {cid}: pypdfbox {py_gid} != PDFBox {java_gids[cid]}"
            )
            assert py_gid == expected_gids[cid]
    finally:
        doc.close()


@requires_oracle
def test_odd_length_stream_matches_pdfbox(tmp_path: Path) -> None:
    """Odd-length stream: PDFBox drops the trailing byte; pypdfbox matches."""
    fixture = _build(tmp_path / "cid_to_gid_odd.pdf", "odd")
    _assert_oracle_parity(fixture, "stream", _ODD_EXPECTED)


@requires_oracle
def test_empty_stream_matches_pdfbox(tmp_path: Path) -> None:
    """Empty stream: PDFBox resolves every CID to GID 0; pypdfbox matches."""
    fixture = _build(tmp_path / "cid_to_gid_empty.pdf", "empty")
    _assert_oracle_parity(fixture, "stream", _EMPTY_EXPECTED)


@requires_oracle
def test_non_identity_name_matches_pdfbox(tmp_path: Path) -> None:
    """``/Foo`` name: PDFBox treats it as bounded identity; pypdfbox matches."""
    fixture = _build(tmp_path / "cid_to_gid_othername.pdf", "othername")
    _assert_oracle_parity(fixture, "name:" + _OTHER_NAME, _OTHER_NAME_EXPECTED)
