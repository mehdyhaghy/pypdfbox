"""Wave 1286.2 — exercise the four metadata / text / image examples.

Verifies that ``extract_metadata``, ``add_metadata_from_doc_info``,
``show_text_with_positioning``, and ``rubber_stamp_with_image`` drive
their public entry points end-to-end against in-memory PDFs without
requiring external fixtures.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.examples.pdmodel.add_metadata_from_doc_info import (
    AddMetadataFromDocInfo,
)
from pypdfbox.examples.pdmodel.extract_metadata import ExtractMetadata
from pypdfbox.examples.pdmodel.rubber_stamp_with_image import RubberStampWithImage
from pypdfbox.examples.pdmodel.show_text_with_positioning import (
    ShowTextWithPositioning,
)
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _make_blank_pdf(path: Path) -> None:
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(path)


def _make_pdf_with_info(path: Path) -> None:
    with PDDocument() as doc:
        doc.add_page(PDPage())
        info = doc.get_document_information()
        info.set_title("Hello Title")
        info.set_author("Author Name")
        info.set_subject("The subject")
        info.set_keywords("kw1; kw2")
        info.set_creator("creator-tool")
        info.set_producer("pypdfbox")
        doc.save(path)


# ---------------------------------------------------------------------------
# extract_metadata
# ---------------------------------------------------------------------------


def test_extract_metadata_usage_exits_non_zero(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        ExtractMetadata.main([])
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Usage" in err


def test_extract_metadata_falls_back_to_document_information(
    tmp_path: Path, capsys,
) -> None:
    pdf = tmp_path / "info.pdf"
    _make_pdf_with_info(pdf)
    ExtractMetadata.main([str(pdf)])
    out = capsys.readouterr().out
    assert "Hello Title" in out
    assert "Author Name" in out
    assert "creator-tool" in out


def test_extract_metadata_reads_xmp(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src.pdf"
    stamped = tmp_path / "stamped.pdf"
    _make_pdf_with_info(src)
    AddMetadataFromDocInfo.main([str(src), str(stamped)])
    ExtractMetadata.main([str(stamped)])
    out = capsys.readouterr().out
    assert "Hello Title" in out
    assert "The subject" in out  # description from /Subject
    assert "PDFBox" in out  # default creator
    assert "kw1; kw2" in out
    assert "pypdfbox" in out  # producer
    assert "creator-tool" in out


def test_extract_metadata_display_skips_none(capsys) -> None:
    ExtractMetadata.display("Title:", None)
    assert capsys.readouterr().out == ""


def test_extract_metadata_list_string_none_short_circuits(capsys) -> None:
    ExtractMetadata.list_string("Creators:", None)
    assert capsys.readouterr().out == ""


def test_extract_metadata_format_handles_datetime() -> None:
    import datetime

    dt = datetime.date(2025, 5, 1)
    assert ExtractMetadata.format(dt) == "May 01, 2025"


# ---------------------------------------------------------------------------
# add_metadata_from_doc_info
# ---------------------------------------------------------------------------


def test_add_metadata_from_doc_info_usage(tmp_path: Path, capsys) -> None:
    AddMetadataFromDocInfo.main([])
    err = capsys.readouterr().err
    assert "Usage" in err


def test_add_metadata_from_doc_info_writes_xmp(tmp_path: Path) -> None:
    src = tmp_path / "src.pdf"
    dst = tmp_path / "dst.pdf"
    _make_pdf_with_info(src)
    AddMetadataFromDocInfo.main([str(src), str(dst)])
    assert dst.exists()
    with Loader.load_pdf(dst) as cos_doc:
        doc = PDDocument(cos_doc)
        catalog = doc.get_document_catalog()
        metadata = catalog.get_metadata()
        assert metadata is not None
        xmp_bytes = metadata.export_xmp_metadata()
        # Header bits from the inline DOM template.
        assert b"rdf:RDF" in xmp_bytes
        # Schema content survives the round-trip.
        assert b"Hello Title" in xmp_bytes
        assert b"PDFBox" in xmp_bytes
        assert b"kw1; kw2" in xmp_bytes


# ---------------------------------------------------------------------------
# show_text_with_positioning
# ---------------------------------------------------------------------------


def test_show_text_with_positioning_writes_pdf(tmp_path: Path) -> None:
    out = tmp_path / "justify.pdf"
    ShowTextWithPositioning.do_it("Hello World, this is a test!", str(out))
    assert out.exists()
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        assert doc.get_number_of_pages() == 1


def test_show_text_with_positioning_main_default_outfile(
    tmp_path: Path, monkeypatch,
) -> None:
    # The static main() writes ``justify-example.pdf`` in the cwd. Chdir into
    # ``tmp_path`` so the side-effect file lands somewhere disposable.
    monkeypatch.chdir(tmp_path)
    ShowTextWithPositioning.main(None)
    assert (tmp_path / "justify-example.pdf").exists()


# ---------------------------------------------------------------------------
# rubber_stamp_with_image
# ---------------------------------------------------------------------------


def _png_bytes() -> bytes:
    bio = io.BytesIO()
    Image.new("RGB", (100, 100), (255, 0, 0)).save(bio, format="PNG")
    return bio.getvalue()


def test_rubber_stamp_with_image_appends_annotation(tmp_path: Path) -> None:
    src = tmp_path / "src.pdf"
    dst = tmp_path / "dst.pdf"
    _make_blank_pdf(src)
    RubberStampWithImage().do_it_bytes(str(src), str(dst), _png_bytes())
    assert dst.exists()
    with Loader.load_pdf(dst) as cos_doc:
        doc = PDDocument(cos_doc)
        page = doc.get_page(0)
        annotations = page.get_annotations()
        assert len(annotations) == 1
        annotation = annotations[0]
        assert annotation.get_subtype() == "Stamp"


def test_rubber_stamp_with_image_do_it_with_file_path(tmp_path: Path) -> None:
    src = tmp_path / "src.pdf"
    dst = tmp_path / "dst.pdf"
    img = tmp_path / "stamp.png"
    _make_blank_pdf(src)
    img.write_bytes(_png_bytes())
    RubberStampWithImage().do_it([str(src), str(dst), str(img)])
    assert dst.exists()


def test_rubber_stamp_with_image_usage(tmp_path: Path, capsys) -> None:
    # Wrong arity prints usage and exits without raising.
    RubberStampWithImage().do_it([])
    err = capsys.readouterr().err
    assert "Usage" in err


def test_rubber_stamp_with_image_main_short_args(capsys) -> None:
    RubberStampWithImage.main([])
    assert "Usage" in capsys.readouterr().err
