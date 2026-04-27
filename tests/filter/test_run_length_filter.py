"""
Hand-written tests for the upstream-named :class:`RunLengthDecodeFilter`
alias. The full codec is exercised by ``test_run_length_decode.py``;
this module verifies wiring and cross-instance interoperability.
"""

from __future__ import annotations

from io import BytesIO

from pypdfbox.cos import COSName
from pypdfbox.filter import FilterFactory, RunLengthDecode, RunLengthDecodeFilter
from pypdfbox.filter.run_length_filter import (
    RunLengthDecodeFilter as DirectRunLengthDecodeFilter,
)


def _round_trip(f: RunLengthDecode, data: bytes) -> bytes:
    enc = BytesIO()
    f.encode(BytesIO(data), enc, None)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, None)
    return dec.getvalue()


def test_filter_is_run_length_decode_subclass() -> None:
    assert issubclass(RunLengthDecodeFilter, RunLengthDecode)


def test_filter_imports_from_package() -> None:
    assert RunLengthDecodeFilter is DirectRunLengthDecodeFilter


def test_factory_resolves_filter_long_name() -> None:
    inst = FilterFactory.get("RunLengthDecodeFilter")
    assert isinstance(inst, RunLengthDecodeFilter)


def test_factory_resolves_filter_via_cosname() -> None:
    inst = FilterFactory.get(COSName.get_pdf_name("RunLengthDecodeFilter"))
    assert isinstance(inst, RunLengthDecodeFilter)


def test_factory_run_length_decode_unchanged() -> None:
    # The new registration must not displace the PDF short/long names.
    long_filter = FilterFactory.get("RunLengthDecode")
    short_filter = FilterFactory.get("RL")
    assert isinstance(long_filter, RunLengthDecode)
    assert long_filter is short_filter


def test_round_trip_through_filter_simple() -> None:
    payload = b"the quick brown fox jumps over the lazy dog"
    assert _round_trip(RunLengthDecodeFilter(), payload) == payload


def test_round_trip_through_filter_runs_and_literals() -> None:
    payload = b"\x00" * 300 + bytes(range(256)) + b"AB" * 50 + b"\xff" * 200
    assert _round_trip(RunLengthDecodeFilter(), payload) == payload


def test_round_trip_empty_through_filter() -> None:
    enc = BytesIO()
    RunLengthDecodeFilter().encode(BytesIO(b""), enc, None)
    assert enc.getvalue() == b"\x80"
    dec = BytesIO()
    RunLengthDecodeFilter().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == b""


def test_cross_class_round_trip_filter_then_decode() -> None:
    payload = b"AAAAA literal-tail"
    enc = BytesIO()
    RunLengthDecodeFilter().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    RunLengthDecode().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_cross_class_round_trip_decode_then_filter() -> None:
    payload = b"ZZZZ then mixed"
    enc = BytesIO()
    RunLengthDecode().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    RunLengthDecodeFilter().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_factory_is_registered_filter() -> None:
    assert FilterFactory.is_registered("RunLengthDecodeFilter")
