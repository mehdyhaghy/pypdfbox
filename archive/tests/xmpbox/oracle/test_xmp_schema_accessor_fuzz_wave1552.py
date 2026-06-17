"""Live Apache xmpbox differential parity for the SCHEMA-SPECIFIC TYPED
ACCESSORS (wave 1552).

Where ``test_xmp_schema_oracle.py`` / ``test_xmp_dublin_core_oracle.py`` compare
what the *parser* builds from a packet, and waves 1545 / 1548 fuzzed the
DomXmpParser PARSE and XmpSerializer SERIALIZE paths, this file drives the
schema typed getters / setters with cardinality (text / bag / seq / lang-alt)
PROGRAMMATICALLY — exactly how a pypdfbox caller would use them in code — and
compares the projected result against the live Apache xmpbox 3.0.7 jar via the
``XmpSchemaAccessorFuzzProbe`` probe.

Each case builds an :class:`XMPMetadata` plus a schema in code, exercises an
accessor sequence, and projects the outcome into repr-stable ``key = value``
lines that match the Java probe byte-for-byte:

  * strings render verbatim; absent (Java ``null`` / Python ``None``) renders
    as ``__NULL__``;
  * lists (Bag / Seq) join their items with the US (0x1f) separator, preserving
    order;
  * dates render canonically as ``<epochMillis>@<offsetMinutes>`` so Java's
    ``Calendar`` and pypdfbox's ``datetime`` compare repr-independently;
  * booleans render as Java ``Boolean.toString`` (lower-case ``true`` /
    ``false``).

Notable cross-checked parities pinned here:

  * DC ``setTitle(value)`` / ``setTitle(lang, value)`` write a LangAlt entry;
    setting ONLY a non-default language leaves ``getTitle()`` (the no-arg /
    x-default read) returning ``None`` — xmpbox does NOT synthesise an
    x-default from the first language.
  * DC title/description LangAlt setters reorganise ``x-default`` to the front
    (``reorganizeAltOrder``); ``getCreators`` preserves insertion order (Seq);
    ``getSubjects`` preserves insertion order (Bag); duplicates are kept.
  * ``XMPRightsManagementSchema.addUsageTerms`` does NOT reorganise — adding
    only ``en`` / ``fr`` leaves ``getUsageTerms()`` (x-default) ``None``.
  * ``getMarked()`` round-trips a Python ``bool`` / Java ``Boolean``; the
    property absent is distinct from ``False`` (``None`` vs ``False``).
  * Empty-string ``setProducer("")`` is a present-but-empty value (not absent).
  * Reading a property defined on a different schema namespace never leaks
    across schemas.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from tests.oracle.harness import requires_oracle, run_probe_text

_US = chr(0x1F)
_NULL = "__NULL__"

_UTC = UTC


def _fmt_cal(dt: datetime | None) -> str:
    """Canonical ``epochMillis@offsetMinutes`` rendering matching the probe."""
    if dt is None:
        return _NULL
    epoch_millis = int(round(dt.timestamp() * 1000))
    offset = dt.utcoffset()
    offset_minutes = 0 if offset is None else int(offset.total_seconds() // 60)
    return f"{epoch_millis}@{offset_minutes}"


def _emit(key: str, value: str | None) -> str:
    return f"{key} = {_NULL if value is None else value}"


def _emit_list(key: str, values: list[str] | None) -> str:
    if values is None:
        return f"{key} = {_NULL}"
    return f"{key} = {_US.join(values)}"


def _emit_cal(key: str, dt: datetime | None) -> str:
    return f"{key} = {_fmt_cal(dt)}"


def _emit_cals(key: str, dts: list[datetime] | None) -> str:
    if dts is None:
        return f"{key} = {_NULL}"
    return f"{key} = {_US.join(_fmt_cal(d) for d in dts)}"


def _emit_bool(key: str, value: bool | None) -> str:
    return f"{key} = {_NULL if value is None else str(value).lower()}"


def _emit_int(key: str, value: int | None) -> str:
    return f"{key} = {_NULL if value is None else str(value)}"


# ---------------------------------------------------------------------------
# Each case returns the list of projection lines pypdfbox produces; the probe
# emits the same lines for the same id.
# ---------------------------------------------------------------------------


def _dc_title_default() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.set_title("Hello")
    return [_emit("get", dc.get_title()), _emit("get_xdefault", dc.get_title("x-default"))]


def _dc_title_lang_then_get_default() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.set_title_lang("fr", "Bonjour")
    return [
        _emit("get", dc.get_title()),
        _emit("get_fr", dc.get_title("fr")),
        _emit_list("langs", dc.get_title_languages()),
    ]


def _dc_title_overwrite_default() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.set_title("first")
    dc.set_title("second")
    return [_emit("get", dc.get_title()), _emit_list("langs", dc.get_title_languages())]


def _dc_title_xdefault_reorder() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.set_title_lang("fr", "Bonjour")
    dc.set_title_lang("x-default", "Hi")
    return [_emit_list("langs", dc.get_title_languages()), _emit("get", dc.get_title())]


def _dc_title_absent() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    prop = dc.get_title_property()
    return [_emit("get", dc.get_title()), _emit("prop", _NULL if prop is None else "present")]


def _dc_description_missing_default_lang() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.add_description("de", "Beschreibung")
    return [
        _emit("get_default", dc.get_description()),
        _emit("get_de", dc.get_description("de")),
    ]


def _dc_creator_order() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    for name in ("Charlie", "Alice", "Bob"):
        dc.add_creator(name)
    return [_emit_list("creators", dc.get_creators())]


def _dc_creator_dup() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.add_creator("Same")
    dc.add_creator("Same")
    return [_emit_list("creators", dc.get_creators())]


def _dc_creator_remove() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    for name in ("A", "B", "C"):
        dc.add_creator(name)
    dc.remove_creator("B")
    return [_emit_list("creators", dc.get_creators())]


def _dc_creator_remove_absent() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.add_creator("A")
    dc.remove_creator("ZZZ")
    return [_emit_list("creators", dc.get_creators())]


def _dc_creators_absent() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    return [_emit_list("creators", dc.get_creators())]


def _dc_subject_order() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    for s in ("z", "a", "m"):
        dc.add_subject(s)
    return [_emit_list("subjects", dc.get_subjects())]


def _dc_subject_remove() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.add_subject("x")
    dc.add_subject("y")
    dc.remove_subject("x")
    return [_emit_list("subjects", dc.get_subjects())]


def _dc_date_order() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.add_date(datetime(2020, 1, 1, tzinfo=_UTC))
    dc.add_date(datetime(2019, 6, 15, tzinfo=_UTC))
    return [_emit_cals("dates", dc.get_dates())]


def _dc_date_tz() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.add_date(datetime(2021, 3, 1, tzinfo=timezone(timedelta(hours=2))))
    return [_emit_cals("dates", dc.get_dates())]


def _dc_dates_absent() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    return [_emit_cals("dates", dc.get_dates())]


def _dc_format() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    dc.set_format("application/pdf")
    return [_emit("format", dc.get_format())]


def _dc_coverage_absent() -> list[str]:
    dc = XMPMetadata().create_and_add_dublin_core_schema()
    return [_emit("coverage", dc.get_coverage())]


def _pdf_producer() -> list[str]:
    ap = XMPMetadata().add_adobe_pdf_schema()
    ap.set_producer("pypdfbox")
    return [_emit("producer", ap.get_producer())]


def _pdf_producer_absent() -> list[str]:
    ap = XMPMetadata().add_adobe_pdf_schema()
    return [_emit("producer", ap.get_producer())]


def _pdf_keywords() -> list[str]:
    ap = XMPMetadata().add_adobe_pdf_schema()
    ap.set_keywords("a, b, c")
    return [_emit("keywords", ap.get_keywords())]


def _pdf_version_absent() -> list[str]:
    ap = XMPMetadata().add_adobe_pdf_schema()
    return [_emit("version", ap.get_pdf_version())]


def _pdf_version_set() -> list[str]:
    ap = XMPMetadata().add_adobe_pdf_schema()
    ap.set_pdf_version("1.7")
    return [_emit("version", ap.get_pdf_version())]


def _pdf_version_overwrite() -> list[str]:
    ap = XMPMetadata().add_adobe_pdf_schema()
    ap.set_pdf_version("1.4")
    ap.set_pdf_version("2.0")
    return [_emit("version", ap.get_pdf_version())]


def _pdf_producer_empty() -> list[str]:
    ap = XMPMetadata().add_adobe_pdf_schema()
    ap.set_producer("")
    return [_emit("producer", ap.get_producer())]


def _xb_creatortool_absent() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    return [_emit("tool", xb.get_creator_tool())]


def _xb_creatortool() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    xb.set_creator_tool("Tool 1.0")
    return [_emit("tool", xb.get_creator_tool())]


def _xb_createdate() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    xb.set_create_date(datetime(2022, 12, 25, tzinfo=_UTC))
    return [_emit_cal("create", xb.get_create_date_value())]


def _xb_createdate_tz() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    xb.set_create_date(datetime(2022, 12, 25, tzinfo=timezone(timedelta(hours=-5))))
    return [_emit_cal("create", xb.get_create_date_value())]


def _xb_createdate_absent() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    return [_emit_cal("create", xb.get_create_date_value())]


def _xb_modifydate() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    xb.set_modify_date(datetime(2023, 1, 2, tzinfo=_UTC))
    return [_emit_cal("modify", xb.get_modify_date_value())]


def _xb_metadatadate_absent() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    return [_emit_cal("meta", xb.get_metadata_date_value())]


def _xb_label() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    xb.set_label("Red")
    return [_emit("label", xb.get_label())]


def _xb_rating() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    xb.set_rating(4)
    return [_emit_int("rating", xb.get_rating())]


def _xb_rating_absent() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    return [_emit_int("rating", xb.get_rating())]


def _xb_rating_negative() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    xb.set_rating(-5)
    return [_emit_int("rating", xb.get_rating())]


def _xb_identifier_bag() -> list[str]:
    xb = XMPMetadata().create_and_add_xmp_basic_schema()
    xb.add_identifier("id-2")
    xb.add_identifier("id-1")
    return [_emit_list("ids", xb.get_identifiers())]


def _rights_marked_true() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    r.set_marked(True)
    return [_emit_bool("marked", r.get_marked())]


def _rights_marked_false() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    r.set_marked(False)
    return [_emit_bool("marked", r.get_marked())]


def _rights_marked_absent() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    return [_emit_bool("marked", r.get_marked())]


def _rights_owner_bag() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    r.add_owner("Owner B")
    r.add_owner("Owner A")
    return [_emit_list("owners", r.get_owners())]


def _rights_owner_remove() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    r.add_owner("X")
    r.add_owner("Y")
    r.remove_owner("X")
    return [_emit_list("owners", r.get_owners())]


def _rights_usageterms_lang() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    r.add_usage_terms("en", "Use freely")
    r.add_usage_terms("fr", "Utilisez librement")
    return [_emit("default", r.get_usage_terms()), _emit("en", r.get_usage_terms("en"))]


def _rights_usageterms_default() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    r.add_usage_terms("x-default", "Default terms")
    return [_emit("default", r.get_usage_terms())]


def _rights_certificate_absent() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    return [_emit("cert", r.get_certificate())]


def _rights_webstatement() -> list[str]:
    r = XMPMetadata().create_and_add_xmp_rights_management_schema()
    r.set_web_statement("http://example.com/rights")
    return [_emit("web", r.get_web_statement())]


def _cross_schema_producer_on_dc() -> list[str]:
    meta = XMPMetadata()
    meta.add_adobe_pdf_schema().set_producer("ProdX")
    dc = meta.create_and_add_dublin_core_schema()
    return [
        _emit("dc_format", dc.get_format()),
        _emit("pdf_producer", meta.get_adobe_pdf_schema().get_producer()),
    ]


_CASES: dict[str, object] = {
    "dc_title_default": _dc_title_default,
    "dc_title_lang_then_get_default": _dc_title_lang_then_get_default,
    "dc_title_overwrite_default": _dc_title_overwrite_default,
    "dc_title_xdefault_reorder": _dc_title_xdefault_reorder,
    "dc_title_absent": _dc_title_absent,
    "dc_description_missing_default_lang": _dc_description_missing_default_lang,
    "dc_creator_order": _dc_creator_order,
    "dc_creator_dup": _dc_creator_dup,
    "dc_creator_remove": _dc_creator_remove,
    "dc_creator_remove_absent": _dc_creator_remove_absent,
    "dc_creators_absent": _dc_creators_absent,
    "dc_subject_order": _dc_subject_order,
    "dc_subject_remove": _dc_subject_remove,
    "dc_date_order": _dc_date_order,
    "dc_date_tz": _dc_date_tz,
    "dc_dates_absent": _dc_dates_absent,
    "dc_format": _dc_format,
    "dc_coverage_absent": _dc_coverage_absent,
    "pdf_producer": _pdf_producer,
    "pdf_producer_absent": _pdf_producer_absent,
    "pdf_keywords": _pdf_keywords,
    "pdf_version_absent": _pdf_version_absent,
    "pdf_version_set": _pdf_version_set,
    "pdf_version_overwrite": _pdf_version_overwrite,
    "pdf_producer_empty": _pdf_producer_empty,
    "xb_creatortool_absent": _xb_creatortool_absent,
    "xb_creatortool": _xb_creatortool,
    "xb_createdate": _xb_createdate,
    "xb_createdate_tz": _xb_createdate_tz,
    "xb_createdate_absent": _xb_createdate_absent,
    "xb_modifydate": _xb_modifydate,
    "xb_metadatadate_absent": _xb_metadatadate_absent,
    "xb_label": _xb_label,
    "xb_rating": _xb_rating,
    "xb_rating_absent": _xb_rating_absent,
    "xb_rating_negative": _xb_rating_negative,
    "xb_identifier_bag": _xb_identifier_bag,
    "rights_marked_true": _rights_marked_true,
    "rights_marked_false": _rights_marked_false,
    "rights_marked_absent": _rights_marked_absent,
    "rights_owner_bag": _rights_owner_bag,
    "rights_owner_remove": _rights_owner_remove,
    "rights_usageterms_lang": _rights_usageterms_lang,
    "rights_usageterms_default": _rights_usageterms_default,
    "rights_certificate_absent": _rights_certificate_absent,
    "rights_webstatement": _rights_webstatement,
    "cross_schema_producer_on_dc": _cross_schema_producer_on_dc,
}


# Expected projections, captured from Apache xmpbox 3.0.7 via
# XmpSchemaAccessorFuzzProbe (frozen so the value-parity assertions also run
# when the live oracle is unavailable). Lines are joined with newline, matching
# the probe's stdout.
_EXPECTED: dict[str, list[str]] = {
    "dc_title_default": ["get = Hello", "get_xdefault = Hello"],
    "dc_title_lang_then_get_default": [
        f"get = {_NULL}",
        "get_fr = Bonjour",
        "langs = fr",
    ],
    "dc_title_overwrite_default": ["get = second", "langs = x-default"],
    "dc_title_xdefault_reorder": [f"langs = x-default{_US}fr", "get = Hi"],
    "dc_title_absent": [f"get = {_NULL}", f"prop = {_NULL}"],
    "dc_description_missing_default_lang": [
        f"get_default = {_NULL}",
        "get_de = Beschreibung",
    ],
    "dc_creator_order": [f"creators = Charlie{_US}Alice{_US}Bob"],
    "dc_creator_dup": [f"creators = Same{_US}Same"],
    "dc_creator_remove": [f"creators = A{_US}C"],
    "dc_creator_remove_absent": ["creators = A"],
    "dc_creators_absent": [f"creators = {_NULL}"],
    "dc_subject_order": [f"subjects = z{_US}a{_US}m"],
    "dc_subject_remove": ["subjects = y"],
    "dc_date_order": [f"dates = 1577836800000@0{_US}1560556800000@0"],
    "dc_date_tz": ["dates = 1614549600000@120"],
    "dc_dates_absent": [f"dates = {_NULL}"],
    "dc_format": ["format = application/pdf"],
    "dc_coverage_absent": [f"coverage = {_NULL}"],
    "pdf_producer": ["producer = pypdfbox"],
    "pdf_producer_absent": [f"producer = {_NULL}"],
    "pdf_keywords": ["keywords = a, b, c"],
    "pdf_version_absent": [f"version = {_NULL}"],
    "pdf_version_set": ["version = 1.7"],
    "pdf_version_overwrite": ["version = 2.0"],
    "pdf_producer_empty": ["producer = "],
    "xb_creatortool_absent": [f"tool = {_NULL}"],
    "xb_creatortool": ["tool = Tool 1.0"],
    "xb_createdate": ["create = 1671926400000@0"],
    "xb_createdate_tz": ["create = 1671944400000@-300"],
    "xb_createdate_absent": [f"create = {_NULL}"],
    "xb_modifydate": ["modify = 1672617600000@0"],
    "xb_metadatadate_absent": [f"meta = {_NULL}"],
    "xb_label": ["label = Red"],
    "xb_rating": ["rating = 4"],
    "xb_rating_absent": [f"rating = {_NULL}"],
    "xb_rating_negative": ["rating = -5"],
    "xb_identifier_bag": [f"ids = id-2{_US}id-1"],
    "rights_marked_true": ["marked = true"],
    "rights_marked_false": ["marked = false"],
    "rights_marked_absent": [f"marked = {_NULL}"],
    "rights_owner_bag": [f"owners = Owner B{_US}Owner A"],
    "rights_owner_remove": ["owners = Y"],
    "rights_usageterms_lang": [f"default = {_NULL}", "en = Use freely"],
    "rights_usageterms_default": ["default = Default terms"],
    "rights_certificate_absent": [f"cert = {_NULL}"],
    "rights_webstatement": ["web = http://example.com/rights"],
    "cross_schema_producer_on_dc": [f"dc_format = {_NULL}", "pdf_producer = ProdX"],
}


def _py_lines(case_id: str) -> list[str]:
    builder = _CASES[case_id]
    return builder()  # type: ignore[operator]


@pytest.mark.parametrize("case_id", list(_CASES))
def test_schema_accessor_matches_frozen_oracle(case_id: str) -> None:
    """pypdfbox's typed-accessor projection == the frozen xmpbox 3.0.7 value."""
    assert _py_lines(case_id) == _EXPECTED[case_id]


@requires_oracle
@pytest.mark.parametrize("case_id", list(_CASES))
def test_schema_accessor_matches_live_oracle(case_id: str) -> None:
    """pypdfbox's typed-accessor projection == live Apache xmpbox 3.0.7."""
    java = run_probe_text("XmpSchemaAccessorFuzzProbe", case_id)
    java_lines = [ln for ln in java.split("\n") if ln != ""]
    assert _py_lines(case_id) == java_lines
    # And the frozen expectation must still agree with the live oracle.
    assert _EXPECTED[case_id] == java_lines
