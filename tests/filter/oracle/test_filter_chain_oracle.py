"""Live PDFBox differential parity for the MULTI-FILTER chain decode surface.

A stream's ``/Filter`` may be an ARRAY (e.g. ``[/ASCII85Decode /FlateDecode]``),
in which case the filters apply **in order** and ``/DecodeParms`` is a PARALLEL
ARRAY — one entry per filter, with ``null`` (or an absent entry) allowed for a
filter that takes no parameters (ISO 32000-1 §7.4.2 / §7.3.8.2). Decode is
lossless, so pypdfbox must recover the exact bytes Apache PDFBox 3.0.7 does.

This is a strict byte-equality check (length + SHA-256). For each chain we
build the raw (already-encoded) stream bytes with pypdfbox's own encoders, drop
them into a ``COSStream`` with the ``/Filter`` array and the parallel
``/DecodeParms`` array, and assert pypdfbox's ``create_input_stream()`` /
``to_byte_array()`` output equals the oracle's ``COSStream.createInputStream()``.

The Java side runs through ``oracle/probes/FilterChainProbe.java``: it builds a
real ``COSStream``, writes the raw bytes via ``createRawOutputStream()``, sets
the ``/Filter`` + ``/DecodeParms`` entries identically, decodes the whole chain
through ``createInputStream()``, and emits ``"<len> <sha256hex>"``.

Chains covered:

* ``[/ASCII85Decode /FlateDecode]`` — no params (apply-in-order, no parms array).
* ``[/FlateDecode]`` with a bare ``/DecodeParms`` ``<</Predictor 12 .../>>`` —
  the single-filter shape (dict, not a one-element array).
* ``[/ASCIIHexDecode /FlateDecode]`` with ``/DecodeParms [null <</Predictor 2
  .../>>]`` — the parallel-array-with-``null`` case: the param dict must align
  to the *second* filter, and the ``null`` first entry must NOT misroute params
  to the param-less ``ASCIIHexDecode``. This is the high-value alignment check.
"""

from __future__ import annotations

import hashlib
import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------------------
# encode helpers (build the raw encoded chain bytes)
# ---------------------------------------------------------------------------


def _encode(name: str, raw: bytes, parms: dict[str, int] | None = None) -> bytes:
    """Encode ``raw`` through a single filter, with optional predictor parms."""
    flt = FilterFactory.get(name)
    p = COSDictionary()
    if parms:
        for key, value in parms.items():
            p.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
    out = io.BytesIO()
    flt.encode(io.BytesIO(raw), out, p)
    return out.getvalue()


# ---------------------------------------------------------------------------
# pypdfbox decode through a real COSStream filter chain
# ---------------------------------------------------------------------------


def _py_chain_decode(
    raw_encoded: bytes,
    filters: list[str],
    parms_list: list[dict[str, int] | None] | None,
) -> bytes:
    """Decode ``raw_encoded`` through ``filters`` via ``COSStream``.

    ``parms_list`` aligns to ``filters`` (a ``None`` entry → no params for that
    filter). When a single filter has a single non-``None`` parms entry the
    ``/DecodeParms`` is stored as a bare dictionary (the single-filter shape);
    otherwise it is a parallel ``COSArray`` with ``COSNull`` for ``None``
    entries — exactly the on-disk shapes a parser would carry.
    """
    stream = COSStream()
    try:
        with stream.create_raw_output_stream() as out:
            out.write(raw_encoded)

        if len(filters) == 1:
            stream.set_item(COSName.FILTER, COSName.get_pdf_name(filters[0]))
        else:
            stream.set_item(
                COSName.FILTER,
                COSArray([COSName.get_pdf_name(f) for f in filters]),
            )

        if parms_list is not None:
            key = COSName.get_pdf_name("DecodeParms")
            if (
                len(filters) == 1
                and len(parms_list) == 1
                and parms_list[0] is not None
            ):
                stream.set_item(key, _parms_dict(parms_list[0]))
            else:
                arr = COSArray()
                for entry in parms_list:
                    arr.add(COSNull.NULL if entry is None else _parms_dict(entry))
                stream.set_item(key, arr)

        return stream.to_byte_array()
    finally:
        stream.close()


def _parms_dict(parms: dict[str, int]) -> COSDictionary:
    dp = COSDictionary()
    for key, value in parms.items():
        dp.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
    return dp


# ---------------------------------------------------------------------------
# Java oracle decode through PDFBox's COSStream filter chain
# ---------------------------------------------------------------------------

_RAW_TMP = ""


@pytest.fixture(autouse=True)
def _stage_raw(tmp_path_factory):  # type: ignore[no-untyped-def]
    """Per-test scratch file the probe reads its raw encoded bytes from."""
    global _RAW_TMP
    _RAW_TMP = str(tmp_path_factory.mktemp("filter_chain_oracle") / "raw.bin")
    yield


def _java_chain_decode(
    raw_encoded: bytes,
    filter_arg: str,
    parms_arg: str | None = None,
) -> tuple[int, str]:
    """Run the oracle probe; return ``(decoded_length, sha256_hex)``."""
    with open(_RAW_TMP, "wb") as fh:
        fh.write(raw_encoded)
    args = [_RAW_TMP, filter_arg]
    if parms_arg is not None:
        args.append(parms_arg)
    out = run_probe_text("FilterChainProbe", *args)
    length_str, sha = out.split()
    return int(length_str), sha


def _assert_chain_parity(
    raw_encoded: bytes,
    filters: list[str],
    parms_list: list[dict[str, int] | None] | None,
    filter_arg: str,
    parms_arg: str | None,
    expected_raw: bytes,
) -> None:
    """Decode the chain both ways; assert byte-exact (length + SHA-256) parity
    and that the recovered bytes equal the original lossless payload."""
    py = _py_chain_decode(raw_encoded, filters, parms_list)
    java_len, java_sha = _java_chain_decode(raw_encoded, filter_arg, parms_arg)
    py_sha = hashlib.sha256(py).hexdigest()
    assert len(py) == java_len, (
        f"chain {filters} length divergence: py={len(py)} java={java_len}"
    )
    assert py_sha == java_sha, (
        f"chain {filters} byte divergence (SHA-256)\n"
        f"  parms={parms_list}\n  py  ={py_sha}\n  java={java_sha}"
    )
    # Decode is lossless — both engines must reproduce the source payload.
    assert py == expected_raw


# ---------------------------------------------------------------------------
# (a) [/ASCII85Decode /FlateDecode] — no params
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"Hello, multi-filter PDFBox chain!",
        b"the quick brown fox jumps over the lazy dog " * 40,
        bytes(range(256)) * 4,
    ],
    ids=["empty", "short", "repetitive", "all-bytes"],
)
def test_ascii85_flate_chain_parity(payload: bytes) -> None:
    # Encode innermost-first: FlateDecode wraps the payload, ASCII85Decode wraps
    # that. Decode then applies ASCII85Decode first, FlateDecode second.
    inner = _encode("FlateDecode", payload)
    raw = _encode("ASCII85Decode", inner) + b"~>"
    _assert_chain_parity(
        raw,
        ["ASCII85Decode", "FlateDecode"],
        None,
        "ASCII85Decode,FlateDecode",
        None,
        payload,
    )


# ---------------------------------------------------------------------------
# (b) [/FlateDecode] with a bare /DecodeParms dict (PNG predictor 12)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"),
    [(4, 1, 8), (6, 1, 8), (3, 3, 8), (8, 1, 8)],
    ids=["c4", "c6", "rgb", "c8"],
)
def test_flate_predictor12_bare_parms_parity(
    columns: int, colors: int, bpc: int
) -> None:
    row_bytes = (columns * colors * bpc + 7) // 8
    payload = bytes((i * 37 + 11) % 256 for i in range(row_bytes * 6))
    parms = {
        "Predictor": 12,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    raw = _encode("FlateDecode", payload, parms)
    parms_arg = ",".join(f"{k}={v}" for k, v in parms.items())
    _assert_chain_parity(
        raw,
        ["FlateDecode"],
        [parms],
        "FlateDecode",
        parms_arg,
        payload,
    )


# ---------------------------------------------------------------------------
# (c) [/ASCIIHexDecode /FlateDecode] with /DecodeParms [null <<TIFF pred 2>>]
#     — the parallel-array-with-null high-value alignment case.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"),
    [(4, 3, 8), (6, 1, 8), (4, 1, 16)],
    ids=["rgb8", "gray8", "gray16"],
)
def test_asciihex_flate_null_parms_array_parity(
    columns: int, colors: int, bpc: int
) -> None:
    row_bytes = (columns * colors * bpc + 7) // 8
    payload = bytes((i * 19 + 3) % 256 for i in range(row_bytes * 5))
    flate_parms = {
        "Predictor": 2,
        "Colors": colors,
        "Columns": columns,
        "BitsPerComponent": bpc,
    }
    # FlateDecode (with TIFF predictor) innermost, ASCIIHexDecode outermost.
    inner = _encode("FlateDecode", payload, flate_parms)
    raw = _encode("ASCIIHexDecode", inner) + b">"
    parms_seg = ",".join(f"{k}={v}" for k, v in flate_parms.items())
    _assert_chain_parity(
        raw,
        ["ASCIIHexDecode", "FlateDecode"],
        [None, flate_parms],  # null for ASCIIHexDecode, dict for FlateDecode
        "ASCIIHexDecode,FlateDecode",
        f"null;{parms_seg}",
        payload,
    )


@requires_oracle
def test_ascii85_flate_predictor_null_parms_array_parity() -> None:
    # [/ASCII85Decode /FlateDecode] with /DecodeParms [null <</Predictor 12 ...>>]
    # — confirms the PNG-predictor dict aligns to FlateDecode (index 1) even
    # though the first /DecodeParms slot is null for the param-less ASCII85.
    columns, colors = 8, 1
    payload = bytes((i * 53 + 7) % 256 for i in range(columns * 7))
    flate_parms = {"Predictor": 12, "Columns": columns, "Colors": colors}
    inner = _encode("FlateDecode", payload, flate_parms)
    raw = _encode("ASCII85Decode", inner) + b"~>"
    parms_seg = ",".join(f"{k}={v}" for k, v in flate_parms.items())
    _assert_chain_parity(
        raw,
        ["ASCII85Decode", "FlateDecode"],
        [None, flate_parms],
        "ASCII85Decode,FlateDecode",
        f"null;{parms_seg}",
        payload,
    )
