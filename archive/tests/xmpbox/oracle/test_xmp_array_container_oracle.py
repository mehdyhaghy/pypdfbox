"""Live Apache xmpbox differential parity for RDF array container semantics.

Where ``test_xmp_schema_oracle.py`` compares the *flattened scalar* values
each parser reads from a packet (``dc.title`` = the x-default string,
``dc.creators`` = a joined list), this file reaches one level deeper and
compares the *typed container* each parser builds for the Dublin Core array
properties: the RDF container kind (``Seq`` vs ``Bag`` vs ``Alt``) returned by
``ArrayProperty.get_array_type()``, the *ordered* item payload, and — for the
lang-alt properties — the per-``rdf:li`` ``xml:lang`` qualifier paired with its
value in document order.

The Java side is the ``XmpArrayContainerProbe`` probe driving Apache xmpbox
3.0.7's ``DomXmpParser``; the Python side parses the identical packet bytes with
pypdfbox's ``DomXmpParser`` and emits the same canonical JSON shape:

  * plain arrays  -> ``{"type": "Seq"|"Bag", "items": [...]}``
  * lang-alt      -> ``{"type": "Alt", "langs": [["lang", "value"], ...]}``

Absent properties are omitted on both sides, so the key set is itself part of
the assertion. The cases deliberately exercise:

  * a multi-item ``dc:creator`` Seq (order is load-bearing — a Seq parsed as a
    Bag, or reordered, would diverge);
  * a multi-item ``dc:subject`` Bag and ``dc:contributor`` Bag (the parser must
    classify these as Bag, not Seq);
  * a ``dc:date`` Seq;
  * lang-alt ``dc:title`` / ``dc:description`` / ``dc:rights`` where the source
    lists the languages with ``x-default`` NOT first — both parsers must apply
    the spec's "x-default sorts first" reorganisation identically, and preserve
    every other language in source order;
  * a single-language lang-alt with no explicit ``xml:lang`` (defaults to
    ``x-default``).
"""

from __future__ import annotations

import json

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from pypdfbox.xmpbox.type.text_type import TextType
from tests.oracle.harness import requires_oracle, run_probe_text

LANG_ATTR_NAME = "xml:lang"
X_DEFAULT = "x-default"

# --- fixed XMP packets ---------------------------------------------------

_PACKET_HEAD = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/">'
)
_PACKET_TAIL = "</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"


def _packet(body: str) -> bytes:
    return (_PACKET_HEAD + body + _PACKET_TAIL).encode("utf-8")


# Multi-item Seq + Bag mix: creator (Seq, ordered), subject (Bag),
# contributor (Bag), date (Seq).
_BODY_PLAIN_ARRAYS = (
    "<dc:creator><rdf:Seq>"
    "<rdf:li>Zoe Last</rdf:li>"
    "<rdf:li>Alice First</rdf:li>"
    "<rdf:li>Bob Middle</rdf:li>"
    "</rdf:Seq></dc:creator>"
    "<dc:subject><rdf:Bag>"
    "<rdf:li>gamma</rdf:li>"
    "<rdf:li>alpha</rdf:li>"
    "<rdf:li>beta</rdf:li>"
    "</rdf:Bag></dc:subject>"
    "<dc:contributor><rdf:Bag>"
    "<rdf:li>Helper One</rdf:li>"
    "<rdf:li>Helper Two</rdf:li>"
    "</rdf:Bag></dc:contributor>"
    "<dc:date><rdf:Seq>"
    "<rdf:li>2024-06-03T12:00:00Z</rdf:li>"
    "<rdf:li>2024-06-01T10:30:00Z</rdf:li>"
    "</rdf:Seq></dc:date>"
)

# Lang-alt where x-default is NOT first in source order — exercises the
# "x-default sorts first" reorganisation that both parsers must apply.
_BODY_LANG_ALT_REORDER = (
    "<dc:title><rdf:Alt>"
    '<rdf:li xml:lang="en">Hello</rdf:li>'
    '<rdf:li xml:lang="fr">Bonjour</rdf:li>'
    '<rdf:li xml:lang="x-default">Hello</rdf:li>'
    '<rdf:li xml:lang="ja">こんにちは</rdf:li>'
    "</rdf:Alt></dc:title>"
    "<dc:description><rdf:Alt>"
    '<rdf:li xml:lang="de">Beschreibung</rdf:li>'
    '<rdf:li xml:lang="x-default">Description</rdf:li>'
    "</rdf:Alt></dc:description>"
    "<dc:rights><rdf:Alt>"
    '<rdf:li xml:lang="x-default">All rights reserved.</rdf:li>'
    "</rdf:Alt></dc:rights>"
)

_CASES: list[tuple[str, bytes]] = [
    ("plain_arrays", _packet(_BODY_PLAIN_ARRAYS)),
    ("lang_alt_reorder", _packet(_BODY_LANG_ALT_REORDER)),
    ("combined", _packet(_BODY_PLAIN_ARRAYS + _BODY_LANG_ALT_REORDER)),
]


def _lang_pairs(arr) -> list[list[str]]:
    """``[[lang, value], ...]`` in document order from a parsed lang-alt array,
    mirroring the Java probe's per-``rdf:li`` walk."""
    pairs: list[list[str]] = []
    for child in arr.get_all_properties():
        if not isinstance(child, TextType):
            continue
        attr = child.get_attribute(LANG_ATTR_NAME)
        lang = attr.get_value() if attr is not None else X_DEFAULT
        pairs.append([lang, child.get_string_value()])
    return pairs


def _pypdfbox_dump(packet: bytes) -> dict:
    """Parse with pypdfbox and emit the JSON shape the Java probe produces."""
    meta = DomXmpParser().parse(packet)
    root: dict = {}
    dc = meta.get_dublin_core_schema()
    if dc is None:
        return root

    for key, getter in (
        ("creator", dc.get_creators_property),
        ("subject", dc.get_subjects_property),
        ("contributor", dc.get_contributors_property),
        ("publisher", dc.get_publishers_property),
        ("language", dc.get_languages_property),
        ("relation", dc.get_relations_property),
        ("date", dc.get_dates_property),
    ):
        arr = getter()
        if arr is None:
            continue
        root[key] = {
            "type": arr.get_array_type().value,
            "items": list(arr.get_elements_as_string()),
        }

    for key, getter in (
        ("title", dc.get_title_property),
        ("description", dc.get_description_property),
        ("rights", dc.get_rights_property),
    ):
        arr = getter()
        if arr is None:
            continue
        root[key] = {
            "type": arr.get_array_type().value,
            "langs": _lang_pairs(arr),
        }

    return root


@requires_oracle
@pytest.mark.parametrize(
    ("case_name", "packet"),
    _CASES,
    ids=[name for name, _ in _CASES],
)
def test_xmp_array_container_matches_xmpbox(case_name: str, packet: bytes, tmp_path) -> None:
    packet_path = tmp_path / f"{case_name}.xmp"
    packet_path.write_bytes(packet)

    java_dump = json.loads(run_probe_text("XmpArrayContainerProbe", str(packet_path)))
    py_dump = _pypdfbox_dump(packet)

    assert py_dump == java_dump, (
        f"array-container divergence for {case_name}:\n"
        f"  java: {json.dumps(java_dump, sort_keys=True, ensure_ascii=False)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True, ensure_ascii=False)}"
    )
