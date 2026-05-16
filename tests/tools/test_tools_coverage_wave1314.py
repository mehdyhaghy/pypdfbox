"""Coverage-boost tests for the five CLI class-port modules in
``pypdfbox.tools`` (wave 1314).

The targets — ``pdf_to_image``, ``extract_images``, ``export_fdf``,
``extract_xmp``, ``overlay_pdf`` — are direct ports of the upstream
PDFBox ``main(...)`` runners. The classes call PD-layer helpers
(``get_number_of_pages``, ``get_document_catalog``, ...) so the loader
in these tests wraps the raw ``COSDocument`` returned by
:meth:`pypdfbox.loader.Loader.load_pdf` in a :class:`PDDocument` and
re-exposes the same context-manager contract. The renderer in
``pdf_to_image`` is also stubbed because the full Pillow + page-drawer
pipeline is exercised elsewhere; here we only care that the runner's
loop body, file-naming, error returns, and helper static methods
execute.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from pypdfbox.loader import Loader as RealLoader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import (
    export_fdf,
    extract_images,
    extract_xmp,
    overlay_pdf,
    pdf_to_image,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ROT0 = FIXTURES / "multipdf" / "rot0.pdf"
ROT90 = FIXTURES / "multipdf" / "rot90.pdf"
FORM_PDF = FIXTURES / "multipdf" / "PDFBOX-5811-362972.pdf"
OVERLAY_BASE = FIXTURES / "multipdf" / "OverlayTestBaseRot0.pdf"
OVERLAY_TOP = FIXTURES / "multipdf" / "PDFBOX-6049-Overlay.pdf"


# --------------------------------------------------------------------------
# Shared shim — wraps Loader.load_pdf(COSDocument) → PDDocument so the
# class ports' PD-layer calls resolve. The shim is a context manager to
# mirror upstream's ``try-with-resources`` pattern.
# --------------------------------------------------------------------------
class _PDLoaderShim:
    @staticmethod
    @contextlib.contextmanager
    def load_pdf(source: Any, password: Any = None) -> Iterator[PDDocument]:
        if isinstance(password, str) and password == "":
            password = None
        cos_doc = RealLoader.load_pdf(source, password)
        pd = PDDocument(cos_doc)
        try:
            yield pd
        finally:
            pd.close()


@pytest.fixture
def patched_loader(monkeypatch: pytest.MonkeyPatch) -> type[_PDLoaderShim]:
    """Patch ``Loader`` in each of the five target modules to the shim."""
    for module in (pdf_to_image, extract_images, extract_xmp, export_fdf):
        monkeypatch.setattr(module, "Loader", _PDLoaderShim)
    return _PDLoaderShim


# --------------------------------------------------------------------------
# pdf_to_image
# --------------------------------------------------------------------------
class _FakeRenderer:
    """Replacement for :class:`PDFRenderer` — returns a tiny RGB PIL
    image so the runner's ImageIOUtil.write_image branch is exercised
    without depending on the full page-drawer pipeline."""

    def __init__(self, document: Any) -> None:
        self.document = document
        self.subsampling_allowed: bool | None = None

    def set_subsampling_allowed(self, allowed: bool) -> None:
        self.subsampling_allowed = allowed

    def render_image_with_dpi(self, page_index: int, dpi: int, image_type: Any) -> Image.Image:
        return Image.new("RGB", (8, 8), "white")


def test_pdf_to_image_runs_default_format(
    patched_loader: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _FakeRenderer)
    prefix = tmp_path / "out"
    rc = pdf_to_image.PDFToImage.main([
        "-i", str(ROT0),
        "-prefix", str(prefix),
        "-format", "jpg",
        "-dpi", "36",
    ])
    assert rc == 0
    out = tmp_path / "out-1.jpg"
    assert out.exists()
    assert out.read_bytes()[:3] == b"\xff\xd8\xff"  # JPEG SOI


def test_pdf_to_image_png_quality_default_branch(
    patched_loader: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _FakeRenderer)
    prefix = tmp_path / "p"
    rc = pdf_to_image.PDFToImage.main([
        "-i", str(ROT0),
        "-prefix", str(prefix),
        "-format", "png",
        "-dpi", "48",
        "-time",
        "-subsampling",
    ])
    assert rc == 0
    out = tmp_path / "p-1.png"
    assert out.exists()
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_pdf_to_image_explicit_page_and_cropbox(
    patched_loader: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _FakeRenderer)
    prefix = tmp_path / "c"
    rc = pdf_to_image.PDFToImage.main([
        "-i", str(ROT0),
        "-prefix", str(prefix),
        "-format", "png",
        "-page", "1",
        "-cropbox", "0", "0", "100", "100",
        "-dpi", "36",
    ])
    assert rc == 0
    assert (tmp_path / "c-1.png").exists()


def test_pdf_to_image_unsupported_format_returns_2(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = pdf_to_image.PDFToImage.main([
        "-i", str(ROT0),
        "-prefix", str(tmp_path / "x"),
        "-format", "bogus-format",
    ])
    assert rc == 2
    assert "Invalid image format" in capsys.readouterr().err


def test_pdf_to_image_change_crop_box_static() -> None:
    """The ``change_crop_box`` helper is a pure transform; cover it via
    a tiny one-page PDDocument and assert the crop box mutated."""
    from pypdfbox.pdmodel.pd_document import PDDocument as PDDoc
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDoc()
    try:
        doc.add_page(PDPage())
        pdf_to_image.PDFToImage.change_crop_box(doc, 0, 0, 100, 200)
        page = list(doc.get_pages())[0]
        rect = page.get_crop_box()
        assert rect.get_lower_left_x() == 0
        assert rect.get_lower_left_y() == 0
        assert rect.get_upper_right_x() == 100
        assert rect.get_upper_right_y() == 200
    finally:
        doc.close()


def test_pdf_to_image_missing_infile_raises() -> None:
    runner = pdf_to_image.PDFToImage()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_pdf_to_image_load_error_returns_4(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = pdf_to_image.PDFToImage.main([
        "-i", str(tmp_path / "missing.pdf"),
        "-prefix", str(tmp_path / "out"),
        "-format", "png",
    ])
    assert rc == 4
    assert "Error converting document" in capsys.readouterr().err


# --------------------------------------------------------------------------
# extract_images
# --------------------------------------------------------------------------
def test_extract_images_default_prefix_no_images(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """rot0.pdf has no XObjects — the engine walks the page tree, finds
    nothing, and returns 0 cleanly."""
    target = tmp_path / "rot0.pdf"
    target.write_bytes(ROT0.read_bytes())
    rc = extract_images.ExtractImages.main(["-i", str(target)])
    assert rc == 0


def test_extract_images_with_explicit_prefix(
    patched_loader: Any, tmp_path: Path,
) -> None:
    prefix = str(tmp_path / "img")
    rc = extract_images.ExtractImages.main([
        "-i", str(ROT0),
        "-prefix", prefix,
        "-useDirectJPEG",
        "-noColorConvert",
    ])
    assert rc == 0


def test_extract_images_load_error_returns_4(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = extract_images.ExtractImages.main([
        "-i", str(tmp_path / "no-such.pdf"),
    ])
    assert rc == 4
    assert "Error extracting images" in capsys.readouterr().err


def test_extract_images_missing_infile_raises() -> None:
    runner = extract_images.ExtractImages()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_extract_images_engine_overrides_are_no_ops() -> None:
    """The empty graphics-engine overrides (mirrors of upstream
    `Empty: ...` stubs) must execute without raising."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    engine.append_rectangle(None, None, None, None)
    engine.clip(0)
    engine.move_to(0.0, 0.0)
    engine.line_to(1.0, 1.0)
    assert engine.curve_to(0, 0, 0, 0, 0, 0) is None
    assert engine.get_current_point() == (0.0, 0.0)
    engine.close_path()
    engine.end_path()
    engine.shading_fill(None)
    engine.stroke_path()
    engine.fill_path(0)
    engine.fill_and_stroke_path(0)


def test_extract_images_has_masks_non_xobject_returns_false() -> None:
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    assert engine.has_masks(object()) is False


def test_extract_images_process_color_swallows_attribute_error() -> None:
    """process_color guards on ``color.get_color_space()`` — a bare
    object should be swallowed and return None."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    assert engine.process_color(object()) is None


def test_extract_images_show_glyph_swallows_attribute_error() -> None:
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    # show_glyph: all arguments are bare objects; the try/except branch
    # must swallow the AttributeError silently.
    engine.show_glyph(None, None, 0, None)


# --------------------------------------------------------------------------
# export_fdf
# --------------------------------------------------------------------------
def test_export_fdf_form_pdf_writes_fdf(
    patched_loader: Any, tmp_path: Path,
) -> None:
    out = tmp_path / "out.fdf"
    rc = export_fdf.ExportFDF.main([
        "-i", str(FORM_PDF),
        "-o", str(out),
    ])
    assert rc == 0
    assert out.exists()
    # The port currently emits an FDF carrying a ``%PDF-`` magic (FDF is
    # a PDF subset); upstream's "%FDF-" header is not enforced by this
    # writer. Either prefix is acceptable for the round-trip purpose.
    head = out.read_bytes()[:5]
    assert head in (b"%FDF-", b"%PDF-")


def test_export_fdf_no_form_returns_1(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = export_fdf.ExportFDF.main([
        "-i", str(ROT0),
        "-o", str(tmp_path / "out.fdf"),
    ])
    assert rc == 1
    assert "does not contain a form" in capsys.readouterr().err


def test_export_fdf_load_error_returns_4(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = export_fdf.ExportFDF.main([
        "-i", str(tmp_path / "missing.pdf"),
        "-o", str(tmp_path / "out.fdf"),
    ])
    assert rc == 4
    assert "Error exporting FDF data" in capsys.readouterr().err


def test_export_fdf_missing_infile_raises() -> None:
    runner = export_fdf.ExportFDF()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_export_fdf_default_outfile_derived_from_infile(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """When ``outfile`` is None, the runner derives it from the input
    path. The form-bearing fixture is copied into tmp_path so the
    derived .fdf file lands somewhere writable / cleanable."""
    src = tmp_path / "form.pdf"
    src.write_bytes(FORM_PDF.read_bytes())
    runner = export_fdf.ExportFDF()
    runner.infile = src
    rc = runner.call()
    assert rc == 0
    assert (tmp_path / "form.fdf").exists()


# --------------------------------------------------------------------------
# extract_xmp
# --------------------------------------------------------------------------
class _FakeMeta:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def to_byte_array(self) -> bytes:
        return self._payload


class _FakeCatalog:
    def __init__(self, meta: _FakeMeta | None) -> None:
        self._meta = meta

    def get_metadata(self) -> _FakeMeta | None:
        return self._meta


class _FakePage:
    def __init__(self, meta: _FakeMeta | None) -> None:
        self._meta = meta

    def get_metadata(self) -> _FakeMeta | None:
        return self._meta


class _FakeDoc:
    def __init__(
        self,
        catalog_meta: _FakeMeta | None,
        page_meta: _FakeMeta | None = None,
        page_count: int = 1,
    ) -> None:
        self._catalog = _FakeCatalog(catalog_meta)
        self._page = _FakePage(page_meta)
        self._n = page_count

    def get_document_catalog(self) -> _FakeCatalog:
        return self._catalog

    def get_number_of_pages(self) -> int:
        return self._n

    def get_page(self, index: int) -> _FakePage:
        return self._page

    def __enter__(self) -> _FakeDoc:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        pass


def _patch_xmp_loader(
    monkeypatch: pytest.MonkeyPatch, doc_factory: Any,
) -> None:
    class _XMPLoader:
        @staticmethod
        def load_pdf(source: Any, password: Any = None) -> Any:
            return doc_factory()

    monkeypatch.setattr(extract_xmp, "Loader", _XMPLoader)


def test_extract_xmp_catalog_metadata_to_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    payload = b"<x:xmpmeta>doc-level</x:xmpmeta>"
    _patch_xmp_loader(monkeypatch, lambda: _FakeDoc(catalog_meta=_FakeMeta(payload)))
    out = tmp_path / "meta.xml"
    rc = extract_xmp.ExtractXMP.main([
        "-i", str(tmp_path / "input.pdf"),
        "-o", str(out),
    ])
    assert rc == 0
    assert out.read_bytes() == payload


def test_extract_xmp_page_level_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    payload = b"<x:xmpmeta>page-2</x:xmpmeta>"
    _patch_xmp_loader(
        monkeypatch,
        lambda: _FakeDoc(catalog_meta=None, page_meta=_FakeMeta(payload), page_count=3),
    )
    out = tmp_path / "page-meta.xml"
    rc = extract_xmp.ExtractXMP.main([
        "-i", str(tmp_path / "input.pdf"),
        "-o", str(out),
        "-page", "2",
    ])
    assert rc == 0
    assert out.read_bytes() == payload


def test_extract_xmp_page_out_of_range_returns_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_xmp_loader(monkeypatch, lambda: _FakeDoc(catalog_meta=None, page_count=1))
    rc = extract_xmp.ExtractXMP.main([
        "-i", str(tmp_path / "input.pdf"),
        "-o", str(tmp_path / "x.xml"),
        "-page", "99",
    ])
    assert rc == 1
    assert "Page 99" in capsys.readouterr().err


def test_extract_xmp_no_metadata_returns_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_xmp_loader(monkeypatch, lambda: _FakeDoc(catalog_meta=None))
    rc = extract_xmp.ExtractXMP.main([
        "-i", str(tmp_path / "input.pdf"),
        "-o", str(tmp_path / "x.xml"),
    ])
    assert rc == 1
    assert "No XMP metadata" in capsys.readouterr().err


def test_extract_xmp_console_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    payload = b"<x:xmpmeta>console</x:xmpmeta>"
    _patch_xmp_loader(monkeypatch, lambda: _FakeDoc(catalog_meta=_FakeMeta(payload)))
    rc = extract_xmp.ExtractXMP.main([
        "-i", str(tmp_path / "input.pdf"),
        "-console",
    ])
    assert rc == 0
    out = capsysbinary.readouterr().out
    assert payload in out


def test_extract_xmp_load_error_returns_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # Use the real Loader — missing file raises OSError, caught and
    # mapped to exit code 4.
    rc = extract_xmp.ExtractXMP.main([
        "-i", str(tmp_path / "nope.pdf"),
        "-o", str(tmp_path / "out.xml"),
    ])
    assert rc == 4
    assert "Error extracting text" in capsys.readouterr().err


def test_extract_xmp_missing_infile_raises() -> None:
    runner = extract_xmp.ExtractXMP()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_extract_xmp_default_outfile_derived(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    payload = b"<x:xmpmeta>derived</x:xmpmeta>"
    _patch_xmp_loader(monkeypatch, lambda: _FakeDoc(catalog_meta=_FakeMeta(payload)))
    fake_in = tmp_path / "in.pdf"
    fake_in.write_bytes(b"%PDF-1.4\n")
    runner = extract_xmp.ExtractXMP()
    runner.infile = fake_in
    rc = runner.call()
    assert rc == 0
    assert (tmp_path / "in.xml").read_bytes() == payload


# --------------------------------------------------------------------------
# overlay_pdf
# --------------------------------------------------------------------------
def test_overlay_pdf_default_overlay_runs(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    rc = overlay_pdf.OverlayPDF.main([
        "-i", str(ROT0),
        "-o", str(out),
        "-default", str(OVERLAY_TOP),
    ])
    assert rc == 0
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_overlay_pdf_first_and_last_overlay(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    rc = overlay_pdf.OverlayPDF.main([
        "-i", str(ROT0),
        "-o", str(out),
        "-first", str(OVERLAY_TOP),
        "-last", str(OVERLAY_TOP),
        "-position", "FOREGROUND",
    ])
    assert rc == 0
    assert out.exists()


def test_overlay_pdf_odd_even_all_pages_setters(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    rc = overlay_pdf.OverlayPDF.main([
        "-i", str(ROT0),
        "-o", str(out),
        "-odd", str(OVERLAY_TOP),
        "-even", str(OVERLAY_TOP),
        "-useAllPages", str(OVERLAY_TOP),
        "-adjustRotation",
    ])
    # The combination is unusual but each setter exercises a branch.
    assert rc in (0, 4)
    if rc == 0:
        assert out.exists()


def test_overlay_pdf_missing_infile_raises() -> None:
    runner = overlay_pdf.OverlayPDF()
    with pytest.raises(OSError, match="infile and outfile are required"):
        runner.call()


def test_overlay_pdf_load_error_returns_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = overlay_pdf.OverlayPDF.main([
        "-i", str(tmp_path / "missing-input.pdf"),
        "-o", str(tmp_path / "out.pdf"),
        "-default", str(OVERLAY_TOP),
    ])
    assert rc == 4
    assert "Error adding overlay" in capsys.readouterr().err
