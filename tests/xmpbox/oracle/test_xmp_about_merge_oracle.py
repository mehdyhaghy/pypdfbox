"""Live Apache xmpbox parity for the ``rdf:about`` merge corner.

A schema may be split across several ``rdf:Description`` blocks that share one
namespace. The XMP spec lets each block carry its own ``rdf:about``; when those
values *differ*, a parser must decide which one wins and whether the blocks
still fold into a single schema. This corner was previously un-probed.

The probe (``XmpAboutMergeProbe``) parses a hand-crafted packet whose two
Dublin Core ``rdf:Description`` blocks declare *different* ``rdf:about``
values (``uuid:AAA`` then ``uuid:BBB``) and emits a canonical projection of the
merged schema. pypdfbox parses the identical bytes and must agree:

  * both fold the two blocks into a *single* DC schema (``schema_count == 1``);
  * both keep the *first* ``rdf:about`` (``uuid:AAA``);
  * the union of properties (``format`` from the first block, ``creator`` from
    the second) survives the merge.

Confirmed at parity in wave 1499 (round 6) — no fix needed; this pins the
behaviour so a future parser change cannot silently diverge from xmpbox.
"""

from __future__ import annotations

import json

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from tests.oracle.harness import requires_oracle, run_probe_text

_PACKET = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
    ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
    '<rdf:Description rdf:about="uuid:AAA">'
    "<dc:format>application/pdf</dc:format>"
    "</rdf:Description>"
    '<rdf:Description rdf:about="uuid:BBB">'
    "<dc:creator><rdf:Seq><rdf:li>Alice</rdf:li></rdf:Seq></dc:creator>"
    "</rdf:Description>"
    "</rdf:RDF></x:xmpmeta>"
    '<?xpacket end="w"?>'
).encode("utf-8")


def _pypdfbox_dump(packet: bytes) -> dict:
    meta = DomXmpParser().parse(packet)
    root: dict = {"schema_count": len(meta.get_all_schemas())}
    dc = meta.get_dublin_core_schema()
    if dc is not None:
        root["about"] = dc.get_about_value()
        dc_map: dict = {}
        fmt = dc.get_format()
        if fmt is not None:
            dc_map["format"] = fmt
        creators = dc.get_creators()
        if creators:
            dc_map["creator"] = creators
        title = dc.get_title()
        if title is not None:
            dc_map["title"] = title
        root["dc"] = dc_map
    return root


@requires_oracle
def test_about_mismatch_merge_matches_xmpbox(tmp_path) -> None:
    packet_path = tmp_path / "about_mismatch.xmp"
    packet_path.write_bytes(_PACKET)

    java_dump = json.loads(run_probe_text("XmpAboutMergeProbe", str(packet_path)))
    py_dump = _pypdfbox_dump(_PACKET)

    assert py_dump == java_dump, (
        "rdf:about merge divergence:\n"
        f"  java: {json.dumps(java_dump, sort_keys=True, ensure_ascii=False)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True, ensure_ascii=False)}"
    )
