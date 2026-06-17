"""Live PDFBox differential parity for object-stream (/Type /ObjStm) INTERNAL
parsing — the header offset table and object-extraction performed by
:class:`pypdfbox.pdfparser.pdf_object_stream_parser.PDFObjectStreamParser`.

PDF 32000-1 §7.5.7 packs many indirect objects into a single compressed
container stream. The container body begins with ``/N`` integer pairs
``(objectNumber, offsetWithinBodyAfter/First)`` followed — starting at byte
``/First`` — by the concatenated object bodies. Two upstream quirks make the
parsing non-trivial:

* **Offsets are not guaranteed sorted.** The spec says the pairs *shall* be
  ascending by offset, but PDFBox does not trust that: ``privateReadObjectOffsets``
  builds a ``TreeMap`` keyed by offset so the sequential body parser walks
  objects in physical (offset) order regardless of the header's pair order
  (the in-source comment, and ``test_out_of_order_offsets`` below).
* **PDFBOX-4927 — duplicate object numbers.** A malformed ObjStm can list the
  same object number twice at different offsets. ``parseAllObjects`` collapses
  these by ``COSObjectKey`` and the later/stream-index-selected body wins;
  ``readObjectNumbers`` (a ``Long→Integer`` map) likewise keeps the last
  offset written for a repeated number (``test_duplicate_object_numbers``).

This probe isolates the body parsing from any surrounding xref/document
plumbing: the SAME raw (unfiltered) ObjStm body bytes plus the SAME ``/N`` and
``/First`` feed both libraries. ``ObjStmParseProbe`` drives upstream's
``readObjectNumbers()`` and ``parseAllObjects()`` directly.

Comparison is on CONTENT, not map iteration order: upstream returns plain
``HashMap`` instances for both ``readObjectNumbers()`` and the final
``parseAllObjects()`` result (the source explicitly documents the return as
unordered; the ``TreeMap`` is only an internal walk aid). So a faithful port
must reproduce the same ``{objectNumber: offset}`` table and the same
``{(number, generation): parsedValue}`` set — which is exactly what these
assertions pin.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSStream
from pypdfbox.pdfparser import PDFObjectStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# ----------------------------------------------------------------- body builders


def _body_in_order() -> tuple[bytes, int, int]:
    """Three objects, header pairs in ascending object-number AND offset order.

    obj 3 → ``/Foo``, obj 4 → ``42``, obj 5 → ``<< /Type /Demo /Tag (hi) >>``.
    """
    payloads = b"/Foo 42 << /Type /Demo /Tag (hi) >> "
    header = b"3 0 4 5 5 8 "
    return header + payloads, 3, len(header)


def _body_out_of_order() -> tuple[bytes, int, int]:
    """Same three objects, but the header lists them ``5 3 4`` while their
    bodies are laid out physically as ``/Foo`` (off 0), ``42`` (off 5),
    ``dict`` (off 8). Object-number order != offset order, so a parser that
    walks in header order rather than offset order would misalign body
    boundaries. Upstream sorts by offset (TreeMap); the result content must
    be identical to the in-order case.
    """
    payloads = b"/Foo 42 << /Type /Demo /Tag (hi) >> "
    # 5 -> offset 0 (/Foo), 3 -> offset 5 (42), 4 -> offset 8 (dict)
    header = b"5 0 3 5 4 8 "
    return header + payloads, 3, len(header)


def _body_duplicate_numbers() -> tuple[bytes, int, int]:
    """PDFBOX-4927: object number 3 appears twice (offsets 0 and 8); object 4
    once. ``/N`` counts 3 header entries but only 2 distinct object numbers.
    Upstream collapses on the key and the later body (``/NewVal``) wins.
    """
    payloads = b"/OldVal /NewVal 7 "
    header = b"3 0 3 8 4 16 "
    return header + payloads, 3, len(header)


def _body_first_padding() -> tuple[bytes, int, int]:
    """Header followed by extra whitespace before ``/First``. Real producers
    pad the gap between the offset table and the first body; the parser must
    skip to ``/First`` rather than assume the table is tight against object 0.
    """
    header = b"3 0\n4 5\n5 8\n"
    pad = b"   \n  "
    payloads = b"/Foo 42 << /Type /Demo /Tag (hi) >> "
    first = len(header) + len(pad)
    return header + pad + payloads, 3, first


_CASES: list[tuple[str, object]] = [
    ("in_order", _body_in_order),
    ("out_of_order_offsets", _body_out_of_order),
    ("duplicate_object_numbers", _body_duplicate_numbers),
    ("first_padding", _body_first_padding),
]


# ----------------------------------------------------------------- pypdfbox side


def _make_stream(body: bytes, n: int, first: int) -> COSStream:
    stream = COSStream()
    stream.set_item(COSName.N, COSInteger.get(n))
    stream.set_item(COSName.FIRST, COSInteger.get(first))
    out = stream.create_raw_output_stream()
    try:
        out.write(body)
    finally:
        out.close()
    return stream


def _value_summary(value: object) -> str:
    """Match the probe's ``jsonValue`` shape: ``"<type>|<tag>"`` for a dict,
    the name for a COSName, the string for a COSString, the int for a number.
    """
    from pypdfbox.cos import (
        COSDictionary,
        COSNumber,
        COSString,
    )
    from pypdfbox.cos import (
        COSName as _Name,
    )

    if isinstance(value, COSDictionary):
        type_obj = value.get_dictionary_object(COSName.TYPE)
        tag_obj = value.get_dictionary_object(COSName.get_pdf_name("Tag"))
        type_name = type_obj.get_name() if isinstance(type_obj, _Name) else ""
        tag_str = tag_obj.get_string() if isinstance(tag_obj, COSString) else ""
        return f"{type_name}|{tag_str}"
    if isinstance(value, _Name):
        return value.get_name()
    if isinstance(value, COSString):
        return value.get_string()
    if isinstance(value, COSNumber):
        return str(int(value.long_value()))
    return ""


def _py_numbers(body: bytes, n: int, first: int) -> dict[int, int]:
    parser = PDFObjectStreamParser(_make_stream(body, n, first), COSDocument())
    return dict(parser.read_object_numbers())


def _py_objects(body: bytes, n: int, first: int) -> dict[tuple[int, int], str]:
    parser = PDFObjectStreamParser(_make_stream(body, n, first), COSDocument())
    out: dict[tuple[int, int], str] = {}
    for key, value in parser.parse_all_objects().items():
        out[(key.get_number(), key.get_generation())] = _value_summary(value)
    return out


# ----------------------------------------------------------------- oracle parse


def _java_dump(body: bytes, n: int, first: int, tmp_path: Path) -> dict:
    bin_path = tmp_path / "objstm_body.bin"
    bin_path.write_bytes(body)
    raw = run_probe_text("ObjStmParseProbe", str(bin_path), str(n), str(first))
    return json.loads(raw)


def _java_numbers(dump: dict) -> dict[int, int]:
    return {int(num): int(off) for num, off in dump["numbers"]}


def _java_objects(dump: dict) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    for entry in dump["objects"]:
        key = (int(entry["num"]), int(entry["gen"]))
        value = entry["value"]
        out[key] = str(value)
    return out


# ----------------------------------------------------------------- tests


@requires_oracle
@pytest.mark.parametrize(
    ("label", "builder"), _CASES, ids=[c[0] for c in _CASES]
)
def test_obj_stream_header_table_matches_pdfbox(
    label: str, builder, tmp_path: Path
) -> None:
    """``readObjectNumbers()`` produces the identical ``{objectNumber: offset}``
    header table in pypdfbox and PDFBox for every body shape (in-order,
    out-of-order offsets, duplicate numbers, /First padding)."""
    body, n, first = builder()
    dump = _java_dump(body, n, first, tmp_path)
    assert _py_numbers(body, n, first) == _java_numbers(dump)


@requires_oracle
@pytest.mark.parametrize(
    ("label", "builder"), _CASES, ids=[c[0] for c in _CASES]
)
def test_obj_stream_parse_all_matches_pdfbox(
    label: str, builder, tmp_path: Path
) -> None:
    """``parseAllObjects()`` resolves the identical
    ``{(number, generation): value}`` set in pypdfbox and PDFBox.

    Compared on content (a dict equality), not iteration order: upstream
    returns an unordered ``HashMap`` for the final result, so reproducing the
    exact same key set with the exact same parsed values is the parity
    contract — including the offset-sorted body walk (out-of-order case) and
    the PDFBOX-4927 duplicate-number collapse.
    """
    body, n, first = builder()
    dump = _java_dump(body, n, first, tmp_path)
    assert _py_objects(body, n, first) == _java_objects(dump)
