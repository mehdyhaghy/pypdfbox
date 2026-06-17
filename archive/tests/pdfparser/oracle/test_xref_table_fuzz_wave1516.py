"""Live Apache PDFBox differential parse-leniency fuzz for the CLASSIC
cross-reference ``xref``-table + ``trailer`` keyword parse path and its
broken-xref recovery (parity wave 1516, agent B).

Complements the wave-1512 xref-STREAM fuzz
(``test_xref_stream_fuzz_wave1512`` — which drives ``PDFXrefStreamParser`` in
isolation against a malformed ``/W`` // ``/Index`` // ``/Size`` geometry). This
wave targets the DISTINCT classic ``xref`` keyword path end-to-end by driving
WHOLE tiny PDFs through the loader:

* ``xref`` subsection headers: ``<start> <count>``, a wrong (short/long)
  count, count 0, multiple subsections, a non-numeric / mistyped header.
* 20-byte entry framing: ``nnnnnnnnnn ggggg n\\r\\n`` / ``... f``, wrong width,
  missing trailing EOL, a wrong ``n``/``f`` type char, off-by-one offsets.
* ``trailer`` dict: ``/Size`` missing / wrong, ``/Root`` missing / wrong-type,
  ``/Prev`` valid-chain / dangling / cyclic / negative, ``/XRefStm`` hybrid
  offset valid / dangling.
* ``startxref``: valid / mid-object / past-EOF / missing / non-numeric.
* ``%%EOF`` present / absent.

The Java oracle of record is ``oracle/probes/XrefTableFuzzProbe.java``. Both
sides read the IDENTICAL hand-crafted PDF bytes on disk (one ``<case>.pdf`` per
case plus a ``manifest.txt``) and the probe loads each with the empty password.

Output grammar (one line per case)::

    CASE <name> loaded=<1|ERR:<ExcSimpleName>> pages=<n|?> root=<present|absent|?> nobj=<count|?>

``loaded=ERR:<X>`` means the load threw exception class X (then pages/root/nobj
are ``?``). On success ``loaded=1``; ``pages`` is ``getNumberOfPages``, ``root``
is whether the catalog resolves, ``nobj`` is the count of resolved object keys
in the COS xref table — capturing whether the table/trailer resolved and
whether recovery (rebuild) kicked in.

Validation, not blind pinning: the Java line is ground truth. The ``ERR`` arm is
compared on the THROW BOOLEAN only (Java's ``IOException`` family vs pypdfbox's
``PDFParseError`` // ``OSError`` are not the same class name); the success-arm
fields (pages/root/nobj) are asserted verbatim. Real bugs were FIXED in the
classic-xref parse path (see CHANGES.md, wave 1516); the residual defensible
robustness divergences are pinned both-sides in ``_PINNED_DIVERGENCES`` with a
reason and a matching CHANGES.md row.

``@requires_oracle`` so the suite stays green without Java + the jar.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Raw-PDF construction. We control the xref/trailer text directly so the byte
# layout of every edge case is exact.
# --------------------------------------------------------------------------- #

_HEADER = b"%PDF-1.4\n"
_CAT = b"<< /Type /Catalog /Pages 2 0 R >>"
_PAGES = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
_PAGE = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"
_STD_OBJS = ((1, _CAT), (2, _PAGES), (3, _PAGE))


def _lay_body(objs=_STD_OBJS, header: bytes = _HEADER) -> tuple[bytearray, dict[int, int]]:
    """Emit the header + numbered object definitions; return (buffer, offsets)."""
    body = bytearray(header)
    offsets: dict[int, int] = {}
    for num, content in objs:
        offsets[num] = len(body)
        body += b"%d 0 obj\n" % num + content + b"\nendobj\n"
    return body, offsets


def _std_xref(offsets: dict[int, int]) -> bytes:
    """A correct 4-entry classic xref subsection for the standard 3-object body."""
    b = b"xref\n0 4\n0000000000 65535 f\r\n"
    for n in (1, 2, 3):
        b += b"%010d 00000 n\r\n" % offsets[n]
    return b


def _assemble(
    xref_block: bytes,
    trailer: bytes | None,
    startxref: int | None,
    xref_pos: int,
    body: bytearray,
    eof: bool = True,
) -> bytes:
    """Glue an xref block + trailer + startxref + %%EOF onto ``body``."""
    out = bytearray(body)
    out += xref_block
    if trailer is not None:
        out += b"trailer\n" + trailer + b"\n"
    if startxref is not None:
        out += b"startxref\n%d\n" % startxref
    if eof:
        out += b"%%EOF"
    return bytes(out)


def _good(trailer: bytes = b"<< /Size 4 /Root 1 0 R >>") -> bytes:
    body, offsets = _lay_body()
    xref_pos = len(body)
    return _assemble(_std_xref(offsets), trailer, xref_pos, xref_pos, body)


# --------------------------------------------------------------------------- #
# Corpus. Each builder returns the raw PDF bytes for one case.
# --------------------------------------------------------------------------- #


def _build_corpus() -> dict[str, bytes]:
    cases: dict[str, bytes] = {}

    # --- baseline (regression guard) ---
    cases["baseline"] = _good()

    # --- /Size ---
    cases["size_too_small"] = _good(b"<< /Size 2 /Root 1 0 R >>")
    cases["size_too_large"] = _good(b"<< /Size 99 /Root 1 0 R >>")
    cases["size_missing"] = _good(b"<< /Root 1 0 R >>")
    cases["size_zero"] = _good(b"<< /Size 0 /Root 1 0 R >>")
    cases["size_real"] = _good(b"<< /Size 4.0 /Root 1 0 R >>")

    # --- /Root ---
    cases["root_missing"] = _good(b"<< /Size 4 >>")
    cases["root_int"] = _good(b"<< /Size 4 /Root 42 >>")
    cases["root_dangling"] = _good(b"<< /Size 4 /Root 9 0 R >>")
    cases["root_name"] = _good(b"<< /Size 4 /Root /Foo >>")

    # --- subsection headers ---
    def _xref_count_short(offsets: dict[int, int]) -> bytes:
        # Header says 3 entries (objs 0,1,2) but a 4th orphan entry follows.
        b = b"xref\n0 3\n0000000000 65535 f\r\n"
        for n in (1, 2, 3):
            b += b"%010d 00000 n\r\n" % offsets[n]
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["subsec_count_short"] = _assemble(
        _xref_count_short(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body
    )

    def _xref_count_zero(offsets: dict[int, int]) -> bytes:
        # First subsection has count 0, then a real subsection 0..3.
        b = b"xref\n5 0\n0 4\n0000000000 65535 f\r\n"
        for n in (1, 2, 3):
            b += b"%010d 00000 n\r\n" % offsets[n]
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["subsec_count_zero"] = _assemble(
        _xref_count_zero(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body
    )

    def _xref_multi(offsets: dict[int, int]) -> bytes:
        # Three subsections: {0}, {1}, {2,3}.
        b = b"xref\n0 1\n0000000000 65535 f\r\n"
        b += b"1 1\n%010d 00000 n\r\n" % offsets[1]
        b += b"2 2\n%010d 00000 n\r\n%010d 00000 n\r\n" % (offsets[2], offsets[3])
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["subsec_multi"] = _assemble(
        _xref_multi(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body
    )

    def _xref_nonnumeric_header(offsets: dict[int, int]) -> bytes:
        b = b"xref\nzero four\n0000000000 65535 f\r\n"
        for n in (1, 2, 3):
            b += b"%010d 00000 n\r\n" % offsets[n]
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["subsec_header_nonnumeric"] = _assemble(
        _xref_nonnumeric_header(offsets),
        b"<< /Size 4 /Root 1 0 R >>",
        xref_pos,
        xref_pos,
        body,
    )

    # --- 20-byte entry framing ---
    def _xref_lf_only(offsets: dict[int, int]) -> bytes:
        # LF-only line endings (compact form) instead of the canonical CRLF.
        b = b"xref\n0 4\n0000000000 65535 f \n"
        for n in (1, 2, 3):
            b += b"%010d 00000 n \n" % offsets[n]
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["entry_lf_only"] = _assemble(
        _xref_lf_only(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body
    )

    def _xref_wrong_width(offsets: dict[int, int]) -> bytes:
        # Offsets not zero-padded to 10 digits — non-canonical width.
        b = b"xref\n0 4\n0 65535 f\r\n"
        for n in (1, 2, 3):
            b += b"%d 0 n\r\n" % offsets[n]
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["entry_wrong_width"] = _assemble(
        _xref_wrong_width(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body
    )

    def _xref_bad_flag(offsets: dict[int, int]) -> bytes:
        # A well-formed entry line with an unknown type char ('z').
        b = b"xref\n0 4\n0000000000 65535 f\r\n"
        b += b"%010d 00000 z\r\n" % offsets[1]
        for n in (2, 3):
            b += b"%010d 00000 n\r\n" % offsets[n]
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["entry_bad_flag"] = _assemble(
        _xref_bad_flag(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body
    )

    def _xref_off_by_one(offsets: dict[int, int]) -> bytes:
        # Every offset is +1, so each entry points one byte into its object.
        b = b"xref\n0 4\n0000000000 65535 f\r\n"
        for n in (1, 2, 3):
            b += b"%010d 00000 n\r\n" % (offsets[n] + 1)
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["entry_off_by_one"] = _assemble(
        _xref_off_by_one(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body
    )

    def _xref_all_free(offsets: dict[int, int]) -> bytes:
        # All in-use entries mislabelled free — objects must be recovered.
        b = b"xref\n0 4\n0000000000 65535 f\r\n"
        for n in (1, 2, 3):
            b += b"%010d 00000 f\r\n" % offsets[n]
        return b

    body, offsets = _lay_body()
    xref_pos = len(body)
    cases["entry_all_free"] = _assemble(
        _xref_all_free(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body
    )

    # --- /Prev chains (incremental-update layout) ---
    cases["prev_valid"] = _build_prev_valid()
    cases["prev_dangling"] = _build_prev_dangling()
    cases["prev_negative"] = _build_prev_with(b"-5")
    cases["prev_cyclic"] = _build_prev_cyclic()

    # --- /XRefStm hybrid (classic table + /XRefStm pointer) ---
    cases["xrefstm_dangling"] = _good(
        b"<< /Size 4 /Root 1 0 R /XRefStm 999999 >>"
    )

    # --- startxref ---
    cases["startxref_past_eof"] = _build_startxref(999999)
    cases["startxref_mid_obj"] = _build_startxref_mid_obj()
    cases["startxref_zero"] = _build_startxref(0)
    cases["startxref_missing"] = _build_no_startxref()
    cases["startxref_nonnumeric"] = _build_startxref_nonnumeric()

    # --- %%EOF ---
    cases["no_eof"] = _build_no_eof()

    return cases


def _build_prev_valid() -> bytes:
    """Two cross-reference sections chained via /Prev (an incremental update)."""
    body, offsets = _lay_body(objs=((1, _CAT), (2, _PAGES)))
    xref1_pos = len(body)
    # First xref: objs 0,1,2.
    xref1 = b"xref\n0 3\n0000000000 65535 f\r\n"
    xref1 += b"%010d 00000 n\r\n%010d 00000 n\r\n" % (offsets[1], offsets[2])
    body += xref1
    body += b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
    body += b"startxref\n%d\n%%EOF\n" % xref1_pos
    # Incremental update: add obj 3 (the page) + a second xref pointing back.
    obj3_pos = len(body)
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    xref2_pos = len(body)
    xref2 = b"xref\n3 1\n%010d 00000 n\r\n" % obj3_pos
    body += xref2
    body += b"trailer\n<< /Size 4 /Root 1 0 R /Prev %d >>\n" % xref1_pos
    body += b"startxref\n%d\n%%EOF" % xref2_pos
    return bytes(body)


def _build_prev_dangling() -> bytes:
    """A /Prev offset that points nowhere parseable."""
    body, offsets = _lay_body()
    xref_pos = len(body)
    return _assemble(
        _std_xref(offsets),
        b"<< /Size 4 /Root 1 0 R /Prev 999999 >>",
        xref_pos,
        xref_pos,
        body,
    )


def _build_prev_with(prev: bytes) -> bytes:
    body, offsets = _lay_body()
    xref_pos = len(body)
    return _assemble(
        _std_xref(offsets),
        b"<< /Size 4 /Root 1 0 R /Prev " + prev + b" >>",
        xref_pos,
        xref_pos,
        body,
    )


def _build_prev_cyclic() -> bytes:
    """A /Prev that points back at the same xref section (a self-cycle)."""
    body, offsets = _lay_body()
    xref_pos = len(body)
    return _assemble(
        _std_xref(offsets),
        b"<< /Size 4 /Root 1 0 R /Prev %d >>" % xref_pos,
        xref_pos,
        xref_pos,
        body,
    )


def _build_startxref(value: int) -> bytes:
    body, offsets = _lay_body()
    xref_pos = len(body)
    return _assemble(
        _std_xref(offsets), b"<< /Size 4 /Root 1 0 R >>", value, xref_pos, body
    )


def _build_startxref_mid_obj() -> bytes:
    body, offsets = _lay_body()
    xref_pos = len(body)
    return _assemble(
        _std_xref(offsets), b"<< /Size 4 /Root 1 0 R >>", offsets[2], xref_pos, body
    )


def _build_no_startxref() -> bytes:
    body, offsets = _lay_body()
    xref_pos = len(body)
    return _assemble(
        _std_xref(offsets), b"<< /Size 4 /Root 1 0 R >>", None, xref_pos, body
    )


def _build_startxref_nonnumeric() -> bytes:
    body, offsets = _lay_body()
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    out += b"startxref\nABC\n%%EOF"
    return bytes(out)


def _build_no_eof() -> bytes:
    body, offsets = _lay_body()
    xref_pos = len(body)
    return _assemble(
        _std_xref(offsets), b"<< /Size 4 /Root 1 0 R >>", xref_pos, xref_pos, body, eof=False
    )


_CORPUS = _build_corpus()


# --------------------------------------------------------------------------- #
# pypdfbox-side projection (must mirror the probe's grammar exactly).
# --------------------------------------------------------------------------- #


def _py_line(name: str, pdf: Path) -> str:
    doc = None
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as exc:  # noqa: BLE001 - throw boolean is what we compare
        return f"CASE {name} loaded=ERR:{type(exc).__name__} pages=? root=? nobj=?"
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
        return f"CASE {name} loaded=1 pages={pages} root={root} nobj={nobj}"
    finally:
        doc.close()


def _split(line: str) -> tuple[str, str, str]:
    """Return (loaded_token, pages_root_nobj_tail, throw_kind) for one line."""
    parts = line.split(" ", 2)
    body = parts[2]  # "loaded=... pages=... root=... nobj=..."
    loaded = body.split(" ", 1)[0]
    kind = "ERR" if loaded.startswith("loaded=ERR") else "OK"
    return loaded, body, kind


# Defensible robustness divergences, pinned both-sides. Each entry maps a case
# name to the EXACT pypdfbox line tail (everything after "CASE <name> ") that
# pypdfbox is asserted to produce, with a justification (and a CHANGES.md row,
# wave 1516). The Java line for the same case is recorded in the comment.
_PINNED_DIVERGENCES: dict[str, str] = {
    # /Root present but NOT a relocatable reference to a catalog. Upstream's
    # initialParse throws IOException ("Missing root object specification in
    # trailer") because the resolved /Root is not a catalog dictionary;
    # pypdfbox deliberately DEFERS initialParse on the located-xref path (so
    # lazy /Root + stream resolution keeps working) and PDDocumentCatalog
    # synthesises a minimal {/Type /Catalog}, so the document opens empty
    # (root=present, pages=0). No data is fabricated beyond the empty catalog;
    # callers see an empty-but-valid document instead of a hard failure. This
    # is the long-standing deferred-initialParse / catalog-synthesis policy,
    # independent of the xref-table/trailer parse this wave owns.
    #   - root_int / root_name: /Root is a non-reference scalar (42 / /Foo) —
    #     no object to relocate, so it stays unresolved on both sides.
    #   - root_dangling: /Root is 9 0 R but obj 9 is absent from the body, so
    #     the brute-force relocation finds nothing and the synthetic empty
    #     catalog is used.
    #   java (all three): loaded=ERR:IOException pages=? root=? nobj=?
    "root_int": "loaded=1 pages=0 root=present nobj=3",
    "root_name": "loaded=1 pages=0 root=present nobj=3",
    "root_dangling": "loaded=1 pages=0 root=present nobj=3",
    # All in-use entries mislabelled free: both libraries now RECOVER and open
    # (the wave-1516 fix relocates the catalog — mislabelled /Root target —
    # via the brute-force object merge, so root=present and pages=1 on both).
    # They differ only on the projected nobj: pypdfbox's brute-force merge
    # registers every recovered ``n g obj`` body (objs 1,2,3 → nobj=3) while
    # upstream's checkXrefOffsets relocates the narrower set its consistency
    # walk needs (nobj=2). A recovery-completeness nuance in WHICH objects land
    # in the PUBLIC table, not a parse or reachability defect — the page tree
    # resolves identically.
    #   java: loaded=1 pages=1 root=present nobj=2
    "entry_all_free": "loaded=1 pages=1 root=present nobj=3",
}


@requires_oracle
def test_xref_table_fuzz_parity(tmp_path: Path) -> None:
    for name, data in _CORPUS.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(_CORPUS) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("XrefTableFuzzProbe", str(tmp_path))
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

        _, _, java_kind = _split(java)
        _, _, py_kind = _split(py)
        # ERR arm: compare the throw boolean only (runtime exception class
        # names differ between Java and pypdfbox). OK arm: assert verbatim.
        if java_kind == "ERR" and py_kind == "ERR":
            continue
        if java != py:
            mismatches.append(f"\n  case={name}\n    java={java}\n    py  ={py}")

    assert not mismatches, "xref-table fuzz divergences:" + "".join(mismatches)
