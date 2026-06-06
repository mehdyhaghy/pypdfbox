"""Wave 1368 (agent D) — Filter chain round-trip parity.

Exercises the static :meth:`Filter.decode_chain` helper across multi-filter
``/Filter`` arrays. Verifies byte-identical reconstruction when the chain
inverts ``encode``s applied in reverse, the canonical PDF use case being
``[/ASCIIHexDecode /FlateDecode]`` (decode order, matching the spec's
left-to-right application semantics).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import (
    ASCIIHexDecode,
    ASCIIHexFilter,
    FilterFactory,
    FlateDecode,
)
from pypdfbox.filter.filter import Filter


def _encode_chain(filters: list[Filter], raw: bytes) -> bytes:
    """Encode ``raw`` by applying ``filters`` in reverse order.

    PDF ``/Filter`` arrays are applied left-to-right on decode, so a
    stream tagged ``[/ASCIIHexDecode /FlateDecode]`` was encoded by the
    producer with FlateEncode first, then ASCIIHexEncode. Mirroring that
    here ensures the round-trip is symmetric.
    """
    data = raw
    for f in reversed(filters):
        buf = io.BytesIO()
        f.encode(io.BytesIO(data), buf, COSDictionary())
        data = buf.getvalue()
    return data


def test_flate_then_ascii_hex_chain_round_trip() -> None:
    """``decode_chain`` reverses an ASCIIHex→Flate encode round-trip."""
    raw = b"PDF stream payload " * 50 + b"\x00\xff" * 100
    chain = [ASCIIHexDecode(), FlateDecode()]
    encoded = _encode_chain(chain, raw)
    out = Filter.decode_chain(io.BytesIO(encoded), chain)
    assert out.read() == raw


def test_ascii_hex_only_chain_round_trip() -> None:
    """Single-filter chain still round-trips through ``decode_chain``."""
    raw = bytes(range(256))
    chain = [ASCIIHexDecode()]
    encoded = _encode_chain(chain, raw)
    out = Filter.decode_chain(io.BytesIO(encoded), chain)
    assert out.read() == raw


def test_flate_only_chain_round_trip() -> None:
    raw = b"Hello, PDF!" * 1024
    chain = [FlateDecode()]
    encoded = _encode_chain(chain, raw)
    out = Filter.decode_chain(io.BytesIO(encoded), chain)
    assert out.read() == raw


def test_decode_chain_results_list_populated() -> None:
    """``results`` parameter receives one DecodeResult per filter."""
    raw = b"x" * 200
    chain = [ASCIIHexDecode(), FlateDecode()]
    encoded = _encode_chain(chain, raw)
    results: list = []
    out = Filter.decode_chain(io.BytesIO(encoded), chain, results=results)
    assert out.read() == raw
    assert len(results) == 2
    # bytes_written should be tracked for both intermediate and final stages.
    assert all(r.bytes_written >= 0 for r in results)


def test_decode_chain_dedupes_repeated_filter() -> None:
    """A duplicated filter in the chain is collapsed once.

    Mirrors upstream behaviour: PDF streams that double-list a filter
    are treated as a single application, with a warning logged.
    """
    raw = b"abc" * 64
    flate = FlateDecode()
    # Encode just once.
    encoded = _encode_chain([flate], raw)
    # Pass the same instance twice — dedup should collapse to one decode.
    out = Filter.decode_chain(io.BytesIO(encoded), [flate, flate])
    assert out.read() == raw


def test_decode_chain_empty_list_raises() -> None:
    with pytest.raises(ValueError, match="Empty filterList"):
        Filter.decode_chain(io.BytesIO(b""), [])


def test_decode_chain_preserves_filter_order() -> None:
    """The chain order matters — verify by feeding a hand-crafted payload.

    Constructs an encoded payload as ASCIIHex(Flate(raw)). Reversed
    chain order would attempt to inflate ASCII-hex text and explode.
    """
    raw = b"order matters"
    flate = FlateDecode()
    ahx = ASCIIHexDecode()
    encoded = _encode_chain([ahx, flate], raw)  # correct order
    # Forward order works.
    out = Filter.decode_chain(io.BytesIO(encoded), [ahx, flate])
    assert out.read() == raw
    # Reverse order breaks: the lenient flate decoder (PDFBOX-1232) sees
    # ASCII-hex text instead of deflate bytes and yields garbage / empty
    # rather than raising (matching upstream's FlateFilterDecoderStream),
    # so the chain cannot recover the original payload.
    try:
        broken = Filter.decode_chain(io.BytesIO(encoded), [flate, ahx]).read()
    except OSError:
        broken = None
    assert broken != raw


def test_decode_chain_resolves_via_filter_factory() -> None:
    """Chain populated from FilterFactory.get round-trips."""
    raw = b"factory-resolved chain" * 32
    chain = [FilterFactory.get("ASCIIHexDecode"), FilterFactory.get("FlateDecode")]
    encoded = _encode_chain(chain, raw)
    out = Filter.decode_chain(io.BytesIO(encoded), chain)
    assert out.read() == raw


def test_decode_chain_short_name_resolves_same_instance() -> None:
    """``/Fl`` short-name resolves to the same FlateDecode instance.

    Verifies abbreviation alias parity — the encoded body produced via
    the long-name registration is identical to the one via short-name.
    """
    long_form = FilterFactory.get("FlateDecode")
    short_form = FilterFactory.get("Fl")
    assert long_form is short_form


def test_filter_factory_get_all_filters_dedups() -> None:
    """``get_all_filters`` returns one instance per registration even when
    multiple aliases share the same underlying filter object."""
    all_filters = FilterFactory.get_all_filters()
    # Each filter object appears exactly once in the deduped list.
    assert len(all_filters) == len({id(f) for f in all_filters})


def test_ascii_hex_filter_alias_round_trip() -> None:
    """``ASCIIHexFilter`` (Java-named alias) round-trips identically."""
    raw = bytes(range(256))
    f = ASCIIHexFilter()
    enc = io.BytesIO()
    f.encode(io.BytesIO(raw), enc, COSDictionary())
    dec = io.BytesIO()
    f.decode(io.BytesIO(enc.getvalue()), dec, COSDictionary(), 0)
    assert dec.getvalue() == raw


def test_chain_round_trip_empty_payload() -> None:
    raw = b""
    chain = [ASCIIHexDecode(), FlateDecode()]
    encoded = _encode_chain(chain, raw)
    out = Filter.decode_chain(io.BytesIO(encoded), chain)
    assert out.read() == b""
