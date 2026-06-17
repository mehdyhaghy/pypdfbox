"""Live Apache PDFBox differential fuzz of crypt-filter ROUTING RESOLUTION
(wave 1552, agent C).

The existing crypt-filter oracle suite is entirely file-based round-trips:

* ``test_crypt_filter_oracle.py`` / ``test_crypt_routing_oracle.py`` — introspect
  well-formed ``/StdCF`` documents after ``protect()`` / ``save()`` (routing
  names + decrypted bytes).
* ``test_crypt_filter_fuzz_wave1517.py`` / ``test_decrypt_data_fuzz_wave1532.py``
  — decode-dispatch on a corpus of crafted encrypted PDFs loaded from disk.
* ``test_crypt_filter_dict_default_oracle.py`` / ``test_strf_default_oracle.py``
  — single-field defaults (``getLength`` default, ``/StrF`` Identity default).

NONE of them fuzz the *pure resolution* surface of :class:`PDEncryption` over a
wide battery of ``/CF`` + ``/StmF`` + ``/StrF`` + ``/EFF`` + ``/EncryptMetadata``
shapes:

* ``get_stream_filter_name()`` / ``get_string_filter_name()`` — the ``Identity``
  default substituted for an absent slot (PDF 32000-1 §7.6.4.4 Table 20), even
  when ``/CF`` is present;
* ``get_crypt_filter_dictionary(name)`` returning ``None`` when ``/CF`` is absent
  or the named filter is undefined;
* the resolved ``/CFM`` of the default stream + string filters, including
  ``/None`` / an unknown ``/CFM`` / a missing ``/CFM`` key;
* ``get_length()`` of the resolved crypt-filter dict (bits; default 40);
* ``is_encrypt_meta_data()`` reading the ``/Encrypt``-level flag — NOT any
  ``/CF``-level ``/EncryptMetadata`` (case ``v4_cf_level_meta_false``).

This is exactly the surface
:class:`StandardSecurityHandler` ``._resolve_cfm`` /
``._populate_routing_table`` builds its per-object cipher routing on. Pinning it
both-sides catches divergence in the default-substitution + named-filter-lookup
logic without a full crypto round-trip.

Driven by ``oracle/probes/CryptFilterRoutingFuzzProbe`` — a pure in-memory probe
that builds each ``/Encrypt`` ``COSDictionary`` shape directly (no parser, no key
derivation) and prints one framed resolution line per case. The pypdfbox
companion builds the byte-identical :class:`PDEncryption` and asserts the same
fields.

Result: 30/30 cases byte-for-byte identical against live PDFBox 3.0.7 — NO
divergence found in the crypt-filter resolution surface, and the
``StandardSecurityHandler`` routing-table layer agrees on the same CFM
resolutions. No production bug surfaced; this wave is a both-sides pin of the
routing-resolution contract.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSBoolean, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Case builders — byte-identical to CryptFilterRoutingFuzzProbe.java.
# --------------------------------------------------------------------------- #


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _entry(cfm: str | None, length: int | None, meta: bool | None = None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_name("Type"), _name("CryptFilter"))
    if cfm is not None:
        d.set_item(_name("CFM"), _name(cfm))
    if length is not None and length >= 0:
        d.set_item(_name("Length"), COSInteger.get(length))
    if meta is not None:
        d.set_item(_name("EncryptMetadata"), COSBoolean.get_boolean(meta))
    return d


def _build(
    v: int,
    stm_f: str | None,
    str_f: str | None,
    eff: str | None,
    cf_entries: list[tuple[str, COSDictionary]] | None,
    meta: bool = True,
) -> PDEncryption:
    d = COSDictionary()
    d.set_item(_name("Filter"), _name("Standard"))
    d.set_int(_name("V"), v)
    d.set_int(_name("R"), 6 if v >= 5 else (4 if v == 4 else 3))
    d.set_int(_name("Length"), 256 if v >= 5 else 128)
    if cf_entries is not None:
        cf = COSDictionary()
        for name, entry in cf_entries:
            cf.set_item(_name(name), entry)
        d.set_item(_name("CF"), cf)
    if stm_f is not None:
        d.set_item(_name("StmF"), _name(stm_f))
    if str_f is not None:
        d.set_item(_name("StrF"), _name(str_f))
    if eff is not None:
        d.set_item(_name("EFF"), _name(eff))
    d.set_item(_name("EncryptMetadata"), COSBoolean.get_boolean(meta))
    return PDEncryption(d)


def _legacy(v: int) -> PDEncryption:
    d = COSDictionary()
    d.set_item(_name("Filter"), _name("Standard"))
    d.set_int(_name("V"), v)
    d.set_int(_name("R"), 2 if v == 1 else 3)
    d.set_int(_name("Length"), 40 if v == 1 else 128)
    return PDEncryption(d)


def _cases() -> list[tuple[str, PDEncryption]]:
    """Build the 30-case battery in the SAME order as the Java probe."""
    return [
        ("v4_stdcf_aesv2_both",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_stdcf_v2_both",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry("V2", 16))])),
        ("v4_stm_stdcf_str_identity",
         _build(4, "StdCF", "Identity", None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_stm_identity_str_stdcf",
         _build(4, "Identity", "StdCF", None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_both_identity",
         _build(4, "Identity", "Identity", None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_stm_absent_str_stdcf",
         _build(4, None, "StdCF", None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_str_absent_stm_stdcf",
         _build(4, "StdCF", None, None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_both_absent_cf_present",
         _build(4, None, None, None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_stm_undefined_name",
         _build(4, "MissingCF", "StdCF", None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_cf_absent_stm_stdcf",
         _build(4, "StdCF", "StdCF", None, None)),
        ("v4_custom_name",
         _build(4, "MyCF", "MyCF", None, [("MyCF", _entry("AESV2", 16))])),
        ("v4_cfm_none",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry("None", 16))])),
        ("v4_cfm_unknown",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry("Zz", 16))])),
        ("v4_no_cfm_key",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry(None, 16))])),
        ("v4_no_length",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry("AESV2", -1))])),
        ("v4_length_5",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry("V2", 5))])),
        ("v4_eff_stdcf",
         _build(4, "StdCF", "StdCF", "StdCF", [("StdCF", _entry("AESV2", 16))])),
        ("v4_eff_identity",
         _build(4, "StdCF", "StdCF", "Identity", [("StdCF", _entry("AESV2", 16))])),
        ("v4_eff_undefined",
         _build(4, "StdCF", "StdCF", "NoSuch", [("StdCF", _entry("AESV2", 16))])),
        ("v4_meta_false",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry("AESV2", 16))], meta=False)),
        ("v4_meta_true",
         _build(4, "StdCF", "StdCF", None, [("StdCF", _entry("AESV2", 16))], meta=True)),
        ("v5_stdcf_aesv3_both",
         _build(5, "StdCF", "StdCF", None, [("StdCF", _entry("AESV3", 32))])),
        ("v5_stm_aesv3_str_identity",
         _build(5, "StdCF", "Identity", None, [("StdCF", _entry("AESV3", 32))])),
        ("v5_two_filters",
         _build(5, "FilterA", "FilterB", None,
                [("FilterA", _entry("AESV3", 32)), ("FilterB", _entry("AESV3", 32))])),
        ("v2_legacy_no_cf", _legacy(2)),
        ("v1_legacy_no_cf", _legacy(1)),
        ("v4_stmf_is_algo_no_cf",
         _build(4, "V2", "V2", None, None)),
        ("v4_default_crypt_filter_name",
         _build(4, "DefaultCryptFilter", "DefaultCryptFilter", None,
                [("DefaultCryptFilter", _entry("AESV2", 16))])),
        ("v4_stm_identity_str_undefined",
         _build(4, "Identity", "Ghost", None, [("StdCF", _entry("AESV2", 16))])),
        ("v4_cf_level_meta_false",
         _build(4, "StdCF", "StdCF", None,
                [("StdCF", _entry("AESV2", 16, meta=False))])),
    ]


# --------------------------------------------------------------------------- #
# Field projection — byte-identical to the Java probe's emit() / resolveCFM().
# --------------------------------------------------------------------------- #


def _resolve_cfm(enc: PDEncryption, filter_name: str) -> str:
    if filter_name == "Identity":
        return "Identity"
    cfd = enc.get_crypt_filter_dictionary(filter_name)
    if cfd is None:
        return "NONEDICT"
    method = cfd.get_crypt_filter_method()
    return "NOCFM" if method is None else method.name


def _length_of(enc: PDEncryption, filter_name: str) -> str:
    if filter_name == "Identity":
        return "NODICT"
    cfd = enc.get_crypt_filter_dictionary(filter_name)
    if cfd is None:
        return "NODICT"
    return str(cfd.get_length())


def _project_line(name: str, enc: PDEncryption) -> str:
    stm_f = enc.get_stream_filter_name()
    str_f = enc.get_string_filter_name()
    eff = enc.get_eff()
    eff_cfm = "NOEFF" if eff is None else _resolve_cfm(enc, eff)
    meta = "true" if enc.is_encrypt_meta_data() else "false"
    return (
        f"CASE {name}"
        f" stmF={stm_f}"
        f" strF={str_f}"
        f" stmCFM={_resolve_cfm(enc, stm_f)}"
        f" strCFM={_resolve_cfm(enc, str_f)}"
        f" effCFM={eff_cfm}"
        f" stmLen={_length_of(enc, stm_f)}"
        f" meta={meta}"
    )


# Gold values captured from live Apache PDFBox 3.0.7 via
# CryptFilterRoutingFuzzProbe (`java -cp ... CryptFilterRoutingFuzzProbe`).
# Compact field tuples — (stmF, strF, stmCFM, strCFM, effCFM, stmLen, meta) —
# assembled into the same framed line the probe prints, so the literal is short
# enough to stay under the 100-col line cap while remaining the verbatim
# upstream ground truth. The self-contained test asserts pypdfbox reproduces
# these without the live oracle; the @requires_oracle test re-runs the probe to
# catch upstream drift.
_GOLD: dict[str, tuple[str, str, str, str, str, str, str]] = {
    "v4_stdcf_aesv2_both": ("StdCF", "StdCF", "AESV2", "AESV2", "NOEFF", "16", "true"),
    "v4_stdcf_v2_both": ("StdCF", "StdCF", "V2", "V2", "NOEFF", "16", "true"),
    "v4_stm_stdcf_str_identity": ("StdCF", "Identity", "AESV2", "Identity", "NOEFF", "16", "true"),
    "v4_stm_identity_str_stdcf":
        ("Identity", "StdCF", "Identity", "AESV2", "NOEFF", "NODICT", "true"),
    "v4_both_identity": ("Identity", "Identity", "Identity", "Identity", "NOEFF", "NODICT", "true"),
    "v4_stm_absent_str_stdcf":
        ("Identity", "StdCF", "Identity", "AESV2", "NOEFF", "NODICT", "true"),
    "v4_str_absent_stm_stdcf": ("StdCF", "Identity", "AESV2", "Identity", "NOEFF", "16", "true"),
    "v4_both_absent_cf_present":
        ("Identity", "Identity", "Identity", "Identity", "NOEFF", "NODICT", "true"),
    "v4_stm_undefined_name": ("MissingCF", "StdCF", "NONEDICT", "AESV2", "NOEFF", "NODICT", "true"),
    "v4_cf_absent_stm_stdcf": ("StdCF", "StdCF", "NONEDICT", "NONEDICT", "NOEFF", "NODICT", "true"),
    "v4_custom_name": ("MyCF", "MyCF", "AESV2", "AESV2", "NOEFF", "16", "true"),
    "v4_cfm_none": ("StdCF", "StdCF", "None", "None", "NOEFF", "16", "true"),
    "v4_cfm_unknown": ("StdCF", "StdCF", "Zz", "Zz", "NOEFF", "16", "true"),
    "v4_no_cfm_key": ("StdCF", "StdCF", "NOCFM", "NOCFM", "NOEFF", "16", "true"),
    "v4_no_length": ("StdCF", "StdCF", "AESV2", "AESV2", "NOEFF", "40", "true"),
    "v4_length_5": ("StdCF", "StdCF", "V2", "V2", "NOEFF", "5", "true"),
    "v4_eff_stdcf": ("StdCF", "StdCF", "AESV2", "AESV2", "AESV2", "16", "true"),
    "v4_eff_identity": ("StdCF", "StdCF", "AESV2", "AESV2", "Identity", "16", "true"),
    "v4_eff_undefined": ("StdCF", "StdCF", "AESV2", "AESV2", "NONEDICT", "16", "true"),
    "v4_meta_false": ("StdCF", "StdCF", "AESV2", "AESV2", "NOEFF", "16", "false"),
    "v4_meta_true": ("StdCF", "StdCF", "AESV2", "AESV2", "NOEFF", "16", "true"),
    "v5_stdcf_aesv3_both": ("StdCF", "StdCF", "AESV3", "AESV3", "NOEFF", "32", "true"),
    "v5_stm_aesv3_str_identity": ("StdCF", "Identity", "AESV3", "Identity", "NOEFF", "32", "true"),
    "v5_two_filters": ("FilterA", "FilterB", "AESV3", "AESV3", "NOEFF", "32", "true"),
    "v2_legacy_no_cf": ("Identity", "Identity", "Identity", "Identity", "NOEFF", "NODICT", "true"),
    "v1_legacy_no_cf": ("Identity", "Identity", "Identity", "Identity", "NOEFF", "NODICT", "true"),
    "v4_stmf_is_algo_no_cf": ("V2", "V2", "NONEDICT", "NONEDICT", "NOEFF", "NODICT", "true"),
    "v4_default_crypt_filter_name":
        ("DefaultCryptFilter", "DefaultCryptFilter", "AESV2", "AESV2", "NOEFF", "16", "true"),
    "v4_stm_identity_str_undefined":
        ("Identity", "Ghost", "Identity", "NONEDICT", "NOEFF", "NODICT", "true"),
    "v4_cf_level_meta_false": ("StdCF", "StdCF", "AESV2", "AESV2", "NOEFF", "16", "true"),
}


def _gold_line(name: str) -> str:
    stm_f, str_f, stm_cfm, str_cfm, eff_cfm, stm_len, meta = _GOLD[name]
    return (
        f"CASE {name}"
        f" stmF={stm_f}"
        f" strF={str_f}"
        f" stmCFM={stm_cfm}"
        f" strCFM={str_cfm}"
        f" effCFM={eff_cfm}"
        f" stmLen={stm_len}"
        f" meta={meta}"
    )


_EXPECTED = {name: _gold_line(name) for name in _GOLD}


_CASE_NAMES = [name for name, _ in _cases()]


# --------------------------------------------------------------------------- #
# Self-contained value-pinned test (no oracle required).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("case_name", _CASE_NAMES)
def test_routing_resolution_matches_pinned_pdfbox(case_name: str) -> None:
    enc = dict(_cases())[case_name]
    assert _project_line(case_name, enc) == _EXPECTED[case_name]


def test_battery_is_thirty_distinct_cases() -> None:
    names = _CASE_NAMES
    assert len(names) == 30
    assert len(set(names)) == 30
    # Every pinned expected line is consumed by exactly one case.
    assert set(names) == set(_EXPECTED)


# --------------------------------------------------------------------------- #
# StandardSecurityHandler routing-table layer agrees on the CFM resolutions.
#
# _populate_routing_table feeds the per-object cipher dispatch. For each case
# the resolved (stream, string) CFM must equal what the PDEncryption-level
# resolution projects — with two documented coercions that are the WHOLE POINT
# of the routing table (and verified against PDFBox's reader, see the method
# docstring): (1) when /CF is absent and no /StmF / /StrF entry exists the slot
# stays Python ``None`` (legacy single-algo fallback, not the "Identity"
# string); (2) a /StmF / /StrF name with no matching /CF entry and not itself a
# CFM keyword resolves to ``None`` (legacy fallback) rather than "NONEDICT".
# --------------------------------------------------------------------------- #


def _expected_routing_cfm(enc: PDEncryption, slot_filter_name: str) -> str | None:
    """Project the routing-table CFM the StandardSecurityHandler should hold.

    Mirrors ``_resolve_cfm`` but with the legacy-fallback ``None`` rule the
    handler uses for the per-object dispatch.
    """
    if slot_filter_name == "Identity":
        return "Identity"
    cfd = enc.get_crypt_filter_dictionary(slot_filter_name)
    if cfd is not None:
        cfm = cfd.get_cfm()
        if cfm is not None:
            return cfm
    # No /CF entry: legacy writers occasionally put the algorithm directly in
    # the slot name; otherwise the handler falls back to None (legacy path).
    if slot_filter_name in ("V2", "AESV2", "AESV3", "None"):
        return slot_filter_name
    return None


@pytest.mark.parametrize("case_name", _CASE_NAMES)
def test_routing_table_layer_agrees(case_name: str) -> None:
    enc = dict(_cases())[case_name]
    handler = StandardSecurityHandler()
    handler._populate_routing_table(enc)

    version = int(enc.get_v())
    has_routing = (
        version >= 4
        and (enc.has_cf() or enc.get_stm_f() is not None or enc.get_str_f() is not None)
    )

    if not has_routing:
        # V<4, or V>=4 with neither /CF nor any default-filter entry —
        # the routing table stays empty so the legacy single-algo path runs.
        assert handler.get_stream_cfm() is None
        assert handler.get_string_cfm() is None
        assert handler.get_embedded_file_cfm() is None
        return

    # Absent slots default to /Identity at the routing-table level.
    stm_f = enc.get_stm_f()
    str_f = enc.get_str_f()
    expect_stream = (
        "Identity" if stm_f is None else _expected_routing_cfm(enc, stm_f)
    )
    expect_string = (
        "Identity" if str_f is None else _expected_routing_cfm(enc, str_f)
    )
    assert handler.get_stream_cfm() == expect_stream
    assert handler.get_string_cfm() == expect_string

    # /EFF defaults to /StmF when absent (PDF 32000-1 §7.6.5).
    eff = enc.get_eff()
    expect_eff = (
        expect_stream if eff is None else _expected_routing_cfm(enc, eff)
    )
    assert handler.get_embedded_file_cfm() == expect_eff


# --------------------------------------------------------------------------- #
# Live differential against Apache PDFBox 3.0.7.
# --------------------------------------------------------------------------- #


@requires_oracle
def test_routing_resolution_matches_live_pdfbox() -> None:
    java_out = run_probe_text("CryptFilterRoutingFuzzProbe").strip()
    java_lines = {
        line.split(" ", 2)[1]: line
        for line in java_out.splitlines()
        if line.startswith("CASE ")
    }
    assert set(java_lines) == set(_CASE_NAMES), (
        "probe case set drifted from the Python battery"
    )
    for name, enc in _cases():
        assert _project_line(name, enc) == java_lines[name], (
            f"pypdfbox diverged from live PDFBox on case {name}"
        )
