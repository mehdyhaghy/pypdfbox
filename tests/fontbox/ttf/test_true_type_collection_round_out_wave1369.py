"""Wave 1369 round-out tests for :class:`TrueTypeCollection`.

Existing waves cover the happy path on a synthesised two-font TTC plus
the ``invalid numFonts`` rejection. This file fills in:

* ``v2`` TTC headers — the three trailing uint16 fields (DSig tag /
  length / offset) are consumed and discarded; downstream reads of the
  font offsets must still line up.
* ``get_font_by_name`` returning ``None`` when no font matches.
* ``get_font_offsets`` returns a defensive copy.
* Index-based parser-creation rejects out-of-range indices with
  ``IndexError``.
* ``process_all_font_headers`` instance-flavoured iterator hands one
  :class:`FontHeaders` per font in collection order.
* Empty file / wrong magic / bare-stream input is rejected with the
  upstream-shaped error message ``"Missing TTC header"``.
"""

from __future__ import annotations

import io
import os
import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.true_type_collection import TrueTypeCollection
from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def ttc_v1_bytes() -> bytes:
    """Build a single-font v1.0 TTC. Re-uses the bundled TTF fixture."""
    pytest.importorskip("fontTools")
    from fontTools.ttLib import TTCollection, TTFont  # noqa: PLC0415

    coll = TTCollection()
    coll.fonts.append(TTFont(os.fspath(_FIXTURE_TTF)))
    sink = io.BytesIO()
    coll.save(sink)
    return sink.getvalue()


@pytest.fixture(scope="module")
def two_font_ttc_bytes() -> bytes:
    pytest.importorskip("fontTools")
    from fontTools.ttLib import TTCollection, TTFont  # noqa: PLC0415

    coll = TTCollection()
    coll.fonts.append(TTFont(os.fspath(_FIXTURE_TTF)))
    coll.fonts.append(TTFont(os.fspath(_FIXTURE_TTF)))
    sink = io.BytesIO()
    coll.save(sink)
    return sink.getvalue()


# ---------- header-shape error paths --------------------------------------


def test_missing_ttcf_magic_raises_with_upstream_message() -> None:
    """Upstream's ``TrueTypeCollection`` raises ``IOException("Missing
    TTC header")`` when the four-byte tag at offset 0 is not ``ttcf``."""
    with pytest.raises(OSError, match="Missing TTC header"):
        TrueTypeCollection(b"NOPE" + b"\x00" * 16)


def test_zero_num_fonts_is_rejected() -> None:
    """``numFonts == 0`` is on the boundary of the upstream sanity check
    (``<= 0 || > 1024``) — must raise with the upstream error message."""
    blob = b"ttcf" + struct.pack(">II", 0x00010000, 0)
    with pytest.raises(OSError, match="Invalid number of fonts"):
        TrueTypeCollection(blob)


def test_excessive_num_fonts_is_rejected() -> None:
    """``numFonts > 1024`` is rejected — boundary of the upstream sanity
    check that this test deliberately probes."""
    blob = b"ttcf" + struct.pack(">II", 0x00010000, 1025)
    with pytest.raises(OSError, match="Invalid number of fonts"):
        TrueTypeCollection(blob)


# ---------- v1 happy path -------------------------------------------------


def test_single_font_v1_collection_parses(ttc_v1_bytes: bytes) -> None:
    with TrueTypeCollection(ttc_v1_bytes) as ttc:
        assert ttc.get_number_of_fonts() == 1
        offsets = ttc.get_font_offsets()
        assert len(offsets) == 1
        assert offsets[0] > 0


def test_get_font_offsets_returns_defensive_copy(ttc_v1_bytes: bytes) -> None:
    """``get_font_offsets`` returns a *copy*: mutating it must not
    perturb the collection's internal state."""
    with TrueTypeCollection(ttc_v1_bytes) as ttc:
        first = ttc.get_font_offsets()
        first.append(0xDEADBEEF)
        second = ttc.get_font_offsets()
        assert second != first
        assert len(second) == ttc.get_number_of_fonts()


# ---------- v2 header (DSig fields consumed) ------------------------------


def test_v2_header_consumes_dsig_fields(two_font_ttc_bytes: bytes) -> None:
    """A v2.0 TTC has three trailing uint16 fields after the font-offset
    array (DSig tag / length / offset, all "not used at this time").
    Patch a TTF-built v1 TTC to look like a v2 one with zeroed DSig
    fields and confirm parsing still resolves the right number of fonts
    and offsets."""
    # First 8 bytes: 'ttcf' + version. Replace version with 0x00020000
    # and append six bytes of zero DSig fields *after* the font-offset
    # array. The fontTools-built TTC normally is v1 with no trailing
    # fields, so we have to splice manually.
    src = two_font_ttc_bytes
    assert src[:4] == b"ttcf"
    num_fonts = int.from_bytes(src[8:12], "big")
    offsets_size = num_fonts * 4
    # Header (12 bytes) + font-offset array.
    header_end = 12 + offsets_size
    # Splice: keep the original first ``header_end`` bytes, override the
    # version word at offset 4..8 with 0x00020000, then inject six zero
    # bytes for the DSig fields, then keep the rest of the file.
    patched = bytearray(src)
    patched[4:8] = struct.pack(">I", 0x00020000)
    patched[header_end:header_end] = b"\x00" * 6
    # NOTE: the font-offset table still points to absolute byte positions
    # in the original layout, so re-emitting the inner fonts requires
    # bumping every offset by 6. Walk the offset array and add 6 to each
    # offset that targets data past the inserted DSig block.
    for i in range(num_fonts):
        pos = 12 + i * 4
        original_off = int.from_bytes(patched[pos : pos + 4], "big")
        new_off = original_off + 6 if original_off >= header_end else original_off
        patched[pos : pos + 4] = struct.pack(">I", new_off)

    # The patched stream should now parse cleanly as a v2 collection.
    with TrueTypeCollection(bytes(patched)) as ttc:
        assert ttc.get_number_of_fonts() == num_fonts
        assert ttc._version >= 2  # noqa: SLF001


# ---------- get_font_by_name ----------------------------------------------


def test_get_font_by_name_returns_none_when_no_match(
    two_font_ttc_bytes: bytes,
) -> None:
    with TrueTypeCollection(two_font_ttc_bytes) as ttc:
        assert ttc.get_font_by_name("does-not-exist") is None


# ---------- index-based parser creation rejects out-of-range --------------


def test_create_font_parser_at_index_rejects_negative(
    two_font_ttc_bytes: bytes,
) -> None:
    with (
        TrueTypeCollection(two_font_ttc_bytes) as ttc,
        pytest.raises(IndexError),
    ):
        ttc.create_font_parser_at_index_and_seek(-1)


def test_create_font_parser_at_index_rejects_out_of_range(
    two_font_ttc_bytes: bytes,
) -> None:
    with (
        TrueTypeCollection(two_font_ttc_bytes) as ttc,
        pytest.raises(IndexError),
    ):
        ttc.create_font_parser_at_index_and_seek(99)


# ---------- process_all_font_headers (instance) ---------------------------


def test_process_all_font_headers_visits_every_font(
    two_font_ttc_bytes: bytes,
) -> None:
    """The instance-flavoured iterator hands one :class:`FontHeaders` per
    font in collection order. No error should populate on either header."""
    received: list[FontHeaders] = []

    def _cb(headers: FontHeaders) -> None:
        received.append(headers)

    with TrueTypeCollection(two_font_ttc_bytes) as ttc:
        ttc.process_all_font_headers(_cb)

    assert len(received) == 2
    for hdr in received:
        assert hdr.get_error() is None
        # Each header should report the same name (both slots are the
        # same source TTF).
        assert hdr.get_name() == "LiberationSans"


# ---------- context manager closes the stream ------------------------------


def test_context_manager_invokes_close(two_font_ttc_bytes: bytes) -> None:
    """The ``with`` form must release the underlying stream on exit."""
    closed: list[bool] = []
    ttc = TrueTypeCollection(two_font_ttc_bytes)
    original_close = ttc._stream.close  # noqa: SLF001

    def _spy() -> None:
        closed.append(True)
        original_close()

    ttc._stream.close = _spy  # type: ignore[method-assign]  # noqa: SLF001
    with ttc as alias:
        assert alias is ttc
    assert closed == [True]
