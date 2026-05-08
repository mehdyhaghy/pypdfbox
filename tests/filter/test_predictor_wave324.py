from __future__ import annotations

from pypdfbox.filter._predictor import predict, unpredict


def test_wave324_tiff_decode_pads_short_16bit_final_row() -> None:
    raw = bytes.fromhex("0001 0003 0006")
    encoded = predict(raw, predictor=2, columns=3, colors=1, bits_per_component=16)

    truncated = encoded[:-1]

    assert unpredict(
        truncated,
        predictor=2,
        columns=3,
        colors=1,
        bits_per_component=16,
    ) == bytes.fromhex("0001 0003 0003")
