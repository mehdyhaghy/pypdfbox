"""Differential fuzz audit for the READ side of
``pypdfbox.pdmodel.common.PDStream``'s filter-chain accessors vs Apache
PDFBox 3.0.7 (wave 1529, agent D).

Complements ``test_pd_stream_encode_ctor_wave1483`` (which covers the
encode-on-write constructor / ``addCompression`` write path). This module
targets ``get_filters`` / ``get_decode_parms`` / ``get_file_filters`` /
``get_file_decode_parms`` / ``get_decoded_stream_length`` against
malformed ``/Filter`` and ``/DecodeParms`` shapes:

* ``/Filter`` absent, single name, array, empty array, an unknown filter
  name, a non-name / non-array value (``COSString`` / ``COSInteger``), and
  an array carrying a ``COSString`` / ``COSNull`` element;
* ``/DecodeParms`` absent, single dict, array, array with ``COSNull`` /
  non-dict holes, a non-dict / non-array value, the ``/DP`` alias (alone,
  and shadowed by the canonical key), and ``/Filter``-vs-``/DecodeParms``
  arity mismatches both ways;
* ``/FFilter`` + ``/FDecodeParms`` (external-file) variants.

Both sides are driven on the SAME case ids: the Java probe
(``oracle/probes/PdStreamFilterChainFuzzProbe.java``) builds an in-process
``COSStream`` per id, wraps it in a ``PDStream`` and projects a stable
framed line; this module rebuilds the identical ``COSStream`` shapes
through pypdfbox and projects the identical grammar, then asserts
line-for-line parity.

Line grammar (one per case, ``_CASES`` order)::

    CASE <id> filters=<...> parms=<...> ffilters=<...> fparms=<...> dl=<int>

``filters`` is ``name,name,...`` (``-`` when empty); a non-name array
element is rendered by its COS class simple name (upstream's
``COSArray.toList()`` keeps malformed elements verbatim). ``parms`` is
``null`` when the accessor returns ``None``, else ``<count>:kind,kind``
where kind is ``dict`` for a real dictionary and the class simple name
otherwise; ``ERR:<Exc>`` when the accessor raises. ``ffilters`` is the
string-form chain (matching upstream ``getFileFilters() : List<String>``,
which casts each element to ``COSName`` — a malformed element raises, so we
project ``ERR:ClassCastException`` for both sides). ``dl`` is
``get_decoded_stream_length()``.

Java is ground truth: a divergence is either a production fix in
``pypdfbox/pdmodel/common/pd_stream.py`` or a both-sides pin documented in
``CHANGES.md`` Wave 1529.
"""

from __future__ import annotations

from collections.abc import Mapping

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common import PDStream
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_FILTER = COSName.FILTER  # type: ignore[attr-defined]
_DECODE_PARMS = _N("DecodeParms")
_DP = _N("DP")
_F_FILTER = _N("FFilter")
_F_DECODE_PARMS = _N("FDecodeParms")
_DL = _N("DL")
_FLATE = COSName.FLATE_DECODE  # type: ignore[attr-defined]
_A85 = COSName.ASCII85_DECODE  # type: ignore[attr-defined]


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _dict(key: str, value: int) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N(key), COSInteger.get(value))
    return d


def _build(case_id: str) -> COSStream:
    s = COSStream()
    if case_id == "filter_absent":
        pass
    elif case_id == "filter_single_name":
        s.set_item(_FILTER, _FLATE)
    elif case_id == "filter_array_one":
        s.set_item(_FILTER, _arr(_FLATE))
    elif case_id == "filter_array_two":
        s.set_item(_FILTER, _arr(_A85, _FLATE))
    elif case_id == "filter_array_empty":
        s.set_item(_FILTER, COSArray())
    elif case_id == "filter_unknown_name":
        s.set_item(_FILTER, _N("BogusDecode"))
    elif case_id == "filter_string_invalid":
        s.set_item(_FILTER, COSString("FlateDecode"))
    elif case_id == "filter_int_invalid":
        s.set_item(_FILTER, COSInteger.get(7))
    elif case_id == "filter_array_with_string":
        s.set_item(_FILTER, _arr(_FLATE, COSString("x")))
    elif case_id == "filter_array_with_null":
        s.set_item(_FILTER, _arr(_FLATE, COSNull.NULL))
    elif case_id == "parms_absent":
        s.set_item(_FILTER, _FLATE)
    elif case_id == "parms_single_dict":
        s.set_item(_FILTER, _FLATE)
        s.set_item(_DECODE_PARMS, _dict("Predictor", 12))
    elif case_id == "parms_array_two":
        s.set_item(_FILTER, _arr(_A85, _FLATE))
        s.set_item(_DECODE_PARMS, _arr(_dict("a", 1), _dict("Predictor", 12)))
    elif case_id == "parms_array_with_null":
        s.set_item(_FILTER, _arr(_A85, _FLATE))
        s.set_item(_DECODE_PARMS, _arr(COSNull.NULL, _dict("Predictor", 12)))
    elif case_id == "parms_array_all_null":
        s.set_item(_FILTER, _arr(_FLATE, _FLATE))
        s.set_item(_DECODE_PARMS, _arr(COSNull.NULL, COSNull.NULL))
    elif case_id == "parms_array_with_nondict":
        s.set_item(_FILTER, _arr(_FLATE, _FLATE))
        s.set_item(_DECODE_PARMS, _arr(_dict("Predictor", 12), _N("Oops")))
    elif case_id == "parms_name_invalid":
        s.set_item(_FILTER, _FLATE)
        s.set_item(_DECODE_PARMS, _N("Nope"))
    elif case_id == "parms_int_invalid":
        s.set_item(_FILTER, _FLATE)
        s.set_item(_DECODE_PARMS, COSInteger.get(3))
    elif case_id == "parms_dp_alias_only":
        s.set_item(_FILTER, _FLATE)
        s.set_item(_DP, _dict("Predictor", 15))
    elif case_id == "parms_dp_and_canonical":
        s.set_item(_FILTER, _FLATE)
        s.set_item(_DECODE_PARMS, _dict("Predictor", 2))
        s.set_item(_DP, _dict("Predictor", 99))
    elif case_id == "parms_single_dict_filter_array":
        s.set_item(_FILTER, _arr(_A85, _FLATE))
        s.set_item(_DECODE_PARMS, _dict("Predictor", 12))
    elif case_id == "parms_array_filter_single":
        s.set_item(_FILTER, _FLATE)
        s.set_item(_DECODE_PARMS, _arr(_dict("Predictor", 12)))
    elif case_id == "parms_len_mismatch_more":
        s.set_item(_FILTER, _arr(_FLATE))
        s.set_item(_DECODE_PARMS, _arr(_dict("Predictor", 12), _dict("Predictor", 2)))
    elif case_id == "ffilter_array_with_null":
        s.set_item(_F_FILTER, _arr(_FLATE, COSNull.NULL))
        s.set_item(_F_DECODE_PARMS, _arr(COSNull.NULL, _dict("Predictor", 12)))
    elif case_id == "ffilter_single_fparms_array":
        s.set_item(_F_FILTER, _FLATE)
        s.set_item(_F_DECODE_PARMS, _arr(_dict("Predictor", 12)))
    elif case_id == "fparms_name_invalid":
        s.set_item(_F_FILTER, _FLATE)
        s.set_item(_F_DECODE_PARMS, _N("Nope"))
    elif case_id == "dl_set":
        s.set_item(_FILTER, _FLATE)
        s.set_item(_DL, COSInteger.get(4242))
    else:  # pragma: no cover - guard against typos in _CASES
        raise AssertionError(f"unknown case {case_id}")
    return s


def _filters_proj(pd: PDStream) -> str:
    try:
        fs = pd.get_filters()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _exc_name(exc)
    if not fs:
        return "-"
    parts: list[str] = []
    for o in fs:
        if isinstance(o, COSName):
            parts.append(o.name)
        else:
            parts.append(_cos_simple_name(o))
    return ",".join(parts)


def _ffilters_proj(pd: PDStream) -> str:
    # Java getFileFilters() returns List<String> by casting each element to
    # COSName; pypdfbox's get_file_filters_as_strings is its string-form
    # mirror (a non-name element raises on both sides).
    try:
        fs = pd.get_file_filters_as_strings()
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _java_exc_for(exc)
    if not fs:
        return "-"
    return ",".join(fs)


def _parms_proj_list(parms: list[COSDictionary] | None) -> str:
    if parms is None:
        return "null"
    parts: list[str] = []
    for o in parms:
        if isinstance(o, (COSDictionary, Mapping)):
            parts.append("dict")
        else:
            parts.append(_cos_simple_name(o))
    return f"{len(parms)}:" + ",".join(parts)


def _decode_parms_proj(pd: PDStream) -> str:
    try:
        return _parms_proj_list(pd.get_decode_parms())
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _exc_name(exc)


def _file_parms_proj(pd: PDStream) -> str:
    try:
        return _parms_proj_list(pd.get_file_decode_parms())
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + _exc_name(exc)


def _cos_simple_name(o: object) -> str:
    # Map pypdfbox COS class names onto the Java simple class names the
    # probe emits (they already match: COSName, COSString, COSNull, ...).
    return type(o).__name__


def _exc_name(exc: BaseException) -> str:
    return type(exc).__name__


def _java_exc_for(exc: BaseException) -> str:
    # A non-name element in /FFilter raises TypeError/AttributeError in
    # pypdfbox's string projection; Java raises ClassCastException. Pin
    # both to the Java name for the line-level comparison.
    return "ClassCastException"


def _project(case_id: str) -> str:
    pd = PDStream(_build(case_id))
    filters = _filters_proj(pd)
    parms = _decode_parms_proj(pd)
    ffilters = _ffilters_proj(pd)
    fparms = _file_parms_proj(pd)
    dl = str(pd.get_decoded_stream_length())
    return (
        f"CASE {case_id} filters={filters} parms={parms} "
        f"ffilters={ffilters} fparms={fparms} dl={dl}"
    )


_CASES = [
    "filter_absent",
    "filter_single_name",
    "filter_array_one",
    "filter_array_two",
    "filter_array_empty",
    "filter_unknown_name",
    "filter_string_invalid",
    "filter_int_invalid",
    "filter_array_with_string",
    "filter_array_with_null",
    "parms_absent",
    "parms_single_dict",
    "parms_array_two",
    "parms_array_with_null",
    "parms_array_all_null",
    "parms_array_with_nondict",
    "parms_name_invalid",
    "parms_int_invalid",
    "parms_dp_alias_only",
    "parms_dp_and_canonical",
    "parms_single_dict_filter_array",
    "parms_array_filter_single",
    "parms_len_mismatch_more",
    "ffilter_array_with_null",
    "ffilter_single_fparms_array",
    "fparms_name_invalid",
    "dl_set",
]


@requires_oracle
def test_pd_stream_filter_chain_matches_pdfbox() -> None:
    java = run_probe_text("PdStreamFilterChainFuzzProbe", *_CASES).splitlines()
    py = [_project(c) for c in _CASES]
    assert py == java
