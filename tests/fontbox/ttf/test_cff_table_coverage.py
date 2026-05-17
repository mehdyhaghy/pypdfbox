"""Coverage-boost tests for
:class:`pypdfbox.fontbox.ttf.cff_table.CFFTable`.

These tests target the byte-source re-read helper, the full :meth:`read`
dispatch onto :class:`CFFParser`, and the fast :meth:`read_headers` path
that surfaces ROS metadata without a full font decode. They mirror the
approach used by ``tests/fontbox/cff/test_cff_parser_coverage.py``
(wave 1314): build a minimal CFF payload with :mod:`fontTools` so the
parser end-to-end gets exercised without a system-font fixture.
"""

from __future__ import annotations

import io
import struct

import pytest

from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.ttf.cff_table import CFFTable, _CFFByteSource
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

# ---------------------------------------------------------------------
# Test fixtures — minimal CFF payload + stub host font for the
# byte-source re-read helper.
# ---------------------------------------------------------------------


def _build_minimal_cff_bytes() -> bytes:
    """Construct a minimal Type 1-flavoured CFF byte stream using
    fontTools' :class:`FontBuilder` so the parser end-to-end gets
    exercised without depending on a system font fixture.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString

    fb = FontBuilder(1000, isTTF=False)
    glyph_order = [".notdef", "A"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({ord("A"): "A"})
    cs_notdef = T2CharString()
    cs_notdef.program = ["endchar"]
    cs_a = T2CharString()
    cs_a.program = ["endchar"]
    fb.setupCFF(
        psName="CovTestFont",
        fontInfo={"FullName": "Cov Test Font", "FamilyName": "Cov Test"},
        charStringsDict={".notdef": cs_notdef, "A": cs_a},
        privateDict={},
    )
    buf = io.BytesIO()
    fb.font["CFF "].cff.compile(buf, fb.font, isCFF2=False)
    return buf.getvalue()


_BUILT_CFF: bytes | None
try:
    _BUILT_CFF = _build_minimal_cff_bytes()
except Exception:  # noqa: BLE001
    _BUILT_CFF = None


class _FakeTable:
    """Stand-in for a TTFTable entry inside a host font's table map."""

    def __init__(self, tag: str = CFFTable.TAG) -> None:
        self._tag = tag

    def get_tag(self) -> str:
        return self._tag


class _StubTrueTypeFont:
    """Minimal :class:`TrueTypeFont` stand-in for byte-source re-read.

    Mirrors the surface ``_CFFByteSource`` reaches for:
    :meth:`get_table_map` and :meth:`get_table_bytes`. We avoid spinning
    up a full OpenType font because the byte-source contract is narrow.
    """

    def __init__(
        self,
        payload: bytes | None,
        *,
        include_cff: bool = True,
        bytes_to_return: bytes | None | bytearray = None,
    ) -> None:
        self._payload = payload
        self._include_cff = include_cff
        self._bytes_to_return = bytes_to_return

    def get_table_map(self) -> dict[str, object]:
        if not self._include_cff:
            return {}
        return {CFFTable.TAG: _FakeTable()}

    def get_table_bytes(self, table: object) -> bytes | None:  # noqa: ARG002
        return self._bytes_to_return


# ---------------------------------------------------------------------
# Module-level constants + tag mirror.
# ---------------------------------------------------------------------


def test_cff_table_tag_includes_trailing_space() -> None:
    # The OpenType SFNT tag is literally four bytes with a trailing
    # space — verify the surfaced constant carries it.
    assert CFFTable.TAG == "CFF "
    assert len(CFFTable.TAG) == 4


# ---------------------------------------------------------------------
# _CFFByteSource — covers the missing 46-50 lines.
# ---------------------------------------------------------------------


def test_cff_byte_source_returns_table_bytes() -> None:
    payload = b"PRETEND-CFF-BYTES"
    ttf = _StubTrueTypeFont(payload, bytes_to_return=payload)
    src = _CFFByteSource(ttf)  # type: ignore[arg-type]
    assert src.get_bytes() == payload


def test_cff_byte_source_returns_empty_when_table_missing() -> None:
    ttf = _StubTrueTypeFont(None, include_cff=False)
    src = _CFFByteSource(ttf)  # type: ignore[arg-type]
    assert src.get_bytes() == b""


def test_cff_byte_source_returns_empty_when_bytes_none() -> None:
    # Table present but the host font cannot materialise its bytes.
    ttf = _StubTrueTypeFont(None, include_cff=True, bytes_to_return=None)
    src = _CFFByteSource(ttf)  # type: ignore[arg-type]
    assert src.get_bytes() == b""


def test_cff_byte_source_coerces_bytearray() -> None:
    # ``get_table_bytes`` may return a mutable bytearray (raw I/O buffer).
    # The source must coerce it so downstream consumers get immutable bytes.
    payload = bytearray(b"ABCDEFG")
    ttf = _StubTrueTypeFont(None, include_cff=True, bytes_to_return=payload)
    src = _CFFByteSource(ttf)  # type: ignore[arg-type]
    out = src.get_bytes()
    assert out == b"ABCDEFG"
    assert isinstance(out, bytes)


# ---------------------------------------------------------------------
# CFFTable.read() — full decode round-trip.
# ---------------------------------------------------------------------


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_read_decodes_cff_payload_into_font() -> None:
    assert _BUILT_CFF is not None
    table = CFFTable()
    table.set_length(len(_BUILT_CFF))
    ttf = _StubTrueTypeFont(_BUILT_CFF, bytes_to_return=_BUILT_CFF)
    data = MemoryTTFDataStream(_BUILT_CFF)
    table.read(ttf, data)  # type: ignore[arg-type]
    font = table.get_font()
    assert font is not None
    assert isinstance(font, CFFType1Font)
    assert font.get_name() == "CovTestFont"
    assert table.initialized is True


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_get_font_returns_none_before_read() -> None:
    table = CFFTable()
    assert table.get_font() is None
    assert table.initialized is False


# ---------------------------------------------------------------------
# CFFTable.read_headers() — covers the missing 115-147 block, both
# branches (create_sub_view hit + fallback).
# ---------------------------------------------------------------------


class _StubHeaders:
    """Minimal :class:`FontHeaders` capture used by parse_first_sub_font_ros."""

    def __init__(self) -> None:
        self.error: str | None = None
        self.ros: tuple[str | None, str | None, int | None] | None = None

    def set_error(self, msg: str) -> None:
        self.error = msg

    def set_otf_ros(
        self, registry: str | None, ordering: str | None, supplement: int | None
    ) -> None:
        self.ros = (registry, ordering, supplement)


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_read_headers_uses_create_sub_view_branch() -> None:
    # MemoryTTFDataStream.create_sub_view always returns a usable view;
    # this exercises the "sub_view is not None" branch of ``read_headers``.
    assert _BUILT_CFF is not None
    table = CFFTable()
    table.set_length(len(_BUILT_CFF))
    headers = _StubHeaders()
    data = MemoryTTFDataStream(_BUILT_CFF)
    ttf = _StubTrueTypeFont(_BUILT_CFF, bytes_to_return=_BUILT_CFF)
    table.read_headers(ttf, data, headers)  # type: ignore[arg-type]
    # Built font is name-keyed (no ROS) → no error and no ROS set.
    assert headers.error is None
    assert headers.ros is None


class _NoSubViewTTFDataStream(MemoryTTFDataStream):
    """Force the fallback branch in ``CFFTable.read_headers``.

    Mirrors the upstream comment "``assert false`` upstream — inefficient
    because we copy bytes — but we still need to parse them." This stream
    declines to hand out a sub-view, sending control through the
    ``RandomAccessReadBuffer`` copy path.
    """

    def create_sub_view(self, length: int) -> None:  # noqa: ARG002
        return None


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_read_headers_falls_back_when_no_sub_view() -> None:
    assert _BUILT_CFF is not None
    table = CFFTable()
    table.set_length(len(_BUILT_CFF))
    headers = _StubHeaders()
    data = _NoSubViewTTFDataStream(_BUILT_CFF)
    ttf = _StubTrueTypeFont(_BUILT_CFF, bytes_to_return=_BUILT_CFF)
    table.read_headers(ttf, data, headers)  # type: ignore[arg-type]
    assert headers.error is None
    assert headers.ros is None


def test_read_headers_propagates_parser_error_on_garbage_payload() -> None:
    # A "ttcf" (TrueType Collection) magic forces ``_strip_otf_wrapper``
    # to raise inside ``parse_first_sub_font_ros``, which records the
    # error on the headers stub rather than re-raising. This exercises
    # the read_headers wrapper around the error-capturing branch.
    payload = b"ttcf" + b"\x00" * 32
    table = CFFTable()
    table.set_length(len(payload))
    headers = _StubHeaders()
    data = MemoryTTFDataStream(payload)
    ttf = _StubTrueTypeFont(payload, bytes_to_return=payload)
    table.read_headers(ttf, data, headers)  # type: ignore[arg-type]
    assert headers.error is not None
    assert "True Type Collection" in headers.error


# ---------------------------------------------------------------------
# Defensive edge: ``read`` when the CFF parser yields no fonts.
# ---------------------------------------------------------------------


def test_read_handles_empty_parser_output(monkeypatch: pytest.MonkeyPatch) -> None:
    # ``CFFParser.parse`` returning an empty list should leave _cff_font
    # at ``None`` (mirrors the upstream ``fonts[0] if fonts else None``).
    from pypdfbox.fontbox.cff import cff_parser as cff_parser_mod

    class _EmptyParser:
        def parse(self, _payload: bytes, _source: object) -> list[object]:
            return []

    monkeypatch.setattr(cff_parser_mod, "CFFParser", _EmptyParser)
    table = CFFTable()
    payload = b"unused-by-stub-parser"
    table.set_length(len(payload))
    data = MemoryTTFDataStream(payload)
    ttf = _StubTrueTypeFont(payload, bytes_to_return=payload)
    table.read(ttf, data)  # type: ignore[arg-type]
    assert table.get_font() is None
    assert table.initialized is True


# ---------------------------------------------------------------------
# Sanity: the OTF-wrapped CFF payload also round-trips through read().
# ---------------------------------------------------------------------


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_read_handles_otf_wrapped_payload() -> None:
    # Wrap the raw CFF inside a minimal OTF table directory — the parser
    # strips the wrapper, the CFF table accessor inside the wrapper
    # surfaces the same first font.
    assert _BUILT_CFF is not None
    inner = _BUILT_CFF
    header = b"OTTO" + struct.pack(">HHHH", 1, 0, 0, 0)
    cff_offset = 12 + 16
    record = b"CFF " + struct.pack(">I", 0) + struct.pack(
        ">II", cff_offset, len(inner)
    )
    otf = header + record + inner

    table = CFFTable()
    table.set_length(len(otf))
    data = MemoryTTFDataStream(otf)
    ttf = _StubTrueTypeFont(otf, bytes_to_return=otf)
    table.read(ttf, data)  # type: ignore[arg-type]
    font = table.get_font()
    assert font is not None
    assert font.get_name() == "CovTestFont"
