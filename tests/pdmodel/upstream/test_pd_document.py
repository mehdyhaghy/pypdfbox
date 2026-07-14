"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocument.java

Upstream baseline: PDFBox 3.0 (commit on the 3.0 branch).

Translation conventions follow the project's "Test Porting Conventions".
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter.compress import CompressParameters

# Mirrors upstream's ``static private final File TESTRESULTSDIR``.
# Pytest's ``tmp_path`` fixture replaces it cleanly.


def test_save_load_stream(tmp_path: Path) -> None:
    """``testSaveLoadStream``."""
    baos = io.BytesIO()
    with PDDocument() as document:
        document.add_page(PDPage())
        # Upstream passes ``CompressParameters.NO_COMPRESSION`` here —
        # the default save compresses (ObjStm + xref stream) and would
        # bump the header to 1.6.
        document.save(baos, CompressParameters.NO_COMPRESSION)

    pdf = baos.getvalue()
    assert len(pdf) > 200
    assert pdf[0:8] == b"%PDF-1.4"
    # Upstream asserts the trailer ends with the literal "%%EOF\n";
    # COSWriter emits that exact terminator.
    assert pdf.endswith(b"%%EOF\n")

    with PDDocument.load(pdf) as load_doc:
        assert load_doc.get_number_of_pages() == 1


def test_save_load_file(tmp_path: Path) -> None:
    """``testSaveLoadFile``."""
    target = tmp_path / "pddocument-saveloadfile.pdf"

    with PDDocument() as document:
        document.add_page(PDPage())
        # Upstream passes ``CompressParameters.NO_COMPRESSION`` (the
        # default compressed save would emit a 1.6 header).
        document.save(target, CompressParameters.NO_COMPRESSION)

    assert target.stat().st_size > 200

    pdf = target.read_bytes()
    assert len(pdf) > 200
    assert pdf[0:8] == b"%PDF-1.4"
    assert pdf.endswith(b"%%EOF\n")

    with PDDocument.load(target) as load_doc:
        assert load_doc.get_number_of_pages() == 1


# ``testVersions`` — the upstream test asserts the catalog round-trips
# version "1.6" after auto-bump on save. That auto-bump heuristic lives
# inside upstream's ``PDDocument.save()`` (it raises the catalog version
# to 1.6 if any newer feature was used). pypdfbox cluster #1 mirrors only
# the explicit ``set_version`` path; the implicit auto-bump lands when
# fonts / encryption / signing arrive in clusters #4 / #10.
def test_versions_explicit_only() -> None:
    """``testVersions`` — partial port (explicit set_version only;
    auto-bump-on-save lives in later clusters)."""
    with PDDocument() as document:
        assert document.get_version() == 1.4
        assert document.get_document().get_version() == 1.4
        assert document.get_document_catalog().get_version() == "1.4"
        document.get_document().set_version(1.3)
        document.get_document_catalog().set_version(None)  # type: ignore[arg-type]
        assert document.get_version() == 1.3
        assert document.get_document().get_version() == 1.3
        assert document.get_document_catalog().get_version() is None

    with PDDocument() as document:
        document.set_version(1.3)  # downgrade ignored
        assert document.get_version() == 1.4
        assert document.get_document().get_version() == 1.4
        assert document.get_document_catalog().get_version() == "1.4"

        document.set_version(1.5)
        assert document.get_version() == 1.5
        # Header stays at 1.4 — upstream only updates the catalog when
        # bumping to 1.5+.
        assert document.get_document().get_version() == 1.4
        assert document.get_document_catalog().get_version() == "1.5"


def test_delete_bad_file(tmp_path: Path) -> None:
    """``testDeleteBadFile``."""
    f = tmp_path / "testDeleteBadFile.pdf"
    f.write_text("<script language='JavaScript'>", encoding="utf-8")
    with pytest.raises(OSError):
        Loader.load_pdf(f)
    # Upstream then deletes the file — equivalent here, with pathlib.
    f.unlink()
    assert not f.exists()


def test_delete_good_file(tmp_path: Path) -> None:
    """``testDeleteGoodFile``."""
    f = tmp_path / "testDeleteGoodFile.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(f)

    Loader.load_pdf(f).close()

    f.unlink()
    assert not f.exists()


# Skipped: ``testSaveArabicLocale`` — Java-specific (Locale.setDefault
# affects Java's NumberFormat). Python's ``str(float)`` is locale-
# independent so the underlying bug cannot occur.
