"""Reverse-direction live Apache xmpbox parity for pypdfbox's parser.

The other xmpbox oracle files in this directory all run the
*pypdfbox-serialize → xmpbox-parse* direction: pypdfbox's
:class:`~pypdfbox.xmpbox.xml.xmp_serializer.XmpSerializer` writes the packet
and Apache xmpbox 3.0.7's ``DomXmpParser`` reads it back
(``test_xmp_round_trip_oracle``, ``test_xmp_dublin_core_oracle``) or pins the
emitted shape (``test_xmp_serializer_structure_oracle``). None exercise the
opposite leg — that pypdfbox's :class:`~pypdfbox.xmpbox.dom_xmp_parser.DomXmpParser`
reads a packet produced by xmpbox's *own* ``XmpSerializer`` identically.

This file closes that gap. ``XmpReverseSerializeProbe`` builds a fixed
five-schema document, serializes it with xmpbox's ``XmpSerializer`` to a file
(so pypdfbox parses the exact bytes xmpbox wrote), and prints a canonical JSON
projection of the same property values. The test parses the file with
pypdfbox's ``DomXmpParser``, builds the matching projection, and asserts
equality — a divergence in either the xmpbox-written byte shape or pypdfbox's
parser would surface here.

Corners audited (wave 1499, round 6) — all confirmed at parity:

  * ``xml:lang`` alternative arrays: lang order on xmpbox-serialized output
    (``title_order`` pins that xmpbox writes ``x-default`` first, then source
    order) parsed back without reordering.
  * Element-form simple properties vs attribute-form: xmpbox's serializer
    emits *element*-form (``<dc:format>…</dc:format>``), and pypdfbox reads it.
  * Namespace-prefix assignment determinism: xmpbox hoists per-schema
    ``xmlns`` onto ``rdf:RDF`` / the ``rdf:Description``; pypdfbox resolves the
    same typed values regardless.
  * Multi-``rdf:Description`` packets (one per schema) merged to five schemas.
  * Dublin Core LangAlt / Seq / Bag, dates with explicit and zero offset,
    PDF/A identification (lowercase ``part``/``conformance`` local names that
    xmpbox emits), Photoshop simple text.

Comparison rules mirror the sibling oracle files: dates compare as
``<epoch-millis>@<offset-minutes>`` (absolute instant + explicit zone offset);
LangAlt blocks compare as ``{lang: value}`` maps so ``rdf:li`` ordering does
not affect value equality, while ``title_order`` separately pins the emitted
lang sequence.
"""

from __future__ import annotations

import datetime
import json

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _fmt_instant(dt: datetime.datetime) -> str:
    """``<epoch-millis>@<offset-minutes>`` — matches the probe's fmtCalendar."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.UTC)
    epoch_millis = int(dt.timestamp() * 1000)
    offset = dt.utcoffset()
    offset_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    return f"{epoch_millis}@{offset_minutes}"


def _lang_of(child) -> str:
    for attr in child.get_all_attributes() or []:
        if attr.get_name() in {"lang", "xml:lang"}:
            return attr.get_value() or "x-default"
    return "x-default"


def _lang_alt_to_map(lang_alt) -> dict[str, str]:
    out: dict[str, str] = {}
    for child in lang_alt.get_all_properties() or []:
        value = child.get_string_value()
        if isinstance(value, str):
            out[_lang_of(child)] = value
    return out


def _lang_order(lang_alt) -> list[str]:
    return [_lang_of(child) for child in lang_alt.get_all_properties() or []]


def _pypdfbox_dump(packet: bytes) -> dict:
    meta = DomXmpParser().parse(packet)
    root: dict = {"schema_count": len(meta.get_all_schemas())}

    dc = meta.get_dublin_core_schema()
    dc_map: dict = {}
    title = dc.get_title_property()
    if title is not None:
        dc_map["title"] = _lang_alt_to_map(title)
        root["title_order"] = _lang_order(title)
    description = dc.get_description_property()
    if description is not None:
        dc_map["description"] = _lang_alt_to_map(description)
    creators = dc.get_creators()
    if creators:
        dc_map["creator"] = creators
    subjects = dc.get_subjects()
    if subjects:
        dc_map["subject"] = subjects
    fmt = dc.get_format()
    if fmt is not None:
        dc_map["format"] = fmt
    root["dc"] = dc_map

    xb = meta.get_xmp_basic_schema()
    xb_map: dict = {}
    creator_tool = xb.get_creator_tool()
    if creator_tool is not None:
        xb_map["creatorTool"] = creator_tool
    for key, getter in (
        ("createDate", xb.get_create_date_value),
        ("modifyDate", xb.get_modify_date_value),
    ):
        dt = getter()
        if dt is not None:
            xb_map[key] = _fmt_instant(dt)
    root["xmp"] = xb_map

    ap = meta.get_adobe_pdf_schema()
    ap_map: dict = {}
    for key, getter in (
        ("producer", ap.get_producer),
        ("keywords", ap.get_keywords),
        ("pdfVersion", ap.get_pdf_version),
    ):
        v = getter()
        if v is not None:
            ap_map[key] = v
    root["pdf"] = ap_map

    pa = meta.get_pdfa_identification_schema()
    pa_map: dict = {}
    part = pa.get_part()
    if part is not None:
        pa_map["part"] = part
    conformance = pa.get_conformance()
    if conformance is not None:
        pa_map["conformance"] = conformance
    root["pdfaid"] = pa_map

    ps = meta.get_photoshop_schema()
    ps_map: dict = {}
    city = ps.get_city()
    if city is not None:
        ps_map["city"] = city
    pos = ps.get_authors_position()
    if pos is not None:
        ps_map["authorsPosition"] = pos
    root["photoshop"] = ps_map

    return root


@requires_oracle
def test_reverse_serialize_matches_pypdfbox_parser(tmp_path) -> None:
    out_path = tmp_path / "reverse.xmp"
    java_raw = run_probe_text("XmpReverseSerializeProbe", str(out_path))
    java_dump = json.loads(java_raw)

    packet = out_path.read_bytes()
    py_dump = _pypdfbox_dump(packet)

    assert py_dump == java_dump, (
        "reverse-direction divergence (xmpbox-serialize → pypdfbox-parse):\n"
        f"  java: {json.dumps(java_dump, sort_keys=True, ensure_ascii=False)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True, ensure_ascii=False)}"
    )
