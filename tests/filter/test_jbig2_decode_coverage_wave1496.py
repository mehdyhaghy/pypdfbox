"""Wave 1496 coverage tests for the remaining branches of
:mod:`pypdfbox.filter.jbig2_decode`.

Targets the four still-uncovered lines:

* ``_resolve_decode_params`` — the ``/DecodeParms`` *array* form where the
  entry at ``index`` IS a ``COSDictionary`` (the ``return entry`` branch).
* ``_read_globals_bytes`` — a ``/JBIG2Globals`` value that is present but
  not a ``COSStream`` (malformed input -> empty globals, no crash).
* ``JBIG2Decode.decode`` — ``page is None`` raising ``OSError`` and the
  bare ``except OSError: raise`` re-raise (an ``OSError`` raised inside the
  decode block must propagate verbatim, not be wrapped).

The decoder-path branches (``page is None`` / OSError re-raise) are pinned
by monkeypatching ``JBIG2Document`` so no real codestream is needed — we
assert the *contract* (which exception class surfaces), which is the
observable behaviour callers rely on.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.filter import jbig2_decode
from pypdfbox.filter.jbig2_decode import (
    JBIG2Decode,
    _read_globals_bytes,
    _resolve_decode_params,
)


# ---------------------------------------------------------------------
# _resolve_decode_params — /DecodeParms array with a dict entry.
# ---------------------------------------------------------------------
def test_resolve_decode_params_array_entry_is_dict() -> None:
    entry0 = COSDictionary()
    entry0.set_item(COSName.get_pdf_name("JBIG2Globals"), COSStream())
    entry1 = COSDictionary()
    arr = COSArray()
    arr.add(entry0)
    arr.add(entry1)
    stream_dict = COSDictionary()
    stream_dict.set_item(COSName.get_pdf_name("DecodeParms"), arr)

    assert _resolve_decode_params(stream_dict, 0) is entry0
    assert _resolve_decode_params(stream_dict, 1) is entry1


def test_resolve_decode_params_array_non_dict_entry_is_empty() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("NotADict"))
    stream_dict = COSDictionary()
    stream_dict.set_item(COSName.get_pdf_name("DecodeParms"), arr)

    result = _resolve_decode_params(stream_dict, 0)
    assert isinstance(result, COSDictionary)
    assert result.is_empty()


# ---------------------------------------------------------------------
# _read_globals_bytes — non-stream /JBIG2Globals.
# ---------------------------------------------------------------------
def test_read_globals_bytes_non_stream_is_empty() -> None:
    decode_params = COSDictionary()
    # A name (not a stream) is malformed per spec — treated as no globals.
    decode_params.set_item(
        COSName.get_pdf_name("JBIG2Globals"), COSName.get_pdf_name("bogus")
    )
    assert _read_globals_bytes(decode_params) == b""


def test_read_globals_bytes_absent_is_empty() -> None:
    assert _read_globals_bytes(COSDictionary()) == b""


# ---------------------------------------------------------------------
# JBIG2Decode.decode — page is None and OSError re-raise.
# ---------------------------------------------------------------------
class _NoPageDocument:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def get_global_segments(self):  # pragma: no cover - not reached here
        return None

    def get_page(self, _number):
        return None


class _OSErrorDocument:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def get_global_segments(self):  # pragma: no cover - not reached here
        return None

    def get_page(self, _number):
        raise OSError("synthetic decode failure")


def test_decode_no_page_raises_oserror(monkeypatch) -> None:
    monkeypatch.setattr(
        "pypdfbox.jbig2.jbig2_document.JBIG2Document", _NoPageDocument
    )
    with pytest.raises(OSError, match="no page 1"):
        JBIG2Decode().decode(io.BytesIO(b"\x00\x01\x02\x03"), io.BytesIO())


def test_decode_oserror_propagates_verbatim(monkeypatch) -> None:
    monkeypatch.setattr(
        "pypdfbox.jbig2.jbig2_document.JBIG2Document", _OSErrorDocument
    )
    # The bare ``except OSError: raise`` must NOT wrap into the generic
    # "JBIG2 decode failed" message — the original OSError surfaces.
    with pytest.raises(OSError, match="synthetic decode failure"):
        JBIG2Decode().decode(io.BytesIO(b"\x00\x01\x02\x03"), io.BytesIO())


def test_module_exposes_helpers() -> None:
    # Guard against an accidental rename of the private helpers the tests
    # above pin (keeps the coverage targets discoverable).
    assert hasattr(jbig2_decode, "_resolve_decode_params")
    assert hasattr(jbig2_decode, "_read_globals_bytes")
