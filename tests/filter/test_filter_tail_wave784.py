from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.filter import FilterFactory, LZWDecode, _predictor
from pypdfbox.filter.lzw_decode import _BitReader, _BitWriter, _get_decode_params


class _EmptyFirstRow:
    def __len__(self) -> int:
        return 1

    def __getitem__(self, key: slice) -> bytes:
        assert isinstance(key, slice)
        return b""


def test_wave784_unpng_tolerates_empty_row_slice() -> None:
    assert _predictor._unpng(_EmptyFirstRow(), row_bytes=1, bytes_per_pixel=1) == (
        b""
    )


def test_wave784_bit_reader_short_partial_code_raises_eoferror() -> None:
    reader = _BitReader(BytesIO(b"\x80"))

    with pytest.raises(EOFError, match="unexpected EOF"):
        reader.read_bits(9)


def test_wave784_bit_writer_masks_value_to_requested_width() -> None:
    out = BytesIO()
    writer = _BitWriter(out)

    writer.write_bits(0b1111111111, 3)
    writer.flush()

    assert out.getvalue() == b"\xe0"


def test_wave784_lzw_decode_params_falls_back_to_top_level_dictionary() -> None:
    params = COSDictionary()
    params.set_int("Predictor", 1)

    assert _get_decode_params(params, 0) is params


def test_wave784_lzw_find_pattern_code_skips_reserved_slots() -> None:
    table = LZWDecode.create_code_table()

    assert LZWDecode.find_pattern_code(table, b"\x05") == 5
    assert LZWDecode.find_pattern_code(table, b"missing") == -1


def test_wave784_filter_factory_register_accepts_cos_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = dict(FilterFactory._registry)
    monkeypatch.setattr(FilterFactory, "_registry", dict(original))
    instance = FilterFactory.get("LZWDecode")

    FilterFactory.register(COSName.get_pdf_name("Wave784Decode"), instance)

    assert FilterFactory.get("Wave784Decode") is instance
    assert FilterFactory.is_registered(COSName.get_pdf_name("Wave784Decode")) is True


def test_wave784_cos_float_rejects_multiple_internal_minus_signs() -> None:
    with pytest.raises(OSError, match="misplaced '-'"):
        COSFloat("1-2-3")
