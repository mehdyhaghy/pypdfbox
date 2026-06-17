"""Differential parse-leniency fuzz parity for ``DomXmpParser.parse`` (wave 1512).

Sibling of ``oracle/probes/XmpParseFuzzProbe.java``. A fixed, seed-free corpus
of malformed / edge-case raw XMP packets is built here, written as the probe's
single ``<name>\\t<base64>\\t<strict|lenient>`` input file (so the exact same
bytes drive both arms), then run through the live Apache xmpbox 3.0.7 oracle.
pypdfbox's :class:`~pypdfbox.xmpbox.dom_xmp_parser.DomXmpParser` re-parses the
identical bytes and the per-case shape grammar is asserted line-for-line.

Output grammar (mirrors the probe), one line per case in corpus order::

    CASE <name> EXC <ErrorType>                       (parse threw)
    CASE <name> OK <schemaToken>;<schemaToken>;...     (parse succeeded)

where each ``schemaToken`` is ``<prefix>|<namespace>|<propCount>|<localName,...>``,
schemas sorted by namespace then prefix, property local names sorted, and
``OK -`` means zero schemas.

Apache xmpbox is ground truth. Cases where pypdfbox's leniency contract is a
defensible robustness divergence are listed in :data:`PINNED_DIVERGENCES` with
the pypdfbox-side expected line and a CHANGES.md citation; every other case must
match the oracle byte-for-byte.
"""

from __future__ import annotations

import base64
from pathlib import Path

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser, XmpParsingException
from tests.oracle.harness import requires_oracle, run_probe_text

_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_DC = "http://purl.org/dc/elements/1.1/"


def _packet(body: str) -> bytes:
    """Wrap RDF/XML ``body`` in a canonical xpacket + x:xmpmeta envelope."""
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        f'<rdf:RDF xmlns:rdf="{_RDF}">'
        f"{body}"
        "</rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")


# Reusable RDF/XML fragments ------------------------------------------------

_DC_TITLE = (
    f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
    "<dc:title><rdf:Alt><rdf:li xml:lang=\"x-default\">Hello</rdf:li>"
    "</rdf:Alt></dc:title>"
    "<dc:creator><rdf:Seq><rdf:li>Alice</rdf:li></rdf:Seq></dc:creator>"
    "</rdf:Description>"
)


def _build_corpus() -> list[tuple[str, bytes, bool]]:
    """Return the fixed (name, packet-bytes, strict) corpus.

    Each well-formed-vs-malformed shape is exercised in both arms (strict and
    lenient) so the parser's full strictness contract is covered.
    """
    cases: list[tuple[str, bytes]] = []

    # --- well-formed -------------------------------------------------------
    cases.append(("wellformed_dc", _packet(_DC_TITLE)))
    cases.append(
        (
            "wellformed_two_schemas",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}" '
                'xmlns:pdf="http://ns.adobe.com/pdf/1.3/" '
                'pdf:Producer="ACME">'
                "<dc:format>application/pdf</dc:format>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "wellformed_empty_rdf",
            _packet(""),
        )
    )
    cases.append(
        (
            "wellformed_empty_desc",
            _packet('<rdf:Description rdf:about=""/>'),
        )
    )
    cases.append(
        (
            "wellformed_attr_only",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}" '
                'dc:format="text/plain" dc:source="src"/>'
            ),
        )
    )

    # --- structural / envelope problems ------------------------------------
    cases.append(("empty_input", b""))
    cases.append(("whitespace_only", b"   \n\t  "))
    cases.append(("not_xml", b"this is not xml at all"))
    cases.append(
        (
            "no_rdf_root",
            (
                '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
                '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
                '<foo:bar xmlns:foo="urn:foo">x</foo:bar>'
                "</x:xmpmeta>"
                '<?xpacket end="w"?>'
            ).encode("utf-8"),
        )
    )
    cases.append(
        (
            "bare_rdf_no_xmpmeta",
            (
                f'<rdf:RDF xmlns:rdf="{_RDF}">'
                f"{_DC_TITLE}</rdf:RDF>"
            ).encode("utf-8"),
        )
    )
    cases.append(
        (
            "truncated_mid_element",
            _packet(_DC_TITLE)[:-40],
        )
    )
    cases.append(
        (
            "unclosed_tag",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:format>application/pdf"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "mismatched_tag",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:format>x</dc:source>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "doctype_present",
            (
                '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
                "<!DOCTYPE x:xmpmeta>"
                '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
                f'<rdf:RDF xmlns:rdf="{_RDF}">{_DC_TITLE}</rdf:RDF>'
                "</x:xmpmeta>"
                '<?xpacket end="w"?>'
            ).encode("utf-8"),
        )
    )
    cases.append(
        (
            "undeclared_prefix",
            _packet(
                '<rdf:Description rdf:about="">'
                "<dc:format>x</dc:format>"
                "</rdf:Description>"
            ),
        )
    )

    # --- unknown / custom schema -------------------------------------------
    cases.append(
        (
            "unknown_schema_elem",
            _packet(
                '<rdf:Description rdf:about="" xmlns:my="urn:my:ns">'
                "<my:thing>value</my:thing>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "unknown_schema_attr",
            _packet(
                '<rdf:Description rdf:about="" xmlns:my="urn:my:ns" '
                'my:thing="value"/>'
            ),
        )
    )

    # --- mistyped cardinality (known property, wrong shape) ----------------
    cases.append(
        (
            "dc_title_as_text",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:title>bare text</dc:title>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "dc_creator_as_bag",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:creator><rdf:Bag><rdf:li>A</rdf:li></rdf:Bag></dc:creator>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "dc_format_as_seq",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:format><rdf:Seq><rdf:li>a</rdf:li></rdf:Seq></dc:format>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "dc_subject_as_text_attr",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}" '
                'dc:subject="oops"/>'
            ),
        )
    )

    # --- unknown property on a known schema --------------------------------
    cases.append(
        (
            "dc_unknown_property",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:bogus>x</dc:bogus>"
                "</rdf:Description>"
            ),
        )
    )

    # --- reserved xml namespace as property element ------------------------
    cases.append(
        (
            "xml_ns_as_property",
            _packet(
                '<rdf:Description rdf:about="">'
                "<xml:lang>en</xml:lang>"
                "</rdf:Description>"
            ),
        )
    )

    # --- multiple Descriptions, same namespace -> one schema ---------------
    cases.append(
        (
            "split_namespace",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:format>application/pdf</dc:format></rdf:Description>"
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:source>src</dc:source></rdf:Description>"
            ),
        )
    )

    # --- non-rdf parseType on a struct property ----------------------------
    cases.append(
        (
            "bad_parsetype_ns",
            _packet(
                '<rdf:Description rdf:about="" '
                'xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">'
                '<xmpMM:DerivedFrom xmpMM:parseType="Resource">'
                "<xmpMM:instanceID>x</xmpMM:instanceID>"
                "</xmpMM:DerivedFrom></rdf:Description>"
            ),
        )
    )

    # Each shape is exercised strict + lenient.
    out: list[tuple[str, bytes, bool]] = []
    for name, packet in cases:
        out.append((f"{name}__strict", packet, True))
        out.append((f"{name}__lenient", packet, False))
    return out


# Cases where pypdfbox's leniency contract is a deliberate, documented
# robustness divergence from Apache xmpbox. Maps case name ->
# (oracle_line, pypdfbox_line): the divergence is asserted against BOTH the
# (different) oracle line and the pinned pypdfbox line, so neither side can
# silently drift (an upstream re-sync that changed the oracle line, or a
# pypdfbox change, both fail the test loudly).
#
# Root cause (all entries): pypdfbox's DomXmpParser is a subset port that has
# not yet ported upstream's ``TypeMapping`` / ``PropertiesDescription`` type
# system (see the many "not yet ported" notes in dom_xmp_parser.py). Without
# the per-namespace ``isDefinedSchema`` registry and per-property
# ``checkPropertyDefinition`` type lookup, the strict-mode contract for
# unknown schemas / unknown properties / cardinality mismatches and the
# mandatory-xpacket-PI / x:xmpmeta-shape error-type routing all diverge.
# Validated against live xmpbox 3.0.7. See CHANGES.md (wave 1512).
PINNED_DIVERGENCES: dict[str, tuple[str, str]] = {
    # x:xmpmeta wrapping a non-rdf:RDF child. Upstream's findDescriptionsParent
    # raises FORMAT ("x:xmpmeta does not contains rdf:RDF element"); pypdfbox's
    # parse() locates rdf:RDF via _find_rdf_root and surfaces NoRootElement.
    "no_rdf_root__strict": (
        "CASE no_rdf_root__strict EXC Format",
        "CASE no_rdf_root__strict EXC NoRootElement",
    ),
    "no_rdf_root__lenient": (
        "CASE no_rdf_root__lenient EXC Format",
        "CASE no_rdf_root__lenient EXC NoRootElement",
    ),
    # No leading <?xpacket?> PI. Upstream strict mode mandates it
    # (XpacketBadStart); pypdfbox treats the xpacket envelope as optional and
    # parses the bare RDF/XML.
    "bare_rdf_no_xmpmeta__strict": (
        "CASE bare_rdf_no_xmpmeta__strict EXC XpacketBadStart",
        "CASE bare_rdf_no_xmpmeta__strict OK "
        "dc|http://purl.org/dc/elements/1.1/|2|creator,title",
    ),
    # Unknown schema namespace as a property element. Upstream's
    # parseChildrenAsProperties raises NoSchema (isDefinedSchema gate, NOT
    # gated by strict) in both arms; pypdfbox falls back to a free-form
    # XMPSchema and keeps the property.
    "unknown_schema_elem__strict": (
        "CASE unknown_schema_elem__strict EXC NoSchema",
        "CASE unknown_schema_elem__strict OK my|urn:my:ns|1|thing",
    ),
    # Unknown schema namespace in attribute-shorthand form. Upstream's
    # tryParseAttributesAsProperties drops the attribute (zero schemas);
    # pypdfbox keeps it as a free-form text property.
    "unknown_schema_attr__strict": (
        "CASE unknown_schema_attr__strict OK -",
        "CASE unknown_schema_attr__strict OK my|urn:my:ns|1|thing",
    ),
    "unknown_schema_attr__lenient": (
        "CASE unknown_schema_attr__lenient OK -",
        "CASE unknown_schema_attr__lenient OK my|urn:my:ns|1|thing",
    ),
    # dc:title (declared Alt) presented as bare Text. Both raise in strict
    # mode; the error-type token differs (upstream FORMAT from the
    # IllegalArgumentException wrapper vs pypdfbox's INVALID_TYPE cardinality
    # check).
    "dc_title_as_text__strict": (
        "CASE dc_title_as_text__strict EXC Format",
        "CASE dc_title_as_text__strict EXC InvalidType",
    ),
    # dc:creator (declared Seq) presented as rdf:Bag. Upstream strict raises
    # FORMAT (array-flavour mismatch); pypdfbox tolerates Bag-for-Seq and
    # keeps the property.
    "dc_creator_as_bag__strict": (
        "CASE dc_creator_as_bag__strict EXC Format",
        "CASE dc_creator_as_bag__strict OK "
        "dc|http://purl.org/dc/elements/1.1/|1|creator",
    ),
    # dc:format (declared Simple) presented as rdf:Seq. Upstream strict
    # accepts it (the first li becomes the simple value); pypdfbox's
    # cardinality check rejects an array for a Simple slot.
    "dc_format_as_seq__strict": (
        "CASE dc_format_as_seq__strict OK "
        "dc|http://purl.org/dc/elements/1.1/|1|format",
        "CASE dc_format_as_seq__strict EXC InvalidType",
    ),
    # Unknown property on a known (dc) schema. Upstream strict raises
    # InvalidType ("No type defined"); pypdfbox has no KNOWN_PROPERTIES
    # allow-list wired for the typed schemas, so it keeps the property.
    "dc_unknown_property__strict": (
        "CASE dc_unknown_property__strict EXC InvalidType",
        "CASE dc_unknown_property__strict OK "
        "dc|http://purl.org/dc/elements/1.1/|1|bogus",
    ),
    # Reserved xml: namespace as a property element, lenient arm. Upstream's
    # NoSchema gate is not gated by strict, so it raises even in lenient mode;
    # pypdfbox's _reject_reserved_namespace_as_property drops the element in
    # lenient mode (yielding zero schemas).
    "xml_ns_as_property__lenient": (
        "CASE xml_ns_as_property__lenient EXC NoSchema",
        "CASE xml_ns_as_property__lenient OK -",
    ),
    # Non-rdf parseType="Resource" on a struct property. Upstream raises
    # FORMAT in both arms (the IllegalArgumentException wrapper); pypdfbox
    # raises INVALID_TYPE in strict mode and drops the bad attribute in
    # lenient mode (keeping the property).
    "bad_parsetype_ns__strict": (
        "CASE bad_parsetype_ns__strict EXC Format",
        "CASE bad_parsetype_ns__strict EXC InvalidType",
    ),
    "bad_parsetype_ns__lenient": (
        "CASE bad_parsetype_ns__lenient EXC Format",
        "CASE bad_parsetype_ns__lenient OK "
        "xmpMM|http://ns.adobe.com/xap/1.0/mm/|1|DerivedFrom",
    ),
}


def _shape(meta: object) -> str:
    schemas = meta.get_all_schemas()
    if not schemas:
        return "-"
    tokens: list[str] = []
    for s in schemas:
        names = sorted(s.get_all_properties().keys())
        tokens.append(
            f"{s.get_prefix()}|{s.get_namespace()}|{len(names)}|{','.join(names)}"
        )
    tokens.sort()
    return ";".join(tokens)


def _py_line(name: str, packet: bytes, strict: bool) -> str:
    parser = DomXmpParser()
    parser.set_strict_parsing(strict)
    try:
        meta = parser.parse(packet)
    except XmpParsingException as exc:
        # pypdfbox's ErrorType member names are UPPER_SNAKE_CASE; the upstream
        # token is the Java enum *constant* name (e.g. "Format"), which pypdfbox
        # mirrors as the enum member's ``.value``. Emit ``.value`` so the token
        # matches the probe's ``getErrorType().name()``.
        return f"CASE {name} EXC {exc.get_error_type().value}"
    except Exception as exc:  # noqa: BLE001 - mirror probe's Throwable catch
        return f"CASE {name} EXC OTHER:{type(exc).__name__}"
    return f"CASE {name} OK {_shape(meta)}"


def _write_corpus_file(
    corpus: list[tuple[str, bytes, bool]], path: Path
) -> None:
    lines: list[str] = []
    for name, packet, strict in corpus:
        b64 = base64.b64encode(packet).decode("ascii")
        arm = "strict" if strict else "lenient"
        lines.append(f"{name}\t{b64}\t{arm}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@requires_oracle
def test_xmp_parse_fuzz_parity(tmp_path: Path) -> None:
    corpus = _build_corpus()
    input_file = tmp_path / "xmp_parse_fuzz_corpus.tsv"
    _write_corpus_file(corpus, input_file)

    oracle_out = run_probe_text("XmpParseFuzzProbe", str(input_file))
    oracle_lines = [ln for ln in oracle_out.splitlines() if ln]
    assert len(oracle_lines) == len(corpus), (
        f"oracle emitted {len(oracle_lines)} lines for {len(corpus)} cases"
    )

    mismatches: list[str] = []
    pinned_hits = 0
    for (name, packet, strict), oracle_line in zip(
        corpus, oracle_lines, strict=True
    ):
        py_line = _py_line(name, packet, strict)
        if name in PINNED_DIVERGENCES:
            pinned_hits += 1
            pinned_oracle, pinned_py = PINNED_DIVERGENCES[name]
            # Validate BOTH sides of the pin so neither can drift silently:
            # an upstream re-sync that changed the oracle line, or a pypdfbox
            # change, both fail loudly here.
            assert oracle_line == pinned_oracle, (
                f"pinned oracle line drifted for {name}:\n"
                f"  expected {pinned_oracle!r}\n  got      {oracle_line!r}"
            )
            assert py_line == pinned_py, (
                f"pinned pypdfbox line drifted for {name}:\n"
                f"  expected {pinned_py!r}\n  got      {py_line!r}"
            )
            assert oracle_line != py_line, (
                f"{name} is pinned as a divergence but oracle now agrees; "
                "remove the pin."
            )
            continue
        if py_line != oracle_line:
            mismatches.append(
                f"{name}: oracle={oracle_line!r} pypdfbox={py_line!r}"
            )

    assert not mismatches, "XMP parse-fuzz divergences:\n" + "\n".join(mismatches)
    assert pinned_hits == len(PINNED_DIVERGENCES), (
        "stale PINNED_DIVERGENCES entries not exercised by the corpus: "
        f"{set(PINNED_DIVERGENCES) - {c[0] for c in corpus}}"
    )
