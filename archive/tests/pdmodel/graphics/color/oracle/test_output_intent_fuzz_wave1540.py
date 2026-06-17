"""Differential malformed-dictionary fuzz parity for ``PDOutputIntent`` — the
``/OutputIntents`` entry — against the live Apache PDFBox 3.0.7 oracle
(wave 1540, agent C).

The Java side is ``oracle/probes/OutputIntentFuzzProbe.java``. Two surfaces:

* ``field <field> <case>`` — build a fresh ``/OutputIntent`` ``COSDictionary``,
  set a single entry to a (possibly malformed) value, and project one accessor:

  - ``condid`` / ``condition`` / ``registry`` / ``info`` go through
    ``COSDictionary.getString``, so only a ``COSString`` (direct *or* behind an
    indirect reference) decodes — names / ints / floats / ``COSNull`` / dicts
    all fall back to ``null``.
  - ``subtype`` reads ``/S`` via ``getCOSObject().getNameAsString(COSName.S)``
    (PDFBox 3.0 has no ``getSubtype()``), so a name *or* a string decodes.

* ``profile <case>`` — vary ``/DestOutputProfile`` and project
  ``getDestOutputIntent() != null`` plus the decoded byte length.

DIVERGENCE pinned honestly: pypdfbox's :meth:`PDOutputIntent.get_subtype`
mirrors upstream's *constructor* default (which sets ``/S`` to a **name**) and
therefore resolves ``/S`` with ``getName`` — a string-valued ``/S`` returns
``None`` on the Python side where PDFBox's ``getNameAsString``-based read
returns the text. We pin BOTH values: the divergence is real and intentional
(get_subtype is a name accessor). The four ``getString`` fields match PDFBox
byte-for-byte on every case.

BUG FIXED in this wave: pypdfbox ``get_dest_output_intent()`` (the
upstream-named alias documented as mirroring ``getDestOutputIntent()``) used to
raise ``TypeError`` when ``/DestOutputProfile`` was a non-stream value (a dict /
name / int / ``COSNull``). Upstream resolves it via
``COSDictionary.getCOSStream``, which returns ``null`` for any non-stream and
never raises. The alias now matches upstream exactly (returns ``None``); the
stricter pypdfbox-enrichment accessors (``get_dest_output_profile`` /
``get_dest_output_profile_cos``) keep their documented TypeError contract.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color.pd_output_intent import PDOutputIntent
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- malformed entry-value factory (mirrors the Java probe) ----------


def _field_value(case: str) -> object | None:
    """Mirror ``OutputIntentFuzzProbe.fieldValue`` — return ``None`` for the
    ``absent`` case (no entry set) or the COS object for every other case."""
    if case == "absent":
        return None
    if case == "string":
        return COSString("sRGB")
    if case == "empty_string":
        return COSString("")
    if case == "name":
        return COSName.get_pdf_name("sRGB")
    if case == "int":
        return COSInteger.get(42)
    if case == "float":
        return COSFloat(2.5)
    if case == "null":
        return COSNull.NULL
    if case == "dict":
        return COSDictionary()
    if case == "ind_string":
        return COSObject(1, 0, resolved=COSString("sRGB"))
    if case == "ind_name":
        return COSObject(2, 0, resolved=COSName.get_pdf_name("sRGB"))
    if case == "ind_null":
        return COSObject(3, 0, resolved=COSNull.NULL)
    raise AssertionError(f"unknown case: {case}")


def _make_intent(field_key: str, case: str) -> PDOutputIntent:
    dictionary = COSDictionary()
    dictionary.set_item(COSName.TYPE, COSName.get_pdf_name("OutputIntent"))
    value = _field_value(case)
    if value is not None:
        dictionary.set_item(COSName.get_pdf_name(field_key), value)
    return PDOutputIntent(dictionary)


# Java COSName key for each probe ``field`` token.
_FIELD_KEY = {
    "condid": "OutputConditionIdentifier",
    "condition": "OutputCondition",
    "registry": "RegistryName",
    "info": "Info",
    "subtype": "S",
}


def _project_py(oi: PDOutputIntent, field: str) -> str:
    """Reproduce the probe's ``value=`` projection from pypdfbox."""
    if field == "condid":
        result = oi.get_output_condition_identifier()
    elif field == "condition":
        result = oi.get_output_condition()
    elif field == "registry":
        result = oi.get_registry_name()
    elif field == "info":
        result = oi.get_info()
    elif field == "subtype":
        result = oi.get_subtype()
    else:
        raise AssertionError(field)
    return "null" if result is None else result


_ALL_CASES = [
    "absent",
    "string",
    "empty_string",
    "name",
    "int",
    "float",
    "null",
    "dict",
    "ind_string",
    "ind_name",
    "ind_null",
]

# Expected values for the four ``getString`` fields — identical across all four
# and identical to PDFBox 3.0.7 (only a COSString, direct or indirect, decodes).
_STRING_FIELD_EXPECTED = {
    "absent": "null",
    "string": "sRGB",
    "empty_string": "",
    "name": "null",
    "int": "null",
    "float": "null",
    "null": "null",
    "dict": "null",
    "ind_string": "sRGB",
    "ind_name": "null",
    "ind_null": "null",
}

# Expected ``/S`` subtype values, captured per side from the live oracle.
# PDFBox uses getNameAsString (name OR string decode); pypdfbox get_subtype
# uses getName (only a name decodes) — the divergence is pinned explicitly.
_SUBTYPE_EXPECTED_PDFBOX = {
    "absent": "null",
    "string": "sRGB",
    "empty_string": "",
    "name": "sRGB",
    "int": "null",
    "float": "null",
    "null": "null",
    "dict": "null",
    "ind_string": "sRGB",
    "ind_name": "sRGB",
    "ind_null": "null",
}
_SUBTYPE_EXPECTED_PYPDFBOX = {
    "absent": "null",
    "string": "null",  # DIVERGENCE: getName ignores a string under /S
    "empty_string": "null",  # DIVERGENCE
    "name": "sRGB",
    "int": "null",
    "float": "null",
    "null": "null",
    "dict": "null",
    "ind_string": "null",  # DIVERGENCE
    "ind_name": "sRGB",
    "ind_null": "null",
}


# ---------- /DestOutputProfile factory ----------


def _profile_value(case: str) -> object | None:
    if case == "absent":
        return None
    if case == "empty_stream":
        stream = COSStream()
        stream.set_raw_data(b"")
        return stream
    if case == "stream":
        stream = COSStream()
        stream.set_raw_data(b"\x01\x02\x03\x04\x05")
        return stream
    if case == "dict":
        return COSDictionary()
    if case == "name":
        return COSName.get_pdf_name("DestOutputProfile")
    if case == "int":
        return COSInteger.get(7)
    if case == "null":
        return COSNull.NULL
    if case == "ind_stream":
        stream = COSStream()
        stream.set_raw_data(b"\x09\x08\x07")
        return COSObject(1, 0, resolved=stream)
    raise AssertionError(f"unknown case: {case}")


_PROFILE_CASES = [
    "absent",
    "empty_stream",
    "stream",
    "dict",
    "name",
    "int",
    "null",
    "ind_stream",
]

# Expected (present, len) per case — identical on both sides after the fix.
_PROFILE_EXPECTED = {
    "absent": ("null", "-1"),
    "empty_stream": ("stream", "0"),
    "stream": ("stream", "5"),
    "dict": ("null", "-1"),
    "name": ("null", "-1"),
    "int": ("null", "-1"),
    "null": ("null", "-1"),
    "ind_stream": ("stream", "3"),
}


def _project_profile_py(oi: PDOutputIntent) -> tuple[str, str]:
    try:
        profile = oi.get_dest_output_intent()
    except Exception as exc:  # noqa: BLE001 — mirror probe's ERR: framing
        return f"ERR:{type(exc).__name__}", "-1"
    if profile is None:
        return "null", "-1"
    return "stream", str(len(PDStream(profile).to_byte_array()))


# ---------- self-contained pypdfbox value tests (no oracle needed) ----------


@pytest.mark.parametrize("field", ["condid", "condition", "registry", "info"])
@pytest.mark.parametrize("case", _ALL_CASES)
def test_string_field_value(field: str, case: str) -> None:
    """The four getString-backed fields decode only a COSString (direct or
    indirect) and match the PDFBox 3.0.7 expected value on every case."""
    oi = _make_intent(_FIELD_KEY[field], case)
    assert _project_py(oi, field) == _STRING_FIELD_EXPECTED[case]


@pytest.mark.parametrize("case", _ALL_CASES)
def test_subtype_value(case: str) -> None:
    """get_subtype is a name accessor — pin the pypdfbox value (including the
    documented divergence from PDFBox's getNameAsString-based read)."""
    oi = _make_intent("S", case)
    assert _project_py(oi, "subtype") == _SUBTYPE_EXPECTED_PYPDFBOX[case]


@pytest.mark.parametrize("case", _PROFILE_CASES)
def test_dest_output_intent_value(case: str) -> None:
    """get_dest_output_intent mirrors upstream getCOSStream: a stream (direct
    or indirect) resolves; every non-stream value returns None without raising
    (regression guard for the wave-1540 TypeError fix)."""
    dictionary = COSDictionary()
    dictionary.set_item(COSName.TYPE, COSName.get_pdf_name("OutputIntent"))
    value = _profile_value(case)
    if value is not None:
        dictionary.set_item(COSName.get_pdf_name("DestOutputProfile"), value)
    oi = PDOutputIntent(dictionary)
    assert _project_profile_py(oi) == _PROFILE_EXPECTED[case]


def test_dest_output_profile_strict_accessors_still_raise() -> None:
    """The pypdfbox-enrichment accessors keep their stricter documented
    contract: a non-stream /DestOutputProfile raises TypeError (only the
    upstream-named alias was relaxed to match getCOSStream)."""
    dictionary = COSDictionary()
    dictionary.set_item(COSName.TYPE, COSName.get_pdf_name("OutputIntent"))
    dictionary.set_item(
        COSName.get_pdf_name("DestOutputProfile"), COSInteger.get(7)
    )
    oi = PDOutputIntent(dictionary)
    # Relaxed alias tolerates the malformed entry.
    assert oi.get_dest_output_intent() is None
    # Strict enrichment accessors still flag it.
    with pytest.raises(TypeError):
        oi.get_dest_output_profile_cos()
    with pytest.raises(TypeError):
        oi.get_dest_output_profile()


# ---------- live-oracle differential parity ----------


@requires_oracle
@pytest.mark.parametrize("field", ["condid", "condition", "registry", "info"])
@pytest.mark.parametrize("case", _ALL_CASES)
def test_string_field_oracle_parity(field: str, case: str) -> None:
    """pypdfbox's getString-backed field matches live PDFBox 3.0.7."""
    java = run_probe_text("OutputIntentFuzzProbe", "field", field, case).strip()
    assert java.startswith("value=")
    java_value = java.split("=", 1)[1]
    oi = _make_intent(_FIELD_KEY[field], case)
    assert _project_py(oi, field) == java_value


@requires_oracle
@pytest.mark.parametrize("case", _ALL_CASES)
def test_subtype_oracle_divergence(case: str) -> None:
    """Pin the /S subtype divergence against the live oracle: PDFBox's
    getNameAsString read and pypdfbox's getName-based get_subtype both match
    their recorded expectations on the same input."""
    java = run_probe_text("OutputIntentFuzzProbe", "field", "subtype", case).strip()
    assert java.startswith("value=")
    java_value = java.split("=", 1)[1]
    assert java_value == _SUBTYPE_EXPECTED_PDFBOX[case]
    oi = _make_intent("S", case)
    assert _project_py(oi, "subtype") == _SUBTYPE_EXPECTED_PYPDFBOX[case]


@requires_oracle
@pytest.mark.parametrize("case", _PROFILE_CASES)
def test_profile_oracle_parity(case: str) -> None:
    """pypdfbox's get_dest_output_intent (present + decoded length) matches
    live PDFBox 3.0.7 on every malformed /DestOutputProfile case."""
    java = run_probe_text("OutputIntentFuzzProbe", "profile", case).strip()
    # "present=<...> len=<...>"
    parts = dict(token.split("=", 1) for token in java.split(" "))
    java_present = parts["present"]
    java_len = parts["len"]
    dictionary = COSDictionary()
    dictionary.set_item(COSName.TYPE, COSName.get_pdf_name("OutputIntent"))
    value = _profile_value(case)
    if value is not None:
        dictionary.set_item(COSName.get_pdf_name("DestOutputProfile"), value)
    oi = PDOutputIntent(dictionary)
    present, length = _project_profile_py(oi)
    assert (present, length) == (java_present, java_len)
