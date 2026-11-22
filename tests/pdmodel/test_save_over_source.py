"""Saving a document over the file it was loaded from must not corrupt it.

Upstream PDFBox truncates the source while still reading it lazily, which
wipes any file larger than the read buffer. pypdfbox writes to a temp file
beside the source and swaps it in after the save succeeds.
"""

import os
import sys
from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation


def _big_pdf(path: Path, pages: int = 40) -> None:
    """A PDF well over the 128 KiB read buffer, with incompressible streams."""
    rnd = __import__("random").Random(1234)
    with PDDocument() as doc:
        for _ in range(pages):
            page = PDPage()
            doc.add_page(page)
            stream = doc.get_document().create_cos_stream()
            with stream.create_raw_output_stream() as out:
                out.write(bytes(rnd.getrandbits(8) for _ in range(8192)))
            page.get_cos_object().set_item(COSName.get_pdf_name("Junk"), stream)
        doc.save(path)
    assert path.stat().st_size > 256 * 1024


def _leftover_temps(directory: Path) -> list[str]:
    return [p.name for p in directory.iterdir() if p.name.startswith(".pypdfbox-")]


def test_save_over_source_keeps_a_valid_file(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    _big_pdf(src)
    copy = tmp_path / "copy.pdf"
    with PDDocument.load(src) as doc:
        doc.save(copy)
    with PDDocument.load(src) as doc:
        doc.save(src)
    assert src.read_bytes() == copy.read_bytes()
    with PDDocument.load(src) as doc:
        assert doc.get_number_of_pages() == 40
    assert _leftover_temps(tmp_path) == []


def test_save_over_source_twice_from_same_document(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    _big_pdf(src)
    with PDDocument.load(src) as doc:
        doc.save(src)
        doc.save(tmp_path / "again.pdf")
    with PDDocument.load(tmp_path / "again.pdf") as doc:
        assert doc.get_number_of_pages() == 40


def test_save_incremental_over_source(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    _big_pdf(src)
    original = src.read_bytes()
    with PDDocument.load(src) as doc:
        info = PDDocumentInformation()
        info.set_title("updated")
        doc.set_document_information(info)
        info.get_cos_object().set_needs_to_be_updated(True)
        doc.get_document().get_trailer().set_needs_to_be_updated(True)
        doc.save_incremental(src)
    data = src.read_bytes()
    assert data.startswith(original)
    assert len(data) > len(original)
    with PDDocument.load(src) as doc:
        assert doc.get_document_information().get_title() == "updated"
    assert _leftover_temps(tmp_path) == []


def test_failed_save_over_source_leaves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "doc.pdf"
    _big_pdf(src)
    original = src.read_bytes()

    def boom(self: COSWriter, *args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    with PDDocument.load(src) as doc:
        monkeypatch.setattr(COSWriter, "write", boom)
        with pytest.raises(OSError, match="disk full"):
            doc.save(src)
    assert src.read_bytes() == original
    assert _leftover_temps(tmp_path) == []


def test_failed_save_to_other_path_unchanged_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A different target is opened directly, as before (no temp file).
    src = tmp_path / "doc.pdf"
    _big_pdf(src)
    out = tmp_path / "out.pdf"

    def boom(self: COSWriter, *args: object, **kwargs: object) -> None:
        assert _leftover_temps(tmp_path) == []
        raise OSError("disk full")

    with PDDocument.load(src) as doc:
        monkeypatch.setattr(COSWriter, "write", boom)
        with pytest.raises(OSError):
            doc.save(out)
    assert out.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_save_over_source_keeps_permissions(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    _big_pdf(src)
    os.chmod(src, 0o640)
    with PDDocument.load(src) as doc:
        doc.save(src)
    assert (src.stat().st_mode & 0o777) == 0o640


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges")
def test_save_over_source_through_symlink_keeps_link(tmp_path: Path) -> None:
    real = tmp_path / "real.pdf"
    _big_pdf(real)
    link = tmp_path / "link.pdf"
    link.symlink_to(real)
    with PDDocument.load(link) as doc:
        doc.save(link)
    assert link.is_symlink()
    with PDDocument.load(real) as doc:
        assert doc.get_number_of_pages() == 40


def test_save_over_in_memory_loaded_file_writes_directly(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    _big_pdf(src)
    with PDDocument.load(src.read_bytes()) as doc:
        doc.save(src)
    with PDDocument.load(src) as doc:
        assert doc.get_number_of_pages() == 40
