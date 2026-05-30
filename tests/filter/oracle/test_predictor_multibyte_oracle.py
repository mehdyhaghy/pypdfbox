"""Live PDFBox differential parity for MULTI-BYTE-pixel predictor decoding.

The companion ``test_predictor_subbyte_oracle.py`` pins the sub-byte component
widths (``/BitsPerComponent`` 1/2/4) which drive PDFBox's ``getBitSeq`` /
``calcSetBitSeq`` bit-splicing path. This file pins the *other* classic
divergence surface: PNG / TIFF predictors over **multi-byte pixels** —
``/Colors`` > 1 at ``/BitsPerComponent`` 8 (``bytes_per_pixel`` 2/3/4) and
``/BitsPerComponent`` 16 (``bytes_per_pixel`` 2 per component). These are the
inputs where the "left neighbour is ``bpp`` bytes back, not 1" rule and the
first-pixel row-boundary clamp (``left = 0`` / ``up_left = 0`` for the first
pixel of a row) are easy to get wrong — especially for the **Average**
(``floor((left+up)/2)``) and **Paeth** predictors.

Strategy (true decode-vs-decode parity through the oracle boundary):

1. Encode a deterministic payload to a predicted ``/FlateDecode`` body with
   pypdfbox's encoder (predictor params at the top level of the params dict —
   pypdfbox's documented encode-side predictor extension).
2. Decode the body with the live PDFBox oracle (``FilterDecodeProbe`` hands the
   matching ``/DecodeParms`` predictor to ``FlateFilter.decode``, so PDFBox runs
   its own ``Predictor.decodePredictorRow``).
3. Decode the body with pypdfbox.
4. Assert ``java == py == original payload`` — both engines reverse the
   multi-byte predictor identically and recover the source bytes.

If pypdfbox's per-pixel neighbour arithmetic disagreed with PDFBox's, step 2
and step 3 would diverge and the assert would fail; that is the divergence this
oracle pins.
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
    _ENCODED_TMP = str(
        tmp_path_factory.mktemp("predictor_mb_oracle") / "encoded.bin"
    )
    yield


def _flate_encode_predicted(raw: bytes, parms: dict[str, int]) -> bytes:
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


def _java_decode_row(predicted: bytes, parms: dict[str, int]) -> bytes:
    """Reverse already-predicted bytes via PDFBox's decodePredictorRow.

    Isolates the predictor from the (de)compression stage so the comparison is
    the pure decode-side primitive that pypdfbox's ``unpredict`` mirrors.
    """
    with open(_ENCODED_TMP, "wb") as fh:
        fh.write(predicted)
    arg = ",".join(f"{k}={v}" for k, v in parms.items())
    return run_probe("PredictorDecodeProbe", _ENCODED_TMP, arg)


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


def _payload(parms: dict[str, int], rows: int = 6) -> bytes:
    """Deterministic pseudo-random payload sized to a whole number of rows.

    A coprime stride (37) keeps adjacent samples differing so the left / up /
    upper-left neighbour terms are all exercised non-trivially.
    """
    columns = parms["Columns"]
    colors = parms.get("Colors", 1)
    bpc = parms["BitsPerComponent"]
    row_bytes = (columns * colors * bpc + 7) // 8
    return bytes((i * 37 + 11) % 256 for i in range(row_bytes * rows))


# Geometries with bytes_per_pixel > 1 (the multi-byte-pixel surface):
#   (Columns, Colors, BitsPerComponent)  ->  bpp
#   (5, 3, 8)  RGB 8-bit              -> bpp 3
#   (4, 4, 8)  CMYK / RGBA 8-bit      -> bpp 4
#   (6, 2, 8)  gray+alpha 8-bit       -> bpp 2
#   (1, 3, 8)  single RGB pixel/row   -> bpp 3, every byte is "first pixel"-ish
#   (5, 1, 16) 16-bit gray            -> bpp 2
#   (4, 3, 16) 16-bit RGB             -> bpp 6
#   (3, 4, 16) 16-bit CMYK            -> bpp 8
_MULTIBYTE_GEOMETRIES = [
    (5, 3, 8),
    (4, 4, 8),
    (6, 2, 8),
    (1, 3, 8),
    (5, 1, 16),
    (4, 3, 16),
    (3, 4, 16),
]
_MULTIBYTE_IDS = [
    "rgb8", "cmyk8", "graya8", "rgb8-col1", "gray16", "rgb16", "cmyk16",
]


# ---------------------------------------------------------------------------
# TIFF /Predictor 2 — multi-byte pixels (8- and 16-bit components)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"), _MULTIBYTE_GEOMETRIES, ids=_MULTIBYTE_IDS
)
def test_tiff_predictor2_multibyte_parity(
    columns: int, colors: int, bpc: int
) -> None:
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
        f"TIFF P2 multi-byte divergence parms={parms}\n"
        f"  java={java.hex()}\n  py  ={py.hex()}"
    )
    assert py == payload


# ---------------------------------------------------------------------------
# PNG predictors (Up / Average / Paeth) — multi-byte pixels
#
# Up (12), Average (13) and Paeth (14) are the predictors that read the
# previous row and/or the ``bpp``-bytes-back left neighbour, so they are the
# ones whose multi-byte-pixel arithmetic and first-pixel row-boundary clamps
# can diverge. None (10) and Sub (11) are included for completeness.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "predictor", [10, 11, 12, 13, 14],
    ids=["none", "sub", "up", "avg", "paeth"],
)
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"), _MULTIBYTE_GEOMETRIES, ids=_MULTIBYTE_IDS
)
def test_png_predictor_multibyte_parity(
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
        f"PNG predictor {predictor} multi-byte divergence parms={parms}\n"
        f"  java={java.hex()}\n  py  ={py.hex()}"
    )
    assert py == payload


# ---------------------------------------------------------------------------
# Predictor 15 (PNG Optimum) — the encoder picks a per-row filter tag via the
# minimum-sum-of-absolute-values heuristic; PDFBox decodes whatever tag each
# row carries. Pinning the round-trip over multi-byte pixels confirms the
# per-row tag dispatch on decode handles every filter type for bpp > 1.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"), _MULTIBYTE_GEOMETRIES, ids=_MULTIBYTE_IDS
)
def test_png_predictor15_optimum_multibyte_parity(
    columns: int, colors: int, bpc: int
) -> None:
    parms = {
        "Predictor": 15,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    payload = _payload(parms)
    encoded = _flate_encode_predicted(payload, parms)
    # On decode PDFBox sees PNG filter tags (10..14 collapse to the per-row
    # tag byte), so /DecodeParms carries the family marker 15 unchanged.
    java = _java_decode(encoded, parms)
    py = _py_decode(encoded, parms)
    assert java == py, (
        f"PNG predictor 15 multi-byte divergence parms={parms}\n"
        f"  java={java.hex()}\n  py  ={py.hex()}"
    )
    assert py == payload


# ---------------------------------------------------------------------------
# Direct decodePredictorRow parity — feed ARBITRARY already-predicted bytes
# straight through PDFBox's decodePredictorRow (no compression in the way) and
# compare against pypdfbox's unpredict(). This pins the per-pixel neighbour
# arithmetic (left is bpp bytes back, up_left clamps to 0 for the first pixel)
# for every PNG filter type, with multi-byte pixels and an unstable previous
# row — exactly the row-boundary / Average / Paeth surface that is easy to get
# wrong for bpp > 1.
# ---------------------------------------------------------------------------


def _build_predicted_png(parms: dict[str, int], rows: int = 5) -> bytes:
    """Build a PNG-predicted body where every row uses the same filter tag.

    Each row is the geometry's filter tag byte followed by ``row_bytes`` of
    deterministic pseudo-random "filtered" samples. These are NOT a faithful
    encoding of any source image — they are arbitrary post-filter bytes — which
    is the point: it forces both engines through the same reverse arithmetic on
    inputs that stress the row boundary and the previous-row dependency.
    """
    columns = parms["Columns"]
    colors = parms.get("Colors", 1)
    bpc = parms["BitsPerComponent"]
    tag = parms["Predictor"] - 10
    row_bytes = (columns * colors * bpc + 7) // 8
    out = bytearray()
    n = 0
    for _ in range(rows):
        out.append(tag)
        for _ in range(row_bytes):
            out.append((n * 37 + 11) % 256)
            n += 1
    return bytes(out)


@requires_oracle
@pytest.mark.parametrize(
    "predictor", [10, 11, 12, 13, 14],
    ids=["none", "sub", "up", "avg", "paeth"],
)
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"), _MULTIBYTE_GEOMETRIES, ids=_MULTIBYTE_IDS
)
def test_png_decode_row_direct_parity(
    predictor: int, columns: int, colors: int, bpc: int
) -> None:
    parms = {
        "Predictor": predictor,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    predicted = _build_predicted_png(parms)
    java = _java_decode_row(predicted, parms)
    py = unpredict(predicted, predictor, columns, colors, bpc)
    assert java == py, (
        f"PNG decodePredictorRow divergence parms={parms}\n"
        f"  in  ={predicted.hex()}\n  java={java.hex()}\n  py  ={py.hex()}"
    )


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"), _MULTIBYTE_GEOMETRIES, ids=_MULTIBYTE_IDS
)
def test_tiff_decode_row_direct_parity(
    columns: int, colors: int, bpc: int
) -> None:
    parms = {
        "Predictor": 2,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    row_bytes = (columns * colors * bpc + 7) // 8
    predicted = bytes((i * 37 + 11) % 256 for i in range(row_bytes * 5))
    java = _java_decode_row(predicted, parms)
    py = unpredict(predicted, 2, columns, colors, bpc)
    assert java == py, (
        f"TIFF decodePredictorRow divergence parms={parms}\n"
        f"  in  ={predicted.hex()}\n  java={java.hex()}\n  py  ={py.hex()}"
    )
