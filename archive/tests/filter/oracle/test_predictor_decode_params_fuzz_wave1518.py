"""Live PDFBox differential fuzz for predictor row geometry (wave 1518)."""

from __future__ import annotations

from pypdfbox.filter.predictor import Predictor
from tests.oracle.harness import requires_oracle, run_probe_text


def _line(name: str, fn) -> str:
    try:
        return f"CASE {name} {fn()}\n"
    except Exception as exc:
        if isinstance(exc, (IndexError, OSError)):
            java_name = "ArrayIndexOutOfBoundsException"
        else:
            java_name = type(exc).__name__
        return f"CASE {name} ERR:{java_name}\n"


def _row_length(name: str, colors: int, bpc: int, columns: int) -> str:
    return _line(
        name,
        lambda: f"value={Predictor.calculate_row_length(colors, bpc, columns)}",
    )


def _decode(
    name: str,
    predictor: int,
    colors: int,
    bpc: int,
    columns: int,
    row: bytes,
    previous: bytes,
) -> str:
    def run() -> str:
        active = bytearray(row)
        Predictor.decode_predictor_row(
            predictor, colors, bpc, columns, active, previous
        )
        return f"row={active.hex()}"

    return _line(name, run)


def _py_dump() -> str:
    lines = [
        _row_length("row_normal", 3, 8, 5),
        _row_length("row_subbyte", 1, 1, 9),
        _row_length("row_zero_columns", 1, 8, 0),
        _row_length("row_negative_columns", 1, 8, -1),
        _row_length("row_zero_colors", 0, 8, 4),
        _row_length("row_negative_bpc", 1, -8, 4),
        _row_length("row_overflow", 32, 32, 2_147_483_647),
        _decode("none", 1, 0, 0, 0, b"\x01\x02\x03", b""),
        _decode("unknown", 99, 1, 8, 3, b"\x01\x02\x03", bytes(3)),
        _decode("png_sub", 11, 1, 8, 4, b"\x01\x02\x03\x04", bytes(4)),
        _decode("png_up_short_prev", 12, 1, 8, 4, b"\x01\x02\x03\x04", b"\x09"),
        _decode("png_avg", 13, 1, 8, 4, b"\x01\x02\x03\x04", b"\x08\x07\x06\x05"),
        _decode("png_paeth", 14, 1, 8, 4, b"\x01\x02\x03\x04", b"\x08\x07\x06\x05"),
        _decode("tiff_1bit", 2, 1, 1, 9, b"\x93\x80", bytes(2)),
        _decode("empty_invalid_geometry", 12, 0, 0, 0, b"", b""),
    ]
    return "".join(lines)


@requires_oracle
def test_predictor_decode_params_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("PredictorDecodeParamsFuzzProbe")
