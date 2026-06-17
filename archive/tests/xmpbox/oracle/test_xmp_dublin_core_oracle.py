"""Live Apache xmpbox Dublin Core round-trip parity for pypdfbox.

Builds an XMP packet whose Dublin Core schema exercises every array shape DC
uses — ``dc:title`` as a LangAlt, ``dc:creator`` as an ordered ``Seq``,
``dc:subject`` as a ``Bag``, and ``dc:date`` as a ``Seq`` of ISO-8601 dates —
serializes it with pypdfbox's :class:`XmpSerializer`, and asserts that Apache
xmpbox 3.0.7's ``DublinCoreSchema`` reads back the same field values that
pypdfbox's own ``DomXmpParser`` extracts from the identical bytes.

This complements ``test_xmp_round_trip_oracle.py`` (which spans all five
schemas at one value each) by focusing on the DC array surface, and in
particular on ``dc:date`` — a ``Seq`` of typed dates that the broader
round-trip test does not cover. Two probe modes are compared:

  * direct: xmpbox parses the pypdfbox-emitted packet.
  * roundtrip: xmpbox parses, re-serializes through its own ``XmpSerializer``,
    and re-parses — so a divergence introduced by either serializer surfaces.

Comparison rules mirror the sibling round-trip test: dates compare as
``<epoch-millis>@<offset-minutes>`` (absolute instant + explicit zone offset,
independent of wall-clock formatting); LangAlt blocks compare as
``{lang: value}`` maps so rdf:li ordering never matters; ordered (creator) and
bag (subject) arrays compare as plain lists in parsed order.
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


def _lang_alt_to_map(lang_alt) -> dict[str, str]:
    out: dict[str, str] = {}
    children = (
        lang_alt.get_all_properties()
        if hasattr(lang_alt, "get_all_properties")
        else []
    )
    for child in children or []:
        lang = "x-default"
        attrs = (
            child.get_all_attributes()
            if hasattr(child, "get_all_attributes")
            else None
        )
        for attr in attrs or []:
            name = getattr(attr, "get_name", lambda: None)()
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
    return out


def _pypdfbox_dump(packet: bytes) -> dict:
    """Parse ``packet`` with pypdfbox and emit the Java probe's JSON shape."""
    meta = DomXmpParser().parse(packet)
    root: dict = {}
    dc = meta.get_dublin_core_schema()
    if dc is not None:
        title = dc.get_title_property()
        if title is not None:
            payload = _lang_alt_to_map(title)
            if payload:
                root["title"] = payload
        creators = dc.get_creators()
        if creators:
            root["creator"] = creators
        subjects = dc.get_subjects()
        if subjects:
            root["subject"] = subjects
        dates = dc.get_dates()
        if dates:
            root["date"] = [_fmt_instant(d) for d in dates]
    return root


def _build_dc_full() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    # title: LangAlt with x-default + two language variants (one CJK).
    dc.add_title("x-default", "Hello")
    dc.add_title("fr", "Bonjour")
    dc.add_title("ja", "こんにちは")
    # creator: ordered Seq — order is significant.
    dc.add_creator("Alice")
    dc.add_creator("Bob")
    dc.add_creator("Carol")
    # subject: Bag mixing ASCII + accented Latin + CJK.
    dc.add_subject("pdf")
    dc.add_subject("xmp")
    dc.add_subject("café")
    dc.add_subject("日本")
    # date: Seq of dates — UTC and a +02:00 offset.
    dc.add_date(datetime.datetime(2024, 6, 1, 10, 30, 0, tzinfo=datetime.UTC))
    dc.add_date(
        datetime.datetime(
            2023, 1, 2, 3, 4, 5,
            tzinfo=datetime.timezone(datetime.timedelta(hours=2)),
        )
    )
    return m


def _build_dc_single_date_neg_offset() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("Solo Author")
    dc.add_subject("only-keyword")
    dc.add_date(
        datetime.datetime(
            2022, 12, 31, 23, 59, 59,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
        )
    )
    return m


_CASES = [
    ("dc_full", _build_dc_full),
    ("dc_single_date_neg_offset", _build_dc_single_date_neg_offset),
]


@requires_oracle
@pytest.mark.parametrize("mode", ["direct", "roundtrip"])
@pytest.mark.parametrize(
    ("case_name", "builder"),
    _CASES,
    ids=[name for name, _ in _CASES],
)
def test_dublin_core_round_trip_matches_xmpbox(
    case_name: str,
    builder,
    mode: str,
    tmp_path: Path,
) -> None:
    meta = builder()
    packet = _serialize(meta)
    packet_path = tmp_path / f"{case_name}.xmp"
    packet_path.write_bytes(packet)

    probe_args = [str(packet_path)]
    if mode == "roundtrip":
        probe_args.append("roundtrip")
    java_dump = json.loads(run_probe_text("XmpDublinCoreProbe", *probe_args))
    py_dump = _pypdfbox_dump(packet)

    assert py_dump == java_dump, (
        f"DC divergence for {case_name} ({mode}):\n"
        f"  java: {json.dumps(java_dump, sort_keys=True, ensure_ascii=False)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True, ensure_ascii=False)}"
    )
