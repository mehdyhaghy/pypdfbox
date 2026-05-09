from __future__ import annotations

from typing import cast

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject, COSStream
from pypdfbox.multipdf import Overlay
from pypdfbox.multipdf.overlay import _LayoutPage
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _blank_doc(width: float = 400.0, height: float = 300.0) -> PDDocument:
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle.from_width_height(width, height)))
    return doc


def _stream(doc: PDDocument, body: bytes = b"") -> COSStream:
    stream = COSStream(doc.get_document().scratch_file)
    with stream.create_output_stream() as out:
        out.write(body)
    return stream


def test_create_content_stream_list_resolves_nested_indirect_streams() -> None:
    doc = _blank_doc()
    first = _stream(doc, b"first")
    second = _stream(doc, b"second")
    nested = COSArray(
        [
            COSObject(1, resolved=first),
            COSArray([COSObject(2, resolved=second)]),
        ]
    )

    try:
        streams = Overlay._create_content_stream_list(nested)  # noqa: SLF001
    finally:
        doc.close()

    assert streams == [first, second]


def test_create_content_stream_list_rejects_unknown_content_shape() -> None:
    with pytest.raises(OSError, match="Unknown content type: COSDictionary"):
        Overlay._create_content_stream_list(COSDictionary())  # noqa: SLF001


def test_add_original_content_rejects_unknown_content_shape() -> None:
    target = COSArray()

    with pytest.raises(OSError, match="Unknown content type: COSDictionary"):
        Overlay._add_original_content(COSDictionary(), target)  # noqa: SLF001

    assert len(target) == 0


def test_rotated_overlay_stream_uses_swapped_media_box_for_centering() -> None:
    base = _blank_doc(width=400.0, height=300.0)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    layout = _LayoutPage(
        PDRectangle.from_width_height(100.0, 50.0),
        _stream(base),
        COSDictionary(),
        90,
    )

    try:
        stream = overlay._create_overlay_stream(  # noqa: SLF001
            base.get_page(0),
            layout,
            COSName.get_pdf_name("OL0"),
        )
        with stream.create_input_stream() as src:
            body = src.read().decode("latin-1")
    finally:
        base.close()

    assert "1.0 0.0 0.0 1.0 175.0 100.0" in body
    assert " cm" in body
    assert "/OL0 Do Q" in body


def test_rotation_matrix_handles_all_quadrant_rotations() -> None:
    doc = _blank_doc()
    layout = _LayoutPage(
        PDRectangle.from_width_height(100.0, 50.0),
        _stream(doc),
        COSDictionary(),
        0,
    )

    try:
        layout.overlay_rotation = 90
        assert Overlay._rotation_matrix(layout) == [0.0, -1.0, 1.0, 0.0, 0.0, 100.0]  # noqa: SLF001
        layout.overlay_rotation = 180
        assert Overlay._rotation_matrix(layout) == [-1.0, 0.0, 0.0, -1.0, 100.0, 50.0]  # noqa: SLF001
        layout.overlay_rotation = 270
        assert Overlay._rotation_matrix(layout) == [0.0, 1.0, -1.0, 0.0, 50.0, 0.0]  # noqa: SLF001
    finally:
        doc.close()


def test_overlay_documents_skips_none_and_keeps_setter_specific_overlay() -> None:
    base = _blank_doc()
    specific = _blank_doc(width=25.0, height=25.0)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_specific_page_overlay_pdf({1: specific})

    try:
        result = overlay.overlay_documents({1: cast(PDDocument, None)})
    finally:
        specific.close()
        base.close()

    assert result is base
    assert overlay._specific_page_overlay_layout[1].overlay_media_box.get_width() == 25.0  # noqa: SLF001
