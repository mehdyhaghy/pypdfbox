"""PDFBOX-6203 (wave 1603): split output has no xref gaps from imported keys.

Upstream ``Splitter.createNewDocument`` resets the imported object keys on
the destination catalog (``resetImportedObjectKeys``) so that catalog-level
entries copied from the source — ``/ViewerPreferences``, ``/Lang``,
``/MarkInfo``, ``/Metadata`` — do not drag their source object numbers into
the chunk. Without the reset, a classic (uncompressed) save honours the
parser-stamped key of the imported dictionary and emits it under its old
high object number, leaving a gap in the chunk's cross-reference table
(observed here as xref numbers ``[1, 2, 3, 4, 50]`` with ``/Size 51``).

The source fixture is built by hand so the imported ``/ViewerPreferences``
dictionary deterministically carries a high object number (50) in a
five-object document.
"""

from __future__ import annotations

import io
import shutil
import subprocess

import pytest

from pypdfbox import PDDocument
from pypdfbox.loader import Loader
from pypdfbox.multipdf import Splitter
from pypdfbox.pdfwriter.compress import CompressParameters


def _build_sparse_source() -> bytes:
    """A 2-page PDF whose catalog references /ViewerPreferences as object
    50 (xref written as two subsections: 0-4 and 50)."""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R /ViewerPreferences 50 0 R /Lang (en-US) >>",
        2: b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> >>",
        4: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> >>",
        50: b"<< /DisplayDocTitle true >>",
    }
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = {}
    for num, body in objects.items():
        offsets[num] = out.tell()
        out.write(b"%d 0 obj\n%s\nendobj\n" % (num, body))
    startxref = out.tell()
    out.write(b"xref\n0 5\n0000000000 65535 f \n")
    for num in (1, 2, 3, 4):
        out.write(b"%010d 00000 n \n" % offsets[num])
    out.write(b"50 1\n%010d 00000 n \n" % offsets[50])
    out.write(
        b"trailer\n<< /Size 51 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % startxref
    )
    return out.getvalue()


def _split_first_chunk_bytes(compress: CompressParameters | None = None) -> bytes:
    src = PDDocument(Loader.load_pdf(_build_sparse_source()))
    try:
        chunks = Splitter().split(src)
        try:
            out = io.BytesIO()
            if compress is None:
                chunks[0].save(out)
            else:
                chunks[0].save(out, compress_parameters=compress)
            return out.getvalue()
        finally:
            for chunk in chunks:
                chunk.close()
    finally:
        src.close()


def _xref_object_numbers(data: bytes) -> tuple[list[int], int]:
    doc = PDDocument(Loader.load_pdf(data))
    try:
        numbers = sorted(k.object_number for k in doc.get_document().get_xref_table())
        size = doc.get_document().get_trailer().get_int("Size")
        return numbers, size
    finally:
        doc.close()


# ---------- create_new_document resets the imported keys ----------


def test_split_chunk_catalog_imports_are_unkeyed() -> None:
    src = PDDocument(Loader.load_pdf(_build_sparse_source()))
    try:
        src_prefs = (
            src.get_document_catalog().get_cos_object().get_dictionary_object(
                "ViewerPreferences"
            )
        )
        assert src_prefs.get_key() is not None  # parser stamped (50, 0)
        chunks = Splitter().split(src)
        try:
            chunk_catalog = chunks[0].get_document_catalog().get_cos_object()
            prefs = chunk_catalog.get_dictionary_object("ViewerPreferences")
            assert prefs is not None
            assert prefs.get_key() is None
        finally:
            for chunk in chunks:
                chunk.close()
    finally:
        src.close()


# ---------- saved chunks have gap-free, contiguous xrefs ----------


def test_uncompressed_split_chunk_xref_is_contiguous() -> None:
    """Regression shape: without the reset the classic save reuses the
    imported (50, 0) key — xref [1, 2, 3, 4, 50], /Size 51."""
    data = _split_first_chunk_bytes(CompressParameters.NO_COMPRESSION)
    numbers, size = _xref_object_numbers(data)
    assert numbers == list(range(1, len(numbers) + 1))
    assert size == len(numbers) + 1
    # The imported entries themselves survived the renumbering.
    assert b"/ViewerPreferences" in data
    assert b"/Lang" in data


def test_default_compressed_split_chunk_xref_is_contiguous() -> None:
    data = _split_first_chunk_bytes()
    numbers, size = _xref_object_numbers(data)
    assert numbers == list(range(1, len(numbers) + 1))
    assert size == len(numbers) + 1


def test_split_chunk_reparses_with_viewer_preferences_intact() -> None:
    data = _split_first_chunk_bytes(CompressParameters.NO_COMPRESSION)
    doc = PDDocument(Loader.load_pdf(data))
    try:
        catalog = doc.get_document_catalog().get_cos_object()
        prefs = catalog.get_dictionary_object("ViewerPreferences")
        assert prefs is not None
        assert prefs.get_boolean("DisplayDocTitle") is True
        assert doc.get_number_of_pages() == 1
    finally:
        doc.close()


@pytest.mark.skipif(shutil.which("qpdf") is None, reason="qpdf not installed")
def test_split_chunk_passes_qpdf_check(tmp_path) -> None:
    chunk_path = tmp_path / "chunk1.pdf"
    chunk_path.write_bytes(_split_first_chunk_bytes(CompressParameters.NO_COMPRESSION))
    result = subprocess.run(
        ["qpdf", "--check", str(chunk_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
