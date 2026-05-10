"""End-to-end integration tests exercising the full pypdfbox pipeline.

Each test builds a synthetic ``PDDocument`` in memory, drives it through
the writer (and optional encryption / xref-stream / object-stream paths),
reloads the bytes through ``Loader.load_pdf``, and verifies the result
round-trips cleanly. These cover the seams between modules — anything
that exercises ``cos`` + ``pdfwriter`` + ``pdfparser`` + ``pdmodel`` +
``contentstream`` + ``text`` together belongs here.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text import PDFTextStripper

# ---------------------------------------------------------------- helpers


def _helvetica() -> PDType1Font:
    """Bare-bones Type1 Helvetica wrapper — Standard 14, no /ToUnicode.

    Sufficient for the lite stripper which falls back to the COSString's
    Latin-1 decode when no /ToUnicode CMap is present."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    return font


def _add_text_page(doc: PDDocument, text: str, *, x: float = 50.0, y: float = 700.0) -> PDPage:
    """Append a Letter-sized page rendering ``text`` at (x, y) in Helvetica 12."""
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    font = _helvetica()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(x, y)
        cs.show_text(text)
        cs.end_text()
    return page


def _save_to_bytes(doc: PDDocument) -> bytes:
    sink = io.BytesIO()
    doc.save(sink)
    return sink.getvalue()


def _save_with_writer(doc: PDDocument, **writer_kwargs: object) -> bytes:
    """Save via a directly-constructed COSWriter so callers can flip
    xref_stream / object_stream / encryption knobs that ``PDDocument.save``
    doesn't surface yet."""
    sink = io.BytesIO()
    with COSWriter(sink, **writer_kwargs) as writer:  # type: ignore[arg-type]
        writer.write(doc)
    return sink.getvalue()


# ---------------------------------------------------------------- 1. roundtrip


def test_synthetic_build_save_reload_roundtrip() -> None:
    """Build a 2-page document with content streams + info, save to
    bytes, reload via ``Loader.load_pdf``, and verify the page count,
    info dictionary, and extractable text all survive the round trip."""
    doc = PDDocument()
    _add_text_page(doc, "Page 1")
    _add_text_page(doc, "Page 2")

    info = doc.get_document_information()
    info.set_title("Integration Test")
    info.set_author("pypdfbox")

    saved = _save_to_bytes(doc)
    doc.close()

    cos_doc = Loader.load_pdf(saved)
    try:
        reloaded = PDDocument(cos_doc)
        # Ownership stays with the loader-returned COSDocument; closing
        # ``reloaded`` would otherwise double-close it.
        reloaded._owns_document = False  # noqa: SLF001
        try:
            assert reloaded.get_number_of_pages() == 2

            reloaded_info = reloaded.get_document_information()
            assert reloaded_info.get_title() == "Integration Test"
            assert reloaded_info.get_author() == "pypdfbox"

            extracted = PDFTextStripper().get_text(reloaded)
            assert "Page 1" in extracted
            assert "Page 2" in extracted
        finally:
            reloaded.close()
    finally:
        cos_doc.close()


# ---------------------------------------------------------------- 2. encryption


def test_build_encrypt_save_reload_with_password() -> None:
    """Protect a freshly-built doc with a user password, save, reload
    once without the password (to confirm ``is_encrypted`` is True), then
    again with the password (to confirm the contents are readable)."""
    pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    doc = PDDocument()
    _add_text_page(doc, "Encrypted body")

    doc.protect(StandardProtectionPolicy(owner_password="o", user_password="u"))
    saved = _save_to_bytes(doc)
    doc.close()

    # Pre-decrypt: parser sees /Encrypt in the trailer and flags it.
    encrypted = Loader.load_pdf(saved)
    try:
        assert encrypted.is_encrypted() is True
    finally:
        encrypted.close()

    # Post-decrypt: open with the user password and confirm content reads.
    with PDDocument.load(saved, password="u") as reloaded:
        assert reloaded.get_number_of_pages() == 1
        # Pull the decoded /Contents bytes through the security handler.
        page = reloaded.get_pages()[0]
        contents = page.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Contents")
        )
        if isinstance(contents, COSStream):
            with contents.create_input_stream() as src:
                body = src.read()
        elif isinstance(contents, COSArray):
            chunks: list[bytes] = []
            for i in range(contents.size()):
                entry = contents.get_object(i)
                if isinstance(entry, COSStream):
                    with entry.create_input_stream() as cs_src:
                        chunks.append(cs_src.read())
            body = b"\n".join(chunks)
        else:
            body = b""
        assert b"Encrypted body" in body


# ---------------------------------------------------------------- 3. modern PDF


def test_build_save_with_xref_and_object_streams_reload() -> None:
    """Save through ``COSWriter(xref_stream=True, object_stream=True)``
    so the xref-stream parser + ObjStm loader both have to fire on
    reload. The reloaded doc must expose the same page count + info."""
    doc = PDDocument()
    _add_text_page(doc, "Modern PDF page A")
    _add_text_page(doc, "Modern PDF page B")
    doc.get_document_information().set_title("Modern")

    saved = _save_with_writer(doc, xref_stream=True, object_stream=True)
    doc.close()

    # Sanity: a /Type /XRef stream MUST appear, and at least one /ObjStm.
    assert b"/XRef" in saved
    assert b"/ObjStm" in saved

    cos_doc = Loader.load_pdf(saved)
    try:
        reloaded = PDDocument(cos_doc)
        reloaded._owns_document = False  # noqa: SLF001
        try:
            assert reloaded.get_number_of_pages() == 2
            assert reloaded.get_document_information().get_title() == "Modern"
            # Force materialisation of every page dict so the ObjStm loader
            # path runs end-to-end (a partial parse wouldn't surface here).
            for page in reloaded.get_pages():
                assert page.get_cos_object() is not None
        finally:
            reloaded.close()
    finally:
        cos_doc.close()


# ---------------------------------------------------------------- 4. text


def test_text_extraction_multiple_runs_preserves_separators() -> None:
    """A single page with two ``Tj`` runs at different baselines should
    produce a line-separated result; two runs on the same baseline far
    apart in x produce a word-separated result."""
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    font = _helvetica()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        # Line 1
        cs.new_line_at_offset(50, 700)
        cs.show_text("Hello")
        # Line 2 — different y, same font; lite heuristic emits a line
        # separator when y differs by > 0.5 * font_size.
        cs.new_line_at_offset(0, -40)
        cs.show_text("World")
        cs.end_text()

    extracted = PDFTextStripper().get_text(doc)
    assert "Hello" in extracted
    assert "World" in extracted
    # The two runs sit on different lines — confirm the line separator
    # made it into the joined output (default = "\n").
    hello_idx = extracted.index("Hello")
    world_idx = extracted.index("World")
    between = extracted[hello_idx + len("Hello") : world_idx]
    assert "\n" in between


# ---------------------------------------------------------------- 5. import


def test_cross_document_import_page_preserves_contents() -> None:
    """A 3-page source doc imported page-by-page into a fresh dest doc
    yields a 3-page dest with the same content-stream bodies."""
    src = PDDocument()
    _add_text_page(src, "alpha")
    _add_text_page(src, "beta")
    _add_text_page(src, "gamma")

    dst = PDDocument()
    for src_page in list(src.get_pages()):
        dst.import_page(src_page)

    assert dst.get_number_of_pages() == 3

    # Per-page raw /Contents bytes should match what the source emitted.
    for i in range(3):
        src_body = src.get_pages()[i].get_contents()
        dst_body = dst.get_pages()[i].get_contents()
        assert src_body == dst_body
        assert src_body  # non-empty

    src.close()
    dst.close()


def test_cross_document_import_then_save_reload_text_extracts() -> None:
    """Import preserves enough context that the destination doc, once
    saved + reloaded, still produces extractable text for the imported
    pages."""
    src = PDDocument()
    _add_text_page(src, "imported alpha")
    _add_text_page(src, "imported beta")

    dst = PDDocument()
    for src_page in list(src.get_pages()):
        dst.import_page(src_page)
    src.close()

    saved = _save_to_bytes(dst)
    dst.close()

    cos_doc = Loader.load_pdf(saved)
    try:
        reloaded = PDDocument(cos_doc)
        reloaded._owns_document = False  # noqa: SLF001
        try:
            assert reloaded.get_number_of_pages() == 2
            text = PDFTextStripper().get_text(reloaded)
            assert "imported alpha" in text
            assert "imported beta" in text
        finally:
            reloaded.close()
    finally:
        cos_doc.close()


# ---------------------------------------------------------------- 6. hybrid


def test_encrypt_and_xref_stream_combined_roundtrip() -> None:
    """Hybrid: ``protect()`` the document, save with ``xref_stream=True``,
    then reload with the password and confirm the text still extracts.

    Exercises the writer-side encryption pipeline + the parser's xref-
    stream loader + the security handler in a single end-to-end pass.
    The bootstrap is non-trivial because the xref stream itself is what
    tells the parser where to find the /Encrypt object — see CHANGES.md
    for the writer/parser contract that makes this round-trip safe.
    """
    pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    doc = PDDocument()
    _add_text_page(doc, "hybrid xref+encrypt")

    doc.protect(StandardProtectionPolicy(owner_password="o", user_password="u"))
    saved = _save_with_writer(doc, xref_stream=True)
    doc.close()

    # The xref stream must be present; cleartext must not be — this much
    # is purely the writer's job, and it works today.
    assert b"/XRef" in saved
    assert b"hybrid xref+encrypt" not in saved

    with PDDocument.load(saved, password="u") as reloaded:
        assert reloaded.is_encrypted() is True
        assert reloaded.get_number_of_pages() == 1
        text = PDFTextStripper().get_text(reloaded)
        assert "hybrid xref+encrypt" in text
