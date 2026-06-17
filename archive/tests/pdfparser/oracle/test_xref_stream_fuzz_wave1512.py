"""Live Apache PDFBox differential parse-leniency fuzz for the PDF 1.5+
cross-reference STREAM decoder ``PDFXrefStreamParser`` (parity wave 1512,
agent D).

Complements the existing well-formed xref-stream oracle suite
(``test_xref_w_fields_oracle`` / ``test_xref_index_subsections_oracle`` /
``test_xref_stream_trailer_oracle`` / ``test_hybrid_xref_oracle`` — all pinned
on VALID streams) and the wave-1503 file-structure mutation fuzz
(``test_mutation_fuzz_oracle`` — which mutates the PDF *container*, not the
xref-stream ``/W`` / ``/Index`` / ``/Size`` geometry against the decoded body
length). None of those exercise the MALFORMED subset this wave targets:

* ``/W`` arity: missing key, 2-element, 4-element, the PDFBOX-6037 sum>20 cap.
* ``/W`` widths: negative, all-zero, ``/W[0]==0`` (type defaults to 1).
* ``/Index``: missing (default ``[0 /Size]``), empty, odd length, a count
  that overruns the decoded body, a ``first`` object number offset, multiple
  subsections.
* entry types: free (type 0, never inserted into the table), in-use (type 1),
  compressed (type 2), unknown (type >= 3 — upstream still emits a non-type-0
  entry via the ``else`` branch).
* body truncation: a body shorter than ``sum(W) * entryCount`` (the
  ``read_next_value`` short-read + ``is_eof`` loop guard).

The Java oracle of record is ``oracle/probes/XrefStreamFuzzProbe.java``. Both
sides build the IDENTICAL ``COSStream`` (``/W`` / ``/Index`` / ``/Size`` dict
entries + the same raw body bytes), drive their respective
``PDFXrefStreamParser`` through an ``XrefTrailerResolver``, and emit the same
projection of the resolved table::

    CASE <name> EXC <ExcSimpleName>            (constructor or parse threw)
    CASE <name> OK <objNum>,<gen>,<streamIndex>,<offset>;...   (success)

Tokens are sorted ascending by (objNum, gen, streamIndex). ``OK -`` means zero
in-use entries. Because the resolver's table holds only in-use (type 1) and
compressed (type 2) entries — free (type 0) entries are never inserted on
either side — the projection is the exact surviving recovery set.

Exception *class names* differ between the two runtimes (Java
``IOException`` family vs pypdfbox ``PDFParseError`` / ``OSError``), so the
``EXC`` arm is compared on the THROW BOOLEAN only — a case that throws on one
side must throw on the other; the specific class name is not asserted. The
``OK`` arm is asserted verbatim (entry-for-entry). This mirrors the
established convention in the wave-1505 filter-decode fuzz, where decode-time
throws are compared on the ``ok`` boolean while successful output is compared
exactly.

Deterministic, seed-free corpus (hand-enumerated edge cases — no PRNG).
``@requires_oracle`` so the suite stays green without Java + the jar.
"""

from __future__ import annotations

import base64

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfparser.pdf_xref_stream_parser import PDFXrefStreamParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefTrailerResolver, XrefType
from tests.oracle.harness import requires_oracle, run_probe_text

_SIZE_KEY = COSName.get_pdf_name("Size")
_INDEX_KEY = COSName.get_pdf_name("Index")


def _be(value: int, width: int) -> bytes:
    """Big-endian ``width``-byte encoding of ``value`` (the on-the-wire form
    of one xref-stream field)."""
    return value.to_bytes(width, "big")


def _row(w: tuple[int, int, int], type_: int, f2: int, f3: int) -> bytes:
    """One xref-stream entry row for field widths ``w``."""
    out = b""
    if w[0]:
        out += _be(type_, w[0])
    if w[1]:
        out += _be(f2, w[1])
    if w[2]:
        out += _be(f3, w[2])
    return out


# --------------------------------------------------------------------------- #
# Corpus. Each entry: (name, W-or-None, Index-or-None, Size-or-None, body).
#   W=None     -> /W key absent
#   Index=None -> /Index key absent (parser defaults to [0 /Size])
#   Size=None  -> /Size key absent
# --------------------------------------------------------------------------- #
def _build_corpus() -> list[tuple[str, list[int] | None, list[int] | None, int | None, bytes]]:
    w = (1, 2, 1)
    # A canonical 3-entry body: free obj0, in-use obj1@10, compressed obj2.
    canon = _row(w, 0, 0, 0) + _row(w, 1, 10, 0) + _row(w, 1, 20, 0)
    compressed = _row(w, 2, 9, 3)  # obj in object-stream 9 at index 3

    cases: list[tuple[str, list[int] | None, list[int] | None, int | None, bytes]] = [
        # --- well-formed baselines (regression guards) ----------------------
        ("baseline_3", [1, 2, 1], None, 3, canon),
        ("baseline_compressed", [1, 2, 1], None, 4, canon + compressed),
        # --- /W arity -------------------------------------------------------
        ("w_missing", None, None, 3, canon),
        ("w_empty", [], None, 3, canon),
        ("w_two_elem", [1, 2], None, 3, canon),
        ("w_four_elem", [1, 2, 1, 1], None, 3, canon),
        ("w_one_elem", [4], None, 3, _be(1, 4) + _be(1, 4)),
        # --- /W widths ------------------------------------------------------
        ("w_negative", [1, -2, 1], None, 3, canon),
        ("w_all_zero", [0, 0, 0], None, 3, b""),
        ("w_sum_21", [1, 19, 1], None, 1, _be(1, 1) + _be(7, 19) + _be(0, 1)),
        ("w_sum_20_ok", [1, 18, 1], None, 1, _be(1, 1) + _be(7, 18) + _be(0, 1)),
        # /W[0]==0 -> type defaults to 1 (in-use) for every row.
        ("w_type0_absent", [0, 2, 1], None, 2, _be(10, 2) + _be(0, 1) + _be(20, 2) + _be(0, 1)),
        # /W[2]==0 -> generation/index field absent (defaults to 0).
        ("w_field3_absent", [1, 2, 0], None, 2, _be(1, 1) + _be(10, 2) + _be(1, 1) + _be(20, 2)),
        # --- /Index ---------------------------------------------------------
        ("index_default_size0", [1, 2, 1], None, 0, canon),
        ("index_empty", [1, 2, 1], [], 3, canon),
        ("index_odd_len", [1, 2, 1], [0, 3, 5], 3, canon),
        ("index_first_offset", [1, 2, 1], [5, 3], None, canon),
        ("index_two_subsections", [1, 2, 1], [0, 1, 7, 2], None, canon),
        ("index_count_overruns_body", [1, 2, 1], [0, 10], None, canon),
        ("index_zero_count", [1, 2, 1], [0, 0], None, b""),
        ("index_huge_count", [1, 2, 1], [0, 1000000], None, canon),
        # --- entry types ----------------------------------------------------
        ("type_free_only", [1, 2, 1], [0, 2], None, _row(w, 0, 0, 0) + _row(w, 0, 0, 0)),
        ("type_unknown_3", [1, 2, 1], [0, 2], None, _row(w, 3, 99, 7) + _row(w, 1, 10, 0)),
        ("type_unknown_255", [1, 2, 1], [0, 1], None, _row(w, 255, 42, 1)),
        ("type_compressed_only", [1, 2, 1], [0, 1], None, compressed),
        ("type_high_gen", [1, 2, 2], [0, 1], None, _be(1, 1) + _be(99, 2) + _be(65535, 2)),
        # --- body truncation ------------------------------------------------
        ("body_empty", [1, 2, 1], None, 3, b""),
        ("body_one_short", [1, 2, 1], None, 3, canon[:-1]),
        ("body_mid_row", [1, 2, 1], [0, 3], None, canon[: len(canon) // 2 + 1]),
        ("body_extra_tail", [1, 2, 1], [0, 2], None, canon + b"\x99\x99\x99\x99\x99"),
        ("body_one_byte", [1, 2, 1], [0, 5], None, b"\x01"),
        # --- combined corners ----------------------------------------------
        ("wide_offset_5", [1, 5, 1], [0, 1], None, _be(1, 1) + _be(0x1_0000_0000, 5) + _be(0, 1)),
        ("type2_index_first", [1, 2, 1], [10, 1], None, compressed),
    ]
    return cases


_CORPUS = _build_corpus()


def _spec(values: list[int] | None) -> str:
    if values is None:
        return "-"
    return ",".join(str(v) for v in values)


def _make_stream(
    w: list[int] | None, index: list[int] | None, size: int | None, body: bytes
) -> COSStream:
    stream = COSStream()
    if w is not None:
        arr = COSArray()
        for v in w:
            arr.add(COSInteger.get(v))
        stream.set_item(COSName.W, arr)
    if index is not None:
        arr = COSArray()
        for v in index:
            arr.add(COSInteger.get(v))
        stream.set_item(_INDEX_KEY, arr)
    if size is not None:
        stream.set_int(_SIZE_KEY, size)
    stream.set_data(body)
    return stream


def _py_line(
    name: str,
    w: list[int] | None,
    index: list[int] | None,
    size: int | None,
    body: bytes,
) -> str:
    """Reproduce the probe's ``CASE <name> ...`` grammar from pypdfbox."""
    try:
        stream = _make_stream(w, index, size, body)
        resolver = XrefTrailerResolver()
        resolver.next_xref_obj(0, XrefType.STREAM)
        parser = PDFXrefStreamParser(stream, None)
        parser.parse(resolver)
        table = resolver.get_xref_table()
    except Exception as exc:  # noqa: BLE001 - throw boolean is what we compare
        return f"CASE {name} EXC {type(exc).__name__}"
    if not table:
        return f"CASE {name} OK -"
    rows = []
    for key, entry in table.items():
        rows.append(
            (key.get_number(), key.get_generation(), key.get_stream_index(), entry.offset)
        )
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    tokens = sorted(f"{n},{g},{i},{o}" for (n, g, i, o) in rows)
    return f"CASE {name} OK " + ";".join(tokens)


def _corpus_file(tmp_path) -> str:
    lines = []
    for name, w, index, size, body in _CORPUS:
        lines.append(
            "\t".join(
                [
                    name,
                    _spec(w),
                    _spec(index),
                    "-" if size is None else str(size),
                    base64.b64encode(body).decode("ascii"),
                ]
            )
        )
    path = tmp_path / "xref_stream_fuzz_corpus.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


@requires_oracle
def test_xref_stream_fuzz_parity(tmp_path):
    corpus = _corpus_file(tmp_path)
    java_out = run_probe_text("XrefStreamFuzzProbe", corpus).strip().splitlines()
    java_by_name = {line.split(" ", 2)[1]: line for line in java_out}

    assert len(java_out) == len(_CORPUS), (
        f"probe emitted {len(java_out)} lines for {len(_CORPUS)} cases"
    )

    mismatches: list[str] = []
    for name, w, index, size, body in _CORPUS:
        java = java_by_name[name]
        py = _py_line(name, w, index, size, body)
        if java == py:
            continue
        java_kind = java.split(" ", 3)[2]  # EXC | OK
        py_kind = py.split(" ", 3)[2]
        # EXC arm: compare the throw boolean only (runtime exception class
        # names differ between Java and pypdfbox). OK arm: assert verbatim.
        if java_kind == "EXC" and py_kind == "EXC":
            continue
        mismatches.append(f"\n  case={name}\n    java={java}\n    py  ={py}")

    assert not mismatches, "xref-stream fuzz divergences:" + "".join(mismatches)
