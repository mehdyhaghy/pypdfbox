"""Live Apache PDFBox differential parse-leniency fuzz for the PDF 1.5+
cross-reference STREAM read path AS DRIVEN THROUGH THE WHOLE-FILE LOADER, plus
the xref-stream ``/Prev`` chain walk and the brute-force rebuild that fires when
the stream xref is unusable (parity wave 1543, agent A).

Complements three earlier xref fuzz waves that left this surface uncovered:

* ``test_xref_stream_fuzz_wave1512`` drives ``PDFXrefStreamParser`` (the stream
  DECODER) in isolation against a malformed ``/W`` // ``/Index`` // ``/Size``
  geometry — never through the loader, so ``startxref`` resolution, the
  ``/Prev`` walk and the rebuild are not exercised.
* ``test_xref_table_fuzz_wave1516`` / ``test_trailer_rebuild_fuzz_wave1517``
  drive WHOLE tiny PDFs through the loader, but every case they build uses the
  CLASSIC ``xref`` keyword table — none builds a PDF whose cross-reference is a
  ``/Type /XRef`` STREAM.

This wave hand-builds ~30 tiny WHOLE PDFs whose cross-reference is a
``/Type /XRef`` stream with deliberately malformed geometry (``/W`` arity /
negative / sum>20 / type-column-absent; ``/Index`` odd / empty / non-integer /
overrunning / negative-first; ``/Size`` too-small / too-large / missing / zero;
truncated body), a broken ``/Prev`` chain between two xref STREAMS (cyclic /
dangling / negative / valid incremental), a missing or dangling trailer
``/Root``, ``startxref`` recovery, and a missing ``/Type /XRef`` tag. It drives
the whole-file parse, the ``startxref``->stream resolution, the ``/Prev`` walk
and (when those fail) the rebuild end-to-end.

The Java oracle of record is ``oracle/probes/XrefRecoveryFuzzProbe.java``. Both
sides read the IDENTICAL hand-crafted PDF bytes on disk (one ``<case>.pdf`` per
case plus a ``manifest.txt``) and the probe loads each with the empty password.

Output grammar (one line per case)::

    CASE <name> loaded=<1|ERR:<ExcSimpleName>> pages=<n|?> root=<present|absent|?>
         nobj=<count|?> enc=<0|1|?>

``loaded=ERR:<X>`` means the load threw exception class X (then the other fields
are ``?``). On success ``loaded=1``; ``pages`` is ``getNumberOfPages``, ``root``
is whether the catalog resolves, ``nobj`` is the count of resolved object keys
in the COS xref table, ``enc`` is whether the document reports itself encrypted.

Validation, not blind pinning: the Java line is ground truth. The ``ERR`` arm is
compared on the THROW BOOLEAN only (Java's ``IOException`` family vs pypdfbox's
``PDFParseError`` // ``OSError`` are not the same class name); the success-arm
fields are asserted verbatim. Residual divergences are pinned both-sides in
``_PINNED_DIVERGENCES`` with a reason and a matching CHANGES.md row (wave 1543).

KEY DIRECTION OF DIVERGENCE (honest note): on a LOCATED-but-malformed xref
STREAM, PDFBox 3.0.7 is the MORE LENIENT party — its ``checkXRefStreamOffsets``
consistency check fails and it brute-force rebuilds, opening the document.
pypdfbox deliberately propagates the structural error from the located-xref
stream path (the documented "located-but-malformed xref STREAM is NOT recovered
here" contract in ``PDFParser.parse``), so it throws where PDFBox recovers.
That is a documented loader-STRICTNESS divergence, not a wrong VALUE: pypdfbox
never fabricates a bad page count — it either opens with an internally
consistent (possibly smaller) object set or refuses the file. Those cases are
pinned on the pypdfbox side below.

``@requires_oracle`` so the suite stays green without Java + the jar.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Raw-PDF construction. The cross-reference is always a /Type /XRef STREAM with
# an UNCOMPRESSED (no /Filter) body, so the /W field bytes are laid out exactly.
# --------------------------------------------------------------------------- #

_HEADER = b"%PDF-1.5\n"
_CAT = b"<< /Type /Catalog /Pages 2 0 R >>"
_PAGES = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
_PAGE = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"
_STD = ((1, _CAT), (2, _PAGES), (3, _PAGE))


def _lay_body(objs=_STD, header: bytes = _HEADER) -> tuple[bytearray, dict[int, int]]:
    body = bytearray(header)
    off: dict[int, int] = {}
    for num, content in objs:
        off[num] = len(body)
        body += b"%d 0 obj\n" % num + content + b"\nendobj\n"
    return body, off


def _entry(type_: int, f2: int, f3: int, w: tuple[int, int, int] = (1, 4, 2)) -> bytes:
    parts = []
    for val, width in zip((type_, f2, f3), w, strict=True):
        parts.append(val.to_bytes(width, "big"))
    return b"".join(parts)


def _std_rows(off: dict[int, int], xref_off: int) -> bytes:
    """Five-entry body (objs 0..4) for the standard 3-object body + self."""
    rows = bytearray()
    rows += _entry(0, 0, 65535)  # obj0 free head
    rows += _entry(1, off[1], 0)
    rows += _entry(1, off[2], 0)
    rows += _entry(1, off[3], 0)
    rows += _entry(1, xref_off, 0)  # obj4 = the xref stream itself
    return bytes(rows)


def _assemble(
    dict_body: bytes,
    rows: bytes,
    body: bytearray,
    xref_off: int,
    startxref: int | None = None,
    eof: bool = True,
) -> bytes:
    out = bytearray(body)
    out += b"4 0 obj\n" + dict_body + b"\nstream\n" + rows + b"\nendstream\nendobj\n"
    out += b"startxref\n%d\n" % (xref_off if startxref is None else startxref)
    if eof:
        out += b"%%EOF"
    return bytes(out)


def _good(
    w_str: bytes | None = b"[1 4 2]",
    size: int | None = 5,
    root: bytes = b"/Root 1 0 R",
    index: bytes | None = None,
    prev: int | None = None,
) -> bytes:
    body, off = _lay_body()
    xref_off = len(body)
    rows = _std_rows(off, xref_off)
    d = b"<< /Type /XRef"
    if size is not None:
        d += b" /Size %d" % size
    if root:
        d += b" " + root
    if w_str is not None:
        d += b" /W %s" % w_str
    if index is not None:
        d += b" /Index %s" % index
    if prev is not None:
        d += b" /Prev %d" % prev
    d += b" /Length %d >>" % len(rows)
    return _assemble(d, rows, body, xref_off)


# --------------------------------------------------------------------------- #
# Corpus.
# --------------------------------------------------------------------------- #


def _build_corpus() -> dict[str, bytes]:
    c: dict[str, bytes] = {}

    # --- baseline (regression guard) ---
    c["baseline"] = _good()

    # --- /W array geometry ---
    c["w_two_elem"] = _good(w_str=b"[4 2]")  # arity 2 (PDFBox pads, pypdfbox rejects)
    c["w_four_elem"] = _good(w_str=b"[1 4 2 1]")  # arity 4
    c["w_negative"] = _good(w_str=b"[1 -4 2]")
    c["w_sum_over_20"] = _good(w_str=b"[1 20 2]")  # PDFBOX-6037 cap
    c["w_zero_entry"] = _good(w_str=b"[0 0 0]")
    c["w_missing"] = _good(w_str=None)
    c["w_type_col_absent"] = _build_w_type_col_absent()

    # --- /Index ---
    c["index_odd"] = _good(index=b"[0 5 0]")
    c["index_empty"] = _good(index=b"[]")
    c["index_nonint"] = _good(index=b"[0 5.0]")
    c["index_overrun"] = _good(index=b"[0 9]")
    c["index_subsections"] = _build_index_subsections()
    c["index_negative_first"] = _good(index=b"[-1 5]")

    # --- /Size ---
    c["size_too_small"] = _good(size=2)
    c["size_too_large"] = _good(size=99)
    c["size_missing"] = _good(size=None)
    c["size_zero"] = _good(size=0)

    # --- truncated body forcing rebuild ---
    c["body_truncated"] = _build_body_truncated()
    c["body_one_byte"] = _build_body_short(1)

    # --- /Root ---
    c["root_missing"] = _good(root=b"")
    c["root_dangling"] = _good(root=b"/Root 9 0 R")

    # --- /Prev chain across two xref STREAMS ---
    c["prev_valid"] = _build_prev_valid()
    c["prev_dangling"] = _good(prev=999999)
    c["prev_cyclic"] = _good(prev=0)  # points at the header, not a stream section
    c["prev_negative"] = _good(prev=-5)

    # --- startxref ---
    c["startxref_past_eof"] = _build_startxref(999999)
    c["startxref_zero"] = _build_startxref(0)
    c["startxref_mid_obj"] = _build_startxref_mid()

    # --- missing /Type /XRef tag ---
    c["type_missing"] = _build_type_missing()

    return c


def _build_w_type_col_absent() -> bytes:
    """/W [0 4 2] — the type column is absent, so every row defaults to type 1
    (in-use). Even obj0's row (offset 0) becomes an in-use entry."""
    body, off = _lay_body()
    xref_off = len(body)
    w = (0, 4, 2)
    rows = bytearray()
    rows += _entry(0, 0, 65535, w)
    rows += _entry(0, off[1], 0, w)
    rows += _entry(0, off[2], 0, w)
    rows += _entry(0, off[3], 0, w)
    rows += _entry(0, xref_off, 0, w)
    d = b"<< /Type /XRef /Size 5 /Root 1 0 R /W [0 4 2] /Length %d >>" % len(rows)
    return _assemble(d, bytes(rows), body, xref_off)


def _build_index_subsections() -> bytes:
    body, off = _lay_body()
    xref_off = len(body)
    rows = _std_rows(off, xref_off)
    d = (
        b"<< /Type /XRef /Size 5 /Root 1 0 R /W [1 4 2] "
        b"/Index [0 1 1 1 2 3] /Length %d >>" % len(rows)
    )
    return _assemble(d, rows, body, xref_off)


def _build_body_truncated() -> bytes:
    body, off = _lay_body()
    xref_off = len(body)
    rows = _std_rows(off, xref_off)
    rows = rows[: len(rows) // 2]
    d = b"<< /Type /XRef /Size 5 /Root 1 0 R /W [1 4 2] /Length %d >>" % len(rows)
    return _assemble(d, rows, body, xref_off)


def _build_body_short(n: int) -> bytes:
    body, off = _lay_body()
    xref_off = len(body)
    rows = _std_rows(off, xref_off)[:n]
    d = b"<< /Type /XRef /Size 5 /Root 1 0 R /W [1 4 2] /Length %d >>" % len(rows)
    return _assemble(d, rows, body, xref_off)


def _build_prev_valid() -> bytes:
    """Two cross-reference STREAMS chained via /Prev (an incremental update)."""
    body, off = _lay_body(objs=((1, _CAT), (2, _PAGES)))
    xref1_off = len(body)
    w = (1, 4, 2)
    rows1 = bytearray()
    rows1 += _entry(0, 0, 65535, w)
    rows1 += _entry(1, off[1], 0, w)
    rows1 += _entry(1, off[2], 0, w)
    rows1 += _entry(0, 0, 0, w)  # obj3 free in rev1
    rows1 += _entry(1, xref1_off, 0, w)
    d1 = b"<< /Type /XRef /Size 5 /Root 1 0 R /W [1 4 2] /Length %d >>" % len(rows1)
    body += b"4 0 obj\n" + d1 + b"\nstream\n" + bytes(rows1) + b"\nendstream\nendobj\n"
    body += b"startxref\n%d\n%%EOF\n" % xref1_off
    obj3_off = len(body)
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    xref2_off = len(body)
    rows2 = bytearray()
    rows2 += _entry(1, obj3_off, 0, w)  # obj3 now in-use (Index [3 1])
    rows2 += _entry(1, xref2_off, 0, w)  # obj5 self (Index [5 1])
    d2 = (
        b"<< /Type /XRef /Size 6 /Root 1 0 R /W [1 4 2] /Index [3 1 5 1] "
        b"/Prev %d /Length %d >>" % (xref1_off, len(rows2))
    )
    body += b"5 0 obj\n" + d2 + b"\nstream\n" + bytes(rows2) + b"\nendstream\nendobj\n"
    body += b"startxref\n%d\n%%EOF" % xref2_off
    return bytes(body)


def _build_startxref(value: int) -> bytes:
    body, off = _lay_body()
    xref_off = len(body)
    rows = _std_rows(off, xref_off)
    d = b"<< /Type /XRef /Size 5 /Root 1 0 R /W [1 4 2] /Length %d >>" % len(rows)
    return _assemble(d, rows, body, xref_off, startxref=value)


def _build_startxref_mid() -> bytes:
    body, off = _lay_body()
    xref_off = len(body)
    rows = _std_rows(off, xref_off)
    d = b"<< /Type /XRef /Size 5 /Root 1 0 R /W [1 4 2] /Length %d >>" % len(rows)
    return _assemble(d, rows, body, xref_off, startxref=off[2])


def _build_type_missing() -> bytes:
    body, off = _lay_body()
    xref_off = len(body)
    rows = _std_rows(off, xref_off)
    d = b"<< /Size 5 /Root 1 0 R /W [1 4 2] /Length %d >>" % len(rows)
    return _assemble(d, rows, body, xref_off)


_CORPUS = _build_corpus()


# --------------------------------------------------------------------------- #
# pypdfbox-side projection (mirrors the probe's grammar exactly).
# --------------------------------------------------------------------------- #


def _py_line(name: str, pdf: Path) -> str:
    doc = None
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as exc:  # noqa: BLE001 - throw boolean is what we compare
        return f"CASE {name} loaded=ERR:{type(exc).__name__} pages=? root=? nobj=? enc=?"
    try:
        try:
            pages = str(doc.get_number_of_pages())
        except Exception:  # noqa: BLE001 - mirror probe's '?' on throw
            pages = "?"
        try:
            root = "present" if doc.get_document_catalog() is not None else "absent"
        except Exception:  # noqa: BLE001 - mirror probe's '?' on throw
            root = "?"
        try:
            nobj = str(len(doc._document.get_xref_table()))  # noqa: SLF001
        except Exception:  # noqa: BLE001 - mirror probe's '?' on throw
            nobj = "?"
        try:
            enc = "1" if doc.is_encrypted() else "0"
        except Exception:  # noqa: BLE001 - mirror probe's '?' on throw
            enc = "?"
        return f"CASE {name} loaded=1 pages={pages} root={root} nobj={nobj} enc={enc}"
    finally:
        doc.close()


def _kind(line: str) -> str:
    body = line.split(" ", 2)[2]
    return "ERR" if body.startswith("loaded=ERR") else "OK"


# Defensible divergences, pinned both-sides. Each entry maps a case name to the
# EXACT pypdfbox line tail (everything after "CASE <name> ") that pypdfbox is
# asserted to produce, with a justification. The Java line is in the comment.
#
# Two divergence FAMILIES live here:
#
# (A) LOADER-STRICTNESS on a located-but-malformed xref STREAM. PDFBox 3.0.7
#     runs checkXRefStreamOffsets after decoding; when it fails it brute-force
#     rebuilds and OPENS the file. pypdfbox follows its documented "located-but-
#     malformed xref STREAM is NOT recovered here" contract (PDFParser.parse)
#     and propagates the structural error. So pypdfbox THROWS where PDFBox
#     recovers. This is a strictness divergence, not a wrong value — pypdfbox
#     never fabricates a bad page count.
#
# (B) RECOVERY-COMPLETENESS nuance in WHICH objects land in the PUBLIC nobj
#     projection / how a /Size cap clips the declared object range. The page
#     tree resolves identically where both sides open.
_PINNED_DIVERGENCES: dict[str, str] = {
    # --- family (A): pypdfbox throws, PDFBox brute-force-recovers ---
    #   java (all): loaded=1 pages=1 root=present nobj=4 enc=0
    "w_two_elem": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "w_negative": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "w_sum_over_20": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "w_zero_entry": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "w_missing": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "index_odd": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "index_nonint": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "index_overrun": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "index_negative_first": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "size_too_large": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "size_missing": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "body_truncated": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    "body_one_byte": "loaded=ERR:OSError pages=? root=? nobj=? enc=?",
    # --- family (B): both open, projection / size-clip nuance ---
    # /Size 2 (Index defaults to [0 2]) declares only objs 0,1. The page tree
    # (objs 2,3) is not in the located xref. Wave 1549 wired up the lenient
    # free/missing-key brute-force fallback (COSParser.parseObjectDynamically),
    # so a reference to obj2/obj3 now resolves its body from the file body —
    # the page tree is reachable (pages=1), matching PDFBox. The residual nuance
    # is nobj: PDFBox's post-decode consistency check MERGES objs 2,3 into the
    # public xref table (nobj=2), whereas pypdfbox resolves them on demand
    # without adding them to the public table (nobj=1). A recovery-completeness
    # nuance in WHICH keys land in the public table — the page tree resolves
    # identically. Same class as the size_zero / w_type_col_absent nobj pins.
    #   java: loaded=1 pages=1 root=present nobj=2 enc=0
    "size_too_small": "loaded=1 pages=1 root=present nobj=1 enc=0",
    # /Size 0 (Index defaults to [0 0]) declares ZERO entries, so the located
    # xref stream registers no objects. Both sides then recover the body: PDFBox
    # brute-force-recovers the narrower consistency-walk set (nobj=2) while
    # pypdfbox's empty-located-xref recovery merges every recovered n g obj body
    # (objs 1,2,3,4 -> nobj=4). Both open with the page tree fully reachable
    # (pages=1, root=present). A recovery-completeness nuance in WHICH objects
    # land in the public table, identical in class to the w_type_col_absent and
    # the wave-1516 entry_all_free pins.
    #   java: loaded=1 pages=1 root=present nobj=2 enc=0
    "size_zero": "loaded=1 pages=1 root=present nobj=4 enc=0",
    # /W [0 4 2]: the type column is absent so every row (incl. obj0's row at
    # offset 0) defaults to type 1 (in-use). pypdfbox registers obj0 as an
    # in-use entry too (nobj=5); PDFBox's table excludes the obj0 head (nobj=4).
    # A projection nuance in WHICH keys land in the public table — the page tree
    # resolves identically (pages=1 both). Same class as the wave-1516
    # entry_all_free nobj nuance.
    #   java: loaded=1 pages=1 root=present nobj=4 enc=0
    "w_type_col_absent": "loaded=1 pages=1 root=present nobj=5 enc=0",
    # /Root 9 0 R dangles (obj9 absent). PDFBox's initialParse throws
    # IOException("Missing root object specification in trailer") because the
    # resolved /Root is not a catalog. pypdfbox DEFERS initialParse on the
    # located-xref path and PDDocumentCatalog synthesises a minimal
    # {/Type /Catalog}, so the document opens empty (root=present, pages=0). The
    # long-standing deferred-initialParse / catalog-synthesis policy, identical
    # to the wave-1516 root_dangling pin.
    #   java: loaded=ERR:IOException pages=? root=? nobj=? enc=?
    "root_dangling": "loaded=1 pages=0 root=present nobj=4 enc=0",
}


@requires_oracle
def test_xref_recovery_fuzz_parity(tmp_path: Path) -> None:
    for name, data in _CORPUS.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text("\n".join(_CORPUS) + "\n", encoding="utf-8")

    raw = run_probe_text("XrefRecoveryFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(_CORPUS), (
        f"probe emitted {len(java_lines)} lines for {len(_CORPUS)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in _CORPUS:
        java = java_by_name[name]
        py = _py_line(name, tmp_path / f"{name}.pdf")

        if name in _PINNED_DIVERGENCES:
            expected = f"CASE {name} {_PINNED_DIVERGENCES[name]}"
            if py != expected:
                mismatches.append(
                    f"\n  PINNED case={name}\n    expected={expected}\n"
                    f"    py      ={py}\n    java    ={java}"
                )
            continue

        # ERR arm: compare the throw boolean only (runtime exception class names
        # differ between Java and pypdfbox). OK arm: assert verbatim.
        if _kind(java) == "ERR" and _kind(py) == "ERR":
            continue
        if java != py:
            mismatches.append(f"\n  case={name}\n    java={java}\n    py  ={py}")

    assert not mismatches, "xref-recovery fuzz divergences:" + "".join(mismatches)
