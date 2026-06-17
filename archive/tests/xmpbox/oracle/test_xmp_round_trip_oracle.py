"""Live Apache xmpbox round-trip parity for pypdfbox-emitted XMP packets.

Writes an XMP packet with :class:`pypdfbox.xmpbox.xml.xmp_serializer.XmpSerializer`,
hands the raw bytes to Apache xmpbox 3.0.7's ``DomXmpParser`` via the
``XmpRoundTripProbe`` Java probe, and asserts the parsed schema/property dump
matches what pypdfbox's own ``DomXmpParser`` extracts from the same bytes.
This is the round-trip half of the xmpbox parity surface: the
``XmpSchemaProbe`` based test (``test_xmp_schema_oracle.py``) covers the
opposite direction (PDFBox-emitted packet → pypdfbox parser parity); this
file covers (pypdfbox-emitted packet → xmpbox parser parity), so a
divergence in either the serializer or the parser would surface here.

Cases (PRD-driven):
  * Empty packet (only xpacket header) — no schemas.
  * All five schemas populated with simple values.
  * Dublin Core ``dc:title`` LangAlt with multiple language variants
    (en, fr, ja, x-default).
  * Dublin Core ``dc:subject`` Bag with five keywords mixing ASCII and
    Unicode (CJK, accented Latin).
  * ISO 8601 dates with explicit timezone and naive (no timezone).
  * ``pdf:Trapped`` written via the generic property setter and parsed in
    lenient mode (upstream xmpbox does not declare a typed ``Trapped``
    field on ``AdobePDFSchema``).

JSON comparison rules
---------------------
Both sides emit canonical JSON. Dates compare as
``<epoch-millis>@<offset-minutes>`` so the absolute instant is independent
of how either side formats the wall-clock string. LangAlt blocks compare
as ``{lang: value}`` maps so ordering of the rdf:li children never matters.
Absent properties are omitted from the JSON on both sides — a property
that one side surfaces but the other does not would break equality.
"""

from __future__ import annotations

import datetime
import json
from io import BytesIO
from pathlib import Path

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from tests.oracle.harness import requires_oracle, run_probe_text


def _serialize(meta: XMPMetadata) -> bytes:
    """Render ``meta`` as XMP RDF/XML bytes via pypdfbox's serializer."""
    buf = BytesIO()
    XmpSerializer().serialize(meta, buf)
    return buf.getvalue()


def _fmt_instant(dt: datetime.datetime) -> str:
    """``<epoch-millis>@<offset-minutes>`` — matches the Java probe fmtCalendar."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.UTC)
    epoch_millis = int(dt.timestamp() * 1000)
    offset = dt.utcoffset()
    offset_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    return f"{epoch_millis}@{offset_minutes}"


def _pypdfbox_dump(packet: bytes, *, lenient: bool) -> dict:
    """Parse ``packet`` with pypdfbox's ``DomXmpParser`` and emit the same
    JSON shape the Java probe produces, so the two dictionaries are directly
    comparable.
    """
    parser = DomXmpParser()
    if lenient:
        parser.set_strict_parsing(False)
    meta = parser.parse(packet)
    root: dict = {"schema_count": len(meta.get_all_schemas())}

    dc = meta.get_dublin_core_schema()
    if dc is not None:
        dc_map: dict = {}
        for key, getter in (
            ("title", dc.get_title_property),
            ("description", dc.get_description_property),
            ("rights", dc.get_rights_property),
        ):
            lang_alt = getter()
            if lang_alt is None:
                continue
            payload = _lang_alt_to_map(lang_alt)
            if payload:
                dc_map[key] = payload
        creators = dc.get_creators()
        if creators:
            dc_map["creator"] = creators
        subjects = dc.get_subjects()
        if subjects:
            dc_map["subject"] = subjects
        fmt = dc.get_format()
        if fmt is not None:
            dc_map["format"] = fmt
        if dc_map:
            root["dc"] = dc_map

    xb = meta.get_xmp_basic_schema()
    if xb is not None:
        xb_map: dict = {}
        creator_tool = xb.get_creator_tool()
        if creator_tool is not None:
            xb_map["creatorTool"] = creator_tool
        for key, getter in (
            ("createDate", xb.get_create_date_value),
            ("modifyDate", xb.get_modify_date_value),
            ("metadataDate", xb.get_metadata_date_value),
        ):
            dt = getter()
            if dt is not None:
                xb_map[key] = _fmt_instant(dt)
        if xb_map:
            root["xmp"] = xb_map

    ap = meta.get_adobe_pdf_schema()
    if ap is not None:
        ap_map: dict = {}
        for key, getter in (
            ("producer", ap.get_producer),
            ("keywords", ap.get_keywords),
            ("pdfVersion", ap.get_pdf_version),
        ):
            v = getter()
            if v is not None:
                ap_map[key] = v
        trapped = ap.get_unqualified_text_property_value("Trapped")
        if trapped is not None:
            ap_map["trapped"] = trapped
        if ap_map:
            root["pdf"] = ap_map

    pa = meta.get_pdfa_identification_schema()
    if pa is not None:
        pa_map: dict = {}
        part = pa.get_part()
        if part is not None:
            pa_map["part"] = part
        conformance = pa.get_conformance()
        if conformance is not None:
            pa_map["conformance"] = conformance
        if pa_map:
            root["pdfaid"] = pa_map

    ps = meta.get_photoshop_schema()
    if ps is not None:
        ps_map: dict = {}
        city = ps.get_city()
        if city is not None:
            ps_map["city"] = city
        ap_pos = ps.get_authors_position()
        if ap_pos is not None:
            ps_map["authorsPosition"] = ap_pos
        date_created = ps.get_date_created()
        if date_created is not None:
            ps_map["dateCreated"] = date_created
        if ps_map:
            root["photoshop"] = ps_map

    return root


def _lang_alt_to_map(lang_alt) -> dict[str, str]:
    """Extract ``{lang: value}`` from a pypdfbox ``LangAlt`` instance,
    falling back to the LangAlt's underlying dict storage when the typed
    child iteration yields nothing (e.g. parser-deposited LangAlts)."""
    out: dict[str, str] = {}
    children = lang_alt.get_all_properties() if hasattr(lang_alt, "get_all_properties") else []
    for child in children or []:
        # TextType child with an xml:lang attribute.
        lang = "x-default"
        attrs = (
            child.get_all_attributes()
            if hasattr(child, "get_all_attributes")
            else None
        )
        for attr in attrs or []:
            name = getattr(attr, "get_name", lambda: None)()
            # Attribute names round-trip with the ``xml:`` prefix in pypdfbox's
            # DomXmpParser; some test cases may also see the bare ``lang``.
            if name in {"lang", "xml:lang"}:
                lang = getattr(attr, "get_value", lambda: "x-default")() or "x-default"
                break
        value = (
            child.get_string_value()
            if hasattr(child, "get_string_value")
            else None
        )
        if isinstance(value, str):
            out[lang] = value
    if out:
        return out
    # Fallback for LangAlts whose underlying storage is a plain {lang: text} dict.
    inner = getattr(lang_alt, "_languages", None)
    if isinstance(inner, dict):
        return {str(k): str(v) for k, v in inner.items()}
    return out


# --- builders for each case ---------------------------------------------


def _build_empty() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def _build_simple_full() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()

    dc = m.add_dublin_core_schema()
    dc.set_title("Sample Title", "x-default")
    dc.set_description("A round-trip sample.", "x-default")
    dc.add_creator("Alice Smith")
    dc.add_subject("pdf")
    dc.set_format("application/pdf")
    dc.set_rights("All rights reserved.", "x-default")

    xb = m.add_xmp_basic_schema()
    xb.set_creator_tool("pypdfbox")
    xb.set_create_date(
        datetime.datetime(2024, 6, 1, 10, 30, 0, tzinfo=datetime.UTC)
    )
    xb.set_modify_date(
        datetime.datetime(2024, 6, 2, 11, 0, 0, tzinfo=datetime.UTC)
    )
    xb.set_metadata_date(
        datetime.datetime(2024, 6, 3, 12, 0, 0, tzinfo=datetime.UTC)
    )

    ap = m.add_adobe_pdf_schema()
    ap.set_producer("pypdfbox/test")
    ap.set_keywords("keyword1, keyword2")
    ap.set_pdf_version("1.7")

    pa = m.add_pdfa_identification_schema()
    pa.set_part(3)
    pa.set_conformance("A")

    ps = m.add_photoshop_schema()
    ps.set_city("Berlin")
    ps.set_authors_position("Editor in chief")
    ps.set_date_created("2024-05-01T00:00:00+00:00")
    return m


def _build_lang_alt_multi() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_title("x-default", "Hello")
    dc.add_title("en", "Hello")
    dc.add_title("fr", "Bonjour")
    dc.add_title("ja", "こんにちは")
    return m


def _build_subject_bag_mixed() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    # Five keywords: three Unicode (CJK + accented Latin) + two ASCII.
    dc.add_subject("安全")
    dc.add_subject("PDF")
    dc.add_subject("日本")
    dc.add_subject("café")
    dc.add_subject("ascii-keyword")
    return m


def _build_date_with_tz() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    xb = m.add_xmp_basic_schema()
    xb.set_create_date(
        datetime.datetime(
            2023, 11, 15, 9, 45, 30,
            tzinfo=datetime.timezone(datetime.timedelta(hours=2)),
        )
    )
    xb.set_modify_date(
        datetime.datetime(
            2023, 11, 15, 9, 45, 30,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
        )
    )
    return m


def _build_date_no_tz() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    xb = m.add_xmp_basic_schema()
    # Naive datetime — serializer promotes to UTC (+00:00). Both sides
    # round-trip via the same convention so the parsed instant matches.
    xb.set_create_date(datetime.datetime(2024, 1, 15, 8, 0, 0))
    return m


def _build_with_trapped() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    ap = m.add_adobe_pdf_schema()
    ap.set_producer("pypdfbox")
    # Trapped is not a typed property on upstream's AdobePDFSchema — write
    # it via the generic setter so it lands as a child of the description.
    ap.set_text_property_value("Trapped", "True")
    return m


_CASES: list[tuple[str, callable, bool]] = [  # type: ignore[type-arg]
    ("empty", _build_empty, False),
    ("simple_full", _build_simple_full, False),
    ("lang_alt_multi", _build_lang_alt_multi, False),
    ("subject_bag_mixed", _build_subject_bag_mixed, False),
    ("date_with_tz", _build_date_with_tz, False),
    ("date_no_tz", _build_date_no_tz, False),
    ("trapped_lenient", _build_with_trapped, True),
]


@requires_oracle
@pytest.mark.parametrize(
    ("case_name", "builder", "lenient"),
    _CASES,
    ids=[name for name, _, _ in _CASES],
)
def test_xmp_round_trip_matches_xmpbox(
    case_name: str,
    builder,
    lenient: bool,
    tmp_path: Path,
) -> None:
    meta = builder()
    packet = _serialize(meta)
    packet_path = tmp_path / f"{case_name}.xmp"
    packet_path.write_bytes(packet)

    probe_args = [str(packet_path)]
    if lenient:
        probe_args.append("lenient")
    java_raw = run_probe_text("XmpRoundTripProbe", *probe_args)
    java_dump = json.loads(java_raw)
    py_dump = _pypdfbox_dump(packet, lenient=lenient)

    assert py_dump == java_dump, (
        f"round-trip divergence for {case_name}:\n"
        f"  java: {json.dumps(java_dump, sort_keys=True, ensure_ascii=False)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True, ensure_ascii=False)}"
    )
