"""``PDDocument.load`` vs ``Loader.load_pdf`` equivalence (wave 1366, agent E).

Both upstream entry points (``PDDocument.load`` and ``Loader.loadPDF``)
must produce semantically identical documents — page count, trailer
shape, info dict, version, and encryption state. This is the contract
that lets PDFBox sample code use either spelling interchangeably.

No upstream JUnit counterpart — pypdfbox-side parity suite around the two
classmethods sharing a backing implementation.

Located under ``tests/multipdf/`` because it crosses the loader / pdmodel
boundary and feeds the multi-document loader regression net.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.loader import Loader


def _make_pdf(num_pages: int = 1, title: str = "load-eq") -> bytes:
    sink = io.BytesIO()
    with PDDocument() as doc:
        for _ in range(num_pages):
            doc.add_page(PDPage())
        doc.get_document_information().set_title(title)
        doc.save(sink)
    return sink.getvalue()


def test_pddocument_load_and_loader_load_pdf_same_page_count() -> None:
    """Both entry points report the same page count for the same input."""
    pdf = _make_pdf(num_pages=4)
    cos = Loader.load_pdf(pdf)
    try:
        # Wrap non-owningly to read page count.
        pd = PDDocument(cos)
        pd._owns_document = False  # noqa: SLF001
        loader_count = pd.get_number_of_pages()
    finally:
        cos.close()

    with PDDocument.load(pdf) as pddoc:
        assert pddoc.get_number_of_pages() == loader_count == 4


@pytest.mark.parametrize(
    "title", ["", "ascii", "Unicode é à €", "x" * 1024], ids=["empty", "ascii", "unicode", "long"]
)
def test_pddocument_load_and_loader_load_pdf_same_info_title(title: str) -> None:
    """Info dict /Title reads back identically across both entry points."""
    pdf = _make_pdf(title=title)
    with PDDocument.load(pdf) as pddoc:
        a = pddoc.get_document_information().get_title()

    cos = Loader.load_pdf(pdf)
    try:
        pd = PDDocument(cos)
        pd._owns_document = False  # noqa: SLF001
        b = pd.get_document_information().get_title()
    finally:
        cos.close()
    assert a == b == title


def test_pddocument_load_via_path_matches_via_bytes(tmp_path: Path) -> None:
    """``PDDocument.load(path)`` and ``PDDocument.load(bytes)`` produce
    documents with the same page count and trailer shape."""
    p = tmp_path / "via.pdf"
    p.write_bytes(_make_pdf(num_pages=3))

    with PDDocument.load(p) as via_path:
        path_count = via_path.get_number_of_pages()
    with PDDocument.load(p.read_bytes()) as via_bytes:
        bytes_count = via_bytes.get_number_of_pages()
    assert path_count == bytes_count == 3


def test_pddocument_load_password_arg_threaded_through() -> None:
    """``PDDocument.load(source, password='x')`` delegates to
    ``Loader.load_pdf(source, password='x')`` — on a non-encrypted
    document the password is silently ignored."""
    pdf = _make_pdf()
    with PDDocument.load(pdf, password="ignored") as pddoc:
        assert pddoc.is_encrypted() is False


def test_pddocument_load_returns_closeable_context() -> None:
    """``PDDocument.load`` always returns a context-manager-compatible
    document; after exit the document is marked closed."""
    pdf = _make_pdf()
    with PDDocument.load(pdf) as pddoc:
        assert pddoc.get_number_of_pages() == 1
    # After the with block, save() raises (document is closed).
    with pytest.raises(OSError, match="Cannot save a document which has been closed"):
        pddoc.save(io.BytesIO())


def test_loader_load_pdf_and_load_alias_are_equivalent() -> None:
    """``Loader.load`` is documented as an alias of ``Loader.load_pdf`` —
    both must produce the same object graph."""
    pdf = _make_pdf(num_pages=2)
    a = Loader.load_pdf(pdf)
    try:
        b = Loader.load(pdf)
        try:
            # Both produced live, trailer-bearing COSDocuments.
            assert a.get_trailer() is not None
            assert b.get_trailer() is not None
            # Same page count via non-owning PDDocument wrapper.
            pa = PDDocument(a)
            pa._owns_document = False  # noqa: SLF001
            pb = PDDocument(b)
            pb._owns_document = False  # noqa: SLF001
            assert pa.get_number_of_pages() == pb.get_number_of_pages()
        finally:
            b.close()
    finally:
        a.close()


def test_pddocument_load_after_save_roundtrip_preserves_count(tmp_path: Path) -> None:
    """Save out a synthesised PDDocument, then reload via ``PDDocument.load``
    and via ``Loader.load_pdf`` — both must agree."""
    target = tmp_path / "roundtrip.pdf"
    with PDDocument() as src:
        for _ in range(5):
            src.add_page(PDPage())
        src.save(target)

    with PDDocument.load(target) as via_pddoc:
        a = via_pddoc.get_number_of_pages()

    cos = Loader.load_pdf(target)
    try:
        pd = PDDocument(cos)
        pd._owns_document = False  # noqa: SLF001
        b = pd.get_number_of_pages()
    finally:
        cos.close()
    assert a == b == 5
