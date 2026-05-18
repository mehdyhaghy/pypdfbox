"""Coverage-boost tests for
``pypdfbox.pdmodel.graphics.image.png_converter`` (wave 1349).

Pre-wave: 96.9% line coverage (228 stmts, 7 missing). Missing lines map to:

* 90-91: ``convert_png_image`` falls through to ``return None`` when the
  Pillow / ``LosslessFactory`` import fails (rare on real installs but
  the upstream-parity behaviour must be exercised);
* 271, 273, 275, 277, 279: ``parse_png_chunks`` populates the
  ``state.iccp / .trns / .srgb / .gama / .chrm`` slots when an ancillary
  PNG chunk of the corresponding type is encountered.

To hit the chunk branches without round-tripping a real PNG through
Pillow's encoder (which does not emit iCCP / sRGB / gAMA / cHRM unless
explicitly configured), the tests build hand-crafted PNG byte streams.
The CRC is *not* validated by ``parse_png_chunks`` (only by
``check_chunk_sane``), so the constructed chunks can use ``crc=0``.
"""

from __future__ import annotations

import builtins
import sys

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.image.png_converter import PNGConverter

# ---- helpers ---------------------------------------------------------------


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk: length + type + data + (zero) CRC.

    The parser ignores the CRC value at chunk-walk time, so the trailing
    four bytes can be zeros.
    """
    return len(data).to_bytes(4, "big") + chunk_type + data + b"\x00\x00\x00\x00"


def _make_ihdr_chunk(
    width: int = 1,
    height: int = 1,
    bit_depth: int = 8,
    color_type: int = 2,  # RGB
) -> bytes:
    payload = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([bit_depth, color_type, 0, 0, 0])
    )
    return _make_chunk(b"IHDR", payload)


_IEND_CHUNK = _make_chunk(b"IEND", b"")


# ---- line 271: iCCP chunk --------------------------------------------------


def test_parse_png_chunks_records_iccp_chunk() -> None:
    """An iCCP chunk after IHDR must populate ``state.iccp``."""
    blob = (
        _PNG_MAGIC
        + _make_ihdr_chunk()
        # iCCP payload: profile-name + null + compression-method + compressed bytes.
        + _make_chunk(b"iCCP", b"name\x00\x00fakeprofile")
        + _IEND_CHUNK
    )
    state = PNGConverter.parse_png_chunks(blob)
    assert state is not None
    assert state.iccp is not None
    assert state.iccp.get_data() == b"name\x00\x00fakeprofile"


# ---- line 273: tRNS chunk --------------------------------------------------


def test_parse_png_chunks_records_trns_chunk() -> None:
    """A tRNS chunk encodes alpha-channel transparency for non-alpha image
    types (greyscale / RGB / indexed). The parser stashes it for later
    inspection by ``build_transparency_mask_from_indexed_data``."""
    blob = (
        _PNG_MAGIC
        + _make_ihdr_chunk(color_type=3)  # indexed
        + _make_chunk(b"tRNS", b"\xff\x80\x00")
        + _IEND_CHUNK
    )
    state = PNGConverter.parse_png_chunks(blob)
    assert state is not None
    assert state.trns is not None
    assert state.trns.get_data() == b"\xff\x80\x00"


# ---- line 275: sRGB chunk --------------------------------------------------


def test_parse_png_chunks_records_srgb_chunk() -> None:
    """An sRGB chunk carries a single rendering-intent byte (0..3)."""
    blob = (
        _PNG_MAGIC
        + _make_ihdr_chunk()
        + _make_chunk(b"sRGB", b"\x01")  # rendering intent: 1 = relative colorimetric
        + _IEND_CHUNK
    )
    state = PNGConverter.parse_png_chunks(blob)
    assert state is not None
    assert state.srgb is not None
    assert state.srgb.get_data() == b"\x01"


# ---- line 277: gAMA chunk --------------------------------------------------


def test_parse_png_chunks_records_gama_chunk() -> None:
    """A gAMA chunk encodes one 4-byte big-endian fixed-point gamma value
    (image gamma * 100000)."""
    payload = (45455).to_bytes(4, "big")  # 0.45455 — sRGB-ish gamma
    blob = (
        _PNG_MAGIC
        + _make_ihdr_chunk()
        + _make_chunk(b"gAMA", payload)
        + _IEND_CHUNK
    )
    state = PNGConverter.parse_png_chunks(blob)
    assert state is not None
    assert state.gama is not None
    assert state.gama.get_data() == payload


# ---- line 279: cHRM chunk --------------------------------------------------


def test_parse_png_chunks_records_chrm_chunk() -> None:
    """A cHRM chunk encodes eight 4-byte fixed-point values describing the
    primaries + whitepoint chromaticities (32 bytes total)."""
    payload = b"\x00" * 32
    blob = (
        _PNG_MAGIC
        + _make_ihdr_chunk()
        + _make_chunk(b"cHRM", payload)
        + _IEND_CHUNK
    )
    state = PNGConverter.parse_png_chunks(blob)
    assert state is not None
    assert state.chrm is not None
    assert state.chrm.get_data() == payload


# ---- bonus: all ancillary chunks in one go ---------------------------------


def test_parse_png_chunks_collects_all_ancillary_chunks_in_one_pass() -> None:
    """A PNG with iCCP + tRNS + sRGB + gAMA + cHRM all present must
    populate every slot (no early break)."""
    blob = (
        _PNG_MAGIC
        + _make_ihdr_chunk()
        + _make_chunk(b"iCCP", b"x\x00\x00y")
        + _make_chunk(b"tRNS", b"\xaa")
        + _make_chunk(b"sRGB", b"\x00")
        + _make_chunk(b"gAMA", b"\x00\x00\x00\x01")
        + _make_chunk(b"cHRM", b"\x00" * 32)
        + _IEND_CHUNK
    )
    state = PNGConverter.parse_png_chunks(blob)
    assert state is not None
    assert state.iccp is not None
    assert state.trns is not None
    assert state.srgb is not None
    assert state.gama is not None
    assert state.chrm is not None


# ---- lines 90-91: convert_png_image ImportError fall-through ---------------


def test_convert_png_image_returns_none_when_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the lazy ``PIL`` / ``LosslessFactory`` import inside
    ``convert_png_image`` fails, the helper must return ``None`` rather
    than propagating the ``ImportError`` to callers."""
    real_import = builtins.__import__

    def _raising_import(
        name: str,
        globals_: object = None,
        locals_: object = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "PIL" or name.endswith(".lossless_factory"):
            raise ImportError(f"forced import failure for {name!r}")
        return real_import(name, globals_, locals_, fromlist, level)

    # Drop cached modules so the patched __import__ runs.
    for mod_name in list(sys.modules):
        if mod_name == "PIL" or mod_name.endswith(".lossless_factory"):
            monkeypatch.delitem(sys.modules, mod_name, raising=False)

    monkeypatch.setattr(builtins, "__import__", _raising_import)
    doc = PDDocument()
    try:
        result = PNGConverter.convert_png_image(doc, b"\x89PNG\r\n\x1a\nignored")
        assert result is None
    finally:
        doc.close()


def test_convert_png_image_returns_none_when_only_lossless_factory_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same fall-through path, this time with PIL importable but
    ``lossless_factory`` raising. Confirms the ``except ImportError`` block
    catches the second import too."""
    real_import = builtins.__import__

    def _raising_import(
        name: str,
        globals_: object = None,
        locals_: object = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name.endswith("lossless_factory"):
            raise ImportError(f"forced lossless_factory import failure: {name!r}")
        if fromlist and "LosslessFactory" in fromlist:
            raise ImportError("forced LosslessFactory symbol import failure")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.delitem(
        sys.modules, "pypdfbox.pdmodel.graphics.image.lossless_factory", raising=False,
    )
    monkeypatch.setattr(builtins, "__import__", _raising_import)

    doc = PDDocument()
    try:
        result = PNGConverter.convert_png_image(doc, b"\x89PNG\r\n\x1a\nignored")
        assert result is None
    finally:
        doc.close()
