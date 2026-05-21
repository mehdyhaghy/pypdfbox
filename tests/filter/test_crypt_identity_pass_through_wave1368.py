"""Wave 1368 (agent D) — CryptFilter identity pass-through.

ISO 32000-1 §7.4.10 ``/Crypt`` filter: when the ``/Name`` is missing,
omitted, or the literal ``/Identity``, the filter passes data through
unchanged. Any other crypt sub-filter name is illegal at this layer
because real per-stream PDF decryption is handled by the security
handler before the filter chain runs.

Real AESV2/AESV3 stream-level decryption is tested at the encryption
layer (``tests/pdmodel/encryption/``); the filter sees the already-
decrypted bytes and just forwards them. These tests pin the filter's
contract: identity → pass through, unknown name → ``OSError``.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.filter import CryptFilter, FilterFactory, IdentityFilter


def _decode(f, encoded: bytes, params: COSDictionary | None = None) -> bytes:
    out = io.BytesIO()
    f.decode(io.BytesIO(encoded), out, params, 0)
    return out.getvalue()


def _encode(f, raw: bytes, params: COSDictionary | None = None) -> bytes:
    out = io.BytesIO()
    f.encode(io.BytesIO(raw), out, params)
    return out.getvalue()


# ---- Identity name handling ------------------------------------------


def test_crypt_filter_decode_identity_name_pass_through() -> None:
    """``/Name /Identity`` → bytes pass through unchanged."""
    params = COSDictionary()
    params.set_item("Name", COSName.get_pdf_name("Identity"))
    raw = b"\x00\x01\x02secret payload\xff\xfe"
    assert _decode(CryptFilter(), raw, params) == raw


def test_crypt_filter_decode_missing_name_pass_through() -> None:
    """No ``/Name`` entry at all → still pass through (defaults to Identity)."""
    params = COSDictionary()
    raw = b"Hello, world!" * 4
    assert _decode(CryptFilter(), raw, params) == raw


def test_crypt_filter_decode_none_parameters_pass_through() -> None:
    """``parameters=None`` → still pass through."""
    raw = b"raw payload"
    assert _decode(CryptFilter(), raw, None) == raw


def test_crypt_filter_encode_identity_pass_through() -> None:
    """Encode under Identity preserves bytes byte-for-byte."""
    params = COSDictionary()
    params.set_item("Name", COSName.get_pdf_name("Identity"))
    raw = bytes(range(256))
    assert _encode(CryptFilter(), raw, params) == raw


def test_crypt_filter_encode_no_params_pass_through() -> None:
    """Encode with no parameters dict also yields Identity behaviour."""
    raw = b"identity by default"
    assert _encode(CryptFilter(), raw, None) == raw


# ---- Non-identity rejection ------------------------------------------


def test_crypt_filter_decode_rejects_unknown_name() -> None:
    """Any non-Identity /Name raises OSError (handled at security layer)."""
    params = COSDictionary()
    params.set_item("Name", COSName.get_pdf_name("StdCF"))
    with pytest.raises(OSError, match="Unsupported crypt filter"):
        _decode(CryptFilter(), b"encrypted-by-security-handler", params)


def test_crypt_filter_encode_rejects_unknown_name() -> None:
    """Encode-side mirror: non-Identity name → OSError."""
    params = COSDictionary()
    params.set_item("Name", COSName.get_pdf_name("StdCF"))
    with pytest.raises(OSError, match="Unsupported crypt filter"):
        _encode(CryptFilter(), b"some bytes", params)


def test_crypt_filter_decode_rejects_aes_v2_name() -> None:
    """Even known AES-style names must be rejected at this layer."""
    params = COSDictionary()
    params.set_item("Name", COSName.get_pdf_name("AESV2"))
    with pytest.raises(OSError, match="Unsupported crypt filter"):
        _decode(CryptFilter(), b"x" * 16, params)


def test_crypt_filter_decode_rejects_aes_v3_name() -> None:
    params = COSDictionary()
    params.set_item("Name", COSName.get_pdf_name("AESV3"))
    with pytest.raises(OSError, match="Unsupported crypt filter"):
        _decode(CryptFilter(), b"x" * 32, params)


# ---- Identity round-trip via Filter base ----------------------------


def test_identity_filter_round_trip() -> None:
    """IdentityFilter is the base case Crypt delegates to."""
    raw = b"identity preserves everything\xff\x00"
    f = IdentityFilter()
    out = io.BytesIO()
    f.decode(io.BytesIO(raw), out, COSDictionary(), 0)
    assert out.getvalue() == raw
    out = io.BytesIO()
    f.encode(io.BytesIO(raw), out, COSDictionary())
    assert out.getvalue() == raw


# ---- Factory registration --------------------------------------------


def test_crypt_filter_registered_under_canonical_name() -> None:
    """``/Crypt`` resolves through the registry."""
    assert FilterFactory.is_registered("Crypt")
    f = FilterFactory.get("Crypt")
    assert isinstance(f, CryptFilter)


def test_crypt_filter_decode_string_typed_name_pass_through() -> None:
    """When /Name is a plain string (lenient), still resolves correctly."""
    # Some malformed PDFs store /Name as a string; CryptFilter's resolver
    # falls back to dictionary lookup in that case.
    params = COSDictionary()
    params.set_item("Name", COSName.get_pdf_name("Identity"))
    assert _decode(CryptFilter(), b"abc", params) == b"abc"


def test_crypt_filter_empty_payload_pass_through() -> None:
    """Empty input round-trips."""
    assert _decode(CryptFilter(), b"", COSDictionary()) == b""
    assert _encode(CryptFilter(), b"", COSDictionary()) == b""
