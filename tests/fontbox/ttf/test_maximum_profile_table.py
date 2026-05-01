from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.maximum_profile_table import MaximumProfileTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _build_v05(num_glyphs: int = 229) -> bytes:
    # Version 0.5 = 0x00005000 (whole=0, frac=0x5000) → 0.3125 ... actually
    # CFF maxp uses 0x00005000 meaning 0 + 0x5000/0x10000 = 0.3125. Real
    # OpenType says 0.5 corresponds to 0x00005000? PDFBox tests against
    # version >= 1.0 only — the v0.5 path is just "version + numGlyphs".
    # We use 0x00005000 here which decodes to 0.3125 (under 1.0 threshold).
    return struct.pack(">hHH", 0, 0x5000, num_glyphs)


def _build_v10(
    *,
    num_glyphs: int = 500,
    max_points: int = 100,
    max_contours: int = 10,
    max_composite_points: int = 200,
    max_composite_contours: int = 20,
    max_zones: int = 2,
    max_twilight_points: int = 16,
    max_storage: int = 32,
    max_function_defs: int = 64,
    max_instruction_defs: int = 0,
    max_stack_elements: int = 256,
    max_size_of_instructions: int = 1024,
    max_component_elements: int = 5,
    max_component_depth: int = 3,
) -> bytes:
    return struct.pack(
        ">hHHHHHHHHHHHHHHH",
        1,  # version whole
        0,  # version frac
        num_glyphs,
        max_points,
        max_contours,
        max_composite_points,
        max_composite_contours,
        max_zones,
        max_twilight_points,
        max_storage,
        max_function_defs,
        max_instruction_defs,
        max_stack_elements,
        max_size_of_instructions,
        max_component_elements,
        max_component_depth,
    )


def test_v05_payload_size_is_six_bytes() -> None:
    assert len(_build_v05()) == 6


def test_v10_payload_size_is_thirty_two_bytes() -> None:
    assert len(_build_v10()) == 32


def test_v05_reads_only_version_and_numglyphs() -> None:
    table = MaximumProfileTable()
    table.read(None, MemoryTTFDataStream(_build_v05(num_glyphs=42)))  # type: ignore[arg-type]
    assert table.get_initialized() is True
    assert table.get_num_glyphs() == 42
    # Version 0.x → tt-only fields stay at their defaults.
    assert table.get_max_points() == 0
    assert table.get_max_contours() == 0
    assert table.get_max_component_depth() == 0


def test_v10_reads_full_record() -> None:
    table = MaximumProfileTable()
    table.read(None, MemoryTTFDataStream(_build_v10()))  # type: ignore[arg-type]
    assert table.get_initialized() is True
    assert table.get_version() == 1.0
    assert table.get_num_glyphs() == 500
    assert table.get_max_points() == 100
    assert table.get_max_contours() == 10
    assert table.get_max_composite_points() == 200
    assert table.get_max_composite_contours() == 20
    assert table.get_max_zones() == 2
    assert table.get_max_twilight_points() == 16
    assert table.get_max_storage() == 32
    assert table.get_max_function_defs() == 64
    assert table.get_max_instruction_defs() == 0
    assert table.get_max_stack_elements() == 256
    assert table.get_max_size_of_instructions() == 1024
    assert table.get_max_component_elements() == 5
    assert table.get_max_component_depth() == 3


def test_zero_component_depth_promoted_to_one_pdfbox_6105() -> None:
    # Per PDFBOX-6105 the parser bumps a zero maxComponentDepth to 1.
    raw = _build_v10(max_component_depth=0)
    table = MaximumProfileTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_max_component_depth() == 1


def test_tag_constant() -> None:
    assert MaximumProfileTable.TAG == "maxp"


def test_defaults_before_read() -> None:
    table = MaximumProfileTable()
    assert table.get_initialized() is False
    assert table.get_num_glyphs() == 0
    assert table.get_max_points() == 0


def test_set_num_glyphs_round_trip() -> None:
    table = MaximumProfileTable()
    table.set_num_glyphs(321)
    assert table.get_num_glyphs() == 321


def test_set_version_round_trip() -> None:
    table = MaximumProfileTable()
    table.set_version(1.0)
    assert table.get_version() == 1.0


def test_setters_round_trip_all_max_fields() -> None:
    # Mirrors the upstream Java setter surface — every numeric maxXxx getter
    # also has a setter pair (PDFBox MaximumProfileTable).
    table = MaximumProfileTable()
    table.set_max_points(150)
    table.set_max_contours(15)
    table.set_max_composite_points(300)
    table.set_max_composite_contours(25)
    table.set_max_zones(2)
    table.set_max_twilight_points(64)
    table.set_max_storage(128)
    table.set_max_function_defs(96)
    table.set_max_instruction_defs(8)
    table.set_max_stack_elements(512)
    table.set_max_size_of_instructions(2048)
    table.set_max_component_elements(7)
    table.set_max_component_depth(4)

    assert table.get_max_points() == 150
    assert table.get_max_contours() == 15
    assert table.get_max_composite_points() == 300
    assert table.get_max_composite_contours() == 25
    assert table.get_max_zones() == 2
    assert table.get_max_twilight_points() == 64
    assert table.get_max_storage() == 128
    assert table.get_max_function_defs() == 96
    assert table.get_max_instruction_defs() == 8
    assert table.get_max_stack_elements() == 512
    assert table.get_max_size_of_instructions() == 2048
    assert table.get_max_component_elements() == 7
    assert table.get_max_component_depth() == 4


def test_setters_overwrite_values_after_read() -> None:
    table = MaximumProfileTable()
    table.read(None, MemoryTTFDataStream(_build_v10()))  # type: ignore[arg-type]
    # Setters should be allowed to write back values, including 0 — they do
    # NOT re-trigger the PDFBOX-6105 "0 → 1" fix-up (that only runs in read()).
    table.set_max_component_depth(0)
    assert table.get_max_component_depth() == 0
    table.set_num_glyphs(9999)
    assert table.get_num_glyphs() == 9999
