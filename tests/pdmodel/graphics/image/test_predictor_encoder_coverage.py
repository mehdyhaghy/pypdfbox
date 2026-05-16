"""Coverage tests for :mod:`pypdfbox.pdmodel.graphics.image.predictor_encoder`.

Targets the small static PNG-filter helpers, the ``encode`` top-level
short-circuit, the row-cost chooser, and the per-pixel ``copy_*``
helpers — the bits of the wave 1286 module that the existing tests
didn't reach.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.graphics.image.predictor_encoder import PredictorEncoder


def _encoder(mode: str = "RGB", width: int = 4, height: int = 3) -> PredictorEncoder:
    return PredictorEncoder(PDDocument(), Image.new(mode, (width, height)))


# ----------------------------------------------------------------------
# encode() — top-level guards (lines 69-78)
# ----------------------------------------------------------------------
def test_encode_rgb_returns_pd_image_x_object() -> None:
    encoder = _encoder("RGB", width=4, height=3)
    result = encoder.encode()
    assert isinstance(result, PDImageXObject)


def test_encode_returns_none_when_image_is_none() -> None:
    encoder = PredictorEncoder(PDDocument(), None)
    encoder.image = None  # type: ignore[assignment]
    encoder.width = 0
    encoder.height = 0
    assert encoder.encode() is None


def test_encode_returns_none_when_width_zero() -> None:
    encoder = _encoder("RGB", width=4, height=3)
    encoder.width = 0
    assert encoder.encode() is None


def test_encode_returns_none_when_height_zero() -> None:
    encoder = _encoder("RGB", width=4, height=3)
    encoder.height = 0
    assert encoder.encode() is None


def test_encode_returns_none_on_lossless_factory_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``LosslessFactory.create_from_image`` raises ``OSError`` /
    ``ValueError`` the encoder swallows it and returns ``None``."""
    from pypdfbox.pdmodel.graphics.image import lossless_factory

    def _boom(*args: object, **kwargs: object) -> object:
        raise OSError("boom")

    monkeypatch.setattr(lossless_factory.LosslessFactory, "create_from_image", _boom)
    encoder = _encoder("RGB")
    assert encoder.encode() is None


def test_encode_returns_none_when_lossless_factory_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive ``ImportError`` branch — when ``.lossless_factory``
    cannot be loaded the encoder returns ``None`` without raising
    (lines 71-72)."""
    import builtins

    real_import = builtins.__import__

    def _filtered_import(name: str, *args: object, **kwargs: object) -> object:
        if name.endswith("lossless_factory") or name == "lossless_factory":
            raise ImportError("simulated lossless_factory absence")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _filtered_import)
    encoder = _encoder("RGB", width=2, height=2)
    assert encoder.encode() is None


# ----------------------------------------------------------------------
# PNG filter helpers (lines 82-106) — exhaustive small-input parity
# ----------------------------------------------------------------------
def test_png_filter_sub_wraps_modulo_256() -> None:
    assert PredictorEncoder.png_filter_sub(10, 3) == 7
    # underflow wraps with byte-mask.
    assert PredictorEncoder.png_filter_sub(3, 10) == (3 - 10) & 0xFF


def test_png_filter_up_wraps_modulo_256() -> None:
    assert PredictorEncoder.png_filter_up(200, 50) == 150
    assert PredictorEncoder.png_filter_up(0, 1) == 0xFF


def test_png_filter_average_floors_pairwise_mean() -> None:
    # average((4+8)//2) = 6 -> 10 - 6 = 4
    assert PredictorEncoder.png_filter_average(10, 4, 8) == 4


def test_png_filter_paeth_picks_a_when_pa_smallest() -> None:
    # a=10, b=10, c=10, x=20  -> p=10, pa=pb=pc=0 -> pa branch (a).
    assert PredictorEncoder.png_filter_paeth(20, 10, 10, 10) == 10


def test_png_filter_paeth_picks_b_when_pb_smallest() -> None:
    # a=0, b=100, c=0, x=120  -> p=100, pa=100, pb=0 -> pb branch (b=100).
    assert PredictorEncoder.png_filter_paeth(120, 0, 100, 0) == 20


def test_png_filter_paeth_picks_c_when_pc_smallest() -> None:
    # a=0, b=0, c=100, x=50  -> p=-100, pa=100, pb=100, pc=200 ->
    # actually pa==pb<pc so falls into pb branch; pick params to hit
    # the c branch. Use a=200, b=0, c=100, x=50:
    # p = 200+0-100 = 100; pa = |100-200|=100; pb = |100-0|=100;
    # pc = |100-100|=0 -> pc branch.
    assert PredictorEncoder.png_filter_paeth(50, 200, 0, 100) == (50 - 100) & 0xFF


# ----------------------------------------------------------------------
# est_compress_sum + choose_data_row_to_write (lines 109-125)
# ----------------------------------------------------------------------
def test_est_compress_sum_signed_byte_abs_values() -> None:
    # 0x80 -> -128 -> abs 128; 0x7F -> 127; 0x00 -> 0.
    assert PredictorEncoder.est_compress_sum(b"\x00\x7f\x80\xff") == 0 + 127 + 128 + 1


def test_choose_data_row_to_write_picks_lowest_sum() -> None:
    encoder = _encoder("RGB", width=2, height=2)
    # Set all rows to high-cost bytes, then make ``up`` the cheapest.
    high = bytes([0x80] * len(encoder.data_raw_row_none))
    low = bytes([0x00] * len(encoder.data_raw_row_up))
    encoder.data_raw_row_none[:] = high
    encoder.data_raw_row_sub[:] = high
    encoder.data_raw_row_up[:] = low
    encoder.data_raw_row_average[:] = high
    encoder.data_raw_row_paeth[:] = high
    assert encoder.choose_data_row_to_write() == low


# ----------------------------------------------------------------------
# copy_image_bytes / copy_int_to_bytes / copy_shorts_to_bytes
# ----------------------------------------------------------------------
def test_copy_image_bytes_copies_pixel_slice() -> None:
    encoder = _encoder("RGB", width=4, height=3)
    transfer = bytes([10, 20, 30, 40, 50, 60])
    out = bytearray(encoder.bytes_per_pixel)
    next_alpha = encoder.copy_image_bytes(transfer, 0, out, alpha_pos=7)
    assert bytes(out) == bytes([10, 20, 30])
    # alpha_pos is returned untouched.
    assert next_alpha == 7


def test_copy_int_to_bytes_packs_rgb_word() -> None:
    encoder = _encoder("RGB", width=2, height=2)
    transfer = [0x00112233]
    out = bytearray(encoder.bytes_per_pixel)
    encoder.copy_int_to_bytes(transfer, 0, out, alpha_pos=0)
    # high-byte first: 0x11, 0x22, 0x33.
    assert bytes(out) == bytes([0x11, 0x22, 0x33])


def test_copy_int_to_bytes_handles_single_byte_per_pixel() -> None:
    encoder = _encoder("L", width=2, height=2)
    transfer = [0x00440000]
    out = bytearray(encoder.bytes_per_pixel)
    encoder.copy_int_to_bytes(transfer, 0, out, alpha_pos=0)
    # bytes_per_pixel == 1 -> only the high byte is written.
    assert bytes(out) == bytes([0x44])


def test_copy_int_to_bytes_handles_two_byte_pixel() -> None:
    """Forces the ``bytes_per_pixel == 2`` path (no third byte)."""
    encoder = _encoder("L", width=2, height=2)
    # Force the bpp to 2 manually — there's no native PIL mode that gives
    # exactly 2 bytes_per_pixel via the constructor.
    encoder.bytes_per_pixel = 2
    out = bytearray(encoder.bytes_per_pixel)
    encoder.copy_int_to_bytes([0x00AABBCC], 0, out, alpha_pos=0)
    assert bytes(out) == bytes([0xAA, 0xBB])


def test_copy_shorts_to_bytes_packs_big_endian_pairs() -> None:
    out = bytearray(4)
    PredictorEncoder.copy_shorts_to_bytes([0x1234, 0xABCD], 0, out, bytes_per_pixel=4)
    assert bytes(out) == bytes([0x12, 0x34, 0xAB, 0xCD])


def test_copy_shorts_to_bytes_masks_high_bits() -> None:
    """Values above 0xFFFF wrap with ``& 0xFFFF`` before packing."""
    out = bytearray(2)
    PredictorEncoder.copy_shorts_to_bytes([0x123456], 0, out, bytes_per_pixel=2)
    # Low 16 bits = 0x3456 -> packed big-endian.
    assert bytes(out) == bytes([0x34, 0x56])


# ----------------------------------------------------------------------
# prepare_predictor_pd_image — ImportError early-return (lines 205-206)
# ----------------------------------------------------------------------
def test_prepare_predictor_pd_image_handles_missing_cos_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the ``pypdfbox.cos`` import inside the method fails (e.g. a
    pruned install), the helper returns ``None`` instead of raising.
    """
    import builtins

    real_import = builtins.__import__

    def _filtered_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "pypdfbox.cos":
            raise ImportError("simulated pruning")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _filtered_import)
    encoder = _encoder("RGB", width=2, height=2)
    assert encoder.prepare_predictor_pd_image(io.BytesIO(b"x"), bits_per_component=8) is None
