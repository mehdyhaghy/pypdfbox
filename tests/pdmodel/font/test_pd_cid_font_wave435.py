from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


class _MappedCIDFont(PDCIDFont):
    def get_subtype(self) -> str:
        return "CIDFontType2"

    def code_to_cid(self, code: int) -> int:
        return int(code) + 10


def _ints(*values: int) -> COSArray:
    return COSArray([COSInteger.get(value) for value in values])


def test_w_parser_skips_malformed_entries_and_keeps_valid_forms() -> None:
    font = _MappedCIDFont()
    widths = COSArray(
        [
            COSName.get_pdf_name("bad"),
            COSInteger.get(10),
            COSArray(
                [
                    COSInteger.get(100),
                    COSName.get_pdf_name("skip"),
                    COSInteger.get(300),
                ]
            ),
            COSInteger.get(20),
            COSInteger.get(22),
            COSInteger.get(500),
            COSInteger.get(30),
            COSInteger.get(31),
            COSName.get_pdf_name("badWidth"),
            COSInteger.get(99),
        ]
    )

    font.set_w(widths)

    assert font.get_widths() == {
        10: 100.0,
        12: 300.0,
        20: 500.0,
        21: 500.0,
        22: 500.0,
    }
    assert font.get_width(0) == 100.0
    assert font.has_explicit_width(2) is True
    assert font.has_explicit_width(3) is False


def test_width_cache_can_be_cleared_after_in_place_w_mutation() -> None:
    font = _MappedCIDFont()
    widths = COSArray([COSInteger.get(1), COSArray([COSInteger.get(200)])])
    font.set_w(widths)
    assert font.get_glyph_width(1) == 200.0

    widths.get_object(1).add(COSInteger.get(400))  # type: ignore[union-attr]
    assert font.get_glyph_width(2) == 1000.0

    font.clear_widths_cache()
    assert font.get_glyph_width(2) == 400.0


def test_w2_parser_handles_malformed_entries_and_large_ranges_compactly() -> None:
    font = _MappedCIDFont()
    font.set_dw(600)
    font.set_dw2(COSArray([COSName.get_pdf_name("badY"), COSInteger.get(-900)]))
    font.set_w2(
        COSArray(
            [
                COSName.get_pdf_name("bad"),
                COSInteger.get(2),
                COSArray(
                    [
                        COSInteger.get(700),
                        COSInteger.get(100),
                        COSInteger.get(800),
                        COSName.get_pdf_name("badTriple"),
                        COSInteger.get(1),
                        COSInteger.get(2),
                        COSInteger.get(710),
                        COSInteger.get(110),
                        COSInteger.get(810),
                    ]
                ),
                COSInteger.get(10),
                COSInteger.get(12),
                COSInteger.get(900),
                COSInteger.get(200),
                COSInteger.get(880),
                COSInteger.get(1000),
                COSInteger.get(6000),
                COSInteger.get(-1200),
                COSInteger.get(300),
                COSInteger.get(900),
                COSInteger.get(50),
                COSInteger.get(49),
                COSInteger.get(1),
                COSInteger.get(2),
                COSInteger.get(3),
            ]
        )
    )

    parsed = font.get_widths2()

    assert parsed[2] == (700.0, 100.0, 800.0)
    assert parsed[4] == (710.0, 110.0, 810.0)
    assert parsed[10] == (900.0, 200.0, 880.0)
    assert 1000 not in parsed
    assert font.get_height(5000) == -1200.0
    assert font.get_position_vector(5000) == (300.0, 900.0)
    assert font.get_position_vector(99) == (300.0, 880.0)
    assert font.get_vertical_displacement_vector_y(89) == -900.0


def test_cid_to_gid_map_accessors_stream_identity_and_type_errors() -> None:
    font = _MappedCIDFont()
    stream = COSStream()
    stream.set_data(b"\x00\x01\x01\x00\xff")

    font.set_cid_to_gid_map(stream)

    assert font.get_cid_to_gid_map() is stream
    assert font.has_cid_to_gid_map_stream() is True
    assert font.is_identity_cid_to_gid_map() is False
    assert font.read_cid_to_gid_map() == [1, 256]

    font.set_cid_to_gid_map("Identity")
    assert font.get_cid_to_gid_map() == "Identity"
    assert font.has_cid_to_gid_map_stream() is False
    assert font.is_identity_cid_to_gid_map() is True
    assert font.read_cid_to_gid_map() is None

    with pytest.raises(TypeError):
        font.set_cid_to_gid_map(123)  # type: ignore[arg-type]


def test_program_detection_reads_first_available_descriptor_stream() -> None:
    descriptor = PDFontDescriptor()
    font_file = COSStream()
    font_file.set_data(b"font-file")
    font_file2 = COSStream()
    font_file2.set_data(b"font-file-2")
    font_file3 = COSStream()
    font_file3.set_data(b"font-file-3")
    descriptor.set_font_file(font_file)
    descriptor.set_font_file2(font_file2)
    descriptor.set_font_file3(font_file3)
    font = _MappedCIDFont()
    font.set_font_descriptor(descriptor)

    assert font.is_embedded() is True
    assert font.get_program() == b"font-file"


def test_descriptor_bbox_returns_none_for_short_or_malformed_arrays() -> None:
    descriptor = PDFontDescriptor()
    descriptor.set_font_b_box(COSArray([COSInteger.get(0), COSInteger.get(1)]))
    font = _MappedCIDFont()
    font.set_font_descriptor(descriptor)
    assert font.get_bounding_box() is None

    descriptor.set_font_b_box(
        COSArray(
            [
                COSFloat(0),
                COSFloat(1),
                COSName.get_pdf_name("bad"),
                COSFloat(3),
            ]
        )
    )
    assert font.get_bounding_box() is None
