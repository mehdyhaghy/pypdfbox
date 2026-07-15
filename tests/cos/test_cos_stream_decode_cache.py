"""Correctness tests for the ``COSStream`` decoded-bytes memo.

``create_input_stream`` memoises the fully decoded body so repeat callers
(form XObjects stamped via ``Do``, tiling patterns, annotation appearances,
``to_byte_array`` / ``create_view`` / ``to_text_string``) do not re-run the
whole /Filter chain each call. These tests pin that the memo is invalidated
on EVERY input change, so it can never serve stale bytes. Each assertion
checks the semantically correct (uncached) value, so a stale cache can only
fail a test.
"""
from __future__ import annotations

import base64
import zlib

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.io import MemoryUsageSetting, ScratchFile


def _flate(data: bytes) -> bytes:
    return zlib.compress(data, 6)


def _a85(data: bytes) -> bytes:
    return base64.a85encode(data) + b"~>"


def _decode(st: COSStream) -> bytes:
    with st.create_input_stream() as s:
        return s.read()


_INNER = b"the quick brown fox " * 500


# ---------- (a) repeat decode is byte-identical ----------

def test_repeat_decode_byte_identical() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    first = _decode(st)
    second = _decode(st)
    assert first == _INNER
    assert second == first


def test_repeat_decode_returns_independent_streams() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    s1 = st.create_input_stream()
    s2 = st.create_input_stream()
    assert s1 is not s2
    # Consuming one must not affect the other (independent buffers).
    assert s1.read() == _INNER
    assert s2.read() == _INNER


# ---------- (b) raw-data write invalidates ----------

def test_set_raw_data_invalidates_memo() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    assert _decode(st) == _INNER  # prime
    new = b"replacement payload " * 30
    st.set_raw_data(_flate(new))
    assert _decode(st) == new


def test_set_raw_data_keep_length_invalidates_memo() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    assert _decode(st) == _INNER  # prime
    new = b"kept-length payload " * 12
    st.set_raw_data_keep_length(_flate(new))
    assert _decode(st) == new


# ---------- (c) filter / decode-parms change invalidates ----------

def test_in_place_decodeparms_predictor_change() -> None:
    cols = 6
    rows = 200
    raw_img = bytearray()
    for r in range(rows):
        raw_img.append(2)  # PNG "Up" predictor tag
        raw_img.extend(bytes((r * 3 + c) & 0xFF for c in range(cols)))
    comp = _flate(bytes(raw_img))
    st = COSStream()
    st.set_raw_data(comp)
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    dp = COSDictionary()
    dp.set_int("Predictor", 15)
    dp.set_int("Columns", cols)
    st.set_item("DecodeParms", dp)
    predicted = _decode(st)  # prime with predictor applied
    # Mutate the SAME DecodeParms dict in place -> predictor off.
    dp.set_int("Predictor", 1)
    assert _decode(st) == zlib.decompress(comp)
    assert _decode(st) != predicted
    # Restore -> predicted result returns.
    dp.set_int("Predictor", 15)
    assert _decode(st) == predicted


def test_in_place_decodeparms_columns_change() -> None:
    cols = 8
    rows = 100
    raw_img = bytearray()
    for r in range(rows):
        raw_img.append(2)
        raw_img.extend(bytes((r + c) & 0xFF for c in range(cols)))
    comp = _flate(bytes(raw_img))
    st = COSStream()
    st.set_raw_data(comp)
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    dp = COSDictionary()
    dp.set_int("Predictor", 15)
    dp.set_int("Columns", cols)
    st.set_item("DecodeParms", dp)
    base = _decode(st)
    dp.set_int("Columns", cols // 2)
    assert _decode(st) != base


def test_add_and_remove_filter_via_set_item() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    assert _decode(st) == _flate(_INNER)  # no filter -> raw
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    assert _decode(st) == _INNER
    st.remove_item("Filter")
    assert _decode(st) == _flate(_INNER)


def test_add_and_remove_filter_via_helpers() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_filters(COSName.get_pdf_name("FlateDecode"))
    assert _decode(st) == _INNER
    st.clear_filters()
    assert _decode(st) == _flate(_INNER)


def test_in_place_filter_array_grow() -> None:
    double = _a85(_flate(_INNER))
    st = COSStream()
    st.set_raw_data(double)
    arr = COSArray([COSName.get_pdf_name("FlateDecode")])
    st.set_item("Filter", arr)
    _decode(st)  # prime with the WRONG single-filter interpretation
    arr.clear()
    arr.add(COSName.get_pdf_name("ASCII85Decode"))
    arr.add(COSName.get_pdf_name("FlateDecode"))
    assert _decode(st) == _INNER


# ---------- (d) create_output_stream commit invalidates ----------

def test_create_output_stream_commit_invalidates() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    _decode(st)  # prime
    fresh = b"brand new payload " * 40
    with st.create_output_stream(COSName.get_pdf_name("FlateDecode")) as out:
        out.write(fresh)
    assert _decode(st) == fresh


def test_raw_output_stream_commit_invalidates() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    _decode(st)  # prime
    with st.create_output_stream() as out:  # filters=None clears /Filter
        out.write(b"verbatim")
    assert _decode(st) == b"verbatim"


# ---------- (e) multi-filter, scratch-backed, encrypted ----------

def test_multi_filter_chain_cached() -> None:
    st = COSStream()
    st.set_raw_data(_a85(_flate(_INNER)))
    st.set_item(
        "Filter",
        COSArray(
            [
                COSName.get_pdf_name("ASCII85Decode"),
                COSName.get_pdf_name("FlateDecode"),
            ]
        ),
    )
    assert _decode(st) == _INNER
    assert _decode(st) == _INNER


def test_scratch_file_backed_stream() -> None:
    sf = ScratchFile(MemoryUsageSetting.setup_temp_file_only())
    try:
        big = bytes((i * 5) & 0xFF for i in range(500_000))
        st = COSStream(sf)
        st.set_raw_data(_flate(big))
        st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
        assert _decode(st) == big
        assert _decode(st) == big
        st.set_raw_data(_flate(big[::-1]))
        assert _decode(st) == big[::-1]
    finally:
        sf.close()


class _ToyHandler:
    """Symmetric XOR 'cipher' — ``decrypt_stream`` is its own inverse."""

    def __init__(self, key: int) -> None:
        self.key = key

    def decrypt_stream(self, data: bytes, obj: int, gen: int) -> bytes:
        return bytes(b ^ self.key for b in data)

    def is_encrypt_metadata(self) -> bool:
        return True


def test_encrypted_stream_not_double_decrypted() -> None:
    plain_body = _flate(_INNER)
    cipher_body = bytes(b ^ 0x5A for b in plain_body)
    st = COSStream()
    st.set_raw_data(cipher_body)
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    st.set_security_handler(_ToyHandler(0x5A), 7, 0)
    # First decode decrypts in place then inflates; repeat decodes must
    # serve the same bytes, never re-decrypt the now-plaintext buffer.
    assert _decode(st) == _INNER
    assert _decode(st) == _INNER
    assert _decode(st) == _INNER


# ---------- (f) stop_filters never touches the full-decode memo ----------

def test_stop_filters_bypasses_cache() -> None:
    st = COSStream()
    st.set_raw_data(_a85(_flate(_INNER)))
    st.set_item(
        "Filter",
        COSArray(
            [
                COSName.get_pdf_name("ASCII85Decode"),
                COSName.get_pdf_name("FlateDecode"),
            ]
        ),
    )
    full = _decode(st)  # prime full-decode memo
    with st.create_input_stream(stop_filters=["FlateDecode"]) as s:
        partial = s.read()
    assert partial == _flate(_INNER)
    assert partial != full
    # The stop call must not have poisoned the full-decode memo.
    assert _decode(st) == _INNER


def test_full_decode_correct_after_stop_primed_first() -> None:
    st = COSStream()
    st.set_raw_data(_a85(_flate(_INNER)))
    st.set_item(
        "Filter",
        COSArray(
            [
                COSName.get_pdf_name("ASCII85Decode"),
                COSName.get_pdf_name("FlateDecode"),
            ]
        ),
    )
    with st.create_input_stream(stop_filters=["FlateDecode"]) as s:
        s.read()
    assert _decode(st) == _INNER


# ---------- (g) convenience funnels stay correct ----------

def test_to_byte_array_and_view_funnels() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    assert st.to_byte_array() == _INNER
    assert st.to_byte_array() == _INNER
    assert st.create_view().length() == len(_INNER)
    st.set_raw_data(_flate(b"XY" * 100))
    assert st.to_byte_array() == b"XY" * 100


def test_closed_stream_drops_memo() -> None:
    st = COSStream()
    st.set_raw_data(_flate(_INNER))
    st.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
    assert _decode(st) == _INNER
    st.close()
    # Memo released with the buffer.
    assert st._decode_cache is None
