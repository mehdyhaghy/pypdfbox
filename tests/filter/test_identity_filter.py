from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import IdentityFilter


def test_identity_decode_passes_bytes_through_unchanged() -> None:
    payload = b"hello, world!\x00\xff\x7f\x80"
    out = io.BytesIO()

    result = IdentityFilter().decode(io.BytesIO(payload), out)

    assert out.getvalue() == payload
    assert result.bytes_written == len(payload)


def test_identity_decode_empty_input() -> None:
    out = io.BytesIO()
    result = IdentityFilter().decode(io.BytesIO(b""), out)
    assert out.getvalue() == b""
    assert result.bytes_written == 0


def test_identity_decode_returns_input_parameters_when_provided() -> None:
    params = COSDictionary()
    params.set_int("Width", 42)

    result = IdentityFilter().decode(io.BytesIO(b"abc"), io.BytesIO(), params)

    # Mirrors upstream: ``new DecodeResult(parameters)`` reuses the
    # caller's dict — the same instance, not a copy.
    assert result.parameters is params
    assert result.parameters.get_int("Width") == 42


def test_identity_decode_yields_empty_dict_when_no_parameters() -> None:
    result = IdentityFilter().decode(io.BytesIO(b"abc"), io.BytesIO())
    assert isinstance(result.parameters, COSDictionary)
    assert len(result.parameters) == 0


def test_identity_encode_passes_bytes_through_unchanged() -> None:
    payload = b"\x01\x02\x03 round-trip"
    out = io.BytesIO()

    IdentityFilter().encode(io.BytesIO(payload), out, COSDictionary())

    assert out.getvalue() == payload


def test_identity_encode_empty_input() -> None:
    out = io.BytesIO()
    IdentityFilter().encode(io.BytesIO(b""), out)
    assert out.getvalue() == b""


def test_identity_decode_handles_large_payload_across_buffer_boundary() -> None:
    # Sized to exceed the default 8 KiB IO copy buffer so we exercise
    # the multi-chunk path.
    payload = b"\xa5" * (8192 * 4 + 17)
    out = io.BytesIO()

    result = IdentityFilter().decode(io.BytesIO(payload), out)

    assert out.getvalue() == payload
    assert result.bytes_written == len(payload)


def test_identity_filter_not_registered_in_factory() -> None:
    # Upstream: IdentityFilter is package-private, never registered with
    # FilterFactory. ``/Identity`` is not a real PDF filter name — the
    # spec only references it as a /Crypt-filter sub-name.
    from pypdfbox.filter import FilterFactory

    assert not FilterFactory.is_registered("Identity")
    assert not FilterFactory.is_registered("IdentityFilter")
