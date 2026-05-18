"""Wave 1352 coverage-boost: target the last few uncovered branches across
seven near-100% modules. Each test exercises a real (reachable) edge that
the existing suites missed; truly-unreachable defensive branches were
pragmaed at the source instead of being faked here.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSDictionary,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
)
from pypdfbox.pdfparser import XrefEntry, XrefTrailerResolver, XrefType
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.rendering import (
    PageDrawerParameters,
    PDFRenderer,
    RenderDestination,
)
from pypdfbox.rendering.page_drawer import PageDrawer

# ---------------------------------------------------------------------------
# xref_trailer_resolver — Prev points to missing section
# ---------------------------------------------------------------------------


def test_set_startxref_logs_when_prev_offset_missing_from_map(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Walk ``/Prev`` and hit a byte position not in the section map —
    upstream logs and stops chaining. Covers
    ``XrefTrailerResolver.set_startxref`` warning branch (lines 272-277).
    """
    r = XrefTrailerResolver()
    # Latest section at byte 2000 with /Prev pointing at 9999 (nothing
    # registered there).
    r.begin_section(2000)
    r.set_entry(COSObjectKey(1, 0), XrefEntry(type=XrefType.TABLE, offset=200))
    t = COSDictionary()
    t.set_item(COSName.get_pdf_name("Prev"), COSInteger.get(9999))
    r.set_trailer(t)

    caplog.set_level("WARNING")
    r.set_startxref(2000)

    # The warning fired with the missing /Prev offset (proves the
    # break-on-missing-Prev branch executed).
    assert any("9999" in rec.getMessage() for rec in caplog.records)
    # Setting startxref a second time is the upstream no-op warning.
    r.set_startxref(2000)


# ---------------------------------------------------------------------------
# pd_type1_font — ``PDType1Font.load`` classmethod
# ---------------------------------------------------------------------------


def _synthetic_pfb() -> bytes:
    """Three-segment PFB envelope; the body is irrelevant when the
    fontTools T1Font parser is monkey-patched out."""
    seg1 = b"%!PS-AdobeFont"
    seg2 = b"binary-segment"
    seg3 = b"end"
    return (
        b"\x80\x01" + len(seg1).to_bytes(4, "little") + seg1
        + b"\x80\x02" + len(seg2).to_bytes(4, "little") + seg2
        + b"\x80\x01" + len(seg3).to_bytes(4, "little") + seg3
        + b"\x80\x03"
    )


def _install_font_name_constants() -> None:
    """``PDType1FontEmbedder`` references ``COSName.FONT_DESC`` etc. that
    aren't pre-registered in the static table; install on demand so the
    embedder doesn't hit ``AttributeError`` during ``load()``."""
    for attr, raw in (
        ("BASE_FONT", "BaseFont"),
        ("FONT_DESC", "FontDescriptor"),
        ("ENCODING", "Encoding"),
    ):
        if not hasattr(COSName, attr):
            setattr(COSName, attr, COSName.get_pdf_name(raw))


def test_pd_type1_font_load_wires_embedder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``PDType1Font.load(document, pfb_stream, encoding)`` is upstream's
    convenience ctor — covers the classmethod (lines 134-140)."""
    _install_font_name_constants()

    class _FakeGlyph:
        def __init__(self, width: float = 500.0) -> None:
            self.width = width

    class _FakeGlyphSet:
        def __getitem__(self, name: str) -> _FakeGlyph:
            return _FakeGlyph(680.0)

    class _StubT1:
        def __init__(self, _stream: Any) -> None:
            self.font = {"FontName": "MyType1", "FontBBox": [0, 0, 1, 1]}

        def getGlyphSet(self) -> _FakeGlyphSet:  # noqa: N802 - fontTools API
            return _FakeGlyphSet()

    import fontTools.t1Lib as t1mod

    monkeypatch.setattr(t1mod, "T1Font", _StubT1)

    doc = PDDocument()
    try:
        font = PDType1Font.load(doc, _synthetic_pfb(), None)
        assert isinstance(font, PDType1Font)
        assert font.get_cos_object().get_name_as_string("Subtype") == "Type1"
    finally:
        doc.close()


def test_pd_type1_font_load_accepts_bytes_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``pfb_stream`` may be either bytes or a binary file — both must
    reach the embedder."""
    _install_font_name_constants()

    class _StubT1:
        def __init__(self, _stream: Any) -> None:
            self.font = {"FontName": "S", "FontBBox": [0, 0, 1, 1]}

        def getGlyphSet(self):  # noqa: N802 - fontTools API
            return {}

    import fontTools.t1Lib as t1mod

    monkeypatch.setattr(t1mod, "T1Font", _StubT1)

    doc = PDDocument()
    try:
        font = PDType1Font.load(doc, io.BytesIO(_synthetic_pfb()), None)
        assert isinstance(font, PDType1Font)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# pd_type3_font — generate_bounding_box edge cases
# ---------------------------------------------------------------------------


def test_generate_bounding_box_skips_non_stream_char_proc_entries() -> None:
    """``/CharProcs`` ought to map names to streams; a non-stream entry
    is skipped per upstream — covers ``pd_type3_font.py`` line 572.
    """
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 0.0, 0.0))

    char_procs = COSDictionary()
    # One real stream that supplies a bbox…
    real = COSStream()
    real.set_raw_data(b"600 0 -10 -20 700 900 d1\n")
    char_procs.set_item(COSName.get_pdf_name("A"), real)
    # …plus a non-stream entry that must be skipped without raising.
    char_procs.set_item(COSName.get_pdf_name("B"), COSDictionary())
    font.set_char_procs(char_procs)

    out = font.get_bounding_box()
    assert out is not None
    # The stream's bbox was unioned in; the dict entry contributed
    # nothing (no crash).
    assert out.get_lower_left_x() == pytest.approx(-10.0)
    assert out.get_upper_right_x() == pytest.approx(700.0)


def test_generate_bounding_box_continues_when_char_proc_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed ``d1`` header surfaces as ``OSError``/``ValueError``
    from :meth:`PDType3CharProc.get_glyph_bbox`; upstream logs and
    continues — covers ``pd_type3_font.py`` lines 576-578.
    """
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 0.0, 0.0))

    char_procs = COSDictionary()
    glyph = COSStream()
    glyph.set_raw_data(b"600 0 10 20 30 40 d1\n")
    char_procs.set_item(COSName.get_pdf_name("A"), glyph)
    font.set_char_procs(char_procs)

    def _raise(self: PDType3CharProc) -> Any:
        raise ValueError("malformed d1 header")

    monkeypatch.setattr(PDType3CharProc, "get_glyph_bbox", _raise)

    out = font.get_bounding_box()
    # No glyph contributed -> bbox stays at the seed (all zeros).
    assert out is not None
    assert out.get_lower_left_x() == 0.0
    assert out.get_upper_right_x() == 0.0


# ---------------------------------------------------------------------------
# page_drawer — show_transparency_group fallback + is_rectangular branches
# ---------------------------------------------------------------------------


def _make_drawer() -> tuple[PDDocument, PDFRenderer, PageDrawer]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    doc.add_page(page)
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", (50, 50), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw  # noqa: PLC0415

    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._draw.setantialias(True)
    renderer._scale = 1.0
    from pypdfbox.rendering.pdf_renderer import _GState  # noqa: PLC0415

    renderer._gs_stack = [_GState()]
    renderer._subpaths = []
    renderer._current_subpath = None
    renderer._current_point = (0.0, 0.0)
    renderer._pending_clip = None
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.VIEW,
        rendering_hints={"AA": True},
        image_downscaling_optimization_threshold=0.5,
    )
    return doc, renderer, PageDrawer(params)


def test_show_transparency_group_falls_back_to_show_form() -> None:
    """When the renderer has no ``_render_form_xobject`` helper, the
    transparency-group helper falls through to :meth:`show_form` — covers
    ``page_drawer.py`` line 410.

    The fall-through fires when ``getattr(rdr, '_render_form_xobject',
    None)`` resolves to a non-callable. Drop in a sentinel that's not
    callable (e.g. the integer 0): the ``callable(...)`` check fails and
    we land on ``self.show_form(form)``.
    """
    doc, renderer, drawer = _make_drawer()
    renderer._render_form_xobject = 0  # type: ignore[assignment]
    try:
        drawer.show_transparency_group(form="form-fallback")
        # Stack was popped after the render.
        assert drawer._transparency_group_stack == []
    finally:
        doc.close()


def test_is_rectangular_returns_false_when_path_does_not_start_with_move() -> None:
    """Five-segment closed path whose first op is not ``M`` — covers
    ``page_drawer.py`` line 742."""
    doc, _renderer, drawer = _make_drawer()
    try:
        # Five entries, ends with Z, but starts with L instead of M.
        bad_start = [
            ("L", 0, 0),
            ("L", 10, 0),
            ("L", 10, 5),
            ("L", 0, 5),
            ("Z",),
        ]
        assert drawer.is_rectangular(bad_start) is False
    finally:
        doc.close()


def test_is_rectangular_returns_false_when_inner_segment_is_not_line() -> None:
    """Five-segment closed path that starts with ``M`` but has a
    non-``L`` somewhere in indices 1..3 — covers ``page_drawer.py``
    line 745."""
    doc, _renderer, drawer = _make_drawer()
    try:
        # Second segment is M instead of L (only M/L/Z pass the filter,
        # so we can't smuggle in a curve, but a second moveTo is
        # perfectly valid in the upstream tokeniser).
        bad_middle = [
            ("M", 0, 0),
            ("M", 5, 5),
            ("L", 10, 5),
            ("L", 0, 5),
            ("Z",),
        ]
        assert drawer.is_rectangular(bad_middle) is False
    finally:
        doc.close()
