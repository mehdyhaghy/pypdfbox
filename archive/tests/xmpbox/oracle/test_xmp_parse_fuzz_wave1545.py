"""Differential parse-leniency fuzz parity for ``DomXmpParser.parse`` (wave 1545).

Second-generation sibling of ``oracle/probes/XmpParseFuzzProbe.java`` (the probe
is a generic corpus runner; wave 1512 introduced it, this wave reuses it with a
fresh, non-overlapping corpus). A fixed, seed-free corpus of malformed / edge
XMP packets is built here, written as the probe's single
``<name>\\t<base64>\\t<strict|lenient>`` input file (so the exact same bytes
drive both arms), then run through the live Apache xmpbox 3.0.7 oracle.
pypdfbox's :class:`~pypdfbox.xmpbox.dom_xmp_parser.DomXmpParser` re-parses the
identical bytes and the per-case shape grammar is asserted line-for-line.

Angles this wave fuzzes (deliberately disjoint from wave 1512's corpus):
  * lang-Alt ``rdf:li`` with no ``xml:lang`` (implicit x-default);
  * ``xml:lang`` on a ``rdf:Bag`` ``rdf:li`` (qualifier on a non-Alt array);
  * duplicate property elements / attribute-vs-element-form collision;
  * XML comment and CDATA inside a property's text node;
  * nested / deeply-nested ``parseType="Resource"`` struct under an array;
  * an extra non-Description child under ``rdf:RDF``;
  * empty ``rdf:Alt`` container;
  * mixed text+container content in one property element;
  * duplicate ``xml:lang`` keys in an Alt;
  * a numeric (``xmp:Rating``) / date (``xmp:CreateDate``) property holding a
    non-numeric / non-date text value;
  * a ResourceRef simple-struct given only as a bare ``rdf:resource`` attribute;
  * UTF-16-LE encoded packet + UTF-8 BOM with an explicit XML declaration;
  * a malformed trailing ``<?xpacket end="z"?>`` marker (FIXED this wave);
  * a wholly absent trailing ``<?xpacket?>`` end PI;
  * a known LangAlt property presented as ``rdf:Seq`` and a known Bag property
    presented as ``rdf:Alt`` (cardinality-flavour mismatches).

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
_XMP = "http://ns.adobe.com/xap/1.0/"
_MM = "http://ns.adobe.com/xap/1.0/mm/"
_STEVT = "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"


def _packet(body: str, end: str = '<?xpacket end="w"?>') -> bytes:
    """Wrap RDF/XML ``body`` in a canonical xpacket + x:xmpmeta envelope."""
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        f'<rdf:RDF xmlns:rdf="{_RDF}">'
        f"{body}"
        "</rdf:RDF></x:xmpmeta>" + end
    ).encode("utf-8")


_DC_TITLE = (
    f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
    '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">Hi</rdf:li>'
    "</rdf:Alt></dc:title></rdf:Description>"
)


def _build_corpus() -> list[tuple[str, bytes, bool]]:
    """Return the fixed (name, packet-bytes, strict) corpus."""
    cases: list[tuple[str, bytes]] = []

    # --- lang-alternative edge cases ---------------------------------------
    cases.append(
        (
            "alt_no_lang",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:title><rdf:Alt><rdf:li>NoLang</rdf:li></rdf:Alt></dc:title>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "dup_lang",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                '<dc:title><rdf:Alt><rdf:li xml:lang="en">A</rdf:li>'
                '<rdf:li xml:lang="en">B</rdf:li></rdf:Alt></dc:title>'
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "empty_alt",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:title><rdf:Alt></rdf:Alt></dc:title></rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "bag_li_lang",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                '<dc:subject><rdf:Bag><rdf:li xml:lang="en">x</rdf:li>'
                "</rdf:Bag></dc:subject></rdf:Description>"
            ),
        )
    )

    # --- duplicate / colliding properties ----------------------------------
    cases.append(
        (
            "dup_prop",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:format>a</dc:format><dc:format>b</dc:format>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "mixed_attr_elem",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}" '
                'dc:format="attrval"><dc:format>elemval</dc:format>'
                "</rdf:Description>"
            ),
        )
    )

    # --- comment / CDATA / mixed content in property text ------------------
    cases.append(
        (
            "comment_in_prop",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:format>app<!--c-->lication</dc:format></rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "cdata_prop",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:format><![CDATA[a<b]]></dc:format></rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "mixed_content",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:subject>leadtext<rdf:Bag><rdf:li>a</rdf:li></rdf:Bag>"
                "</dc:subject></rdf:Description>"
            ),
        )
    )

    # --- structured types under arrays -------------------------------------
    cases.append(
        (
            "nested_desc_struct",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:stEvt="{_STEVT}" '
                f'xmlns:xmpMM="{_MM}"><xmpMM:History><rdf:Seq>'
                '<rdf:li rdf:parseType="Resource">'
                "<stEvt:action>saved</stEvt:action></rdf:li>"
                "</rdf:Seq></xmpMM:History></rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "deep_struct",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:stEvt="{_STEVT}" '
                f'xmlns:xmpMM="{_MM}"><xmpMM:History><rdf:Seq>'
                '<rdf:li rdf:parseType="Resource">'
                "<stEvt:action>saved</stEvt:action>"
                "<stEvt:changed>/metadata</stEvt:changed>"
                "<stEvt:when>2020-01-01T00:00:00Z</stEvt:when>"
                "</rdf:li></rdf:Seq></xmpMM:History></rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "resource_ref",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:xmpMM="{_MM}">'
                '<xmpMM:DerivedFrom rdf:resource="uuid:abc"/>'
                "</rdf:Description>"
            ),
        )
    )

    # --- extra non-Description child under rdf:RDF -------------------------
    cases.append(
        (
            "rdf_extra_child",
            _packet(
                _DC_TITLE + '<foo:bar xmlns:foo="urn:foo">x</foo:bar>'
            ),
        )
    )

    # --- bad datatypes (numeric / date slots holding junk text) -----------
    cases.append(
        (
            "bad_numeric",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:xmp="{_XMP}">'
                "<xmp:Rating>notanumber</xmp:Rating></rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "rating_ws",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:xmp="{_XMP}">'
                "<xmp:Rating> 3 </xmp:Rating></rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "bad_date",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:xmp="{_XMP}">'
                "<xmp:CreateDate>not-a-date</xmp:CreateDate></rdf:Description>"
            ),
        )
    )

    # --- encoding / BOM edge cases -----------------------------------------
    cases.append(
        (
            "utf16le",
            (
                '﻿<?xpacket begin="" id="id"?>'
                '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
                f'<rdf:RDF xmlns:rdf="{_RDF}">{_DC_TITLE}'
                "</rdf:RDF></x:xmpmeta>"
                '<?xpacket end="w"?>'
            ).encode("utf-16-le"),
        )
    )
    cases.append(
        (
            "xmldecl_bom",
            b"\xef\xbb\xbf<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            + _packet(_DC_TITLE),
        )
    )

    # --- xpacket end-marker edge cases (bad_end_val FIXED wave 1545) -------
    cases.append(("bad_end_val", _packet(_DC_TITLE, end='<?xpacket end="z"?>')))
    cases.append(("no_end", _packet(_DC_TITLE, end="")))

    # --- cardinality-flavour mismatches (declared Alt as Seq, Bag as Alt) --
    cases.append(
        (
            "title_as_seq",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                "<dc:title><rdf:Seq><rdf:li>x</rdf:li></rdf:Seq></dc:title>"
                "</rdf:Description>"
            ),
        )
    )
    cases.append(
        (
            "subject_as_alt",
            _packet(
                f'<rdf:Description rdf:about="" xmlns:dc="{_DC}">'
                '<dc:subject><rdf:Alt><rdf:li xml:lang="en">x</rdf:li>'
                "</rdf:Alt></dc:subject></rdf:Description>"
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
# drift silently.
#
# Root cause (almost all entries): pypdfbox's DomXmpParser is a subset port
# that has not yet ported upstream's ``TypeMapping`` / ``PropertiesDescription``
# type system. Without the per-property typed-field model, upstream's value
# typing (numeric / date), duplicate-property handling, and the simple-struct
# ResourceRef materialisation all diverge from pypdfbox's plain-primitive
# representation. Validated against live xmpbox 3.0.7. See CHANGES.md (wave
# 1545).
PINNED_DIVERGENCES: dict[str, tuple[str, str]] = {
    # Duplicate <dc:format> element. Upstream keeps both properties (it stores
    # a list of TextType siblings under the same name, propCount=2); pypdfbox's
    # plain-dict slot is last-write-wins, collapsing to a single property.
    "dup_prop__strict": (
        "CASE dup_prop__strict OK "
        "dc|http://purl.org/dc/elements/1.1/|2|format,format",
        "CASE dup_prop__strict OK "
        "dc|http://purl.org/dc/elements/1.1/|1|format",
    ),
    "dup_prop__lenient": (
        "CASE dup_prop__lenient OK "
        "dc|http://purl.org/dc/elements/1.1/|2|format,format",
        "CASE dup_prop__lenient OK "
        "dc|http://purl.org/dc/elements/1.1/|1|format",
    ),
    # dc:format given in BOTH attribute-shorthand and element form. Upstream
    # treats them as two distinct properties (propCount=2); pypdfbox's
    # last-write-wins slot keeps one.
    "mixed_attr_elem__strict": (
        "CASE mixed_attr_elem__strict OK "
        "dc|http://purl.org/dc/elements/1.1/|2|format,format",
        "CASE mixed_attr_elem__strict OK "
        "dc|http://purl.org/dc/elements/1.1/|1|format",
    ),
    "mixed_attr_elem__lenient": (
        "CASE mixed_attr_elem__lenient OK "
        "dc|http://purl.org/dc/elements/1.1/|2|format,format",
        "CASE mixed_attr_elem__lenient OK "
        "dc|http://purl.org/dc/elements/1.1/|1|format",
    ),
    # xmp:Rating is declared Integer; a non-numeric text value fails upstream's
    # value typing (IntegerType.setValue → NumberFormatException, wrapped as
    # FORMAT) in both arms. pypdfbox has no value-typing pass, so it keeps the
    # raw text. Same root cause as the numeric-vs-date typing gap.
    "bad_numeric__strict": (
        "CASE bad_numeric__strict EXC Format",
        "CASE bad_numeric__strict OK "
        "xmp|http://ns.adobe.com/xap/1.0/|1|Rating",
    ),
    "bad_numeric__lenient": (
        "CASE bad_numeric__lenient EXC Format",
        "CASE bad_numeric__lenient OK "
        "xmp|http://ns.adobe.com/xap/1.0/|1|Rating",
    ),
    # xmp:Rating = " 3 " — surrounding whitespace. Upstream's IntegerType still
    # rejects it (it does not trim before Integer.parseInt), so both arms raise
    # FORMAT; pypdfbox keeps the trimmed text. Same value-typing gap.
    "rating_ws__strict": (
        "CASE rating_ws__strict EXC Format",
        "CASE rating_ws__strict OK xmp|http://ns.adobe.com/xap/1.0/|1|Rating",
    ),
    "rating_ws__lenient": (
        "CASE rating_ws__lenient EXC Format",
        "CASE rating_ws__lenient OK xmp|http://ns.adobe.com/xap/1.0/|1|Rating",
    ),
    # xmp:CreateDate is declared Date; a non-date text value fails upstream's
    # DateType.setValue (DateConverter throws, wrapped FORMAT) in both arms.
    # pypdfbox keeps the raw text (no date typing on parse).
    "bad_date__strict": (
        "CASE bad_date__strict EXC Format",
        "CASE bad_date__strict OK "
        "xmp|http://ns.adobe.com/xap/1.0/|1|CreateDate",
    ),
    "bad_date__lenient": (
        "CASE bad_date__lenient EXC Format",
        "CASE bad_date__lenient OK "
        "xmp|http://ns.adobe.com/xap/1.0/|1|CreateDate",
    ),
    # xmpMM:DerivedFrom (a ResourceRef simple-struct) given only as a bare
    # rdf:resource attribute with no struct children. Upstream's
    # manageStructuredType requires the struct's typed fields; a childless
    # resource ref materialises no property (propCount=0). pypdfbox's
    # _parse_property_value treats the rdf:resource as a simple text value and
    # keeps the property (propCount=1).
    "resource_ref__strict": (
        "CASE resource_ref__strict OK xmpMM|http://ns.adobe.com/xap/1.0/mm/|0|",
        "CASE resource_ref__strict OK "
        "xmpMM|http://ns.adobe.com/xap/1.0/mm/|1|DerivedFrom",
    ),
    "resource_ref__lenient": (
        "CASE resource_ref__lenient OK xmpMM|http://ns.adobe.com/xap/1.0/mm/|0|",
        "CASE resource_ref__lenient OK "
        "xmpMM|http://ns.adobe.com/xap/1.0/mm/|1|DerivedFrom",
    ),
    # No trailing <?xpacket?> end PI at all. Upstream strict mode mandates the
    # end PI (XpacketBadEnd); pypdfbox treats the end PI as optional (the
    # malformed-marker case bad_end_val IS now rejected — wave 1545 — but a
    # wholly absent PI is still tolerated). Lenient mode agrees on both sides.
    "no_end__strict": (
        "CASE no_end__strict EXC XpacketBadEnd",
        "CASE no_end__strict OK dc|http://purl.org/dc/elements/1.1/|1|title",
    ),
    # dc:title (declared Alt) presented as rdf:Seq. Both raise in strict mode;
    # upstream's array-flavour check raises FORMAT, pypdfbox's cardinality
    # check raises INVALID_TYPE. Lenient mode tolerates on both sides.
    "title_as_seq__strict": (
        "CASE title_as_seq__strict EXC Format",
        "CASE title_as_seq__strict EXC InvalidType",
    ),
    # dc:subject (declared Bag) presented as rdf:Alt. Same FORMAT vs
    # INVALID_TYPE token split; lenient tolerates on both sides.
    "subject_as_alt__strict": (
        "CASE subject_as_alt__strict EXC Format",
        "CASE subject_as_alt__strict EXC InvalidType",
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
        # token is the Java enum *constant* name (e.g. "Format"), mirrored as
        # the enum member's ``.value``. Emit ``.value`` so the token matches
        # the probe's ``getErrorType().name()``.
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
def test_xmp_parse_fuzz_wave1545_parity(tmp_path: Path) -> None:
    corpus = _build_corpus()
    input_file = tmp_path / "xmp_parse_fuzz_wave1545_corpus.tsv"
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
            # Validate BOTH sides of the pin so neither can drift silently.
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
