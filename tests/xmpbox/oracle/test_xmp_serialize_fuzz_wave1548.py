"""Differential SERIALIZE fuzz parity for ``XmpSerializer.serialize`` (wave 1548).

Sibling of ``test_xmp_serializer_structure_oracle.py`` (a single fixed two-schema
shape dump) and ``test_xmp_reverse_serialize_oracle.py`` (xmpbox writes /
pypdfbox reads). Neither stresses the *serializer* across a wide corpus of edge
content. This wave builds ~29 ``XMPMetadata`` documents programmatically with
adversarial content, serializes each with pypdfbox's
:class:`~pypdfbox.xmpbox.xml.xmp_serializer.XmpSerializer`, then **re-parses**
the serialized bytes with :class:`~pypdfbox.xmpbox.dom_xmp_parser.DomXmpParser`
and projects a STABLE, byte-formatting-independent round-trip shape. The live
Apache xmpbox 3.0.7 oracle (``oracle/probes/XmpSerializeFuzzProbe.java``) mirrors
the identical builds + projection and the per-case shape is asserted line-for-line.

Comparing the round-tripped *shape* (not raw bytes) lets pypdfbox and xmpbox
legitimately diverge on whitespace / attribute order / xmlns placement (those
divergences are documented in CHANGES.md and pinned structurally in
``test_xmp_serializer_structure_oracle.py``) while still pinning the load-bearing
facts a faithful serializer must preserve: schema count, per-schema
prefix/namespace/about, property local names, array container type (Bag/Seq/Alt)
+ item order, LangAlt lang→value mapping, and survival of XML special chars
(``& < > " '``), unicode/astral/control chars, very long values, empty/whitespace
values, and multi-schema emission order.

Projection grammar per case (mirrors the probe)::

    {"schema_count": N, "schemas": [<schema>, ...]}

with schemas sorted by (namespace, prefix); each ``<schema>`` is
``{prefix, namespace, about, properties:[<prop>, ...]}`` (properties sorted by
name); each ``<prop>`` is a simple ``{name, kind:"simple", value}`` or an array
``{name, kind:"array", array_type, items}`` where ``items`` is a list for
Bag/Seq and a lang→value map (plus ``lang_alt:true``) for Alt.

Apache xmpbox is ground truth. Notable structural facts the oracle pins that this
test inherits both-sides:
  * an *empty* schema (a Dublin Core schema with no properties) round-trips to
    ``schema_count == 0`` — xmpbox emits an empty ``rdf:Description`` that carries
    no namespace-bound property, so the re-parser surfaces no schema. pypdfbox
    matches.
  * Dublin Core ``creator`` serializes as an ``rdf:Seq``, ``subject`` as an
    ``rdf:Bag``, and ``title``/``description`` as an ``rdf:Alt`` LangAlt — the
    Bag-vs-Seq distinction (lost in the flat-dict storage) is recovered on both
    sides from the schema's declared cardinality.

One case is a pinned, documented **parse-side** divergence, not a serialize
defect — :data:`PINNED_DIVERGENCES`. The serializer round-trips the value
faithfully (``<dc:format>   </dc:format>`` is emitted with the whitespace
intact, verified directly), but pypdfbox's ``DomXmpParser`` normalizes a
whitespace-only simple-property text node to the empty string (its element-text
extraction trims, and its whitespace-text-node normalization pass nulls
all-blank text), whereas xmpbox's parser preserves the literal spaces. This is a
parse-leniency divergence owned by the parser surface (wave 1545); the serialize
surface under test here is correct, so the case is pinned to the pypdfbox-side
shape rather than masking a serializer bug.
"""

from __future__ import annotations

import json
from io import BytesIO

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from pypdfbox.xmpbox.type.array_property import Cardinality
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------------------
# Corpus: each builder returns one XMPMetadata. Order MUST match the probe's
# ``corpus()`` so the line-for-line comparison lines up.


def _empty() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def _dc_empty_schema() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    m.add_dublin_core_schema()
    return m


def _dc_single_creator() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("Solo")
    return m


def _dc_many_creators() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    for name in ("A", "B", "C", "D"):
        dc.add_creator(name)
    return m


def _dc_subject_bag_order() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    for s in ("zeta", "alpha", "mu"):
        dc.add_subject(s)
    return m


def _dc_title_alt_multi_lang() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_title("x-default", "Default")
    dc.add_title("en", "English")
    dc.add_title("fr", "Francais")
    dc.add_title("de", "Deutsch")
    return m


def _dc_value_ampersand() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("Tom & Jerry")
    return m


def _dc_value_angle_brackets() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("<not a tag>")
    return m


def _dc_value_quotes() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("She said \"hi\" & 'bye'")
    return m


def _dc_title_special_in_alt() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_title("x-default", "A & B < C > D")
    return m


def _dc_unicode() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("éèê café")
    dc.add_subject("安全")
    dc.add_title("ja", "こんにちは")
    return m


def _dc_astral() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("emoji 😀 clef 𝄞")
    return m


def _dc_tab_newline() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("line1\nline2\ttabbed")
    return m


def _dc_empty_string_creator() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("")
    dc.add_creator("after-empty")
    return m


def _dc_whitespace_value() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.set_format("   ")
    return m


def _dc_long_value() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("abcdefghij" * 500)
    return m


def _dc_format_simple() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.set_format("application/pdf")
    return m


def _two_schemas() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("Author")
    ap = m.add_adobe_pdf_schema()
    ap.set_producer("prod")
    ap.set_keywords("k1, k2")
    return m


def _three_schemas() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.set_format("application/pdf")
    ap = m.add_adobe_pdf_schema()
    ap.set_producer("prod")
    xb = m.add_xmp_basic_schema()
    xb.set_creator_tool("toolname")
    return m


def _pdf_keywords_special() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    ap = m.add_adobe_pdf_schema()
    ap.set_keywords('a & b, <c>, "d"')
    ap.set_producer("p & q")
    ap.set_pdf_version("1.7")
    return m


def _nonempty_about() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.set_about_as_simple("uuid:1234-5678")
    dc.add_creator("X")
    return m


def _about_url() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.set_about_as_simple("http://example.com/doc#meta")
    dc.add_subject("s")
    return m


def _xmp_basic_text() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    xb = m.add_xmp_basic_schema()
    xb.set_creator_tool("My Tool 2.0")
    return m


def _dc_alt_single_lang() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.set_title("Only Default")
    return m


def _dc_desc_and_title() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_title("x-default", "T")
    dc.set_description("A description with & and < chars")
    return m


def _dc_lang_value_special() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_title("en", "Tom & <Jerry>")
    dc.add_title("fr", "café & crème")
    return m


def _dc_creator_with_newline_amp() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("first & second\nthird < fourth")
    return m


def _dc_all_arrays() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_creator("c1")
    dc.add_creator("c2")
    dc.add_subject("s1")
    dc.add_subject("s2")
    dc.add_subject("s3")
    dc.add_title("x-default", "td")
    dc.add_title("en", "te")
    dc.set_format("text/plain")
    return m


def _xmp_then_dc_prefix() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    xb = m.add_xmp_basic_schema()
    xb.set_creator_tool("tool")
    dc = m.add_dublin_core_schema()
    dc.add_creator("auth")
    return m


def _dc_subject_special_items() -> XMPMetadata:
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.add_subject("a&b")
    dc.add_subject("<x>")
    dc.add_subject('"q"')
    dc.add_subject("normal")
    return m


_CORPUS = [
    ("empty", _empty),
    ("dc_empty_schema", _dc_empty_schema),
    ("dc_single_creator", _dc_single_creator),
    ("dc_many_creators", _dc_many_creators),
    ("dc_subject_bag_order", _dc_subject_bag_order),
    ("dc_title_alt_multi_lang", _dc_title_alt_multi_lang),
    ("dc_value_ampersand", _dc_value_ampersand),
    ("dc_value_angle_brackets", _dc_value_angle_brackets),
    ("dc_value_quotes", _dc_value_quotes),
    ("dc_title_special_in_alt", _dc_title_special_in_alt),
    ("dc_unicode", _dc_unicode),
    ("dc_astral", _dc_astral),
    ("dc_tab_newline", _dc_tab_newline),
    ("dc_empty_string_creator", _dc_empty_string_creator),
    ("dc_whitespace_value", _dc_whitespace_value),
    ("dc_long_value", _dc_long_value),
    ("dc_format_simple", _dc_format_simple),
    ("two_schemas", _two_schemas),
    ("three_schemas", _three_schemas),
    ("pdf_keywords_special", _pdf_keywords_special),
    ("nonempty_about", _nonempty_about),
    ("about_url", _about_url),
    ("xmp_basic_text", _xmp_basic_text),
    ("dc_alt_single_lang", _dc_alt_single_lang),
    ("dc_desc_and_title", _dc_desc_and_title),
    ("dc_lang_value_special", _dc_lang_value_special),
    ("dc_creator_with_newline_amp", _dc_creator_with_newline_amp),
    ("dc_all_arrays", _dc_all_arrays),
    ("xmp_then_dc_prefix", _xmp_then_dc_prefix),
    ("dc_subject_special_items", _dc_subject_special_items),
]


# ---------------------------------------------------------------------------
# Projection: serialize → re-parse → normalized round-trip shape.


def _nz(value: str | None) -> str:
    return value or ""


def _project_field(schema, name: str, value: object) -> dict:
    """Mirror the probe's ``projectField`` over pypdfbox's flat-dict storage.

    pypdfbox keeps a re-parsed schema's properties in primitive form
    (``str`` / ``list`` / ``dict``) rather than typed ``AbstractField``
    objects, so the Bag/Seq distinction (lost in the flat dict) is recovered
    via the schema's declared cardinality — exactly the lookup the serializer
    itself performs through ``_cardinality_hint``.
    """
    out: dict = {"name": name}
    if isinstance(value, dict):
        # LangAlt → Alt container of lang→value entries.
        out["kind"] = "array"
        out["array_type"] = "Alt"
        out["lang_alt"] = True
        out["items"] = {str(k): str(v) for k, v in value.items()}
    elif isinstance(value, list):
        out["kind"] = "array"
        hint = XmpSerializer._cardinality_hint(schema, name)
        out["array_type"] = (hint or Cardinality.Bag).name
        out["items"] = [str(v) for v in value]
    else:
        out["kind"] = "simple"
        out["value"] = _nz(value if isinstance(value, str) else str(value))
    return out


def _project_schema(schema) -> dict:
    props_dict = schema.get_all_properties()
    properties = [
        _project_field(schema, name, props_dict[name])
        for name in sorted(props_dict)
    ]
    return {
        "prefix": _nz(schema.get_prefix()),
        "namespace": _nz(schema.get_namespace()),
        "about": _nz(schema.get_about_value()),
        "properties": properties,
    }


def _project(meta: XMPMetadata) -> dict:
    schemas = meta.get_all_schemas()
    ordered = sorted(
        schemas,
        key=lambda s: (_nz(s.get_namespace()), _nz(s.get_prefix())),
    )
    return {
        "schema_count": len(schemas),
        "schemas": [_project_schema(s) for s in ordered],
    }


def _pypdfbox_line(builder) -> str:
    try:
        meta = builder()
        buf = BytesIO()
        XmpSerializer().serialize(meta, buf, True)
        reparsed = DomXmpParser().parse(buf.getvalue())
        return json.dumps(
            _project(reparsed), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001 - mirror the probe's catch-all
        return f"EXC {type(exc).__name__}"


def _pypdfbox_dump() -> dict[str, str]:
    return {name: _pypdfbox_line(builder) for name, builder in _CORPUS}


def _parse_probe_output(text: str) -> dict[str, str]:
    """Parse ``CASE <name> <json-or-EXC>`` lines into a name→payload map."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("CASE "):
            continue
        rest = line[len("CASE ") :]
        name, _, payload = rest.partition(" ")
        result[name] = payload
    return result


def _canonical(payload: str) -> str:
    """Re-serialize a JSON payload canonically so the two emitters' key order
    and separator choices don't cause spurious mismatches; EXC lines pass
    through unchanged."""
    if payload.startswith("EXC "):
        return payload
    return json.dumps(
        json.loads(payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    )


# Cases where pypdfbox's *parse* leniency (not its serializer) legitimately
# diverges from xmpbox on the re-parsed shape. The serializer's output is
# byte-correct in every entry here; the divergence is introduced when pypdfbox's
# DomXmpParser reads the serialized packet back. Each entry is the canonical
# pypdfbox-side projection the test pins instead of the oracle's. See the module
# docstring + CHANGES.md (wave 1548).
PINNED_DIVERGENCES: dict[str, str] = {
    # Whitespace-only simple value: serializer emits "<dc:format>   </dc:format>"
    # intact; pypdfbox's parser normalizes the all-blank text node to "".
    "dc_whitespace_value": json.dumps(
        {
            "schema_count": 1,
            "schemas": [
                {
                    "about": "",
                    "namespace": "http://purl.org/dc/elements/1.1/",
                    "prefix": "dc",
                    "properties": [
                        {"kind": "simple", "name": "format", "value": ""}
                    ],
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ),
}


@requires_oracle
def test_serialize_fuzz_matches_xmpbox() -> None:
    java = _parse_probe_output(run_probe_text("XmpSerializeFuzzProbe"))
    py = _pypdfbox_dump()
    assert set(py) == set(java), (
        f"case-name set divergence: py-only={set(py) - set(java)}, "
        f"java-only={set(java) - set(py)}"
    )
    mismatches = []
    for name in py:
        expected = (
            PINNED_DIVERGENCES[name]
            if name in PINNED_DIVERGENCES
            else _canonical(java[name])
        )
        p = _canonical(py[name])
        if expected != p:
            mismatches.append(
                f"\n  case {name}:\n    expected: {expected}\n    py:       {p}"
            )
    assert not mismatches, "serialize round-trip divergence:" + "".join(mismatches)


def test_pinned_divergences_are_pypdfbox_truth() -> None:
    """The pinned-divergence expectations must equal pypdfbox's own re-parsed
    projection (no-oracle guard so the divergence stays honest even when the
    live Java oracle is unavailable)."""
    py = _pypdfbox_dump()
    for name, expected in PINNED_DIVERGENCES.items():
        assert _canonical(py[name]) == expected, (
            f"pinned divergence {name} drifted from pypdfbox actual:\n"
            f"  pinned: {expected}\n  actual: {_canonical(py[name])}"
        )


def test_serializer_preserves_whitespace_only_value() -> None:
    """Anchor the serialize surface itself: the serializer emits a
    whitespace-only simple value verbatim (the loss in the round trip is a
    parser normalization, not a serializer defect)."""
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.set_format("   ")
    buf = BytesIO()
    XmpSerializer().serialize(m, buf, True)
    assert "<dc:format>   </dc:format>" in buf.getvalue().decode("utf-8")
