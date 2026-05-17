"""Coverage-boost tests for ``JPXDecode`` (wave 1323).

Targets the residual missing branches in ``pypdfbox.filter.jpx_decode``:

* ``_mode_components_and_bpc`` for the 1-bit ``"1"`` mode plus the
  unknown-mode fallback.
* ``_encode_mode_for`` for RGB / CMYK / L / I;16 returns and the
  raise on unsupported component counts.
* ``encode()`` width/height guard, ``ColorComponents`` inference failure,
  raw-raster-too-short guard, and the OpenJPEG encode failure path.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import JPXDecode
from pypdfbox.filter.jpx_decode import _encode_mode_for, _mode_components_and_bpc

# ---------------------------------------------------------------------------
# _mode_components_and_bpc — minor mode branches
# ---------------------------------------------------------------------------


def test_mode_components_and_bpc_one_bit_mode() -> None:
    """Pillow's ``"1"`` mode is treated as 1 component, 1 bpc — rare for
    JPX but exercised so the spec-edge branch (line 26) is covered."""
    assert _mode_components_and_bpc("1", ("1",)) == (1, 1)


def test_mode_components_and_bpc_unknown_mode_falls_back_to_band_count() -> None:
    """An unrecognised Pillow mode falls back to ``(len(bands), 8)`` — the
    final ``return`` on line 27."""
    assert _mode_components_and_bpc("YCbCr", ("Y", "Cb", "Cr")) == (3, 8)


def test_mode_components_and_bpc_l_and_rgb_and_rgba_and_cmyk_and_i16() -> None:
    assert _mode_components_and_bpc("L", ("L",)) == (1, 8)
    assert _mode_components_and_bpc("RGB", ("R", "G", "B")) == (3, 8)
    assert _mode_components_and_bpc("RGBA", ("R", "G", "B", "A")) == (4, 8)
    assert _mode_components_and_bpc("CMYK", ("C", "M", "Y", "K")) == (4, 8)
    assert _mode_components_and_bpc("I;16", ("I",)) == (1, 16)
    assert _mode_components_and_bpc("I;16B", ("I",)) == (1, 16)


# ---------------------------------------------------------------------------
# _encode_mode_for — full branch coverage
# ---------------------------------------------------------------------------


def test_encode_mode_for_one_component_eight_bpc_returns_l() -> None:
    """1 component, 8 bpc → ``"L"`` — covers line 48 fallthrough."""
    assert _encode_mode_for(1, 8) == "L"


def test_encode_mode_for_one_component_sixteen_bpc_returns_i16() -> None:
    assert _encode_mode_for(1, 16) == "I;16"


def test_encode_mode_for_three_components_returns_rgb() -> None:
    assert _encode_mode_for(3, 8) == "RGB"


def test_encode_mode_for_four_components_returns_cmyk() -> None:
    assert _encode_mode_for(4, 8) == "CMYK"


def test_encode_mode_for_invalid_component_count_raises_value_error() -> None:
    """2 / 5 / 6 components don't map to any PDF image XObject shape;
    upstream raises rather than silently producing a spec-illegal stream
    (lines 52-54)."""
    for bad in (0, 2, 5, 6, 7):
        with pytest.raises(ValueError, match="unsupported raster shape"):
            _encode_mode_for(bad, 8)


# ---------------------------------------------------------------------------
# encode() — error arms
# ---------------------------------------------------------------------------


def _params(width: int, height: int, bpc: int, components: int) -> COSDictionary:
    params = COSDictionary()
    params.set_int("Width", width)
    params.set_int("Height", height)
    params.set_int("BitsPerComponent", bpc)
    params.set_int("ColorComponents", components)
    return params


def test_encode_zero_height_raises_oserror() -> None:
    """``/Width`` and ``/Height`` must be positive — covers line 162."""
    params = _params(4, 0, 8, 3)
    with pytest.raises(OSError, match="must be positive"):
        JPXDecode().encode(io.BytesIO(b""), io.BytesIO(), params)


def test_encode_negative_width_raises_oserror() -> None:
    params = _params(-1, 4, 8, 3)
    with pytest.raises(OSError, match="must be positive"):
        JPXDecode().encode(io.BytesIO(b""), io.BytesIO(), params)


def test_encode_cannot_infer_component_count_raises_oserror() -> None:
    """When ``/ColorComponents`` is missing and the raw byte count is not
    divisible by pixels * bytes-per-sample, the inference fails — covers
    lines 184-190."""
    params = COSDictionary()
    params.set_int("Width", 4)
    params.set_int("Height", 4)
    params.set_int("BitsPerComponent", 8)
    # No ColorComponents; raw length 17 isn't a multiple of 4*4*1 = 16.
    with pytest.raises(OSError, match="cannot infer component count"):
        JPXDecode().encode(
            io.BytesIO(b"\x00" * 17), io.BytesIO(), params
        )


def test_encode_infers_component_count_when_divisible() -> None:
    """When ``/ColorComponents`` is missing but the raw byte count is
    divisible, the inferred count is used and encoding succeeds.
    Covers line 190 (the fallthrough assignment) on the happy path."""
    params = COSDictionary()
    params.set_int("Width", 4)
    params.set_int("Height", 4)
    params.set_int("BitsPerComponent", 8)
    # 48 bytes = 4*4*3, infers 3 components.
    encoded = io.BytesIO()
    JPXDecode().encode(io.BytesIO(b"\x00" * 48), encoded, params)
    assert len(encoded.getvalue()) > 0


def test_encode_raw_raster_too_short_raises_oserror() -> None:
    """Buffer shorter than declared geometry — covers lines 193-197."""
    params = _params(4, 4, 8, 3)
    with pytest.raises(OSError, match="raw raster too short"):
        JPXDecode().encode(io.BytesIO(b"\x00" * 10), io.BytesIO(), params)


def test_encode_openjpeg_failure_wraps_into_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Image.save`` failure is re-raised as ``OSError`` with the upstream
    error chained on ``__cause__``. Covers lines 208-209."""
    import pypdfbox.filter.jpx_decode as jmod

    class _FakeImage:
        def save(self, buf: Any, format: str | None = None) -> None:  # noqa: ARG002
            raise RuntimeError("simulated OpenJPEG crash")

    def fake_frombytes(mode: str, size: tuple[int, int], raw: bytes) -> _FakeImage:  # noqa: ARG001
        return _FakeImage()

    monkeypatch.setattr(jmod.Image, "frombytes", fake_frombytes)

    params = _params(4, 4, 8, 3)
    with pytest.raises(OSError, match="OpenJPEG encode failed"):
        JPXDecode().encode(io.BytesIO(b"\x00" * 48), io.BytesIO(), params)


def test_encode_trims_trailing_padding_when_raw_buffer_oversized() -> None:
    """When the raw buffer is *longer* than the declared geometry, the
    encoder trims it to the exact size before handing it to Pillow
    (line 200)."""
    params = _params(2, 2, 8, 1)
    encoded = io.BytesIO()
    # 4 bytes required; pass 10 — the excess must be silently dropped.
    JPXDecode().encode(io.BytesIO(b"\x00\x01\x02\x03" + b"\xff" * 6),
                       encoded, params)
    assert len(encoded.getvalue()) > 0
