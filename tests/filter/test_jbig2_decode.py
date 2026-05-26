from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import FilterFactory, JBIG2Decode

# JBIG2 decoding is intentionally unsupported: the only available
# decoder (jbig2-parser → jbig2dec) is GPL-3.0/AGPL-licensed, which the
# project's permissive-only license policy forbids (CLAUDE.md §4). The
# filter is still *registered* so /JBIG2Decode is a recognised filter
# name, but decode() raises OSError.

_UNSUPPORTED_MATCH = "intentionally unsupported"


# ---------- registration ----------------------------------------------


def test_jbig2_filter_registered_under_long_name_only() -> None:
    assert FilterFactory.is_registered("JBIG2Decode")
    assert isinstance(FilterFactory.get("JBIG2Decode"), JBIG2Decode)
    # ISO 32000-1 §7.4.2 Table 6 defines NO short-name abbreviation
    # for /JBIG2Decode — make sure we haven't invented one.
    with pytest.raises(KeyError):
        FilterFactory.get("JBIG2")


def test_jbig2_globals_class_constant_matches_pdf_spec_key() -> None:
    """Mirrors upstream's ``COSName.JBIG2_GLOBALS`` reference site —
    porters reaching for the constant land on a stable name on the
    filter class."""
    assert JBIG2Decode.JBIG2_GLOBALS == "JBIG2Globals"


# ---------- decode: unsupported (GPL/AGPL-only decoder excluded) -------


def test_jbig2_decode_raises_unsupported_oserror() -> None:
    with pytest.raises(OSError, match=_UNSUPPORTED_MATCH) as exc:
        JBIG2Decode().decode(io.BytesIO(b"\xfa\xce\x01jbig2-body"), io.BytesIO())
    # The message names the licensing reason so the failure is actionable.
    assert "GPL-3.0/AGPL" in str(exc.value)


def test_jbig2_decode_raises_unsupported_even_with_parameters() -> None:
    parent = COSDictionary()
    with pytest.raises(OSError, match=_UNSUPPORTED_MATCH):
        JBIG2Decode().decode(io.BytesIO(b"body"), io.BytesIO(), parent, index=0)


def test_jbig2_decode_raises_unsupported_on_empty_input() -> None:
    # Even an empty stream is rejected — no decode path exists at all.
    with pytest.raises(OSError, match=_UNSUPPORTED_MATCH):
        JBIG2Decode().decode(io.BytesIO(b""), io.BytesIO())


# ---------- encode -----------------------------------------------------


def test_jbig2_encode_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="decode-only"):
        JBIG2Decode().encode(io.BytesIO(b""), io.BytesIO(), COSDictionary())
