"""Live Apache PDFBox differential parity for malformed /SV seed-value
sub-dictionaries (wave 1538, agent D).

Surface: ``PDSeedValue`` plus its three typed sub-dictionaries
(``PDSeedValueCertificate`` / ``PDSeedValueMDP`` / ``PDSeedValueTimeStamp``).
The companion ``SignatureDictProbe`` owns the main ``/Sig`` dictionary; this
file owns the seed-value (``/Type /SV``) accessor surface under malformed /
edge-case input.

Rather than round-trip through PDF bytes, both sides construct the *identical*
``/SV`` ``COSDictionary`` in memory (Python builder ``_build`` mirrors the
Java ``build`` switch one case at a time) and project every public accessor.
``SeedValueFuzzProbe`` reports PDFBox 3.0.7's output as JSON; the test builds
the same dict with pypdfbox and compares.

Characterised divergences (deliberate pypdfbox design — pinned BOTH-sides so
they cannot silently drift):

* **Absent optional → ``None`` vs Java sentinel.** ``PDSeedValue.getV()``
  returns the primitive ``-1.0f`` when ``/V`` is absent *or wrong-typed*;
  pypdfbox ``get_v()`` returns ``None`` (the project-wide idiom for an absent
  optional). Likewise ``getSubFilter()`` / ``getReasons()`` return Java's
  ``Collections.emptyList()`` (``[]``) for an absent / wrong-typed entry while
  pypdfbox returns ``None``.
* **``/SubFilter`` / ``/Reasons`` wrong-type tolerance.** PDFBox reads both
  through ``COSArray.toCOSNameStringList()``, which throws
  ``ClassCastException`` when the array carries ``COSString`` entries (the
  documented upstream ``/Reasons`` bug — ``/Reasons`` is spec'd as an array of
  *text strings*, Table 234). pypdfbox reads ``/SubFilter`` as names and
  ``/Reasons`` as text strings (spec-correct) and returns ``None`` rather than
  raising on the mismatched shape.
* **``/Reasons`` names-vs-strings.** Because PDFBox reads ``/Reasons`` as names
  and pypdfbox reads them as text strings, an array of *names* yields the name
  list on the Java side and ``None`` on the pypdfbox side; an array of *text
  strings* yields ``ClassCastException`` on the Java side and the string list
  on the pypdfbox side. Both interpretations are pinned.

Every other accessor (the seven ``/Ff`` flag predicates, ``getFilter`` via
``getNameAsString``, ``getDigestMethod`` as names, ``getMDP().getP()``,
``getTimeStamp().getURL()`` / ``isTimestampRequired``,
``getSeedValueCertificate().getURL()`` / ``getURLType()`` / required flags)
agrees byte-for-byte. No real pypdfbox bug surfaced on this surface.
"""

from __future__ import annotations

import json

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.digitalsignature import PDSeedValue
from tests.oracle.harness import requires_oracle, run_probe_text

_TYPE = COSName.get_pdf_name("Type")
_SV = COSName.get_pdf_name("SV")
_FF = COSName.get_pdf_name("Ff")
_FILTER = COSName.get_pdf_name("Filter")
_SUB_FILTER = COSName.get_pdf_name("SubFilter")
_REASONS = COSName.get_pdf_name("Reasons")
_DIGEST_METHOD = COSName.get_pdf_name("DigestMethod")
_V = COSName.get_pdf_name("V")
_MDP = COSName.get_pdf_name("MDP")
_P = COSName.get_pdf_name("P")
_TIME_STAMP = COSName.get_pdf_name("TimeStamp")
_CERT = COSName.get_pdf_name("Cert")
_URL = COSName.get_pdf_name("URL")
_URL_TYPE = COSName.get_pdf_name("URLType")


# --------------------------------------------------------------- builder
#
# Mirrors SeedValueFuzzProbe.build(COSDictionary, String) case for case.


def _build(case: str) -> PDSeedValue:
    d = COSDictionary()
    d.set_item(_TYPE, _SV)
    if case in ("empty", "ff_missing"):
        pass
    elif case == "ff_all_bits":
        d.set_int(_FF, 0x7F)
    elif case == "ff_filter_only":
        d.set_int(_FF, 1)
    elif case == "subfilter_names":
        a = COSArray()
        a.add(COSName.get_pdf_name("adbe.pkcs7.detached"))
        a.add(COSName.get_pdf_name("ETSI.CAdES.detached"))
        d.set_item(_SUB_FILTER, a)
    elif case == "subfilter_strings":
        a = COSArray()
        a.add(COSString("adbe.pkcs7.detached"))
        d.set_item(_SUB_FILTER, a)
    elif case == "subfilter_notarray":
        d.set_item(_SUB_FILTER, COSName.get_pdf_name("adbe.pkcs7.detached"))
    elif case == "reasons_strings":
        a = COSArray()
        a.add(COSString("I approve"))
        a.add(COSString("I reviewed"))
        d.set_item(_REASONS, a)
    elif case == "reasons_names":
        a = COSArray()
        a.add(COSName.get_pdf_name("approve"))
        d.set_item(_REASONS, a)
    elif case == "digest_names":
        a = COSArray()
        a.add(COSName.get_pdf_name("SHA256"))
        a.add(COSName.get_pdf_name("SHA512"))
        d.set_item(_DIGEST_METHOD, a)
    elif case == "v_float":
        d.set_item(_V, COSFloat(1.5))
    elif case == "v_int":
        d.set_item(_V, COSInteger.get(2))
    elif case == "v_missing":
        pass
    elif case == "v_wrongtype":
        d.set_item(_V, COSString("Hi"))
    elif case in ("mdp_p0", "mdp_p1", "mdp_p2", "mdp_p3"):
        mdp = COSDictionary()
        mdp.set_int(_P, int(case[5]))
        d.set_item(_MDP, mdp)
    elif case == "mdp_nop":
        d.set_item(_MDP, COSDictionary())
    elif case == "mdp_missing":
        pass
    elif case == "ts_url_req":
        ts = COSDictionary()
        ts.set_string(_URL, "https://tsa.example/ts")
        ts.set_int(_FF, 1)
        d.set_item(_TIME_STAMP, ts)
    elif case == "ts_url_noff":
        ts = COSDictionary()
        ts.set_string(_URL, "https://tsa.example/ts")
        d.set_item(_TIME_STAMP, ts)
    elif case == "ts_missing":
        pass
    elif case == "cert_subj_url":
        cert = COSDictionary()
        cert.set_int(_FF, 1 | (1 << 6))
        cert.set_string(_URL, "https://ca.example/enroll")
        cert.set_name(_URL_TYPE, "ASSP")
        d.set_item(_CERT, cert)
    elif case == "cert_missing":
        pass
    elif case == "filter_name":
        d.set_item(_FILTER, COSName.get_pdf_name("Adobe.PPKLite"))
    elif case == "filter_string":
        d.set_item(_FILTER, COSString("Adobe.PPKLite"))
    else:
        raise AssertionError(f"unknown case {case!r}")
    return PDSeedValue(d)


# --------------------------------------------------------------- projection
#
# Project the pypdfbox accessors into the same key shape the Java probe emits.
# Where pypdfbox deliberately diverges (None vs sentinel; graceful None vs
# ClassCastException; names vs strings on /Reasons) we record pypdfbox's own
# value here and translate the EXPECTED Java value in the test below.


def _project(seed: PDSeedValue) -> dict[str, object]:
    mdp = seed.get_mdp()
    ts = seed.get_time_stamp()
    cert = seed.get_seed_value_certificate()
    return {
        "filterReq": seed.is_filter_required(),
        "subFilterReq": seed.is_sub_filter_required(),
        "vReq": seed.is_v_required(),
        "reasonReq": seed.is_reason_required(),
        "legalReq": seed.is_legal_attestation_required(),
        "addRevReq": seed.is_add_rev_info_required(),
        "digestReq": seed.is_digest_method_required(),
        "filter": seed.get_filter(),
        "subFilter": seed.get_sub_filter(),
        "reasons": seed.get_reasons(),
        "digestMethod": seed.get_digest_method(),
        "legalAttestation": seed.get_legal_attestation(),
        "v": seed.get_v(),
        "mdpPresent": mdp is not None,
        "mdpP": -1 if mdp is None else mdp.get_p(),
        "tsPresent": ts is not None,
        "tsUrl": None if ts is None else ts.get_url(),
        "tsReq": False if ts is None else ts.is_timestamp_required(),
        "certPresent": cert is not None,
        "certUrl": None if cert is None else cert.get_url(),
        "certUrlType": None if cert is None else cert.get_url_type(),
        "certSubjReq": False if cert is None else cert.is_subject_required(),
        "certUrlReq": False if cert is None else cert.is_url_required(),
    }


# Keys whose pypdfbox value is compared verbatim against the Java probe.
_DIRECT_KEYS = (
    "filterReq",
    "subFilterReq",
    "vReq",
    "reasonReq",
    "legalReq",
    "addRevReq",
    "digestReq",
    "filter",
    "digestMethod",
    "legalAttestation",
    "mdpPresent",
    "mdpP",
    "tsPresent",
    "tsUrl",
    "tsReq",
    "certPresent",
    "certUrl",
    "certUrlType",
    "certSubjReq",
    "certUrlReq",
)

_CASES = [
    "empty",
    "ff_all_bits",
    "ff_filter_only",
    "subfilter_names",
    "subfilter_strings",
    "subfilter_notarray",
    "reasons_strings",
    "reasons_names",
    "digest_names",
    "v_float",
    "v_int",
    "v_missing",
    "v_wrongtype",
    "mdp_p0",
    "mdp_p1",
    "mdp_p2",
    "mdp_p3",
    "mdp_nop",
    "mdp_missing",
    "ts_url_req",
    "ts_url_noff",
    "ts_missing",
    "cert_subj_url",
    "cert_missing",
    "filter_name",
    "filter_string",
]


@requires_oracle
@pytest.mark.parametrize("case", _CASES, ids=_CASES)
def test_seed_value_fuzz_parity(case: str) -> None:
    """Every PDFBox-aligned accessor agrees verbatim; the deliberate
    None-vs-sentinel / graceful-None / names-vs-strings divergences are
    pinned BOTH-sides so the contract cannot drift."""
    java = json.loads(run_probe_text("SeedValueFuzzProbe", case))
    py = _project(_build(case))

    # ---- aligned accessors: verbatim parity ----
    for key in _DIRECT_KEYS:
        assert py[key] == java[key], f"{case}.{key}: py={py[key]!r} java={java[key]!r}"

    # ---- /V: pypdfbox None  <->  PDFBox -1.0 sentinel for absent/wrong-type
    if java["v"] == -1.0:
        assert py["v"] is None
    else:
        assert py["v"] == java["v"]

    # ---- /SubFilter: None (pypdfbox) <-> [] / ClassCastException (PDFBox)
    java_sf = java["subFilter"]
    if java_sf == []:
        # absent / wrong-type (notarray): PDFBox empty list, pypdfbox None
        assert py["subFilter"] is None
    elif java_sf == "err.ClassCastException":
        # array of strings: PDFBox throws, pypdfbox tolerantly returns None
        assert py["subFilter"] is None
    else:
        # array of names: both read the names
        assert py["subFilter"] == java_sf

    # ---- /Reasons: names-as-strings (pypdfbox) vs names (PDFBox) divergence
    java_reasons = java["reasons"]
    if java_reasons == []:
        # absent: PDFBox empty list, pypdfbox None
        assert py["reasons"] is None
    elif java_reasons == "err.ClassCastException":
        # array of text strings: PDFBox throws (the documented /Reasons bug),
        # pypdfbox reads the spec-correct text strings.
        assert py["reasons"] == ["I approve", "I reviewed"]
    else:
        # array of names: PDFBox returns the name list, pypdfbox returns None
        # (it reads /Reasons as text strings per the spec).
        assert java_reasons == ["approve"]
        assert py["reasons"] is None


@requires_oracle
def test_v_sentinel_divergence_is_explicit() -> None:
    """Lock the /V None-vs-(-1.0) divergence directly: PDFBox reports the
    -1.0 sentinel for an absent /V while pypdfbox reports None, and both read
    a present numeric /V identically."""
    java_missing = json.loads(run_probe_text("SeedValueFuzzProbe", "v_missing"))
    assert java_missing["v"] == -1.0
    assert _build("v_missing").get_v() is None

    java_float = json.loads(run_probe_text("SeedValueFuzzProbe", "v_float"))
    assert java_float["v"] == 1.5
    assert _build("v_float").get_v() == 1.5


@requires_oracle
def test_reasons_classcast_divergence_is_explicit() -> None:
    """Lock the /Reasons divergence: PDFBox's getReasons() throws
    ClassCastException on the text-string array its own setReasons() writes,
    whereas pypdfbox reads the spec-correct text strings."""
    java = json.loads(run_probe_text("SeedValueFuzzProbe", "reasons_strings"))
    assert java["reasons"] == "err.ClassCastException"
    assert _build("reasons_strings").get_reasons() == ["I approve", "I reviewed"]
