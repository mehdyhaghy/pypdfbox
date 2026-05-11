"""Hand-written tests covering the smaller class ports in
``pypdfbox.tools`` (Decompress, Export, Import, ExtractXMP, OverlayPDF,
PDFBox, Version, Decrypt, Encrypt, WriteDecodedDoc, PrintPDF, PDFToImage,
ImageToPDF, TextToPDF, ExtractText, ExtractImages)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.tools.decompress_objectstreams import DecompressObjectstreams
from pypdfbox.tools.decrypt_tool import Decrypt
from pypdfbox.tools.encrypt_tool import Encrypt
from pypdfbox.tools.export_fdf import ExportFDF
from pypdfbox.tools.export_xfdf import ExportXFDF
from pypdfbox.tools.extract_images import ExtractImages, ImageGraphicsEngine
from pypdfbox.tools.extract_text import (
    AngleCollector,
    ExtractText,
    FilteredText2Markdown,
    FilteredTextStripper,
    NullWriter,
    get_angle,
)
from pypdfbox.tools.extract_xmp import ExtractXMP
from pypdfbox.tools.image_to_pdf import ImageToPDF
from pypdfbox.tools.import_fdf import ImportFDF
from pypdfbox.tools.import_xfdf import ImportXFDF
from pypdfbox.tools.overlay_pdf import OverlayPDF
from pypdfbox.tools.pdf_box import PDFBox
from pypdfbox.tools.pdf_text2_html import FontState as HtmlFontState
from pypdfbox.tools.pdf_text2_html import PDFText2HTML
from pypdfbox.tools.pdf_text2_markdown import FontState as MdFontState
from pypdfbox.tools.pdf_text2_markdown import PDFText2Markdown
from pypdfbox.tools.pdf_to_image import PDFToImage
from pypdfbox.tools.print_pdf import Duplex, PrintPDF
from pypdfbox.tools.text_to_pdf import PageSizes, TextToPDF
from pypdfbox.tools.version_tool import Version
from pypdfbox.tools.write_decoded_doc import WriteDecodedDoc


@pytest.mark.parametrize("cls", [
    DecompressObjectstreams, Decrypt, Encrypt, ExportFDF, ExportXFDF,
    ExtractImages, ExtractText, ExtractXMP, ImageToPDF, ImportFDF,
    ImportXFDF, OverlayPDF, PDFToImage, PrintPDF, TextToPDF,
    WriteDecodedDoc,
])
def test_construct(cls: type) -> None:
    inst = cls()
    assert inst is not None


def test_version_outputs(capsys: pytest.CaptureFixture[str]) -> None:
    v = Version()
    rc = v.call()
    captured = capsys.readouterr()
    assert rc == 0
    assert "pypdfbox" in captured.out or "unknown" in captured.out


def test_pdfbox_dispatch_unknown(capsys: pytest.CaptureFixture[str]) -> None:
    rc = PDFBox.main(["not-a-real-command"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Unknown" in err


def test_pdfbox_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    rc = PDFBox.main([])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Subcommand" in err


def test_pdfbox_version_dispatch() -> None:
    rc = PDFBox.main(["version"])
    assert rc == 0


def test_duplex_to_sides() -> None:
    assert Duplex.SIMPLEX.to_sides() == "ONE_SIDED"
    assert Duplex.DUPLEX.to_sides() == "DUPLEX"
    assert Duplex.TUMBLE.to_sides() == "TUMBLE"
    assert Duplex.DOCUMENT.to_sides() is None


def test_page_sizes_lookup() -> None:
    assert PageSizes.LETTER.get_page_size() is not None
    assert PageSizes.A4.get_page_size() is not None
    assert PageSizes["A0"].get_page_size() is not None


def test_print_pdf_helpers_are_stubs() -> None:
    p = PrintPDF()
    assert p.get_trays_from_print_service(None) == []
    assert p.get_media_sizes_from_print_service(None) == []
    # call() with no input configured fails fast with exit code 4
    # (mirrors upstream's IOException -> exit 4 contract).
    assert p.call() == 4


def test_write_decoded_doc_calc_filename() -> None:
    assert WriteDecodedDoc.calculate_output_filename("a.pdf") == "a_unc.pdf"
    assert WriteDecodedDoc.calculate_output_filename("a.PDF") == "a_unc.pdf"
    assert WriteDecodedDoc.calculate_output_filename("a") == "a_unc.pdf"


def test_image_to_pdf_create_rectangle() -> None:
    assert ImageToPDF.create_rectangle("A4") is not None
    # unknown sizes fall through to LETTER
    fallback = ImageToPDF.create_rectangle("XYZ")
    letter = ImageToPDF.create_rectangle("LETTER")
    assert fallback is letter


def test_null_writer_is_silent() -> None:
    w = NullWriter()
    w.write("hello")
    w.write(b"world")
    w.flush()
    w.close()


def test_get_angle_handles_attribute_error() -> None:
    class _Bogus:
        def get_text_matrix(self) -> None:
            raise AttributeError("no")

    assert get_angle(_Bogus()) == 0


def test_html_and_md_font_state_round_trip() -> None:
    html = HtmlFontState()
    # Empty push returns empty
    assert html.push("", []) == ""
    assert html.clear() == ""
    md = MdFontState()
    assert md.push("", []) == ""
    assert md.clear() == ""


def test_text_to_pdf_setters_validate() -> None:
    t = TextToPDF()
    with pytest.raises(ValueError):
        t.set_line_spacing(0)


def test_image_graphics_engine_runs_no_page() -> None:
    # Sanity: a constructed engine with no page returns cleanly.
    outer = ExtractImages()
    engine = ImageGraphicsEngine(page=None, outer=outer)
    # run() with no page should be a no-op
    engine.run()


def test_extract_pages_helpers() -> None:
    # AngleCollector / FilteredTextStripper / FilteredText2Markdown all
    # subclass the stripper without surprises.
    a = AngleCollector()
    f = FilteredTextStripper()
    m = FilteredText2Markdown()
    assert a.get_angles() == set()
    assert f is not None
    assert m is not None


def test_extract_text_main_parses(tmp_path: Path) -> None:
    rc = ExtractText.main([
        "-i", str(tmp_path / "missing.pdf"),
        "-o", str(tmp_path / "out.txt"),
    ])
    # OSError on load → 4
    assert rc == 4


def test_pdf_text2_html_constructs_subclass() -> None:
    h = PDFText2HTML()
    assert h.get_paragraph_start() == "<p>"


def test_pdf_text2_markdown_constructs_subclass() -> None:
    m = PDFText2Markdown()
    ls = m.get_line_separator()
    assert m.get_paragraph_start() == ls
