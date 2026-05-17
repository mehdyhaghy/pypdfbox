"""Wave 1347 coverage boost for ``pypdfbox.filter.dct_decode``.

Targets the residual Pillow-fallback mode branches not exercised by
``test_dct_decode``/``test_dct_filter``/``test_ccitt_dct_filters_wave695``:

- Pillow fallback ``mode == "L"`` (line 86) — single-band luma JPEG.
- Pillow fallback ``mode == "CMYK"`` (line 88) — 4-component CMYK JPEG.
- Pillow fallback ``mode == "RGB"`` (line 90) — 3-component RGB JPEG.

The fallback is engaged by forcing the primary ``imagecodecs.jpeg8_decode``
path to raise, then handing :class:`DCTDecode` a freshly-encoded JPEG
in each colour mode.

Pre-wave the module sat at 94.1 % (3 missing); this set takes it to
100 %.
"""

from __future__ import annotations

import io

import numpy as _np_preload  # noqa: F401  pre-import: see test_aggdraw_compat_coverage.py
import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import dct_decode as dct_decode_module
from pypdfbox.filter.dct_decode import DCTDecode


def _encode_jpeg(mode: str, size: tuple[int, int] = (4, 4)) -> bytes:
    img = Image.new(mode, size)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def force_pillow_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the primary ``imagecodecs.jpeg8_decode`` path raise so
    ``DCTDecode.decode`` falls through to the Pillow branch."""

    def _raise(_data: bytes) -> object:
        raise RuntimeError("force fallback")

    monkeypatch.setattr(dct_decode_module.imagecodecs, "jpeg8_decode", _raise)


# ---------------------------------------------------------------------------
# Pillow fallback mode coverage
# ---------------------------------------------------------------------------
def test_pillow_fallback_mode_l(force_pillow_fallback: None) -> None:
    """Line 86: ``mode == "L"`` → ``num_components, bpc = 1, 8``."""
    encoded = _encode_jpeg("L")
    out = io.BytesIO()
    params = COSDictionary()
    DCTDecode().decode(io.BytesIO(encoded), out, params, 0)
    assert params.get_int("ColorComponents") == 1
    assert params.get_int("BitsPerComponent") == 8
    assert params.get_int("Width") == 4
    assert params.get_int("Height") == 4
    # 4x4 single-band = 16 bytes of samples
    assert len(out.getvalue()) == 16


def test_pillow_fallback_mode_cmyk(force_pillow_fallback: None) -> None:
    """Line 88: ``mode == "CMYK"`` → ``num_components, bpc = 4, 8``."""
    encoded = _encode_jpeg("CMYK")
    out = io.BytesIO()
    params = COSDictionary()
    DCTDecode().decode(io.BytesIO(encoded), out, params, 0)
    assert params.get_int("ColorComponents") == 4
    assert params.get_int("BitsPerComponent") == 8
    assert params.get_int("Width") == 4
    assert params.get_int("Height") == 4
    assert len(out.getvalue()) == 4 * 4 * 4  # 4x4 pixels x 4 channels


def test_pillow_fallback_mode_rgb(force_pillow_fallback: None) -> None:
    """Line 90: ``mode == "RGB"`` → ``num_components, bpc = 3, 8``."""
    encoded = _encode_jpeg("RGB")
    out = io.BytesIO()
    params = COSDictionary()
    DCTDecode().decode(io.BytesIO(encoded), out, params, 0)
    assert params.get_int("ColorComponents") == 3
    assert params.get_int("BitsPerComponent") == 8
    assert params.get_int("Width") == 4
    assert params.get_int("Height") == 4
    assert len(out.getvalue()) == 4 * 4 * 3  # 4x4 pixels x 3 channels


# ---------------------------------------------------------------------------
# Negative: Pillow ``Image.open`` also raises → wrapped as OSError
# ---------------------------------------------------------------------------
def test_pillow_fallback_propagates_decode_failure_as_oserror(
    force_pillow_fallback: None,
) -> None:
    """Both decoders refuse → upstream-parity wrapping in ``OSError``."""
    with pytest.raises(OSError, match="DCTDecode: JPEG decode failed"):
        DCTDecode().decode(io.BytesIO(b"not a jpeg"), io.BytesIO(), COSDictionary(), 0)
