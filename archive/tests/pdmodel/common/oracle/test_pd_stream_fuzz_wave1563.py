"""Differential fuzz audit for the DECODE / RAW byte-level read path of
``pypdfbox.pdmodel.common.PDStream`` vs Apache PDFBox 3.0.7 (wave 1563,
agent B).

Complements the two existing PDStream oracle probes:

* ``PdStreamEncodeProbe`` — the encode-on-write constructor
  (``PDStream(doc, input, filters)``);
* ``PdStreamFilterChainFuzzProbe`` (wave 1529) — the pure dictionary-shape
  ``/Filter`` / ``/DecodeParms`` accessors against a *body-less*
  ``COSStream``.

This module covers the angle neither of those does: a ``COSStream`` carrying
*real already-encoded body bytes* (the parser-populated shape — bytes stored
verbatim via ``create_raw_output_stream``), with a fuzzed ``/Filter`` chain
and a fuzzed ``/Length``. It projects, per case:

* ``create_input_stream()``                     → decoded length + sha8
* ``get_cos_object().create_raw_input_stream()`` → raw length + sha8
* ``get_filters()``                              → ordered name list
* ``get_length()``                               → the ``/Length`` int

The Java probe (``oracle/probes/PdStreamFuzzProbe.java``) plants the same
encoded bytes (shared bit-for-bit via hex constants) and projects the
identical grammar::

    CASE <id> dec=<len|ERR:Exc>/<sha8> raw=<len|ERR:Exc>/<sha8> filters=<...> length=<int>

Java is ground truth. Where pypdfbox legitimately and *intentionally*
diverges from upstream, the Python projection is normalised back onto the
Java token with an explicit ``# DIVERGENCE`` comment, so the assertion stays
a true line-for-line comparison while documenting the gap:

1. **Empty stream + ``create_input_stream()``** — upstream ``COSStream``
   raises ``IOException`` ("stream has no data"); ``PDStream`` wraps that and
   re-raises. pypdfbox's ``PDStream.create_input_stream`` deliberately
   returns an empty ``BytesIO`` for a body-less stream (documented in the
   method docstring — typed handles often wrap a fresh-and-empty stream).
   We remap pypdfbox's ``0/<sha8-of-empty>`` to the Java ``ERR:IOException``
   token for these cases.

2. **``get_length()`` on a body-less stream** — upstream returns ``0``
   (``getInt(LENGTH, 0)``); pypdfbox returns ``None`` when neither a
   ``/Length`` entry nor a body exists. Remapped to ``0``.

3. **Exception class names** — ``IOException`` (Java) ↔ ``OSError`` (Python).
   The Java ``ERR:IOException`` and pypdfbox ``ERR:OSError`` are the same
   contract; normalised to the Java spelling.

Two further divergences this module originally pinned — a non-name ``/Filter``
raising ``TypeError`` and consecutive duplicate filters not being
deduplicated — were genuine ``pypdfbox/cos/cos_stream.py`` bugs and were
**fixed in wave 1564**. The corresponding cases (``filter_string_wrongtype``,
``filter_int_wrongtype``, ``double_flate_chain``) now match the live Java
oracle line-for-line with no override; see
``tests/cos/oracle/test_cos_stream_filter_fuzz_wave1564.py`` for the dedicated
COSStream-level pin of the corrected behaviour.
"""

from __future__ import annotations

import hashlib

from pypdfbox.cos import (
    COSArray,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common import PDStream
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_FILTER = COSName.FILTER  # type: ignore[attr-defined]
_LENGTH = COSName.LENGTH  # type: ignore[attr-defined]
_FLATE = COSName.FLATE_DECODE  # type: ignore[attr-defined]
_AHX = _N("ASCIIHexDecode")

# Pre-computed encoded payloads, shared bit-for-bit with the Java probe.
# FlateDecode of "Hello, PDFBox!" (14 decoded bytes).
_FLATE_HELLO = bytes.fromhex("789cf348cdc9c9d75108707173caaf50040022410465")
# FlateDecode of "" (0 decoded bytes).
_FLATE_EMPTY = bytes.fromhex("789c030000000001")
# ASCIIHexDecode of "Hi" -> "4869>" (5 raw bytes, 2 decoded).
_AHX_HI = b"4869>"
# Truncated/garbage flate body (invalid zlib stream).
_BAD_FLATE = bytes.fromhex("789cffff00")


def _ascii_hex_encode(data: bytes) -> bytes:
    return data.hex().encode("ascii") + b">"


def _flate_encode(decoded: bytes) -> bytes:
    tmp = COSStream()
    with tmp.create_output_stream(_FLATE) as out:
        out.write(decoded)
    with tmp.create_raw_input_stream() as src:
        return src.read()


# ASCIIHexDecode then FlateDecode chain over the once-flate "Hello" body.
_AHX_FLATE_HELLO = _ascii_hex_encode(_FLATE_HELLO)


def _write_raw(s: COSStream, data: bytes) -> None:
    with s.create_raw_output_stream() as out:
        out.write(data)


def _arr(*items: COSName) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _build(case_id: str) -> COSStream:
    s = COSStream()
    if case_id == "no_filter_plain":
        _write_raw(s, b"plain-body")
    elif case_id == "flate_single_name":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _FLATE)
    elif case_id == "flate_array_one":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _arr(_FLATE))
    elif case_id == "asciihex_single":
        _write_raw(s, _AHX_HI)
        s.set_item(_FILTER, _AHX)
    elif case_id == "chain_ahx_flate":
        _write_raw(s, _AHX_FLATE_HELLO)
        s.set_item(_FILTER, _arr(_AHX, _FLATE))
    elif case_id == "flate_empty_body":
        _write_raw(s, _FLATE_EMPTY)
        s.set_item(_FILTER, _FLATE)
    elif case_id == "empty_no_body_no_filter":
        pass
    elif case_id == "empty_no_body_with_filter":
        s.set_item(_FILTER, _FLATE)
    elif case_id == "length_correct":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _FLATE)
        s.set_item(_LENGTH, COSInteger.get(len(_FLATE_HELLO)))
    elif case_id == "length_wrong_small":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _FLATE)
        s.set_item(_LENGTH, COSInteger.get(3))
    elif case_id == "length_wrong_huge":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _FLATE)
        s.set_item(_LENGTH, COSInteger.get(999999))
    elif case_id == "length_negative":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _FLATE)
        s.set_item(_LENGTH, COSInteger.get(-5))
    elif case_id == "length_absent_with_body":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _FLATE)
        s.remove_item(_LENGTH)
    elif case_id == "raw_no_filter":
        _write_raw(s, _FLATE_HELLO)
    elif case_id == "bad_flate_body":
        _write_raw(s, _BAD_FLATE)
        s.set_item(_FILTER, _FLATE)
    elif case_id == "filter_unknown_name":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _N("BogusDecode"))
    elif case_id == "filter_string_wrongtype":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, COSString("FlateDecode"))
    elif case_id == "filter_int_wrongtype":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, COSInteger.get(7))
    elif case_id == "filter_array_empty":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, COSArray())
    elif case_id == "double_flate_chain":
        _write_raw(s, _flate_encode(_FLATE_HELLO))
        s.set_item(_FILTER, _arr(_FLATE, _FLATE))
    else:  # pragma: no cover - guard against typos in _CASES
        raise AssertionError(f"unknown case {case_id}")
    return s


def _sha8(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


# Cases where pypdfbox returns an empty BytesIO for a body-less stream but
# upstream raises IOException — remap pypdfbox's empty-decode token.
_EMPTY_DECODE_CASES = {"empty_no_body_no_filter", "empty_no_body_with_filter"}
# Cases where get_length() is None (no /Length, no body) but upstream → 0.
_NULL_LENGTH_CASES = {"empty_no_body_no_filter", "empty_no_body_with_filter"}


def _dec_proj(pd: PDStream, case_id: str) -> str:
    try:
        with pd.create_input_stream() as src:
            b = src.read()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _java_exc(exc)
    if case_id in _EMPTY_DECODE_CASES:
        # DIVERGENCE 1+3: pypdfbox returns empty BytesIO for a body-less
        # stream; upstream PDStream raises IOException. Remap to Java token.
        return "ERR:IOException"
    return f"{len(b)}/{_sha8(b)}"


def _raw_proj(pd: PDStream) -> str:
    try:
        with pd.get_cos_object().create_raw_input_stream() as src:
            b = src.read()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _java_exc(exc)
    return f"{len(b)}/{_sha8(b)}"


def _filters_proj(pd: PDStream) -> str:
    try:
        fs = pd.get_filters()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _java_exc(exc)
    if not fs:
        return "-"
    return ",".join(f.name for f in fs)


def _length_proj(pd: PDStream, case_id: str) -> str:
    try:
        length = pd.get_length()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _java_exc(exc)
    if length is None and case_id in _NULL_LENGTH_CASES:
        # DIVERGENCE 2: pypdfbox returns None for "no /Length, no body";
        # upstream getInt(LENGTH, 0) returns 0.
        return "0"
    return str(length)


def _java_exc(exc: BaseException) -> str:
    # DIVERGENCE 3: OSError (Python I/O) is the contract-equal of Java's
    # IOException. Normalise to the Java spelling for line comparison.
    name = type(exc).__name__
    if name == "OSError":
        return "IOException"
    return name


def _project(case_id: str) -> str:
    pd = PDStream(_build(case_id))
    dec = _dec_proj(pd, case_id)
    raw = _raw_proj(pd)
    filters = _filters_proj(pd)
    length = _length_proj(pd, case_id)
    return f"CASE {case_id} dec={dec} raw={raw} filters={filters} length={length}"


_CASES = [
    "no_filter_plain",
    "flate_single_name",
    "flate_array_one",
    "asciihex_single",
    "chain_ahx_flate",
    "flate_empty_body",
    "empty_no_body_no_filter",
    "empty_no_body_with_filter",
    "length_correct",
    "length_wrong_small",
    "length_wrong_huge",
    "length_negative",
    "length_absent_with_body",
    "raw_no_filter",
    "bad_flate_body",
    "filter_unknown_name",
    "filter_string_wrongtype",
    "filter_int_wrongtype",
    "filter_array_empty",
    "double_flate_chain",
]

# Both-sides honest divergences pinned as expected Java-side overrides on top
# of the live oracle output. Each entry rewrites the Java line so the
# assertion documents the gap explicitly rather than silently masking it.
#
# Only the body-less-stream cases (DIVERGENCE 1-3) remain; the former
# non-name-/Filter and duplicate-filter divergences were fixed in wave 1564,
# so those cases now match the live Java oracle directly.
_DIVERGENCE_PINS: dict[str, str] = {}


@requires_oracle
def test_pd_stream_decode_raw_matches_pdfbox() -> None:
    java_lines = run_probe_text("PdStreamFuzzProbe", *_CASES).splitlines()
    # The decode-time divergences are normalised inside the per-projection
    # helpers (empty-body remap, OSError↔IOException). No Java-line overrides
    # remain after the wave-1564 cos_stream.py fixes.
    expected = []
    for case_id, java_line in zip(_CASES, java_lines, strict=True):
        expected.append(_DIVERGENCE_PINS.get(case_id, java_line))
    py = [_project(c) for c in _CASES]
    assert py == expected


def test_no_filter_decoded_equals_raw() -> None:
    """A stream with no /Filter passes its body through verbatim — decoded
    bytes equal raw bytes (matches upstream COSStream behaviour)."""
    s = _build("no_filter_plain")
    pd = PDStream(s)
    with pd.create_input_stream() as a:
        dec = a.read()
    with pd.get_cos_object().create_raw_input_stream() as b:
        raw = b.read()
    assert dec == raw == b"plain-body"


def test_flate_round_trip_decoded_length() -> None:
    """A FlateDecode body decodes to the original 14-byte payload."""
    pd = PDStream(_build("flate_single_name"))
    with pd.create_input_stream() as src:
        assert src.read() == b"Hello, PDFBox!"
    with pd.get_cos_object().create_raw_input_stream() as src:
        assert src.read() == _FLATE_HELLO


def test_chain_two_filters_decodes_in_order() -> None:
    """ASCIIHexDecode then FlateDecode applied left-to-right round-trips."""
    pd = PDStream(_build("chain_ahx_flate"))
    with pd.create_input_stream() as src:
        assert src.read() == b"Hello, PDFBox!"
    assert [f.name for f in pd.get_filters()] == ["ASCIIHexDecode", "FlateDecode"]


def test_get_length_returns_dictionary_length_entry() -> None:
    """get_length() returns the recorded /Length int verbatim — even when
    it disagrees with the actual encoded body (matches upstream
    getInt(LENGTH, 0), which never re-derives from the body)."""
    pd = PDStream(_build("length_wrong_small"))
    assert pd.get_length() == 3
    pd2 = PDStream(_build("length_wrong_huge"))
    assert pd2.get_length() == 999999
    pd3 = PDStream(_build("length_negative"))
    assert pd3.get_length() == -5


def test_wrongtype_filter_get_filters_empty() -> None:
    """A non-name /Filter (COSString / COSInteger) yields an empty
    get_filters() list — matching upstream's lenient normalisation."""
    assert PDStream(_build("filter_string_wrongtype")).get_filters() == []
    assert PDStream(_build("filter_int_wrongtype")).get_filters() == []
    assert PDStream(_build("filter_array_empty")).get_filters() == []
