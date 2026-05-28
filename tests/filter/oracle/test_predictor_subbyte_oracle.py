"""Live PDFBox differential parity for SUB-BYTE predictor un-filtering.

The existing ``test_filter_decode_oracle.py`` covers ``/FlateDecode`` +
``/LZWDecode`` predictors only for ``/BitsPerComponent`` 8 and 16. The
sub-byte component widths (1, 2, 4 bits per component) drive a completely
different code path in pypdfbox — ``_predictor._untiff_bits`` for TIFF
``/Predictor 2`` and the byte-wise PNG row filters with ``bytes_per_pixel``
clamped to 1 — and are a classic byte-for-byte divergence point because the
sample bit-packing has to match Apache PDFBox's ``Predictor.getBitSeq`` /
``calcSetBitSeq`` exactly.

Strategy (strict byte-equality through the oracle boundary):

1. Build a predicted ``/FlateDecode`` stream with pypdfbox's encoder driving
   the predictor at the *top level* of the params dict (pypdfbox's documented
   encode-side predictor extension — see ``test_filter_encode_oracle.py``).
2. Decode it with the live PDFBox oracle (``FilterDecodeProbe`` hands the
   matching ``/DecodeParms`` predictor to ``FlateFilter.decode`` so PDFBox runs
   its own ``Predictor.decodePredictorRow``).
3. Decode it with pypdfbox.
4. Assert ``java == py == original payload`` — i.e. both engines reverse the
   sub-byte predictor identically and recover the source bytes.

If pypdfbox's sub-byte packing disagreed with PDFBox's, step 2 and step 3
would produce different bytes and the assert would fail; that is the
divergence this oracle pins.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter import FilterFactory
from pypdfbox.filter._predictor import unpredict
from tests.oracle.harness import requires_oracle, run_probe

# Staged per-test by the autouse fixture below.
_ENCODED_TMP = ""


@pytest.fixture(autouse=True)
def _stage(tmp_path_factory):  # type: ignore[no-untyped-def]
    global _ENCODED_TMP
    _ENCODED_TMP = str(tmp_path_factory.mktemp("predictor_oracle") / "encoded.bin")
    yield


def _flate_encode_predicted(raw: bytes, parms: dict[str, int]) -> bytes:
    """Encode ``raw`` to a predicted /FlateDecode body.

    The predictor params are placed at the TOP LEVEL of the params dict so
    pypdfbox's encode-side predictor extension applies them before deflating.
    """
    flt = FilterFactory.get("FlateDecode")
    p = COSDictionary()
    for key, value in parms.items():
        p.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
    out = io.BytesIO()
    flt.encode(io.BytesIO(raw), out, p)
    return out.getvalue()


def _java_decode(encoded: bytes, parms: dict[str, int]) -> bytes:
    with open(_ENCODED_TMP, "wb") as fh:
        fh.write(encoded)
    arg = ",".join(f"{k}={v}" for k, v in parms.items())
    return run_probe("FilterDecodeProbe", _ENCODED_TMP, "FlateDecode", arg)


def _py_decode(encoded: bytes, parms: dict[str, int]) -> bytes:
    flt = FilterFactory.get("FlateDecode")
    sd = COSDictionary()
    dp = COSDictionary()
    for key, value in parms.items():
        dp.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
    sd.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    out = io.BytesIO()
    flt.decode(io.BytesIO(encoded), out, sd, 0)
    return out.getvalue()


def _java_predictor(predicted: bytes, parms: dict[str, int]) -> bytes:
    """Run PDFBox's predictor transform directly on already-predicted bytes.

    ``PredictorProbe`` feeds ``predicted`` through ``Predictor.wrapPredictor``'s
    ``PredictorOutputStream`` — i.e. PDFBox's ``decodePredictorRow`` — and emits
    the un-predicted bytes, isolated from the (de)compression stage.
    """
    with open(_ENCODED_TMP, "wb") as fh:
        fh.write(predicted)
    arg = ",".join(f"{k}={v}" for k, v in parms.items())
    return run_probe("PredictorProbe", _ENCODED_TMP, arg)


def _payload(parms: dict[str, int], rows: int = 5) -> bytes:
    """Deterministic pseudo-random payload sized to a whole number of rows."""
    columns = parms["Columns"]
    colors = parms.get("Colors", 1)
    bpc = parms["BitsPerComponent"]
    row_bytes = (columns * colors * bpc + 7) // 8
    return bytes((i * 31 + 7) % 256 for i in range(row_bytes * rows))


# ---------------------------------------------------------------------------
# TIFF /Predictor 2 — sub-byte component widths
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"),
    [
        (8, 1, 1),  # 1-bit gray, byte-aligned row
        (13, 1, 1),  # 1-bit gray, non-byte-aligned row (13 bits -> 2 bytes)
        (8, 1, 2),  # 2-bit gray
        (5, 1, 2),  # 2-bit gray, 10 bits/row -> 2 bytes (6 padding bits)
        (8, 1, 4),  # 4-bit gray
        (3, 1, 4),  # 4-bit gray, 12 bits/row -> 2 bytes (4 padding bits)
        (4, 3, 1),  # RGB 1-bit, 12 bits/row
        (4, 3, 2),  # RGB 2-bit, 24 bits/row -> 3 bytes
        (3, 3, 4),  # RGB 4-bit, 36 bits/row -> 5 bytes
    ],
    ids=[
        "gray1-c8", "gray1-c13", "gray2-c8", "gray2-c5",
        "gray4-c8", "gray4-c3", "rgb1", "rgb2", "rgb4",
    ],
)
def test_tiff_predictor2_subbyte_parity(columns: int, colors: int, bpc: int) -> None:
    parms = {
        "Predictor": 2,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    payload = _payload(parms)
    encoded = _flate_encode_predicted(payload, parms)
    java = _java_decode(encoded, parms)
    py = _py_decode(encoded, parms)
    assert java == py, (
        f"TIFF P2 sub-byte divergence parms={parms}\n"
        f"  java={java.hex()}\n  py  ={py.hex()}"
    )
    assert py == payload


# ---------------------------------------------------------------------------
# PNG predictors (10..14) — sub-byte component widths
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Direct decodePredictorRow parity — feed arbitrary already-predicted bytes
# straight through PDFBox's PredictorOutputStream (no compression in the way)
# and compare against pypdfbox's unpredict(). This pins the byte-exact handling
# of trailing padding bits in non-byte-aligned rows, the divergence fixed in
# _predictor._untiff_bits / _untiff_1bit_1color.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"),
    [
        (8, 1, 1), (13, 1, 1), (1, 1, 1), (7, 1, 1),
        (8, 1, 2), (5, 1, 2), (3, 1, 2),
        (8, 1, 4), (3, 1, 4), (1, 1, 4),
        (4, 3, 1), (4, 3, 2), (3, 3, 4),
    ],
    ids=[
        "g1-c8", "g1-c13", "g1-c1", "g1-c7",
        "g2-c8", "g2-c5", "g2-c3",
        "g4-c8", "g4-c3", "g4-c1",
        "rgb1", "rgb2", "rgb4",
    ],
)
def test_tiff_predictor2_decode_row_direct_parity(
    columns: int, colors: int, bpc: int
) -> None:
    parms = {
        "Predictor": 2,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    row_bytes = (columns * colors * bpc + 7) // 8
    # Arbitrary "already-predicted" input (including non-zero padding bits) so
    # the comparison exercises the padding-bit treatment, not just samples.
    predicted = bytes((i * 31 + 7) % 256 for i in range(row_bytes * 4))
    java = _java_predictor(predicted, parms)
    py = unpredict(predicted, 2, columns, colors, bpc)
    assert java == py, (
        f"decodePredictorRow divergence parms={parms}\n"
        f"  in  ={predicted.hex()}\n  java={java.hex()}\n  py  ={py.hex()}"
    )


@requires_oracle
@pytest.mark.parametrize("predictor", [10, 11, 12, 13, 14],
                         ids=["none", "sub", "up", "avg", "paeth"])
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"),
    [
        (8, 1, 1),
        (13, 1, 1),
        (8, 1, 2),
        (8, 1, 4),
        (3, 1, 4),
        (4, 3, 2),
    ],
    ids=["gray1-c8", "gray1-c13", "gray2-c8", "gray4-c8", "gray4-c3", "rgb2"],
)
def test_png_predictor_subbyte_parity(
    predictor: int, columns: int, colors: int, bpc: int
) -> None:
    parms = {
        "Predictor": predictor,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    payload = _payload(parms)
    encoded = _flate_encode_predicted(payload, parms)
    java = _java_decode(encoded, parms)
    py = _py_decode(encoded, parms)
    assert java == py, (
        f"PNG predictor {predictor} sub-byte divergence parms={parms}\n"
        f"  java={java.hex()}\n  py  ={py.hex()}"
    )
    assert py == payload
