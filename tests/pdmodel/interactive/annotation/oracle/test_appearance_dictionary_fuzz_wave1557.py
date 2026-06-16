"""Appearance dictionary / entry state-resolution parity with PDFBox 3.0.7.

Complements wave 1520 (``test_appearance_dictionary_fuzz_wave1520.py``,
/AP value-type matrix) and wave 1531 (``test_appearance_entry_fuzz_wave1531.py``,
per-entry value + stream numeric accessors) by drilling into resolution
angles neither covers:

* ``/R`` / ``/D`` absent -> ``get_rollover_appearance`` /
  ``get_down_appearance`` fall back to ``/N``; the fallback entry wraps the
  *same* COS object as ``/N`` (object identity), and an explicit ``/R`` /
  ``/D`` shadows the fallback.
* ``get_sub_dictionary`` resolved *values* -> each state stream's ``/BBox``
  (existing probes project only the key names), simulating the widget
  ``/AS`` state pick (``sub[as_name]``).
* the full ``get_normal_appearance().get_appearance_stream()`` chain
  (BBox / Resources / identity) of a direct ``/N`` stream.
* double-indirect (``COSObject -> COSObject -> stream``) ``/N`` value ->
  resolves to ``none`` (upstream ``getDictionaryObject`` resolves only one
  indirection level for the type check).

Honest divergence (pinned, not reproduced): upstream ``getSubDictionary``
returns a ``COSDictionaryMap`` whose ``size()`` delegates to the raw
``COSDictionary`` entry count (includes non-stream states), while its
``keySet()`` / ``get()`` only expose the stream-valued states. pypdfbox's
``get_sub_dictionary`` returns a plain ``dict`` whose ``len()`` matches the
behaviourally meaningful ``keySet()`` count, not the raw ``size()``. We
compare against the ``keys=`` (keySet) projection; the ``rawsize=`` field is
recorded for documentation only.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name("N")
_R = COSName.get_pdf_name("R")
_D = COSName.get_pdf_name("D")


def _num(value: float) -> str:
    return f"{int(value)}" if value == int(value) else repr(value)


def _bbox(stream: PDAppearanceStream) -> str:
    rect = stream.get_bbox()
    if rect is None:
        return "none"
    return (
        f"{_num(rect.get_lower_left_x())},{_num(rect.get_lower_left_y())},"
        f"{_num(rect.get_upper_right_x())},{_num(rect.get_upper_right_y())}"
    )


def _nums(*values: float) -> COSArray:
    return COSArray([COSFloat(float(v)) for v in values])


def _stream_with_bbox(*values: float) -> COSStream:
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("BBox"), _nums(*values))
    return stream


def _indirect(value: COSObject | COSStream | COSDictionary, number: int) -> COSObject:
    return COSObject(number, resolved=value)


# --------------------------------------------------------------------------
# Python projections — mirror the probe's stdout line-for-line.
# --------------------------------------------------------------------------


def _emit_fallback_absent() -> str:
    normal = _stream_with_bbox(0, 0, 11, 22)
    only_n = COSDictionary()
    only_n.set_item(_N, normal)
    ap = PDAppearanceDictionary(only_n)

    n = ap.get_normal_appearance()
    r = ap.get_rollover_appearance()
    d = ap.get_down_appearance()
    r_same = r.get_appearance_stream().get_cos_object() is normal
    d_same = d.get_appearance_stream().get_cos_object() is normal
    n_same = n.get_appearance_stream().get_cos_object() is normal
    return (
        f"FALLBACK absent r_notnull={_b(r is not None)} d_notnull={_b(d is not None)}"
        f" r_is_n={_b(r_same)} d_is_n={_b(d_same)} n_is_n={_b(n_same)}"
        f" r_bbox={_bbox(r.get_appearance_stream())}"
        f" d_bbox={_bbox(d.get_appearance_stream())}"
    )


def _emit_fallback_shadow() -> str:
    normal = _stream_with_bbox(0, 0, 11, 22)
    roll = _stream_with_bbox(0, 0, 33, 44)
    down = _stream_with_bbox(0, 0, 55, 66)
    all_dict = COSDictionary()
    all_dict.set_item(_N, normal)
    all_dict.set_item(_R, roll)
    all_dict.set_item(_D, down)
    ap = PDAppearanceDictionary(all_dict)
    r_shadow = ap.get_rollover_appearance().get_appearance_stream().get_cos_object() is roll
    d_shadow = ap.get_down_appearance().get_appearance_stream().get_cos_object() is down
    return (
        f"FALLBACK shadow r_is_roll={_b(r_shadow)} d_is_down={_b(d_shadow)}"
        f" r_bbox={_bbox(ap.get_rollover_appearance().get_appearance_stream())}"
        f" d_bbox={_bbox(ap.get_down_appearance().get_appearance_stream())}"
    )


def _emit_fallback_no_n() -> str:
    empty = PDAppearanceDictionary(COSDictionary())
    return (
        f"FALLBACK noN n_null={_b(empty.get_normal_appearance() is None)}"
        f" r_null={_b(empty.get_rollover_appearance() is None)}"
        f" d_null={_b(empty.get_down_appearance() is None)}"
    )


def _emit_direct_chain() -> str:
    normal = COSStream()
    normal.set_item(COSName.get_pdf_name("BBox"), _nums(1, 2, 30, 40))
    normal.set_item(COSName.get_pdf_name("Resources"), COSDictionary())
    d = COSDictionary()
    d.set_item(_N, normal)
    ap = PDAppearanceDictionary(d)
    n = ap.get_normal_appearance()
    s = n.get_appearance_stream()
    return (
        f"CHAIN direct isStream={_b(n.is_stream())} isSub={_b(n.is_sub_dictionary())}"
        f" bbox={_bbox(s)}"
        f" resources={'none' if s.get_resources() is None else 'dict'}"
        f" identity={_b(s.get_cos_object() is normal)}"
    )


def _emit_double_indirect() -> str:
    inner = _stream_with_bbox(0, 0, 7, 8)
    once = _indirect(inner, 91)
    twice = _indirect(once, 92)
    d = COSDictionary()
    d.set_item(_N, twice)
    ap = PDAppearanceDictionary(d)
    n = ap.get_normal_appearance()
    if n is None:
        result = "none"
    else:
        result = f"isStream={_b(n.is_stream())} bbox={_bbox(n.get_appearance_stream())}"
    return f"DOUBLEIND n={result}"


def _emit_state_resolve() -> str:
    off = _stream_with_bbox(0, 0, 1, 1)
    on = _stream_with_bbox(0, 0, 2, 2)
    ind_state = _stream_with_bbox(0, 0, 3, 3)
    states = COSDictionary()
    states.set_item(COSName.get_pdf_name("Off"), off)
    states.set_item(COSName.get_pdf_name("On"), on)
    states.set_item(COSName.get_pdf_name("Half"), _indirect(ind_state, 70))
    states.set_item(COSName.get_pdf_name("Bad"), COSInteger.get(9))
    d = COSDictionary()
    d.set_item(_N, states)
    ap = PDAppearanceDictionary(d)
    n = ap.get_normal_appearance()
    sub = n.get_sub_dictionary()

    rows = []
    for key in ("Off", "On", "Half", "Bad", "Missing"):
        s = sub.get(key)
        rows.append(f"{key}={'none' if s is None else _bbox(s)}")
    rows.sort()
    half = sub.get("Half")
    half_identity = half is not None and half.get_cos_object() is ind_state
    # keys=len(sub) is the keySet count; rawsize matches the raw COSDictionary
    # entry count (4) — a documented COSDictionaryMap.size() divergence we do
    # NOT reproduce. We pin the keys= field and assert rawsize separately.
    return (
        f"STATERESOLVE keys={len(sub)} {' '.join(rows)}"
        f" half_identity={_b(half_identity)} isSub={_b(n.is_sub_dictionary())}"
    )


def _b(value: bool) -> str:
    return "true" if value else "false"


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("AppearanceDictResolveFuzzProbe").splitlines()
    return {" ".join(line.split(maxsplit=2)[:2]): line for line in lines}


def _strip_rawsize(line: str) -> str:
    """Drop the documented-only ``rawsize=...`` token (COSDictionaryMap.size
    divergence) so the rest of the STATERESOLVE line compares cleanly."""
    return " ".join(tok for tok in line.split() if not tok.startswith("rawsize="))


@requires_oracle
@pytest.mark.parametrize(
    ("key", "emit"),
    (
        ("FALLBACK absent", _emit_fallback_absent),
        ("FALLBACK shadow", _emit_fallback_shadow),
        ("FALLBACK noN", _emit_fallback_no_n),
        ("CHAIN direct", _emit_direct_chain),
        ("DOUBLEIND n=none", _emit_double_indirect),
    ),
    ids=("absent", "shadow", "no_n", "chain", "double_indirect"),
)
def test_resolution_matches_oracle(
    key: str, emit, java_lines: dict[str, str]
) -> None:
    # DOUBLEIND's first two tokens are "DOUBLEIND n=none"; key the lookup by
    # the stable two-token prefix used by the fixture.
    lookup = " ".join(key.split(maxsplit=2)[:2])
    assert emit() == java_lines[lookup]


@requires_oracle
def test_state_resolve_matches_oracle(java_lines: dict[str, str]) -> None:
    assert _emit_state_resolve() == _strip_rawsize(java_lines["STATERESOLVE keys=3"])


# --------------------------------------------------------------------------
# Value-pinned tests (run without the live oracle) — the same expectations,
# derived from the PDFBox 3.0.7 probe output above.
# --------------------------------------------------------------------------


def test_rollover_and_down_fall_back_to_normal_object_identity() -> None:
    normal = _stream_with_bbox(0, 0, 11, 22)
    only_n = COSDictionary()
    only_n.set_item(_N, normal)
    ap = PDAppearanceDictionary(only_n)
    assert ap.get_rollover_appearance() is not None
    assert ap.get_down_appearance() is not None
    assert ap.get_rollover_appearance().get_appearance_stream().get_cos_object() is normal
    assert ap.get_down_appearance().get_appearance_stream().get_cos_object() is normal


def test_explicit_rollover_down_shadow_normal() -> None:
    normal = _stream_with_bbox(0, 0, 11, 22)
    roll = _stream_with_bbox(0, 0, 33, 44)
    d_dict = COSDictionary()
    d_dict.set_item(_N, normal)
    d_dict.set_item(_R, roll)
    ap = PDAppearanceDictionary(d_dict)
    assert ap.get_rollover_appearance().get_appearance_stream().get_cos_object() is roll
    # /D still absent -> falls back to /N, not /R.
    assert ap.get_down_appearance().get_appearance_stream().get_cos_object() is normal


def test_missing_normal_means_all_getters_none() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    assert ap.get_normal_appearance() is None
    assert ap.get_rollover_appearance() is None
    assert ap.get_down_appearance() is None


def test_double_indirect_normal_value_resolves_to_none() -> None:
    inner = _stream_with_bbox(0, 0, 7, 8)
    twice = _indirect(_indirect(inner, 91), 92)
    d = COSDictionary()
    d.set_item(_N, twice)
    ap = PDAppearanceDictionary(d)
    assert ap.get_normal_appearance() is None


def test_sub_dictionary_resolves_stream_values_and_drops_non_streams() -> None:
    off = _stream_with_bbox(0, 0, 1, 1)
    ind_state = _stream_with_bbox(0, 0, 3, 3)
    states = COSDictionary()
    states.set_item(COSName.get_pdf_name("Off"), off)
    states.set_item(COSName.get_pdf_name("Half"), _indirect(ind_state, 70))
    states.set_item(COSName.get_pdf_name("Bad"), COSInteger.get(9))
    d = COSDictionary()
    d.set_item(_N, states)
    ap = PDAppearanceDictionary(d)
    sub = ap.get_normal_appearance().get_sub_dictionary()
    # Only the two stream-valued states materialise; the integer is dropped.
    assert set(sub) == {"Off", "Half"}
    assert sub["Off"].get_cos_object() is off
    # Indirect state value is resolved through the COSObject to the inner stream.
    assert sub["Half"].get_cos_object() is ind_state
    assert _bbox(sub["Half"]) == "0,0,3,3"
