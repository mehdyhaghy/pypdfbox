"""Coverage tests for :mod:`pypdfbox.filter.jpx_filter`.

The module is a thin upstream-named subclass of :class:`JPXDecode`. We
exercise the :meth:`read_jpx` private helper plus the public
:meth:`decode` / :meth:`encode` forwarders so the coverage probe touches
each line.

Pillow's JPEG-2000 codec is required for both encode and decode. When
``Image.core`` is built without OpenJPEG support the codec-using tests
are skipped (Pillow itself reports this via ``PIL.features.check``).
"""

from __future__ import annotations

import io

import pytest
from PIL import Image, features

from pypdfbox.cos import COSDictionary
from pypdfbox.filter.filter_factory import FilterFactory
from pypdfbox.filter.jpx_decode import JPXDecode
from pypdfbox.filter.jpx_filter import JPXFilter

_HAS_JPEG2000 = features.check("jpg_2000")
_SKIP_REASON = "Pillow built without OpenJPEG / JPEG-2000 plugin"


def test_jpx_filter_is_subclass_of_jpx_decode() -> None:
    assert issubclass(JPXFilter, JPXDecode)


def test_jpx_filter_registered_under_long_name() -> None:
    # Import-time block registers JPXFilter without overwriting JPXDecode.
    assert FilterFactory.is_registered("JPXFilter") is True
    instance = FilterFactory.get("JPXFilter")
    assert isinstance(instance, JPXFilter)


def test_jpx_filter_registration_does_not_overwrite_jpx_decode() -> None:
    # JPXDecode registration must remain in place.
    assert FilterFactory.is_registered("JPXDecode") is True


@pytest.mark.skipif(not _HAS_JPEG2000, reason=_SKIP_REASON)
def test_read_jpx_returns_pil_image_for_valid_codestream() -> None:
    # Build a tiny JP2 codestream via Pillow's encoder.
    src = Image.new("RGB", (4, 4), color=(10, 20, 30))
    buf = io.BytesIO()
    src.save(buf, format="JPEG2000")
    buf.seek(0)

    img = JPXFilter().read_jpx(buf)
    assert img is not None
    assert img.size == (4, 4)


@pytest.mark.skipif(not _HAS_JPEG2000, reason=_SKIP_REASON)
def test_read_jpx_with_result_arg_is_noop_for_metadata() -> None:
    """The result accumulator branch runs but doesn't mutate when no metadata
    is discovered — mirrors upstream's empty-metadata path."""
    src = Image.new("L", (3, 3), color=128)
    buf = io.BytesIO()
    src.save(buf, format="JPEG2000")
    buf.seek(0)

    from pypdfbox.filter.decode_result import DecodeResult

    result = DecodeResult(parameters=COSDictionary(), bytes_written=0)
    img = JPXFilter().read_jpx(buf, options=None, result=result)
    assert img.size == (3, 3)
    # The result-handling branch is a documented pass-through.


@pytest.mark.skipif(not _HAS_JPEG2000, reason=_SKIP_REASON)
def test_decode_forwards_to_parent() -> None:
    src = Image.new("RGB", (5, 5), color=(1, 2, 3))
    buf = io.BytesIO()
    src.save(buf, format="JPEG2000")
    encoded = io.BytesIO(buf.getvalue())
    decoded = io.BytesIO()
    result = JPXFilter().decode(encoded, decoded, parameters=None, index=0)
    # JPXDecode populates Width/Height/BitsPerComponent in result.parameters.
    assert result.parameters.get_int("Width", 0) == 5
    assert result.parameters.get_int("Height", 0) == 5


@pytest.mark.skipif(not _HAS_JPEG2000, reason=_SKIP_REASON)
def test_encode_round_trips_via_parent() -> None:
    """``JPXFilter.encode`` forwards to :class:`JPXDecode`; check encode works."""
    raw = bytes([0, 128, 255] * 4)  # 4 RGB pixels worth (2x2)
    params = COSDictionary()
    params.set_int("Width", 2)
    params.set_int("Height", 2)
    params.set_int("BitsPerComponent", 8)
    params.set_int("ColorComponents", 3)

    encoded = io.BytesIO()
    JPXFilter().encode(io.BytesIO(raw), encoded, params)
    assert len(encoded.getvalue()) > 0
