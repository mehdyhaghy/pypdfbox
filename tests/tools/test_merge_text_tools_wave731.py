from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.tools import texttopdf, writedecodedstream


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
