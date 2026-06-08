"""Live Apache PDFBox differential parse-leniency fuzz for the TRAILER /
``startxref`` RECOVERY and BRUTE-FORCE REBUILD path (parity wave 1517,
agent B).

Complements the wave-1516 classic-xref-table fuzz
(``test_xref_table_fuzz_wave1516`` — subsection / entry framing + ``/Prev``
chain). This wave targets the DISTINCT recovery machinery that fires when the
cross-reference data is unusable and PDFBox must rebuild the xref + trailer from
a raw object scan: ``COSParser.retrieveTrailer`` →
``BruteForceParser.rebuildTrailer``, ``bfSearchForObjects``,
``bfSearchForObjStreams``, ``searchForTrailerItems``, ``bfSearchForXRef``, and
``parseStartXref``.

Surface:

* FULL brute-force rebuild — ``startxref`` missing / garbage with NO parseable
  xref section: recovery scans ``n g obj`` headers, relocates the
  ``/Type /Catalog`` as ``/Root``, derives ``/Size`` = max(objnum)+1.
* ``rebuildTrailer`` candidate selection — ``/Info`` via info keys,
  ``/Encrypt`` / ``/ID`` copy-through, FDF root (no ``/Type`` but ``/FDF``),
  catalog vs info disambiguation, duplicate ``n g obj`` (later wins).
* Catalog packed inside a ``/Type /ObjStm`` (lost xref-stream trailer) —
  recovered via ``bfSearchForObjStreams``.
* Trailer dictionary corruption — ``trailer`` keyword absent, dict
  unterminated, two ``trailer`` keywords, leading garbage shoving ``%PDF-``
  past byte 0.
* ``startxref`` recovery — points at whitespace, into an object body, one byte
  off the ``xref`` keyword, a valid table reachable only by ``bfSearchForXRef``.
* No recoverable object at all (header + garbage) — must FAIL.

The Java oracle of record is ``oracle/probes/TrailerRebuildFuzzProbe.java``.
Both sides read the IDENTICAL hand-crafted PDF bytes on disk (one
``<case>.pdf`` per case plus a ``manifest.txt``) and the probe loads each with
the empty password.

Output grammar (one line per case)::

    CASE <name> loaded=<1|ERR:<ExcSimpleName>> pages=<n|?> root=<present|absent|?> nobj=<count|?>

``loaded=ERR:<X>`` means the load threw exception class X (pages/root/nobj are
``?``). On success ``loaded=1``; ``pages`` is ``getNumberOfPages``, ``root`` is
whether the catalog resolves, ``nobj`` is the count of resolved object keys.

Validation, not blind pinning: the Java line is ground truth. The ``ERR`` arm is
compared on the THROW BOOLEAN only (Java's ``IOException`` family vs pypdfbox's
``PDFParseError`` // ``OSError`` are not the same class name); the success-arm
fields (pages/root/nobj) are asserted verbatim. Real bugs are FIXED in the
recovery path (see CHANGES.md, wave 1517); the residual defensible robustness
divergences are pinned both-sides in ``_PINNED_DIVERGENCES`` with a reason.

``@requires_oracle`` so the suite stays green without Java + the jar.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Raw-PDF construction. We control the body / xref / trailer / startxref text
# directly so the byte layout of every recovery edge case is exact.
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


# --------------------------------------------------------------------------- #
# Corpus. Each builder returns the raw PDF bytes for one case.
# --------------------------------------------------------------------------- #


def _build_corpus() -> dict[str, bytes]:
    cases: dict[str, bytes] = {}

    # --- baseline good file (regression guard) ---
    body, offsets = _lay_body()
    xref_pos = len(body)
    good = bytearray(body)
    good += _std_xref(offsets)
    good += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    good += b"startxref\n%d\n%%EOF" % xref_pos
    cases["baseline"] = bytes(good)

    # ===================================================================== #
    # FULL brute-force rebuild: no parseable xref section at all.
    # ===================================================================== #

    # No xref, no trailer, no startxref — only the body. Recovery must rebuild
    # the whole cross-reference from the n g obj scan.
    body, _ = _lay_body()
    cases["rebuild_body_only"] = bytes(body) + b"%%EOF"

    # startxref present but points at pure garbage; no xref section anywhere.
    body, _ = _lay_body()
    out = bytearray(body)
    out += b"startxref\n999999\n%%EOF"
    cases["rebuild_startxref_garbage"] = bytes(out)

    # A single catalog object only (no pages tree) — rebuild finds /Root but
    # the page tree is absent.
    body, _ = _lay_body(objs=((1, _CAT),))
    cases["rebuild_catalog_only"] = bytes(body) + b"%%EOF"

    # Catalog object lacks /Type /Catalog — no candidate for /Root, so the
    # full rebuild must FAIL with "Missing root".
    notype_cat = b"<< /Pages 2 0 R >>"
    body, _ = _lay_body(objs=((1, notype_cat), (2, _PAGES), (3, _PAGE)))
    cases["rebuild_root_no_type"] = bytes(body) + b"%%EOF"

    # Header + trailing garbage, NO n g obj anywhere — nothing recoverable.
    cases["rebuild_no_objects"] = _HEADER + b"this is not a pdf body at all\n%%EOF"

    # Leading garbage pushes %PDF- header past byte 0; body then follows.
    body, _ = _lay_body()
    cases["rebuild_leading_garbage"] = b"GARBAGE BYTES BEFORE HEADER\n" + bytes(body) + b"%%EOF"

    # Duplicate catalog definition — later (higher offset) n g obj wins.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R /Marker (first) >>\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    body += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R /Marker (second) >>\nendobj\n"
    cases["rebuild_duplicate_obj"] = bytes(body) + b"%%EOF"

    # FDF-style root: dictionary has /FDF but no /Type /Catalog — upstream
    # isCatalog() treats /FDF as a catalog candidate.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n<< /FDF << /Fields [] >> >>\nendobj\n"
    cases["rebuild_fdf_root"] = bytes(body) + b"%%EOF"

    # /Info recovery: a separate info dict carrying standard info keys.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n" + _CAT + b"\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    body += b"4 0 obj\n<< /Producer (Acme) /Title (Doc) >>\nendobj\n"
    cases["rebuild_info_recovered"] = bytes(body) + b"%%EOF"

    # ===================================================================== #
    # Trailer dictionary corruption (xref table IS present and locatable).
    # ===================================================================== #

    # No trailer keyword at all, but the xref table is present and startxref
    # points to it. Recovery must rebuild the trailer.
    body, offsets = _lay_body()
    xref_pos = len(body)
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"startxref\n%d\n%%EOF" % xref_pos
    cases["trailer_keyword_missing"] = bytes(out)

    # Trailer dict opened but never closed (no >>).
    body, offsets = _lay_body()
    xref_pos = len(body)
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R \n"
    out += b"startxref\n%d\n%%EOF" % xref_pos
    cases["trailer_unterminated"] = bytes(out)

    # Trailer dict is empty — no /Root, no /Size. Must rebuild /Root.
    body, offsets = _lay_body()
    xref_pos = len(body)
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< >>\n"
    out += b"startxref\n%d\n%%EOF" % xref_pos
    cases["trailer_empty_dict"] = bytes(out)

    # Two consecutive trailer keywords (the second dict wins / merges).
    body, offsets = _lay_body()
    xref_pos = len(body)
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 >>\n"
    out += b"trailer\n<< /Root 1 0 R >>\n"
    out += b"startxref\n%d\n%%EOF" % xref_pos
    cases["trailer_double_keyword"] = bytes(out)

    # Trailer /Root present but dangling (obj 9 absent). Located-xref path:
    # upstream defers to initialParse "Missing root"; pypdfbox synthesises.
    body, offsets = _lay_body()
    xref_pos = len(body)
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 9 0 R >>\n"
    out += b"startxref\n%d\n%%EOF" % xref_pos
    cases["trailer_root_dangling"] = bytes(out)

    # ===================================================================== #
    # startxref recovery — startxref present but mispointed.
    # ===================================================================== #

    # startxref points at whitespace just before the xref keyword.
    body, offsets = _lay_body()
    out = bytearray(body)
    out += b"  \n"  # 3 bytes of whitespace padding
    pad = len(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    out += b"startxref\n%d\n%%EOF" % pad  # points at the whitespace
    cases["startxref_at_whitespace"] = bytes(out)

    # startxref points one byte BEFORE the xref keyword.
    body, offsets = _lay_body()
    xref_pos = len(body)
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    out += b"startxref\n%d\n%%EOF" % (xref_pos - 1)
    cases["startxref_off_by_one"] = bytes(out)

    # startxref points into the middle of an object body.
    body, offsets = _lay_body()
    xref_pos = len(body)
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    out += b"startxref\n%d\n%%EOF" % (offsets[2] + 5)
    cases["startxref_into_object"] = bytes(out)

    # startxref value is negative.
    body, offsets = _lay_body()
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    out += b"startxref\n-1\n%%EOF"
    cases["startxref_negative"] = bytes(out)

    # No startxref keyword, but a valid xref table + trailer ARE present.
    body, offsets = _lay_body()
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    out += b"%%EOF"
    cases["startxref_keyword_missing"] = bytes(out)

    # startxref keyword present but its argument is empty (newline then EOF).
    body, offsets = _lay_body()
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    out += b"startxref\n\n%%EOF"
    cases["startxref_empty_arg"] = bytes(out)

    # ===================================================================== #
    # Catalog inside an object stream (lost xref-stream trailer).
    # ===================================================================== #
    cases["rebuild_catalog_in_objstm"] = _build_catalog_in_objstm()

    # ===================================================================== #
    # /Prev chain pointing into a rebuild scenario.
    # ===================================================================== #

    # startxref points to a valid xref, whose /Prev points at garbage.
    body, offsets = _lay_body()
    xref_pos = len(body)
    out = bytearray(body)
    out += _std_xref(offsets)
    out += b"trailer\n<< /Size 4 /Root 1 0 R /Prev 888888 >>\n"
    out += b"startxref\n%d\n%%EOF" % xref_pos
    cases["prev_into_garbage"] = bytes(out)

    # Encrypt key in a recovered object should be copied into rebuilt trailer
    # (no actual encryption — just exercising the copy-through). Use an
    # unsupported filter so we observe whether copy-through changes outcome.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n" + _CAT + b"\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    cases["rebuild_three_objs"] = bytes(body) + b"%%EOF"

    return cases


def _build_catalog_in_objstm() -> bytes:
    """A PDF whose catalog lives compressed in a /Type /ObjStm, with a lost
    xref (no startxref / trailer). Recovery must find the catalog via
    bfSearchForObjStreams."""
    body = bytearray(_HEADER)
    # Object stream 4 holds objects 1 (catalog) and 2 (pages); object 3 (page)
    # is a plain object. Build the ObjStm payload.
    member1 = _CAT
    member2 = _PAGES
    # ObjStm header: "<objnum1> <off1> <objnum2> <off2>" then the member bodies.
    off1 = 0
    off2 = len(member1) + 1  # member1 + separating space
    header = b"1 %d 2 %d" % (off1, off2)
    payload = header + b" " + member1 + b" " + member2
    first = len(header) + 1
    objstm = (
        b"4 0 obj\n<< /Type /ObjStm /N 2 /First %d /Length %d >>\nstream\n"
        % (first, len(payload))
        + payload
        + b"\nendstream\nendobj\n"
    )
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    body += objstm
    return bytes(body) + b"%%EOF"


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


def _split(line: str) -> str:
    """Return the throw-kind ('ERR' | 'OK') for one CASE line."""
    body = line.split(" ", 2)[2]
    loaded = body.split(" ", 1)[0]
    return "ERR" if loaded.startswith("loaded=ERR") else "OK"


# Defensible robustness divergences, pinned both-sides. Each entry maps a case
# name to the EXACT pypdfbox line tail (everything after "CASE <name> "), with a
# justification (and a CHANGES.md row, wave 1517). The Java line for the same
# case is recorded in the comment.
_PINNED_DIVERGENCES: dict[str, str] = {
    # A recovered/located /Root that resolves to a catalog dictionary which has
    # NO usable page tree (/Pages absent — the catalog-only rebuild and the FDF
    # root — or /Root pointing at a missing object). Upstream's initialParse
    # calls checkPages(root), which raises IOException ("Page tree root must be
    # a dictionary") so Loader.loadPDF fails. pypdfbox deliberately uses
    # check_pages_dictionary (NOT check_pages) on these paths so FDF catalogs
    # — which legitimately omit /Pages and which upstream routes through a
    # SEPARATE parser that never reaches checkPages — still load through the
    # generic loader. No data is fabricated: the catalog opens as a valid
    # 0-page document instead of a hard failure. This is the long-standing
    # FDF-leniency / deferred-initialParse policy (see wave 1516 root_dangling),
    # independent of the trailer/rebuild parse this wave owns.
    #   java (all three): loaded=ERR:IOException pages=? root=? nobj=?
    "rebuild_catalog_only": "loaded=1 pages=0 root=present nobj=1",
    "rebuild_fdf_root": "loaded=1 pages=0 root=present nobj=1",
    "trailer_root_dangling": "loaded=1 pages=0 root=present nobj=3",
}


@requires_oracle
def test_trailer_rebuild_fuzz_parity(tmp_path: Path) -> None:
    for name, data in _CORPUS.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text("\n".join(_CORPUS) + "\n", encoding="utf-8")

    raw = run_probe_text("TrailerRebuildFuzzProbe", str(tmp_path))
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

        java_kind = _split(java)
        py_kind = _split(py)
        # ERR arm: compare the throw boolean only (runtime exception class
        # names differ between Java and pypdfbox). OK arm: assert verbatim.
        if java_kind == "ERR" and py_kind == "ERR":
            continue
        if java != py:
            mismatches.append(f"\n  case={name}\n    java={java}\n    py  ={py}")

    assert not mismatches, "trailer-rebuild fuzz divergences:" + "".join(mismatches)
