from __future__ import annotations

from io import BytesIO

import pytest

import pypdfbox.filter.lzw_decode as lzw_decode_module
import pypdfbox.pdfparser.cos_parser as cos_parser_module
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObjectKey
from pypdfbox.filter import Filter, FilterFactory, LZWDecode
from pypdfbox.filter.lzw_decode import _BitWriter
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.cos_parser import COSParser


def _pack_lzw_codes(codes: list[tuple[int, int]]) -> bytes:
    out = BytesIO()
    writer = _BitWriter(out)
    for code, width in codes:
        writer.write_bits(code, width)
    writer.flush()
    return out.getvalue()


def test_lzw_decode_params_array_exception_returns_empty_dictionary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_from_get_object(self: COSArray, index: int) -> object:  # noqa: ARG001
        raise RuntimeError("boom")

    params_array = COSArray([COSDictionary()])
    parameters = COSDictionary()
    parameters.set_item("DecodeParms", params_array)
    monkeypatch.setattr(COSArray, "get_object", raise_from_get_object)

    payload = b"fallback params"
    encoded = BytesIO()
    LZWDecode().encode(BytesIO(payload), encoded)
    decoded = BytesIO()
    result = LZWDecode().decode(BytesIO(encoded.getvalue()), decoded, parameters)

    assert decoded.getvalue() == payload
    assert result.parameters is parameters


def test_lzw_reserved_code_table_slot_as_data_stops_leniently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A code resolving to a None (reserved) slot is a corrupt stream. Upstream
    # treats every corrupt-code path as a premature EOF (caught + logged →
    # stop, keep partial output). pypdfbox raises EOFError internally and the
    # surrounding handler swallows it, so the decode returns its partial output
    # (here: nothing) rather than raising. (Wave 1505 parity fix.)
    def poisoned_table() -> list[bytes | None]:
        table = [bytes((i,)) for i in range(256)]
        table[65] = None
        table.extend([None, None])
        return table

    monkeypatch.setattr(lzw_decode_module, "_initial_code_table", poisoned_table)

    out = BytesIO()
    LZWDecode._do_lzw_decode(BytesIO(_pack_lzw_codes([(65, 9)])), out, True)
    assert out.getvalue() == b""


def test_filter_decode_params_for_filter_uses_raw_get_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filters = COSArray([COSName.get_pdf_name("FlateDecode")])
    decode_params = COSDictionary()
    params_array = COSArray([decode_params])
    dictionary = COSDictionary()
    dictionary.set_item("Filter", filters)
    dictionary.set_item("DecodeParms", params_array)
    monkeypatch.delattr(COSArray, "get_object")

    assert Filter.get_decode_params_for_filter(dictionary, 0) is decode_params


def test_filter_factory_registered_names_and_missing_short_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(FilterFactory, "_registry", {"ASCII85Decode": object()})

    assert FilterFactory.registered_names() == ["ASCII85Decode"]
    assert FilterFactory.is_registered("A85") is True
    with pytest.raises(KeyError, match="resolved to 'FlateDecode'"):
        FilterFactory.get_filter_by_short_name("Fl")


def test_cos_parser_bruteforce_object_search_skips_value_error_then_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_int = int

    def flaky_int(value: object, *args: object, **kwargs: object) -> int:
        if value == b"1":
            raise ValueError("synthetic")
        return original_int(value, *args, **kwargs)

    monkeypatch.setattr(cos_parser_module, "int", flaky_int, raising=False)
    parser = COSParser(RandomAccessReadBuffer(b"1 0 obj\n2 0 obj"))

    assert parser.bf_search_for_objects() == {COSObjectKey(2, 0): 8}


def test_cos_parser_bruteforce_object_search_skips_negative_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_int = int

    def negative_first_number(value: object, *args: object, **kwargs: object) -> int:
        parsed = original_int(value, *args, **kwargs)
        return -1 if value == b"3" else parsed

    monkeypatch.setattr(cos_parser_module, "int", negative_first_number, raising=False)
    parser = COSParser(RandomAccessReadBuffer(b"3 0 obj\n4 0 obj"))

    assert parser.bf_search_for_objects() == {COSObjectKey(4, 0): 8}


def test_cos_parser_bruteforce_object_search_rejects_trailing_number_fragment() -> None:
    class DigitPrefixBytes:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self._zero_reads = 0

        def __len__(self) -> int:
            return len(self._data)

        def find(self, sub: bytes, start: int = 0) -> int:
            return self._data.find(sub, start)

        def __getitem__(self, key: int | slice) -> int | bytes:
            if isinstance(key, slice):
                return self._data[key]
            if key == 0:
                self._zero_reads += 1
                if self._zero_reads == 1:
                    return ord("x")
                return ord("9")
            return self._data[key]

    parser = COSParser(RandomAccessReadBuffer(b""))
    monkeypatch_data = DigitPrefixBytes(b"x12 0 obj\n4 0 obj")
    parser._read_all_bytes = lambda: monkeypatch_data  # type: ignore[method-assign]  # noqa: SLF001

    assert parser.bf_search_for_objects() == {COSObjectKey(4, 0): 10}
