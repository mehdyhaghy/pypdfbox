"""Live PDFBox differential parity for PARTIAL (stop-filter) chain decode.

ISO 32000-1 §7.4 lets a stream chain several filters; some callers (image
XObjects, in particular) want to decode only the *transport* layers of that
chain and keep the image codec payload encoded — e.g. undo ``/ASCII85Decode``
but stop before ``/DCTDecode`` so the JPEG bytes survive verbatim. PDFBox
exposes this as ``PDStream.createInputStream(List<String> stopFilters)``.

Upstream semantics (decompiled from ``PDStream.createInputStream(java.util.List)``
in PDFBox 3.0.7):

1. A ``null`` ``stopFilters`` is treated as the empty list.
2. The ``/Filter`` chain is walked in order; the FIRST filter whose name is
   contained in ``stopFilters`` HALTS the walk — that filter and every filter
   after it is left un-applied.
3. If the collected (pre-stop) filter list is empty, the RAW stream bytes are
   returned verbatim (no decode at all).
4. Otherwise the collected prefix is decoded through ``Filter.decode`` with the
   FULL stream dictionary, so positional ``/DecodeParms`` still align to the
   original filter indices.

``StopFilterProbe`` builds a real ``COSStream`` from raw (already-encoded)
bytes, sets ``/Filter`` (+ a parallel ``/DecodeParms`` array with ``null`` for
param-less filters) exactly as a parsed PDF would, wraps it in a ``PDStream``,
and drives ``createInputStream(stopFilters)`` — emitting ``"<len> <sha256hex>"``.
The pypdfbox side reproduces the same ``COSStream`` and drives
``PDStream.create_input_stream(stop_filters=...)``, asserting byte-exact parity.

Cases pinned:

* stop at the *first* filter → empty prefix → raw bytes returned (no decode);
* stop at the *second* filter → only the first filter applied (partial decode);
* a stop name NOT in the chain → full decode (identical to no stop);
* a ``null`` stop list (Java null) → full decode;
* the parallel-``/DecodeParms``-array-with-``null`` case still aligns params to
  the correct filter index when only a prefix of the chain is applied.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.filter import FilterFactory
from pypdfbox.pdmodel.common.pd_stream import PDStream
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------------------
# encode helpers — build the raw encoded chain bytes pypdfbox + the probe share
# ---------------------------------------------------------------------------


def _parms_dict(parms: dict[str, int]) -> COSDictionary:
    dp = COSDictionary()
    for key, value in parms.items():
        dp.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
    return dp


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


def _encode_chain(
    raw: bytes,
    filters: list[str],
    parms_list: list[dict[str, int] | None] | None,
) -> bytes:
    """Encode ``raw`` through ``filters`` in DECODE order.

    Decoding walks ``filters`` left-to-right, so encoding must apply them in
    reverse (rightmost decoder is the first encoder). The returned bytes are
    the on-disk raw body for a stream carrying ``/Filter filters``.
    """
    data = raw
    for index in reversed(range(len(filters))):
        parms = parms_list[index] if parms_list is not None else None
        data = _encode(filters[index], data, parms)
    return data


def _build_stream(
    raw_encoded: bytes,
    filters: list[str],
    parms_list: list[dict[str, int] | None] | None,
) -> COSStream:
    """Reproduce the exact ``COSStream`` shape ``StopFilterProbe`` builds."""
    stream = COSStream()
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
        if len(filters) == 1 and len(parms_list) == 1 and parms_list[0] is not None:
            stream.set_item(key, _parms_dict(parms_list[0]))
        else:
            arr = COSArray()
            for entry in parms_list:
                arr.add(COSNull.NULL if entry is None else _parms_dict(entry))
            stream.set_item(key, arr)
    return stream


def _py_facts(
    raw_encoded: bytes,
    filters: list[str],
    parms_list: list[dict[str, int] | None] | None,
    stop_filters: list[str] | None,
) -> str:
    """``"<len> <sha256hex>"`` from pypdfbox's stop-filter partial decode."""
    stream = _build_stream(raw_encoded, filters, parms_list)
    try:
        pd = PDStream(stream)
        with pd.create_input_stream(stop_filters=stop_filters) as src:
            decoded = src.read()
    finally:
        stream.close()
    return f"{len(decoded)} {hashlib.sha256(decoded).hexdigest()}"


# ---------------------------------------------------------------------------
# probe staging
# ---------------------------------------------------------------------------

_RAW_TMP = ""


@pytest.fixture(autouse=True)
def _stage_raw(tmp_path_factory):  # type: ignore[no-untyped-def]
    global _RAW_TMP
    _RAW_TMP = str(tmp_path_factory.mktemp("stop_filter_oracle") / "raw.bin")
    yield


def _run_probe(
    raw_encoded: bytes,
    filters_arg: str,
    parms_arg: str,
    stop_arg: str,
) -> str:
    Path(_RAW_TMP).write_bytes(raw_encoded)
    return run_probe_text(
        "StopFilterProbe", _RAW_TMP, filters_arg, parms_arg, stop_arg
    ).strip()


_PAYLOAD = (
    b"BT /F1 12 Tf 72 720 Td (Stop-filter partial decode parity) Tj ET\n"
    + b"% padding so deflate output is non-trivial " + (b"Z" * 96) + b"\n"
)


# ===========================================================================
# Differential tests — [/ASCII85Decode /FlateDecode], no /DecodeParms
# ===========================================================================


@requires_oracle
def test_stop_at_first_filter_returns_raw_bytes() -> None:
    """``stopFilters=[ASCII85Decode]`` halts before the first filter — the
    collected prefix is empty, so the RAW (still ASCII85+Flate-armoured) bytes
    come back verbatim. PDFBox and pypdfbox must agree byte-for-byte."""
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    java = _run_probe(raw, "ASCII85Decode,FlateDecode", "", "ASCII85Decode")
    py = _py_facts(raw, filters, None, ["ASCII85Decode"])
    assert py == java
    # The returned body is the untouched raw chain bytes.
    assert py == f"{len(raw)} {hashlib.sha256(raw).hexdigest()}"


@requires_oracle
def test_stop_at_second_filter_applies_only_first() -> None:
    """``stopFilters=[FlateDecode]`` halts at the second filter — only
    ``ASCII85Decode`` runs, leaving the inner Flate bytes still compressed."""
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    java = _run_probe(raw, "ASCII85Decode,FlateDecode", "", "FlateDecode")
    py = _py_facts(raw, filters, None, ["FlateDecode"])
    assert py == java
    # Sanity: the partial result equals "ASCII85-decoded only" = the Flate
    # bytes, which differ from both the raw chain and the full decode.
    flate_only = _encode("FlateDecode", _PAYLOAD)
    assert py == f"{len(flate_only)} {hashlib.sha256(flate_only).hexdigest()}"


@requires_oracle
def test_stop_filter_not_in_chain_decodes_fully() -> None:
    """A stop name absent from ``/Filter`` never matches → full decode,
    identical to ``createInputStream()`` with no stop list."""
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    java = _run_probe(raw, "ASCII85Decode,FlateDecode", "", "DCTDecode")
    py = _py_facts(raw, filters, None, ["DCTDecode"])
    assert py == java
    assert py == f"{len(_PAYLOAD)} {hashlib.sha256(_PAYLOAD).hexdigest()}"


@requires_oracle
def test_null_stop_list_decodes_fully() -> None:
    """A ``null`` stop list (Java null → ``Collections.emptyList()``) decodes
    the whole chain. pypdfbox passes ``stop_filters=None``."""
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    java = _run_probe(raw, "ASCII85Decode,FlateDecode", "", "__NULL__")
    py = _py_facts(raw, filters, None, None)
    assert py == java
    assert py == f"{len(_PAYLOAD)} {hashlib.sha256(_PAYLOAD).hexdigest()}"


@requires_oracle
def test_empty_stop_list_decodes_fully() -> None:
    """An empty stop list decodes the whole chain (no filter name matches)."""
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    java = _run_probe(raw, "ASCII85Decode,FlateDecode", "", "")
    py = _py_facts(raw, filters, None, [])
    assert py == java
    assert py == f"{len(_PAYLOAD)} {hashlib.sha256(_PAYLOAD).hexdigest()}"


# ===========================================================================
# Differential tests — [/ASCIIHexDecode /FlateDecode] with /DecodeParms
# [null <<TIFF predictor 2>>] : the parallel-array-with-null alignment case.
# Stopping before FlateDecode must NOT trip the predictor — the prefix that
# runs (ASCIIHexDecode) takes the null param slot at index 0.
# ===========================================================================

_TIFF_PARMS = {"Predictor": 2, "Colors": 3, "Columns": 4, "BitsPerComponent": 8}
_TIFF_PARMS_SEG = "Predictor=2,Colors=3,Columns=4,BitsPerComponent=8"


@requires_oracle
def test_stop_before_predictor_flate_keeps_param_alignment() -> None:
    """``[/ASCIIHexDecode /FlateDecode]`` + ``/DecodeParms [null <<pred 2>>]``;
    stop at ``FlateDecode`` so only ``ASCIIHexDecode`` runs. The ``null`` slot
    at index 0 must keep ASCIIHex param-less (no spurious predictor)."""
    filters = ["ASCIIHexDecode", "FlateDecode"]
    parms_list: list[dict[str, int] | None] = [None, _TIFF_PARMS]
    raw = _encode_chain(_PAYLOAD, filters, parms_list)
    java = _run_probe(
        raw,
        "ASCIIHexDecode,FlateDecode",
        f"null;{_TIFF_PARMS_SEG}",
        "FlateDecode",
    )
    py = _py_facts(raw, filters, parms_list, ["FlateDecode"])
    assert py == java


@requires_oracle
def test_full_decode_with_predictor_array_parity() -> None:
    """Same fixture, no stop filter — the full chain (incl. the index-1 TIFF
    predictor) decodes on both sides to the IDENTICAL bytes.

    The TIFF predictor (row width Colors*Columns = 12 bytes) pads the
    payload to a row multiple, so the decoded length is not the original
    payload length — the load-bearing invariant is that pypdfbox and PDFBox
    land on the same predictor-unfiltered bytes."""
    filters = ["ASCIIHexDecode", "FlateDecode"]
    parms_list: list[dict[str, int] | None] = [None, _TIFF_PARMS]
    raw = _encode_chain(_PAYLOAD, filters, parms_list)
    java = _run_probe(
        raw,
        "ASCIIHexDecode,FlateDecode",
        f"null;{_TIFF_PARMS_SEG}",
        "__NULL__",
    )
    py = _py_facts(raw, filters, parms_list, None)
    assert py == java


# ===========================================================================
# pypdfbox-side invariants (no oracle, fast regression pins)
# ===========================================================================


def test_stop_at_first_filter_short_circuits_to_raw() -> None:
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    stream = _build_stream(raw, filters, None)
    try:
        pd = PDStream(stream)
        with pd.create_input_stream(stop_filters=["ASCII85Decode"]) as src:
            assert src.read() == raw
    finally:
        stream.close()


def test_stop_at_second_filter_applies_prefix_only() -> None:
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    stream = _build_stream(raw, filters, None)
    try:
        pd = PDStream(stream)
        with pd.create_input_stream(stop_filters=["FlateDecode"]) as src:
            assert src.read() == _encode("FlateDecode", _PAYLOAD)
    finally:
        stream.close()


def test_no_stop_filter_full_decode() -> None:
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    stream = _build_stream(raw, filters, None)
    try:
        pd = PDStream(stream)
        with pd.create_input_stream() as src:
            assert src.read() == _PAYLOAD
    finally:
        stream.close()


def test_stop_filter_abbreviation_alias_matches() -> None:
    """The stop set is canonicalised, so the abbreviated ``Fl`` halts at
    ``FlateDecode`` just like the long name does (alias parity)."""
    filters = ["ASCII85Decode", "FlateDecode"]
    raw = _encode_chain(_PAYLOAD, filters, None)
    stream = _build_stream(raw, filters, None)
    try:
        pd = PDStream(stream)
        with pd.create_input_stream(stop_filters=["Fl"]) as src:
            assert src.read() == _encode("FlateDecode", _PAYLOAD)
    finally:
        stream.close()
