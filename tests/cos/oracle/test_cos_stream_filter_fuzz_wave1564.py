"""Differential fuzz audit for ``COSStream``'s ``/Filter`` resolution and
decode path vs Apache PDFBox 3.0.7 (wave 1564, agent A).

Pins the two ``COSStream.get_filter_list`` / decode-loop behaviours that wave
1563 flagged as latent divergences (DEFERRED.md) and that this wave fixed,
each verified against the live PDFBox 3.0.7 oracle
(``oracle/probes/CosStreamFilterFuzzProbe.java``):

1. **Non-name ``/Filter`` is lenient, not an error.** Upstream
   ``COSStream.getFilterList()`` falls through to an empty list for any
   ``/Filter`` that is neither a ``COSName`` nor a ``COSArray`` (a
   ``COSString`` / ``COSInteger`` / ``COSBoolean`` scalar), so the body is
   passed through verbatim — decoded == raw. A non-name **element inside** a
   ``/Filter`` array is the opposite: upstream throws ``IOException``
   ("Forbidden type in filter array: ..."), mirrored here as ``OSError``.

2. **Duplicate filters are deduplicated.** Upstream ``Filter.decode``
   removes duplicate filter entries (keyed on the resolved ``Filter``
   instance, so abbreviated names collapse onto their long form), keeping the
   first occurrence, logs "Removed duplicated filter entries", and decodes
   the deduped chain once. ``[FlateDecode, FlateDecode]`` and ``[Fl, Fl]``
   therefore each decode a *single* time.

The probe and this module plant the same encoded bytes (shared bit-for-bit
via hex constants) and project the identical grammar::

    CASE <id> filters=<...> dec=<len|ERR:Exc>/<sha8> raw=<len>/<sha8>

Java is ground truth; the Python projection matches it line-for-line with no
divergence overrides (this wave closed the two gaps that previously needed
overrides on the wave-1563 PDStream pin).
"""

from __future__ import annotations

import hashlib

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_FILTER = COSName.FILTER  # type: ignore[attr-defined]
_FLATE = COSName.FLATE_DECODE  # type: ignore[attr-defined]
_AHX = COSName.get_pdf_name("ASCIIHexDecode")

# FlateDecode of "Hello, PDFBox!" (14 decoded bytes), shared with the probe.
_FLATE_HELLO = bytes.fromhex("789cf348cdc9c9d75108707173caaf50040022410465")


def _ascii_hex_encode(data: bytes) -> bytes:
    return data.hex().encode("ascii") + b">"


def _write_raw(s: COSStream, data: bytes) -> None:
    with s.create_raw_output_stream() as out:
        out.write(data)


def _arr(*items: COSName) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _mixed_arr(*items: object) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)  # type: ignore[arg-type]
    return a


def _build(case_id: str) -> COSStream:
    s = COSStream()
    if case_id == "single_valid_flate":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _FLATE)
    elif case_id == "non_name_string":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, COSString("FlateDecode"))
    elif case_id == "non_name_int":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, COSInteger.get(7))
    elif case_id == "non_name_bool":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, COSBoolean.TRUE)
    elif case_id == "array_non_name_element":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _mixed_arr(_FLATE, COSInteger.get(3)))
    elif case_id == "dup_flate":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _arr(_FLATE, _FLATE))
    elif case_id == "dup_flate_abbrev":
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, _arr(COSName.get_pdf_name("Fl"), COSName.get_pdf_name("Fl")))
    elif case_id == "distinct_ahx_flate":
        _write_raw(s, _ascii_hex_encode(_FLATE_HELLO))
        s.set_item(_FILTER, _arr(_AHX, _FLATE))
    else:  # pragma: no cover - guard against typos in _CASES
        raise AssertionError(f"unknown case {case_id}")
    return s


def _sha8(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


# Map the few COSBase scalar types to the Java getClass().getSimpleName() that
# the probe prints in the filters token for a non-name /Filter value.
_JAVA_SIMPLE_NAME = {
    "COSString": "COSString",
    "COSInteger": "COSInteger",
    "COSBoolean": "COSBoolean",
}


def _filters_proj(s: COSStream) -> str:
    try:
        f = s.get_filters()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _java_exc(exc)
    if f is None:
        return "-"
    if isinstance(f, COSName):
        return f.name
    if isinstance(f, COSArray):
        parts = []
        for entry in f:
            if isinstance(entry, COSName):
                parts.append(entry.name)
            else:
                parts.append(_JAVA_SIMPLE_NAME.get(type(entry).__name__, type(entry).__name__))
        return ",".join(parts)
    return _JAVA_SIMPLE_NAME.get(type(f).__name__, type(f).__name__)


def _dec_proj(s: COSStream) -> str:
    try:
        with s.create_input_stream() as src:
            b = src.read()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _java_exc(exc)
    return f"{len(b)}/{_sha8(b)}"


def _raw_proj(s: COSStream) -> str:
    try:
        with s.create_raw_input_stream() as src:
            b = src.read()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _java_exc(exc)
    return f"{len(b)}/{_sha8(b)}"


def _java_exc(exc: BaseException) -> str:
    # OSError (Python I/O) is the contract-equal of Java's IOException — the
    # "Forbidden type in filter array" path raises IOException upstream.
    name = type(exc).__name__
    if name == "OSError":
        return "IOException"
    return name


def _project(case_id: str) -> str:
    s = _build(case_id)
    filters = _filters_proj(s)
    dec = _dec_proj(s)
    raw = _raw_proj(s)
    return f"CASE {case_id} filters={filters} dec={dec} raw={raw}"


_CASES = [
    "single_valid_flate",
    "non_name_string",
    "non_name_int",
    "non_name_bool",
    "array_non_name_element",
    "dup_flate",
    "dup_flate_abbrev",
    "distinct_ahx_flate",
]

# PDFBox 3.0.7-derived expected output (verified against the live oracle on a
# dev box with the jar present). Self-contained so the assertions still pin
# the corrected behaviour where the oracle is unavailable.
_EXPECTED = [
    "CASE single_valid_flate filters=FlateDecode dec=14/05810675 raw=22/39ad8646",
    "CASE non_name_string filters=COSString dec=22/39ad8646 raw=22/39ad8646",
    "CASE non_name_int filters=COSInteger dec=22/39ad8646 raw=22/39ad8646",
    "CASE non_name_bool filters=COSBoolean dec=22/39ad8646 raw=22/39ad8646",
    "CASE array_non_name_element filters=FlateDecode,COSInteger "
    "dec=ERR:IOException raw=22/39ad8646",
    "CASE dup_flate filters=FlateDecode,FlateDecode dec=14/05810675 raw=22/39ad8646",
    "CASE dup_flate_abbrev filters=Fl,Fl dec=14/05810675 raw=22/39ad8646",
    "CASE distinct_ahx_flate filters=ASCIIHexDecode,FlateDecode dec=14/05810675 raw=45/6632be35",
]


@requires_oracle
def test_cos_stream_filter_matches_pdfbox() -> None:
    java_lines = run_probe_text("CosStreamFilterFuzzProbe", *_CASES).splitlines()
    assert java_lines == _EXPECTED  # guards the pinned expectations against drift
    py = [_project(c) for c in _CASES]
    assert py == java_lines


def test_cos_stream_filter_matches_pinned_expectations() -> None:
    """Oracle-free pin: the corrected behaviour matches the PDFBox-3.0.7
    ground-truth recorded in ``_EXPECTED``."""
    assert [_project(c) for c in _CASES] == _EXPECTED


def test_non_name_filter_passes_body_through_verbatim() -> None:
    """A non-name scalar /Filter (COSString / COSInteger / COSBoolean) is
    treated as 'no filters': get_filter_list() is empty and the decoded body
    equals the raw body (matches upstream's lenient normalisation)."""
    for value in (COSString("FlateDecode"), COSInteger.get(7), COSBoolean.TRUE):
        s = COSStream()
        _write_raw(s, _FLATE_HELLO)
        s.set_item(_FILTER, value)
        assert s.get_filter_list() == []
        with s.create_input_stream() as dec, s.create_raw_input_stream() as raw:
            assert dec.read() == raw.read() == _FLATE_HELLO


def test_non_name_array_element_raises_oserror() -> None:
    """A non-name element inside a /Filter array raises OSError (upstream
    IOException 'Forbidden type in filter array: ...')."""
    s = _build("array_non_name_element")
    import pytest

    with pytest.raises(OSError, match="Forbidden type in filter array"):
        s.get_filter_list()


def test_duplicate_filters_decode_once() -> None:
    """Consecutive identical filters are deduplicated: [FlateDecode,
    FlateDecode] over a single-flate body decodes once to the original."""
    s = _build("dup_flate")
    with s.create_input_stream() as src:
        assert src.read() == b"Hello, PDFBox!"


def test_abbreviated_duplicate_filters_decode_once() -> None:
    """Abbreviated duplicate names ([Fl, Fl]) resolve to the same filter and
    are deduplicated, decoding once."""
    s = _build("dup_flate_abbrev")
    with s.create_input_stream() as src:
        assert src.read() == b"Hello, PDFBox!"


def test_distinct_filters_all_apply() -> None:
    """Distinct filters ([ASCIIHexDecode, FlateDecode]) are not deduplicated;
    both apply left-to-right."""
    s = _build("distinct_ahx_flate")
    with s.create_input_stream() as src:
        assert src.read() == b"Hello, PDFBox!"
