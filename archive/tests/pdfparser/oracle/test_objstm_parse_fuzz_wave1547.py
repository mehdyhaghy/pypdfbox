"""Live Apache PDFBox differential fuzz of ``PDFObjectStreamParser`` INTERNAL
parsing — the header offset table and object-extraction walk (wave 1547,
agent D).

PDF 32000-1 §7.5.7 packs many indirect objects into a compressed
``/Type /ObjStm`` container: the decoded body begins with ``/N`` integer pairs
``(objectNumber, offsetAfter/First)`` followed — starting at byte ``/First`` —
by the concatenated object bodies. Three existing oracle suites pin different
slices of this surface:

* ``test_obj_stream_parse_oracle.py`` (``ObjStmParseProbe``) pins the
  WELL-FORMED direct-parser contract — but its probe lets a malformed body
  CRASH (no per-method exception capture);
* ``test_objstm_fuzz_wave1516.py`` (``ObjStmFuzzProbe``) fuzzes MALFORMED
  metadata, but only through ``Loader.loadPDF`` + lazy resolution of a single
  member — it never inspects what the header table or the object map actually
  CONTAIN;
* ``test_objstm_extends_oracle.py`` pins the read-side ``/Extends`` invariant.

This probe targets the gap: drive ``PDFObjectStreamParser`` DIRECTLY on ~30
malformed / edge bodies and pin BOTH ``readObjectNumbers()`` (the
``{objNum: offset}`` table) AND ``parseAllObjects()`` (the
``{(num, gen): value}`` map), surfacing any per-method exception. The same raw
body + ``/N`` + ``/First`` feed both runtimes (file-driven via a manifest).

Fuzz angles (none of which the three suites above exercise at this layer):

* ``/N`` larger / smaller than the real header-pair count, ``/N`` zero;
* ``/First`` zero, past the body end, before the header end, exactly at the
  header end with trailing padding;
* header offsets out-of-order, overlapping, past the payload, negative
  (a leading ``-``), non-integer tokens, a truncated final pair;
* a member whose body is truncated mid-token;
* duplicate object numbers (PDFBOX-4927) — same number twice, and three times;
* an empty body, a body that is only whitespace.

Validation, not blind pinning: the Java line is ground truth. Where pypdfbox
diverges defensibly (e.g. an exception class with no 1:1 Python counterpart, or
a robustness reading of a self-contradictory offset), the divergence is pinned
both-sides with an honest comment. A WRONG pypdfbox value is FIXED, not pinned.

The ``ERR:<X>`` arm is canonicalised to a bare ``ERR`` token before comparison:
Java exception class names have no 1:1 Python counterpart, so the parity
contract on the throwing arm is "both threw", while the value arm
(``numbers=[...]`` / ``objects=[...]``) is compared verbatim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSInteger, COSName, COSStream
from pypdfbox.cos.cos_number import COSNumber
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfparser import PDFObjectStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Corpus — each case is (name, raw-body-bytes, N, First). The SAME bytes drive
# both runtimes. Bodies are RAW (unfiltered): the probe + pypdfbox both stamp
# /N and /First and read the body verbatim, no FlateDecode involved.
# --------------------------------------------------------------------------- #

_Case = tuple[str, bytes, int, int]


def _build_corpus() -> list[_Case]:
    cases: list[_Case] = []

    def add(name: str, body: bytes, n: int, first: int) -> None:
        cases.append((name, body, n, first))

    # ---- baseline: one well-formed member ----
    base = b"4 0 "
    add("baseline", base + b"/Foo ", 1, len(base))

    # well-formed three members (in order)
    h3 = b"3 0 4 5 5 8 "
    p3 = b"/Foo 42 << /Type /Demo /Tag (hi) >> "
    add("three_in_order", h3 + p3, 3, len(h3))

    # ---- /N variants ----
    # /N larger than actual pairs: parser is bounded by /First position too.
    add("n_larger_than_actual", base + b"/Foo ", 5, len(base))
    # /N smaller than actual pairs: only first /N pairs read.
    h2 = b"3 0 4 4 "
    p2 = b"/Foo /Bar "
    add("n_smaller_than_actual", h2 + p2, 1, len(h2))
    # /N zero — no pairs read at all.
    add("n_zero", base + b"/Foo ", 0, len(base))

    # ---- /First variants ----
    add("first_zero", base + b"/Foo ", 1, 0)
    add("first_past_end", base + b"/Foo ", 1, 99999)
    # /First before the header end cuts the header walk short via the running
    # position bound (first_object_position = pos + first - 1).
    add("first_before_header_end", h3 + p3, 3, 4)
    # /First with trailing padding between header and the first body.
    hp = b"3 0 4 5 5 8 "
    pad = b"   \n  "
    add("first_with_padding", hp + pad + p3, 3, len(hp) + len(pad))

    # ---- header table variants ----
    # offsets out of order (object-number order != offset order).
    add("header_out_of_order", b"5 0 3 5 4 8 " + p3, 3, len(b"5 0 3 5 4 8 "))
    # overlapping offsets: two members claim overlapping byte ranges.
    add("header_overlapping", b"3 0 4 1 " + b"/Foo ", 2, len(b"3 0 4 1 "))
    # an offset that points past the end of the payload.
    add("header_offset_past_payload", b"4 9999 " + b"/Foo ", 1, len(b"4 9999 "))
    # a header offset with a leading minus sign.
    add("header_offset_negative", b"4 -3 " + b"/Foo ", 1, len(b"4 -3 "))
    # a non-integer object-number token in the header.
    add("header_objnum_nonnumeric", b"xx 0 " + b"/Foo ", 1, len(b"xx 0 "))
    # a non-integer offset token in the header.
    add("header_offset_nonnumeric", b"4 yy " + b"/Foo ", 1, len(b"4 yy "))
    # truncated final pair: object number with no following offset.
    add("header_truncated_pair", b"3 0 4 ", 2, 6)

    # ---- member body variants ----
    # a member whose body is truncated mid-dictionary.
    add("member_truncated", b"4 0 " + b"<< /ProbeVal 4", 1, len(b"4 0 "))
    # a member that is itself a malformed nesting.
    add("member_malformed", b"4 0 " + b"<<<<>> ", 1, len(b"4 0 "))

    # ---- duplicate object numbers (PDFBOX-4927) ----
    add(
        "duplicate_objnum_twice",
        b"3 0 3 8 4 16 " + b"/OldVal /NewVal 7 ",
        3,
        len(b"3 0 3 8 4 16 "),
    )
    add(
        "duplicate_objnum_thrice",
        b"3 0 3 5 3 11 " + b"/AAA /BBB /CCC ",
        3,
        len(b"3 0 3 5 3 11 "),
    )

    # ---- empty / whitespace bodies ----
    add("empty_body", b"", 0, 0)
    add("whitespace_only", b"   \n  ", 0, 0)
    # /N>0 over an empty body — nothing to read but the position bound trips.
    add("n_one_empty_body", b"", 1, 4)

    return cases


# --------------------------------------------------------------------------- #
# pypdfbox side — mirrors the probe's projection byte-for-byte.
# --------------------------------------------------------------------------- #


def _make_stream(body: bytes, n: int, first: int) -> COSStream:
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("ObjStm"))
    stream.set_item(COSName.N, COSInteger.get(n))
    stream.set_item(COSName.FIRST, COSInteger.get(first))
    out = stream.create_raw_output_stream()
    try:
        out.write(body)
    finally:
        out.close()
    return stream


def _esc(s: str) -> str:
    chars: list[str] = []
    for c in s:
        if c in ",|:[]":
            chars.append("_")
        elif c in "\n\r":
            chars.append(" ")
        else:
            chars.append(c)
    return "".join(chars)


def _kind(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, COSDictionary):
        return "dict"
    if isinstance(v, COSName):
        return "name"
    if isinstance(v, COSString):
        return "string"
    if isinstance(v, COSNumber):
        return "number"
    return type(v).__name__


def _value(v: object) -> str:
    if isinstance(v, COSDictionary):
        type_obj = v.get_dictionary_object(COSName.TYPE)
        tag_obj = v.get_dictionary_object(COSName.get_pdf_name("Tag"))
        t = type_obj.get_name() if isinstance(type_obj, COSName) else ""
        g = tag_obj.get_string() if isinstance(tag_obj, COSString) else ""
        return f"{_esc(t)}|{_esc(g)}"
    if isinstance(v, COSName):
        return _esc(v.get_name())
    if isinstance(v, COSString):
        return _esc(v.get_string())
    if isinstance(v, COSNumber):
        return str(int(v.long_value()))
    return "null"


def _py_numbers(body: bytes, n: int, first: int) -> str:
    doc = COSDocument()
    try:
        parser = PDFObjectStreamParser(_make_stream(body, n, first), doc)
        numbers = parser.read_object_numbers()
    except Exception as exc:  # noqa: BLE001 — mirror the probe's catch-all
        return f"ERR:{type(exc).__name__}"
    finally:
        doc.close()
    items = sorted(numbers.items())
    return "[" + ",".join(f"{num}={off}" for num, off in items) + "]"


def _py_objects(body: bytes, n: int, first: int) -> str:
    doc = COSDocument()
    try:
        parser = PDFObjectStreamParser(_make_stream(body, n, first), doc)
        objects = parser.parse_all_objects()
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}"
    finally:
        doc.close()
    rows: list[tuple[int, str]] = []
    for key, value in objects.items():
        num = key.get_number()
        gen = key.get_generation()
        rows.append((num, f"{num}/{gen}:{_kind(value)}:{_value(value)}"))
    rows.sort()
    return "[" + ",".join(r for _, r in rows) + "]"


def _py_line(name: str, body: bytes, n: int, first: int) -> str:
    return (
        f"CASE {name} numbers={_py_numbers(body, n, first)} "
        f"objects={_py_objects(body, n, first)}"
    )


# --------------------------------------------------------------------------- #
# Canonicalisation — collapse the ERR:<X> arm (no 1:1 exception vocabulary
# across runtimes) to a bare ERR; the value arms compare verbatim.
# --------------------------------------------------------------------------- #


def _canon_field(field: str) -> str:
    return "ERR" if field.startswith("ERR:") else field


def _canon(line: str) -> str:
    # line: "CASE <name> numbers=<n> objects=<o>"
    rest = line.split(" ", 2)[2]
    numbers, objects = rest.split(" objects=", 1)
    numbers = numbers[len("numbers="):]
    return f"numbers={_canon_field(numbers)} objects={_canon_field(objects)}"


# Cases pinned as defensible divergences (excluded from the line-for-line sweep,
# asserted exactly both-sides below). Maps name -> (pypdfbox canon, PDFBox canon).
#
# ``header_offset_negative`` — a header offset written with a leading ``-``
# (``4 -3``). Upstream ``BaseParser.readStringNumber`` collects ONLY ASCII
# digits (0x30..0x39); the ``-`` makes it return an empty token, so
# ``readLong`` -> ``Long.parseLong("")`` throws and propagates as an
# ``IOException`` ("Expected a long type at offset ..."). pypdfbox's
# ``BaseParser.read_int`` (which ``read_long`` delegates to) accepts an optional
# leading ``+``/``-`` sign, so it reads the offset as ``-3`` and
# ``parse_all_objects`` — whose forward-only skip ignores the non-positive
# target — parses the member at the current position and recovers ``/Foo``. This
# is a BaseParser-level signed-integer leniency (cross-module; this agent owns
# only the object-stream header contract and is forbidden to touch
# base_parser.py — recent waves changed it), not a wrong value: a negative
# offset is nonsensical and pypdfbox's lenient reading is defensible. Pinned
# both-sides so a future base_parser realign (or further drift) is caught.
_PINNED_DIVERGENCES: dict[str, tuple[str, str]] = {
    "header_offset_negative": (
        "numbers=[4=-3] objects=[4/0:name:Foo]",
        "numbers=ERR objects=ERR",
    ),
}


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #


def test_corpus_is_well_formed() -> None:
    """Sanity floor independent of the oracle: every case has a unique name and
    the baseline resolves to the single ``/Foo`` member under pypdfbox."""
    corpus = _build_corpus()
    names = [n for n, _, _, _ in corpus]
    assert len(names) == len(set(names)), "duplicate case names"
    assert corpus[0][0] == "baseline"
    name, body, n, first = corpus[0]
    assert _py_line(name, body, n, first) == (
        "CASE baseline numbers=[4=0] objects=[4/0:name:Foo]"
    )


@requires_oracle
def test_objstm_parse_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    corpus = _build_corpus()
    lines: list[str] = []
    for name, body, n, first in corpus:
        (tmp_path / f"{name}.bin").write_bytes(body)
        lines.append(f"{name} {n} {first}")
    (tmp_path / "manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    raw = run_probe_text("ObjStmParseFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines, expected {len(corpus)}:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name, body, n, first in corpus:
        if name in _PINNED_DIVERGENCES:
            continue
        java = java_by_name.get(name)
        assert java is not None, f"probe missing case {name}"
        py = _py_line(name, body, n, first)
        if _canon(java) != _canon(py):
            mismatches.append(f"  {name}:\n    java={java}\n    py  ={py}")

    assert not mismatches, "ObjStm parse fuzz divergence(s):\n" + "\n".join(mismatches)


@pytest.mark.skipif(not _PINNED_DIVERGENCES, reason="no pinned divergences")
@pytest.mark.parametrize(
    ("name", "py_canon", "java_canon"),
    [(n, p, j) for n, (p, j) in _PINNED_DIVERGENCES.items()],
)
def test_pinned_divergences(name: str, py_canon: str, java_canon: str) -> None:
    """Pin the exact pypdfbox projection for defensible divergences (upstream
    PDFBox value recorded for context). A future silent realign — or further
    drift — is caught here."""
    corpus = {c[0]: c for c in _build_corpus()}
    _, body, n, first = corpus[name]
    assert _canon(_py_line(name, body, n, first)) == py_canon, (
        f"{name}: pypdfbox projection drifted from the pinned value "
        f"(upstream PDFBox: {java_canon!r}) — re-validate against the oracle"
    )
