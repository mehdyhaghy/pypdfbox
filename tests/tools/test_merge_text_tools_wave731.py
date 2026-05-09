from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull, COSStream, COSString
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.tools import merge, texttopdf, writedecodedstream


def test_wave731_merge_remap_page_links_skips_non_dictionary_annots() -> None:
    src_page = COSDictionary()
    new_page = COSDictionary()
    src_link = COSDictionary()
    src_link.set_name("Subtype", "Link")

    src_page.set_item("Annots", COSArray([COSString("not-a-dict"), src_link]))
    new_page.set_item("Annots", COSArray([COSDictionary(), COSString("not-a-dict")]))

    merge._remap_page_links(src_page, new_page, {})  # noqa: SLF001

    new_annots = new_page.get_dictionary_object("Annots")
    assert isinstance(new_annots, COSArray)
    assert isinstance(new_annots.get_object(0), COSDictionary)
    assert isinstance(new_annots.get_object(1), COSString)


def test_wave731_merge_supported_names_merges_legacy_dests_and_skips_null() -> None:
    src = PDDocument()
    target = PDDocument()
    try:
        src_page = PDPage()
        src.add_page(src_page)
        imported_page = COSDictionary()

        legacy = COSDictionary()
        legacy.set_item("intro", COSArray([src_page.get_cos_object()]))
        legacy.set_item("missing", COSNull.NULL)
        src.get_document_catalog().get_cos_object().set_item("Dests", legacy)

        target_names = merge._ensure_names_dictionary(  # noqa: SLF001
            target.get_document_catalog().get_cos_object()
        )
        target_tree = COSDictionary()
        target_tree.set_item("Names", COSArray([COSString("intro"), COSString("old")]))
        target_names.set_item("Dests", target_tree)

        renamed = merge._merge_supported_names(  # noqa: SLF001
            src,
            target,
            {("id", id(src_page.get_cos_object())): imported_page},
        )

        assert renamed == {"intro": "intro#2"}
        entries = merge._collect_name_tree_entries(target_tree)  # noqa: SLF001
        assert [name for name, _value in entries] == ["intro", "intro#2"]
        assert entries[1][1].get_object(0) is imported_page
    finally:
        src.close()
        target.close()


def test_wave731_merge_collect_page_object_keys_ignores_malformed_nodes() -> None:
    keys: list[tuple[str, int, int] | None] = []

    merge._collect_page_object_keys(COSString("bad"), None, keys, set())  # noqa: SLF001

    pages_without_kids = COSDictionary()
    pages_without_kids.set_name("Type", "Pages")
    merge._collect_page_object_keys(  # noqa: SLF001
        pages_without_kids,
        ("obj", 1, 0),
        keys,
        set(),
    )

    assert keys == []


def test_wave731_texttopdf_font_bbox_descriptor_and_fallback_paths() -> None:
    font = PDFont()
    descriptor = PDFontDescriptor()
    descriptor.set_font_bounding_box(PDRectangle(0.0, -5.0, 10.0, 15.0))
    font.set_font_descriptor(descriptor)

    assert texttopdf._font_bbox_height(font) == pytest.approx(20.0)  # noqa: SLF001
    assert texttopdf._font_bbox_height(PDFont()) == pytest.approx(1000.0)  # noqa: SLF001


def test_wave731_texttopdf_empty_string_width_is_zero() -> None:
    font = PDFontFactory.create_default_font()

    assert texttopdf._string_width_units(font, "") == 0.0  # noqa: SLF001


def test_wave731_texttopdf_lookahead_trims_form_feed_before_width_check() -> None:
    doc = PDDocument()
    try:
        texttopdf.create_pdf_from_text(
            doc,
            ["alpha beta\fgamma"],
            font=PDFontFactory.create_default_font(),
        )

        assert doc.get_number_of_pages() == 2
    finally:
        doc.close()


def test_wave731_writedecodedstream_skip_images_leaves_stream_encoded() -> None:
    stream = COSStream()
    stream.set_item("Type", COSName.get_pdf_name("XObject"))
    stream.set_item("Subtype", COSName.get_pdf_name("Image"))
    stream.set_data(b"image bytes", filters=COSName.FLATE_DECODE)

    writedecodedstream._process_stream(stream, skip_images=True)  # noqa: SLF001

    assert stream.get_filter_list() == [COSName.FLATE_DECODE]


def test_wave731_writedecodedstream_empty_stream_is_left_unchanged() -> None:
    stream = COSStream()
    stream.set_item("Filter", COSName.FLATE_DECODE)

    writedecodedstream._process_stream(stream, skip_images=False)  # noqa: SLF001

    assert stream.get_filter_list() == [COSName.FLATE_DECODE]


def test_wave731_writedecodedstream_decode_error_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = COSStream()
    stream.set_data(b"plain")
    stream.set_item("Filter", COSName.get_pdf_name("Broken"))

    def _broken_input_stream(self: COSStream) -> object:
        raise OSError("cannot decode")

    monkeypatch.setattr(COSStream, "create_input_stream", _broken_input_stream)

    writedecodedstream._process_stream(stream, skip_images=False)  # noqa: SLF001

    assert stream.get_filter_list() == [COSName.get_pdf_name("Broken")]


def test_wave731_write_decoded_removes_security_when_document_is_encrypted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class _CosDoc:
        def get_objects(self) -> list[object]:
            return []

        def set_xref_stream(self, value: bool) -> None:
            calls.append(f"xref={value}")

    class _Doc:
        def is_encrypted(self) -> bool:
            return True

        def set_all_security_to_be_removed(self, value: bool) -> None:
            calls.append(f"security={value}")

        def get_document(self) -> _CosDoc:
            return _CosDoc()

        def save(self, output_path: str) -> None:
            calls.append(f"save={output_path}")

        def close(self) -> None:
            calls.append("close")

    monkeypatch.setattr(writedecodedstream.PDDocument, "load", lambda *a, **k: _Doc())

    writedecodedstream.write_decoded("input.pdf", "output.pdf", password="secret")

    assert calls == ["security=True", "xref=False", "save=output.pdf", "close"]


def test_wave731_writedecodedstream_run_reraises_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "src.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    def _raise_oserror(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(writedecodedstream, "write_decoded", _raise_oserror)

    with pytest.raises(OSError, match="disk full"):
        writedecodedstream.run(
            argparse.Namespace(input=str(src), output=None, password=None, skip_images=False)
        )
