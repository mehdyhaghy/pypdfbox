"""Hand-written tests for
:class:`pypdfbox.fontbox.cff.cff_parser.CFFParser`.

The parser is a thin shim over fontTools'
``CFFFontSet.decompile``. Tests cover:

  * the ``parse(bytes)`` overload (upstream
    ``CFFParser.parse(byte[], ByteSource)``, ``CFFParser.java`` lines
    78-83);
  * the ``parse(byte_source)`` overload (upstream
    ``CFFParser.parse(RandomAccessRead)`` on lines 92-107) via a
    duck-typed ByteSource object;
  * OTF wrapper stripping (upstream ``createTaggedCFFDataInput``,
    ``CFFParser.java`` lines 222-248);
  * rejection of TrueType containers (upstream ``skipHeader``,
    ``CFFParser.java`` lines 168-180);
  * the post-parse subtype dispatch (CFFType1Font for name-keyed,
    CFFCIDFont for ROS-bearing fonts).

Parsing tests are gated on a real OTF being available on the host;
when no fixture is available the tests are skipped cleanly.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font

# Candidate locations for a Type 1-flavoured (name-keyed) CFF OTF.
_TYPE1_OTF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/STIXGeneral.otf",
    "/System/Library/Fonts/Supplemental/STIXGeneralItalic.otf",
    "/usr/share/fonts/opentype/stix/STIXGeneral.otf",
]


def _load_type1_cff_bytes() -> tuple[bytes, bytes] | None:
    """Return ``(otf_bytes, raw_cff_bytes)`` for the first available
    name-keyed CFF OTF on the host, or ``None`` if no fixture is
    available."""
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415
    except ImportError:
        return None
    for candidate in _TYPE1_OTF_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            otf_bytes = path.read_bytes()
            ttf = TTFont(io.BytesIO(otf_bytes))
            if "CFF " not in ttf:
                continue
            top = ttf["CFF "].cff[ttf["CFF "].cff.fontNames[0]]
            if hasattr(top, "ROS"):
                # Skip CID-keyed candidates here.
                continue
            buf = io.BytesIO()
            ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
            return otf_bytes, buf.getvalue()
        except Exception:  # noqa: BLE001
            continue
    return None


_FIXTURE = _load_type1_cff_bytes()
_SKIP_REASON = "no name-keyed CFF/OTF fixture available on this host"


# -- Repr / construction ------------------------------------------------


def test_parser_construction_does_not_parse() -> None:
    parser = CFFParser()
    assert parser._source is None
    assert parser._debug_font_name is None


def test_parser_to_string_pre_parse() -> None:
    parser = CFFParser()
    rep = parser.to_string()
    assert rep == "CFFParser[None]"
    assert repr(parser) == rep


# -- Empty / malformed input -------------------------------------------


def test_parse_empty_bytes_raises() -> None:
    parser = CFFParser()
    with pytest.raises(Exception):  # noqa: B017, PT011
        # fontTools surfaces this as struct.error / IndexError; we
        # accept any exception — upstream raises IOException.
        parser.parse(b"")


def test_parse_rejects_ttcf_container() -> None:
    parser = CFFParser()
    payload = b"ttcf" + b"\x00" * 32
    with pytest.raises(OSError, match="True Type Collection"):
        parser.parse(payload)


def test_parse_rejects_ttf_container() -> None:
    parser = CFFParser()
    payload = b"\x00\x01\x00\x00" + b"\x00" * 32
    with pytest.raises(OSError, match="OpenType fonts containing a true type"):
        parser.parse(payload)


def test_parse_rejects_otf_without_cff_table() -> None:
    parser = CFFParser()
    # Build a minimal OTF directory with one fake table (not "CFF ").
    header = b"OTTO" + struct.pack(">HHHH", 1, 0, 0, 0)
    record = b"abcd" + struct.pack(">III", 0, 0, 0)
    with pytest.raises(OSError, match="CFF tag not found"):
        parser.parse(header + record)


# -- Real-font parsing (gated) -----------------------------------------


@pytest.mark.skipif(_FIXTURE is None, reason=_SKIP_REASON)
def test_parse_raw_cff_bytes_returns_one_font() -> None:
    assert _FIXTURE is not None
    _, cff_bytes = _FIXTURE
    parser = CFFParser()
    fonts = parser.parse(cff_bytes)
    assert len(fonts) >= 1
    font = fonts[0]
    assert isinstance(font, CFFType1Font)
    assert font.get_name()  # non-empty
    # set_data should have been called with the inner CFF payload.
    assert font.get_data() == cff_bytes


@pytest.mark.skipif(_FIXTURE is None, reason=_SKIP_REASON)
def test_parse_otf_strips_wrapper() -> None:
    assert _FIXTURE is not None
    otf_bytes, _ = _FIXTURE
    parser = CFFParser()
    fonts = parser.parse(otf_bytes)
    assert len(fonts) >= 1
    # The font's ``get_data`` returns the inner CFF table bytes —
    # they must be CFF major version 1 (first byte) and shorter than
    # the wrapping OTF.
    inner = fonts[0].get_data()
    assert inner[:1] == b"\x01"
    assert len(inner) < len(otf_bytes)
    # And the parsed font should expose a real PostScript name.
    assert fonts[0].get_name()


@pytest.mark.skipif(_FIXTURE is None, reason=_SKIP_REASON)
def test_parse_via_byte_source_object() -> None:
    """The :class:`ByteSource` overload — pass an object whose
    ``get_bytes()`` returns the payload (mirrors
    ``CFFParser.parse(RandomAccessRead)``,
    ``CFFParser.java`` lines 92-107)."""
    assert _FIXTURE is not None
    _, cff_bytes = _FIXTURE

    class _Source:
        def get_bytes(self) -> bytes:
            return cff_bytes

    parser = CFFParser()
    fonts = parser.parse(_Source())
    assert len(fonts) >= 1
    assert isinstance(fonts[0], CFFType1Font)


@pytest.mark.skipif(_FIXTURE is None, reason=_SKIP_REASON)
def test_parser_to_string_after_parse() -> None:
    assert _FIXTURE is not None
    _, cff_bytes = _FIXTURE
    parser = CFFParser()
    fonts = parser.parse(cff_bytes)
    name = fonts[-1].get_name()
    assert parser.to_string() == f"CFFParser[{name}]"


# -- CID-keyed dispatch (gated) ----------------------------------------


_CID_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def _load_cid_cff_bytes() -> bytes | None:
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415
    except ImportError:
        return None
    for candidate in _CID_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            for index in range(8):
                ttf = TTFont(str(path), fontNumber=index)
                if "CFF " not in ttf:
                    continue
                top = ttf["CFF "].cff[ttf["CFF "].cff.fontNames[0]]
                if not hasattr(top, "ROS"):
                    continue
                buf = io.BytesIO()
                ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
                return buf.getvalue()
        except Exception:  # noqa: BLE001
            continue
    return None


_CID_CFF = _load_cid_cff_bytes()


@pytest.mark.skipif(_CID_CFF is None, reason="no CID-keyed CFF fixture available")
def test_parse_cid_keyed_returns_cidfont() -> None:
    assert _CID_CFF is not None
    parser = CFFParser()
    fonts = parser.parse(_CID_CFF)
    assert len(fonts) == 1
    assert isinstance(fonts[0], CFFCIDFont)
    assert fonts[0].is_cid_font()
