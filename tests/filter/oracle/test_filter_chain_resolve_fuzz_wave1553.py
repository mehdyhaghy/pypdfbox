"""Differential /Filter + /DecodeParms PARSING + PAIRING + chain-resolution
fuzz vs Apache PDFBox 3.0.7.

Wave 1553, agent C. Where wave-1505 ``FilterFuzzProbe`` fingerprints decoded
BYTES, wave-1518/1543 poke the predictor DECODE math, and the wave-1529
``PdStreamFilterChainFuzzProbe`` exercises ``PDStream``'s name/parm-list
accessors, THIS test pins the three primitives that actually pair a /Filter
chain with its /DecodeParms inside the codec layer:

* ``FilterFactory.getFilter`` — abbreviation normalization (/Fl -> FlateDecode,
  /AHx /A85 /LZW /RL /CCF /DCT) and the unknown-name ``IOException`` (mirrored
  in pypdfbox as a ``KeyError`` surfaced through the factory).
* the shape of the resolved /Filter chain: single name vs array of 1/2/3,
  empty array, an array carrying a non-name element, and /Filter set to a wrong
  type (int / string).
* ``Filter.getDecodeParams(streamDict, index)`` — the per-filter parameter
  dict every concrete PDFBox codec invokes. The strict name+dict / array+array
  shape logic, the DP-over-DecodeParms precedence when both keys are present,
  mismatched array lengths (more/fewer parms than filters), null entries in the
  parms array, single dict on a multi-filter stream (-> empty), and array parms
  on a single-name filter (-> empty).

Java side: ``oracle/probes/FilterChainResolveFuzzProbe.java`` (declared in
package ``org.apache.pdfbox.filter`` so it can call the protected resolver).

Projection per case id (one line):

    CASE <id> resolve=<...> parms0=<...> parms1=<...> parms2=<...>

* ``resolve`` — for each name in chain order, the canonical long name
  ``FilterFactory`` resolves the (possibly abbreviated) name to, joined by
  ``|``; ``ERR:<Exc>`` for an unregistered name; ``SHAPE:<class>`` when the
  /Filter value (or an array element) is not a name; ``-`` for an empty chain.
* ``parmsN`` — ``Filter.getDecodeParams(streamDict, N)`` rendered as
  ``keys=k:v,k:v`` (sorted key order, integer values) or ``empty``.

The pypdfbox side reproduces the SAME projection from
``Filter.get_decode_params_for_filter`` (our strict resolver = upstream's
protected ``getDecodeParams``) plus ``FilterFactory`` + the /Filter shape.
The parity assertion is an exact line-by-line string compare, so both sides
are pinned EXACT. Where the live oracle is unavailable the expected strings
(captured from a live PDFBox-3.0.7 run on 2026-06-16) stand in as the gold.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
)
from pypdfbox.filter import FilterFactory
from pypdfbox.filter.filter import Filter
from tests.oracle.harness import oracle_available

# ---------------------------------------------------------------------------
# Probe runner — the probe is package-declared (org.apache.pdfbox.filter), so
# it is compiled with -d into the build dir and run by fully-qualified name
# (the bare-name harness helper cannot reach a packaged class).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ORACLE = _REPO_ROOT / "oracle"
_JARS_DIR = _ORACLE / "jars"
_PROBES = _ORACLE / "probes"
_BUILD = _ORACLE / "build"
_PROBE_FQN = "org.apache.pdfbox.filter.FilterChainResolveFuzzProbe"


def _classpath() -> str:
    jars = sorted(str(p) for p in _JARS_DIR.glob("*.jar"))
    return os.pathsep.join([*jars, str(_BUILD)])


def _run_probe(*args: str) -> str:
    src = _PROBES / "FilterChainResolveFuzzProbe.java"
    cls = _BUILD / "org/apache/pdfbox/filter/FilterChainResolveFuzzProbe.class"
    if not cls.is_file() or cls.stat().st_mtime < src.stat().st_mtime:
        _BUILD.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["javac", "-cp", _classpath(), "-d", str(_BUILD), str(src)],
            check=True,
            capture_output=True,
        )
    result = subprocess.run(
        ["java", "-cp", _classpath(), _PROBE_FQN, *args],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8")


requires_oracle = pytest.mark.skipif(
    not oracle_available(),
    reason="live PDFBox oracle unavailable — run oracle/download_jars.sh (needs java + javac)",
)

# ---------------------------------------------------------------------------
# Case builders — mirror FilterChainResolveFuzzProbe.build(String) one-for-one.
# ---------------------------------------------------------------------------
_FILTER = COSName.get_pdf_name("Filter")
_DECODE_PARMS = COSName.get_pdf_name("DecodeParms")
_DP = COSName.get_pdf_name("DP")


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _dict(key: str, value: int) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
    return d


def _build(case_id: str) -> COSDictionary:
    s = COSDictionary()
    if case_id == "single_name_flate":
        s.set_item(_FILTER, _name("FlateDecode"))
    elif case_id == "single_abbrev_fl":
        s.set_item(_FILTER, _name("Fl"))
    elif case_id == "single_abbrev_ahx":
        s.set_item(_FILTER, _name("AHx"))
    elif case_id == "single_abbrev_a85":
        s.set_item(_FILTER, _name("A85"))
    elif case_id == "single_abbrev_lzw":
        s.set_item(_FILTER, _name("LZW"))
    elif case_id == "single_abbrev_rl":
        s.set_item(_FILTER, _name("RL"))
    elif case_id == "single_abbrev_ccf":
        s.set_item(_FILTER, _name("CCF"))
    elif case_id == "single_abbrev_dct":
        s.set_item(_FILTER, _name("DCT"))
    elif case_id == "single_unknown":
        s.set_item(_FILTER, _name("BogusDecode"))
    elif case_id == "array_one_flate":
        s.set_item(_FILTER, COSArray([_name("FlateDecode")]))
    elif case_id == "array_two_a85_flate":
        s.set_item(_FILTER, COSArray([_name("ASCII85Decode"), _name("FlateDecode")]))
    elif case_id == "array_three_abbrev":
        s.set_item(_FILTER, COSArray([_name("A85"), _name("Fl"), _name("AHx")]))
    elif case_id == "array_with_unknown":
        s.set_item(_FILTER, COSArray([_name("FlateDecode"), _name("Nope")]))
    elif case_id == "array_empty":
        s.set_item(_FILTER, COSArray())
    elif case_id == "filter_int":
        s.set_item(_FILTER, COSInteger.get(7))
    elif case_id == "filter_string":
        from pypdfbox.cos import COSString  # noqa: PLC0415

        s.set_item(_FILTER, COSString("FlateDecode"))
    elif case_id == "filter_array_with_int":
        ai = COSArray()
        ai.add(_name("FlateDecode"))
        ai.add(COSInteger.get(3))
        s.set_item(_FILTER, ai)
    elif case_id == "name_dict":
        s.set_item(_FILTER, _name("FlateDecode"))
        s.set_item(_DECODE_PARMS, _dict("Predictor", 12))
    elif case_id == "name_dict_dp_alias":
        s.set_item(_FILTER, _name("FlateDecode"))
        s.set_item(_DP, _dict("Predictor", 15))
    elif case_id == "name_dict_both_dp_wins":
        s.set_item(_FILTER, _name("FlateDecode"))
        s.set_item(_DECODE_PARMS, _dict("Predictor", 2))
        s.set_item(_DP, _dict("Predictor", 99))
    elif case_id == "name_array_parms":
        s.set_item(_FILTER, _name("FlateDecode"))
        nap = COSArray()
        nap.add(_dict("Predictor", 12))
        s.set_item(_DECODE_PARMS, nap)
    elif case_id == "name_int_parms":
        s.set_item(_FILTER, _name("FlateDecode"))
        s.set_item(_DECODE_PARMS, COSInteger.get(3))
    elif case_id == "name_name_parms":
        s.set_item(_FILTER, _name("FlateDecode"))
        s.set_item(_DECODE_PARMS, _name("Oops"))
    elif case_id == "array_array_match":
        s.set_item(_FILTER, COSArray([_name("ASCII85Decode"), _name("FlateDecode")]))
        aam = COSArray()
        aam.add(_dict("a", 1))
        aam.add(_dict("Predictor", 12))
        s.set_item(_DECODE_PARMS, aam)
    elif case_id == "array_array_with_null":
        s.set_item(_FILTER, COSArray([_name("ASCII85Decode"), _name("FlateDecode")]))
        awn = COSArray()
        awn.add(COSNull.NULL)
        awn.add(_dict("Predictor", 12))
        s.set_item(_DECODE_PARMS, awn)
    elif case_id == "array_array_short":
        s.set_item(_FILTER, COSArray([_name("ASCII85Decode"), _name("FlateDecode")]))
        aas = COSArray()
        aas.add(_dict("Predictor", 12))
        s.set_item(_DECODE_PARMS, aas)
    elif case_id == "array_array_long":
        s.set_item(_FILTER, COSArray([_name("FlateDecode")]))
        aal = COSArray()
        aal.add(_dict("Predictor", 12))
        aal.add(_dict("Predictor", 2))
        s.set_item(_DECODE_PARMS, aal)
    elif case_id == "array_array_nondict":
        s.set_item(_FILTER, COSArray([_name("FlateDecode"), _name("FlateDecode")]))
        aan = COSArray()
        aan.add(_dict("Predictor", 12))
        aan.add(_name("Oops"))
        s.set_item(_DECODE_PARMS, aan)
    elif case_id == "array_single_dict":
        s.set_item(_FILTER, COSArray([_name("ASCII85Decode"), _name("FlateDecode")]))
        s.set_item(_DECODE_PARMS, _dict("Predictor", 12))
    elif case_id == "array_dp_alias":
        s.set_item(_FILTER, COSArray([_name("ASCII85Decode"), _name("FlateDecode")]))
        ada = COSArray()
        ada.add(_dict("a", 1))
        ada.add(_dict("Predictor", 12))
        s.set_item(_DP, ada)
    elif case_id == "parms_absent":
        s.set_item(_FILTER, COSArray([_name("ASCII85Decode"), _name("FlateDecode")]))
    elif case_id == "parms_null":
        s.set_item(_FILTER, _name("FlateDecode"))
        s.set_item(_DECODE_PARMS, COSNull.NULL)
    elif case_id == "array_array_all_null":
        s.set_item(_FILTER, COSArray([_name("FlateDecode"), _name("FlateDecode")]))
        aanull = COSArray()
        aanull.add(COSNull.NULL)
        aanull.add(COSNull.NULL)
        s.set_item(_DECODE_PARMS, aanull)
    elif case_id == "no_filter_dict_parms":
        s.set_item(_DECODE_PARMS, _dict("Predictor", 12))
    else:
        raise AssertionError(f"unknown case {case_id}")
    return s


# ---------------------------------------------------------------------------
# pypdfbox projections — mirror the Java probe's resolveProj / parmsProj.
# ---------------------------------------------------------------------------
_LONG_NAMES = (
    "FlateDecode",
    "LZWDecode",
    "ASCII85Decode",
    "ASCIIHexDecode",
    "RunLengthDecode",
    "CCITTFaxDecode",
    "DCTDecode",
    "JPXDecode",
    "JBIG2Decode",
    "Crypt",
    "Identity",
)


def _canonical_name(name: COSName) -> str:
    """Long name FilterFactory resolves ``name`` to (visible abbreviation
    expansion), derived by identity-matching against the known long names —
    mirrors the probe's ``canonicalName``."""
    try:
        want = FilterFactory.get(name)
    except KeyError:
        return "ERR:IOException"
    for long_name in _LONG_NAMES:
        try:
            if FilterFactory.get(long_name) is want:
                return long_name
        except KeyError:
            continue
    return type(want).__name__


def _resolve_proj(s: COSDictionary) -> str:
    f = s.get_dictionary_object(_FILTER)
    if f is None:
        return "-"
    names: list[COSName] = []
    if isinstance(f, COSName):
        names.append(f)
    elif isinstance(f, COSArray):
        if f.size() == 0:
            return "-"
        for i in range(f.size()):
            entry = f.get_object(i)
            if isinstance(entry, COSName):
                names.append(entry)
            else:
                cls = "null" if entry is None else type(entry).__name__
                return f"SHAPE:{cls}"
    else:
        return f"SHAPE:{type(f).__name__}"
    return "|".join(_canonical_name(n) for n in names)


def _parms_proj(s: COSDictionary, index: int) -> str:
    d = Filter.get_decode_params_for_filter(s, index)
    if d is None or d.size() == 0:
        return "empty"
    items = sorted((k.name, d.get_dictionary_object(k)) for k in d.key_set())
    rendered = ",".join(f"{k}:{_int_repr(v)}" for k, v in items)
    return f"keys={rendered}"


def _int_repr(value: object) -> str:
    if isinstance(value, COSInteger):
        return str(value.value)
    return "null" if value is None else type(value).__name__


def _py_projection(case_id: str) -> str:
    s = _build(case_id)
    return (
        f"CASE {case_id} resolve={_resolve_proj(s)}"
        f" parms0={_parms_proj(s, 0)}"
        f" parms1={_parms_proj(s, 1)}"
        f" parms2={_parms_proj(s, 2)}"
    )


# ---------------------------------------------------------------------------
# The gold expectations (captured from a live Apache PDFBox 3.0.7 run, the
# strict ``Filter.getDecodeParams`` resolver, on 2026-06-16). Stored compactly
# as ``(case_id, resolve, parms0, parms1, parms2)`` and assembled into the full
# ``CASE ...`` line by ``_line`` — keeps each row inside the line-length gate
# while pinning the projection EXACT.
# ---------------------------------------------------------------------------
_P12 = "keys=Predictor:12"
_P15 = "keys=Predictor:15"
_P99 = "keys=Predictor:99"
_GOLD: tuple[tuple[str, str, str, str, str], ...] = (
    # ---- FilterFactory abbreviation / shape resolution ----
    ("single_name_flate", "FlateDecode", "empty", "empty", "empty"),
    ("single_abbrev_fl", "FlateDecode", "empty", "empty", "empty"),
    ("single_abbrev_ahx", "ASCIIHexDecode", "empty", "empty", "empty"),
    ("single_abbrev_a85", "ASCII85Decode", "empty", "empty", "empty"),
    ("single_abbrev_lzw", "LZWDecode", "empty", "empty", "empty"),
    ("single_abbrev_rl", "RunLengthDecode", "empty", "empty", "empty"),
    ("single_abbrev_ccf", "CCITTFaxDecode", "empty", "empty", "empty"),
    ("single_abbrev_dct", "DCTDecode", "empty", "empty", "empty"),
    # unknown name -> upstream throws IOException; pypdfbox surfaces KeyError
    # through the factory, projected identically as ERR:IOException.
    ("single_unknown", "ERR:IOException", "empty", "empty", "empty"),
    ("array_one_flate", "FlateDecode", "empty", "empty", "empty"),
    ("array_two_a85_flate", "ASCII85Decode|FlateDecode", "empty", "empty", "empty"),
    ("array_three_abbrev", "ASCII85Decode|FlateDecode|ASCIIHexDecode", "empty", "empty", "empty"),
    ("array_with_unknown", "FlateDecode|ERR:IOException", "empty", "empty", "empty"),
    ("array_empty", "-", "empty", "empty", "empty"),
    ("filter_int", "SHAPE:COSInteger", "empty", "empty", "empty"),
    ("filter_string", "SHAPE:COSString", "empty", "empty", "empty"),
    ("filter_array_with_int", "SHAPE:COSInteger", "empty", "empty", "empty"),
    # ---- /DecodeParms pairing ----
    # single name + dict -> the dict at EVERY index (the single-dict case is
    # not bounded by index upstream).
    ("name_dict", "FlateDecode", _P12, _P12, _P12),
    ("name_dict_dp_alias", "FlateDecode", _P15, _P15, _P15),
    # both /DP and /DecodeParms present -> /DP wins (99), not /DecodeParms (2).
    ("name_dict_both_dp_wins", "FlateDecode", _P99, _P99, _P99),
    # single name + ARRAY parms -> mismatched shape -> empty.
    ("name_array_parms", "FlateDecode", "empty", "empty", "empty"),
    # name + non-dict/non-array parms -> logged + empty.
    ("name_int_parms", "FlateDecode", "empty", "empty", "empty"),
    ("name_name_parms", "FlateDecode", "empty", "empty", "empty"),
    ("array_array_match", "ASCII85Decode|FlateDecode", "keys=a:1", _P12, "empty"),
    # null at index 0 -> empty there, dict at index 1.
    ("array_array_with_null", "ASCII85Decode|FlateDecode", "empty", _P12, "empty"),
    # 2 filters, 1 parm -> index 1 out of range -> empty.
    ("array_array_short", "ASCII85Decode|FlateDecode", _P12, "empty", "empty"),
    # 1 filter, 2 parms -> both indices resolve, index 2 empty.
    ("array_array_long", "FlateDecode", _P12, "keys=Predictor:2", "empty"),
    # array + array, second entry a non-dict name -> empty there.
    ("array_array_nondict", "FlateDecode|FlateDecode", _P12, "empty", "empty"),
    # array filter + SINGLE dict -> mismatched shape -> empty everywhere.
    ("array_single_dict", "ASCII85Decode|FlateDecode", "empty", "empty", "empty"),
    ("array_dp_alias", "ASCII85Decode|FlateDecode", "keys=a:1", _P12, "empty"),
    ("parms_absent", "ASCII85Decode|FlateDecode", "empty", "empty", "empty"),
    # /DecodeParms explicitly null -> empty.
    ("parms_null", "FlateDecode", "empty", "empty", "empty"),
    ("array_array_all_null", "FlateDecode|FlateDecode", "empty", "empty", "empty"),
    # /DecodeParms with no /Filter -> filter slot null -> empty.
    ("no_filter_dict_parms", "-", "empty", "empty", "empty"),
)


def _line(case_id: str, resolve: str, p0: str, p1: str, p2: str) -> str:
    return f"CASE {case_id} resolve={resolve} parms0={p0} parms1={p1} parms2={p2}"


_EXPECTED: dict[str, str] = {row[0]: _line(*row) for row in _GOLD}
_CASE_IDS = list(_EXPECTED.keys())


@pytest.mark.parametrize("case_id", _CASE_IDS)
def test_pinned_against_pdfbox_3_0_7(case_id: str) -> None:
    """pypdfbox's strict resolver + factory match the captured PDFBox-3.0.7
    projection for every fuzzed /Filter + /DecodeParms shape."""
    assert _py_projection(case_id) == _EXPECTED[case_id]


@requires_oracle
def test_matches_live_oracle() -> None:
    """When the live PDFBox oracle is available, the captured expectations
    must still match what the jar emits today (guards against stale gold)."""
    raw = _run_probe(*_CASE_IDS)
    lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    got = {ln.split(" ", 2)[1]: ln for ln in lines}
    for case_id in _CASE_IDS:
        assert got[case_id] == _EXPECTED[case_id], case_id


@requires_oracle
def test_python_matches_live_oracle() -> None:
    """End-to-end: pypdfbox projection == live PDFBox projection, line by line."""
    raw = _run_probe(*_CASE_IDS)
    lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    java = {ln.split(" ", 2)[1]: ln for ln in lines}
    for case_id in _CASE_IDS:
        assert _py_projection(case_id) == java[case_id], case_id
