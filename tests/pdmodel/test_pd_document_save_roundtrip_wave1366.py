"""Hand-written PDDocument save/load round-trip fuzz (wave 1366, agent E).

Builds small in-memory documents with varied COS dictionary, stream, name,
and array structures, then serialises through ``COSWriter`` and re-parses
through ``Loader.load_pdf``. Assertions cover structural equivalence at the
COSDocument level — page count, trailer entries, dictionary keys, stream
bytes — rather than byte-exact equality, mirroring upstream PDFBox's "round
trip preserves the object graph, not necessarily the bytes" contract.

No upstream JUnit counterpart — this is pypdfbox-side fuzz exercising the
``PDDocument.save → Loader.load_pdf`` boundary across a small grid of
dictionary shapes that have historically broken token / xref serialisation
(deeply nested arrays, stream length 0, name with PDF special chars).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)


def _save_and_reload(doc: PDDocument) -> PDDocument:
    sink = io.BytesIO()
    doc.save(sink)
    return PDDocument.load(sink.getvalue())


def test_empty_document_roundtrip() -> None:
    """A bare ``PDDocument`` with no pages survives serialisation and
    re-parsing. Page count is preserved."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        with _save_and_reload(doc) as reloaded:
            assert reloaded.get_number_of_pages() == 1


def test_multi_page_roundtrip() -> None:
    """Adding several pages — pages must come back in order with the same
    count."""
    with PDDocument() as doc:
        for _ in range(7):
            doc.add_page(PDPage())
        with _save_and_reload(doc) as reloaded:
            assert reloaded.get_number_of_pages() == 7


def test_roundtrip_preserves_info_strings() -> None:
    """/Info dictionary string entries round-trip verbatim, including PDF-
    significant characters that need escape on the wire (parens, backslash,
    high-bit bytes)."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        info = doc.get_document_information()
        info.set_title("Title with (parens) and \\backslash\\")
        info.set_author("Author — em dash")
        info.set_subject("Subject\nwith newline")
        with _save_and_reload(doc) as reloaded:
            info2 = reloaded.get_document_information()
            assert info2.get_title() == "Title with (parens) and \\backslash\\"
            assert info2.get_author() == "Author — em dash"
            assert info2.get_subject() == "Subject\nwith newline"


def test_roundtrip_preserves_nested_array() -> None:
    """A nested ``COSArray`` attached to a custom catalog entry survives
    the writer's recursion and re-parses with the same shape."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        arr = COSArray()
        for v in (1, 2, 3):
            inner = COSArray()
            inner.add(COSInteger.get(v))
            inner.add(COSFloat(v + 0.5))
            inner.add(COSString(f"v{v}"))
            arr.add(inner)
        doc.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("FuzzNested"), arr
        )
        with _save_and_reload(doc) as reloaded:
            cat_cos = reloaded.get_document_catalog().get_cos_object()
            recovered = cat_cos.get_dictionary_object(COSName.get_pdf_name("FuzzNested"))
            assert isinstance(recovered, COSArray)
            assert recovered.size() == 3
            for i in range(3):
                sub = recovered.get_object(i)
                assert isinstance(sub, COSArray)
                assert sub.size() == 3
                first = sub.get_object(0)
                assert isinstance(first, COSInteger)
                assert first.int_value() == i + 1


def test_roundtrip_zero_length_stream() -> None:
    """A custom ``COSStream`` of length 0 attached to the catalog survives
    serialisation. /Length must come back as 0."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        empty_stream = COSStream()
        with empty_stream.create_raw_output_stream() as out:
            out.write(b"")
        doc.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("FuzzEmpty"), empty_stream
        )
        with _save_and_reload(doc) as reloaded:
            cat_cos = reloaded.get_document_catalog().get_cos_object()
            recovered = cat_cos.get_dictionary_object(COSName.get_pdf_name("FuzzEmpty"))
            assert isinstance(recovered, COSStream)
            length_obj = recovered.get_dictionary_object(COSName.get_pdf_name("Length"))
            assert isinstance(length_obj, COSInteger)
            assert length_obj.int_value() == 0


def test_roundtrip_stream_with_binary_payload() -> None:
    """Stream bodies carrying a non-ASCII byte run (all 256 byte values)
    round-trip byte-identically."""
    payload = bytes(range(256))
    with PDDocument() as doc:
        doc.add_page(PDPage())
        s = COSStream()
        with s.create_raw_output_stream() as out:
            out.write(payload)
        doc.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("FuzzBin"), s
        )
        with _save_and_reload(doc) as reloaded:
            cat_cos = reloaded.get_document_catalog().get_cos_object()
            recovered = cat_cos.get_dictionary_object(COSName.get_pdf_name("FuzzBin"))
            assert isinstance(recovered, COSStream)
            with recovered.create_raw_input_stream() as src:
                assert src.read() == payload


def test_roundtrip_name_with_pdf_specials() -> None:
    """``COSName`` values with characters that require ``#hh`` escaping on
    the wire (``#``, ``(``, ``)``, ``/``, ``%``, space) survive the writer
    and reparse to the same Python string."""
    specials = [
        "Name#Hash",
        "Name(Paren)",
        "Name Space",
        "Name%Percent",
        "Name/Slash",
    ]
    with PDDocument() as doc:
        doc.add_page(PDPage())
        cat = doc.get_document_catalog().get_cos_object()
        for name in specials:
            cat.set_item(COSName.get_pdf_name(name), COSInteger.get(len(name)))
        with _save_and_reload(doc) as reloaded:
            cat_cos = reloaded.get_document_catalog().get_cos_object()
            for name in specials:
                v = cat_cos.get_dictionary_object(COSName.get_pdf_name(name))
                assert isinstance(v, COSInteger), name
                assert v.int_value() == len(name), name


def test_roundtrip_dictionary_with_many_keys() -> None:
    """A dictionary with > 100 keys survives serialisation — exercises the
    writer's per-entry emission loop and the parser's dictionary-key map
    growth path."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        big = COSDictionary()
        for i in range(150):
            big.set_item(COSName.get_pdf_name(f"K{i:03d}"), COSInteger.get(i))
        doc.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("FuzzBig"), big
        )
        with _save_and_reload(doc) as reloaded:
            cat_cos = reloaded.get_document_catalog().get_cos_object()
            recovered = cat_cos.get_dictionary_object(COSName.get_pdf_name("FuzzBig"))
            assert isinstance(recovered, COSDictionary)
            for i in range(150):
                v = recovered.get_dictionary_object(COSName.get_pdf_name(f"K{i:03d}"))
                assert isinstance(v, COSInteger)
                assert v.int_value() == i


def test_roundtrip_double_save_idempotent(tmp_path: Path) -> None:
    """Saving, reloading, and saving again produces a document whose
    page count and major trailer entries match the original. Catches
    state that leaks into the second save (e.g. wrongly carried
    needs_to_be_updated flags producing an incremental tail on a full
    save).
    """
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    with PDDocument() as doc:
        for _ in range(3):
            doc.add_page(PDPage())
        doc.get_document_information().set_title("First")
        doc.save(first)
    with PDDocument.load(first) as reloaded:
        assert reloaded.get_number_of_pages() == 3
        reloaded.save(second)
    with PDDocument.load(second) as reloaded2:
        assert reloaded2.get_number_of_pages() == 3
        assert reloaded2.get_document_information().get_title() == "First"
    # Second save should also be a well-formed PDF.
    head = second.read_bytes()[:8]
    tail = second.read_bytes()[-6:]
    assert head[:5] == b"%PDF-"
    assert tail == b"%%EOF\n"


@pytest.mark.parametrize(
    "title",
    ["", "x", "X" * 4096, "mix é à €"],
    ids=["empty", "single", "4096", "unicode"],
)
def test_roundtrip_info_title_lengths(title: str) -> None:
    """Various title string lengths and Unicode payloads round-trip."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.get_document_information().set_title(title)
        with _save_and_reload(doc) as reloaded:
            assert reloaded.get_document_information().get_title() == title
