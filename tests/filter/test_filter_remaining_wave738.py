from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.cos import COSArray, COSDictionary
from pypdfbox.filter import ASCII85Decode, FilterFactory, LZWDecode, RunLengthDecode, lzw_decode
from pypdfbox.filter.lzw_decode import _BitWriter


def _decode_ascii85(data: bytes) -> bytes:
    out = BytesIO()
    ASCII85Decode().decode(BytesIO(data), out)
    return out.getvalue()


def _pack_lzw_codes(codes: list[tuple[int, int]]) -> bytes:
    out = BytesIO()
    writer = _BitWriter(out)
    for code, width in codes:
        writer.write_bits(code, width)
    writer.flush()
    return out.getvalue()


def test_ascii85_decoder_masks_group_overflow_like_pdfbox() -> None:
    # A 5-digit group of b'u' (0x75, the max digit) overflows 32 bits.
    # PDFBox does NOT reject it — it masks the accumulator to 32 bits and
    # emits the four low bytes. Verified against the live oracle (wave 1412):
    # b"uuuuu~>" decodes to 0x08780ec4.
    assert _decode_ascii85(b"uuuuu~>") == bytes.fromhex("08780ec4")


def test_lzw_decode_params_array_out_of_range_falls_back_to_empty_dict() -> None:
    payload = b"decode params array fallback"
    encoded = BytesIO()
    LZWDecode().encode(BytesIO(payload), encoded)

    parameters = COSDictionary()
    parameters.set_item("DecodeParms", COSArray())

    decoded = BytesIO()
    result = LZWDecode().decode(BytesIO(encoded.getvalue()), decoded, parameters)

    assert decoded.getvalue() == payload
    assert result.parameters is parameters


def test_lzw_reserved_table_slot_referenced_as_data_stops_leniently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A code landing on a None (reserved/placeholder) table slot is a corrupt
    # stream. Upstream classes every corrupt-code path as a premature EOF
    # (EOFException caught + logged → stop, keep partial output), so pypdfbox
    # raises EOFError internally and the surrounding handler swallows it: the
    # decode returns whatever was produced (here: nothing), it does NOT raise.
    def poisoned_table() -> list[bytes | None]:
        table = [bytes((i,)) for i in range(256)]
        table[65] = None
        table.extend([None, None])
        return table

    monkeypatch.setattr(lzw_decode, "_initial_code_table", poisoned_table)

    out = BytesIO()
    LZWDecode._do_lzw_decode(BytesIO(_pack_lzw_codes([(65, 9)])), out, True)
    assert out.getvalue() == b""


def test_run_length_decode_empty_stream_stops_without_eod() -> None:
    decoded = BytesIO()

    result = RunLengthDecode().decode(BytesIO(b""), decoded)

    assert decoded.getvalue() == b""
    assert result.bytes_written == 0


def test_filter_factory_short_name_raises_when_registered_long_name_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(FilterFactory, "_registry", {})

    with pytest.raises(KeyError, match="resolved to 'FlateDecode'"):
        FilterFactory.get_filter_by_short_name("Fl")


def test_filter_factory_registered_names_are_sorted() -> None:
    names = FilterFactory.registered_names()

    assert names == sorted(names)
    assert "ASCII85Decode" in names
