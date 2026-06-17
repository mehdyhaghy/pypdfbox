"""Live Apache PDFBox differential parse-leniency fuzz for the BRUTE-FORCE
OBJECT RECOVERY + ROOT / PAGES RECOVERY path (parity wave 1532, agent D).

Complements the wave-1517 trailer/``startxref`` rebuild fuzz
(``test_trailer_rebuild_fuzz_wave1517`` — trailer candidate selection and the
located-xref vs full-rebuild branch). This wave targets the DISTINCT first half
of recovery: the raw byte scan that finds ``n g obj`` headers
(``BruteForceParser.bfSearchForObjects``) and how the full rebuild then derives
``/Root`` (via ``/Type /Catalog``) and ``/Pages`` and runs ``checkPages``.

Surface:

* Object-header scan robustness — header at EOF (no ``endobj``), header walled
  by garbage, abutting integer literals before the object number, ``obj`` as a
  substring of ``endobj`` (must NOT be picked up).
* Entirely header-less file — must FAIL, not yield an empty document.
* Duplicate ``n g obj`` — the LAST definition wins; verified by which catalog's
  recovered ``/Pages`` target survives.
* ``/Root`` recovery — catalog reachable only via the scan, catalog without
  ``/Type /Catalog`` (no candidate → fail), catalog whose ``/Pages`` dangles.
* ``/Pages`` recovery + ``checkPages`` — a /Kids target that is missing /
  truncated is pruned and /Count rewritten; a valid kid recovers the page.
* Object-stream content recovery — catalog packed in ``/Type /ObjStm`` (members
  parsed to find /Root) and a corrupt ObjStm (bad /First) that yields nothing.
* Garbage interleaved between valid object definitions.

The Java oracle of record is ``oracle/probes/BruteForceRecoveryFuzzProbe.java``.
Both sides read the IDENTICAL hand-crafted PDF bytes on disk (one ``<case>.pdf``
per case plus a ``manifest.txt``) and the probe loads each with the empty
password.

Output grammar (one line per case)::

    CASE <name> loaded=<1|ERR:<ExcSimpleName>> pages=<n|?> root=<present|absent|?> nobj=<count|?>

``loaded=ERR:<X>`` means the load threw exception class X (pages/root/nobj are
``?``). On success ``loaded=1``; ``pages`` is ``getNumberOfPages``, ``root`` is
whether the catalog resolves, ``nobj`` is the count of resolved object keys.

Validation, not blind pinning: the Java line is ground truth. The ``ERR`` arm is
compared on the THROW BOOLEAN only (Java's ``IOException`` family vs pypdfbox's
``PDFParseError`` // ``OSError`` are not the same class name); the success-arm
fields (pages/root/nobj) are asserted verbatim. Real bugs are FIXED in the
recovery path (see CHANGES.md, wave 1532); residual defensible robustness
divergences are pinned both-sides in ``_PINNED_DIVERGENCES`` with a reason.

``@requires_oracle`` so the suite stays green without Java + the jar.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Raw-PDF construction. We control body / xref / trailer / startxref bytes
# directly so the layout of every recovery edge case is exact. None of these
# cases carry a usable startxref/xref, forcing the full brute-force rebuild.
# --------------------------------------------------------------------------- #

_HEADER = b"%PDF-1.4\n"
_CAT = b"<< /Type /Catalog /Pages 2 0 R >>"
_PAGES = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
_PAGE = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"
_STD_OBJS = ((1, _CAT), (2, _PAGES), (3, _PAGE))


def _lay_body(objs=_STD_OBJS, header: bytes = _HEADER) -> bytearray:
    """Emit the header + numbered object definitions (no xref/trailer)."""
    body = bytearray(header)
    for num, content in objs:
        body += b"%d 0 obj\n" % num + content + b"\nendobj\n"
    return body


# --------------------------------------------------------------------------- #
# Corpus. Each builder returns the raw PDF bytes for one case.
# --------------------------------------------------------------------------- #


def _build_corpus() -> dict[str, bytes]:
    cases: dict[str, bytes] = {}

    # --- baseline brute-force rebuild (regression guard): full body, no xref. -
    cases["bf_baseline"] = bytes(_lay_body()) + b"%%EOF"

    # ===================================================================== #
    # Object-header scan robustness.
    # ===================================================================== #

    # Object header sits at the very end of file — no trailing endobj, the last
    # object's body runs to EOF. The scan must still register all three keys.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n" + _CAT + b"\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE  # no endobj, no EOF marker
    cases["bf_header_at_eof"] = bytes(body)

    # Garbage bytes immediately surround every object header.
    body = bytearray(_HEADER)
    body += b"%%%%%% noise %%%%%%\n"
    body += b"1 0 obj\n" + _CAT + b"\nendobj\n"
    body += b"@@@ junk between objects @@@\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"~~~ more junk ~~~\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    body += b"trailing rubbish with no startxref\n"
    cases["bf_garbage_between"] = bytes(body) + b"%%EOF"

    # An integer literal abuts the object number (``99 1 0 obj``): the scan must
    # recover (1 0) — the catalog — not a bogus (991 0) or (1 0) confusion.
    body = bytearray(_HEADER)
    body += b"99 1 0 obj\n" + _CAT + b"\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    cases["bf_abutting_int"] = bytes(body) + b"%%EOF"

    # The word ``endobj`` (contains ``obj``) and a stray ``/obj`` name must NOT
    # be mistaken for an object header.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R /Note /obj >>\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    cases["bf_obj_substring"] = bytes(body) + b"%%EOF"

    # ===================================================================== #
    # Entirely header-less / no-object files (must FAIL).
    # ===================================================================== #

    # Header bytes + freeform text, zero ``n g obj``.
    cases["bf_no_objects"] = _HEADER + b"absolutely no objects here at all\n%%EOF"

    # Not even a %PDF- header — pure garbage. PDFBox tolerates a missing header
    # but still finds no object → fail.
    cases["bf_headerless_garbage"] = b"this file has no pdf header and no objects\n"

    # ===================================================================== #
    # Duplicate definitions — LAST wins (verified by content).
    # ===================================================================== #

    # Two catalog 1 0 obj: the FIRST points /Pages at obj 8 (absent), the SECOND
    # at obj 2 (the real pages tree). Last-wins => page recovered => pages=1.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n<< /Type /Catalog /Pages 8 0 R >>\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    body += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    cases["bf_dup_last_wins"] = bytes(body) + b"%%EOF"

    # Inverse: FIRST catalog is the good one, SECOND points /Pages at the absent
    # obj 8. Last-wins => the broken catalog wins => 0 pages.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    body += b"1 0 obj\n<< /Type /Catalog /Pages 8 0 R >>\nendobj\n"
    cases["bf_dup_last_broken"] = bytes(body) + b"%%EOF"

    # ===================================================================== #
    # /Root recovery.
    # ===================================================================== #

    # Catalog lacks /Type /Catalog AND has no /FDF — no root candidate at all.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n<< /Pages 2 0 R >>\nendobj\n"
    body += b"2 0 obj\n" + _PAGES + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    cases["bf_root_no_type"] = bytes(body) + b"%%EOF"

    # Catalog present, /Pages points at a wholly missing object (obj 7).
    body = bytearray(_HEADER)
    body += b"1 0 obj\n<< /Type /Catalog /Pages 7 0 R >>\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    cases["bf_pages_missing"] = bytes(body) + b"%%EOF"

    # Catalog whose /Pages target IS present but is not a /Type /Pages dict.
    body = bytearray(_HEADER)
    body += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    body += b"2 0 obj\n<< /NotPages true >>\nendobj\n"
    cases["bf_pages_wrong_type"] = bytes(body) + b"%%EOF"

    # ===================================================================== #
    # /Pages + checkPages — kid pruning.
    # ===================================================================== #

    # Pages /Kids lists obj 3 (a valid page) and obj 9 (absent). checkPages
    # prunes obj 9 and rewrites /Count to 1.
    pages_two_kids = b"<< /Type /Pages /Kids [3 0 R 9 0 R] /Count 2 >>"
    body = bytearray(_HEADER)
    body += b"1 0 obj\n" + _CAT + b"\nendobj\n"
    body += b"2 0 obj\n" + pages_two_kids + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    cases["bf_kid_dangling_pruned"] = bytes(body) + b"%%EOF"

    # Two real pages — both kids valid; recovers a 2-page document.
    pages_two = b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>"
    page4 = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>"
    body = bytearray(_HEADER)
    body += b"1 0 obj\n" + _CAT + b"\nendobj\n"
    body += b"2 0 obj\n" + pages_two + b"\nendobj\n"
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    body += b"4 0 obj\n" + page4 + b"\nendobj\n"
    cases["bf_two_pages"] = bytes(body) + b"%%EOF"

    # Nested page tree: catalog -> pages(2) -> intermediate pages(5) -> page(3).
    inter = b"<< /Type /Pages /Parent 2 0 R /Kids [3 0 R] /Count 1 >>"
    outer = b"<< /Type /Pages /Kids [5 0 R] /Count 1 >>"
    body = bytearray(_HEADER)
    body += b"1 0 obj\n" + _CAT + b"\nendobj\n"
    body += b"2 0 obj\n" + outer + b"\nendobj\n"
    body += b"5 0 obj\n" + inter + b"\nendobj\n"
    body += b"3 0 obj\n<< /Type /Page /Parent 5 0 R /MediaBox [0 0 10 10] >>\nendobj\n"
    cases["bf_nested_pages"] = bytes(body) + b"%%EOF"

    # ===================================================================== #
    # Object-stream content recovery.
    # ===================================================================== #
    cases["bf_catalog_in_objstm"] = _build_catalog_in_objstm()
    cases["bf_objstm_bad_first"] = _build_objstm_bad_first()

    return cases


def _build_catalog_in_objstm() -> bytes:
    """Catalog + pages compressed inside a /Type /ObjStm; page is a plain
    object. No startxref/trailer — recovery must reach the catalog via
    bfSearchForObjStreams to populate /Root."""
    member1 = _CAT
    member2 = _PAGES
    off1 = 0
    off2 = len(member1) + 1
    header = b"1 %d 2 %d" % (off1, off2)
    payload = header + b" " + member1 + b" " + member2
    first = len(header) + 1
    objstm = (
        b"4 0 obj\n<< /Type /ObjStm /N 2 /First %d /Length %d >>\nstream\n"
        % (first, len(payload))
        + payload
        + b"\nendstream\nendobj\n"
    )
    body = bytearray(_HEADER)
    body += b"3 0 obj\n" + _PAGE + b"\nendobj\n"
    body += objstm
    return bytes(body) + b"%%EOF"


def _build_objstm_bad_first() -> bytes:
    """An ObjStm whose /First offset is past the payload, so no members can be
    parsed. With the catalog only reachable through that ObjStm, /Root stays
    unrecovered."""
    member1 = _CAT
    payload = b"1 0 " + member1
    objstm = (
        b"4 0 obj\n<< /Type /ObjStm /N 1 /First 9999 /Length %d >>\nstream\n"
        % len(payload)
        + payload
        + b"\nendstream\nendobj\n"
    )
    body = bytearray(_HEADER)
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
# justification (and a CHANGES.md row, wave 1532). The Java line for the same
# case is recorded in the comment.
_PINNED_DIVERGENCES: dict[str, str] = {}


@requires_oracle
def test_brute_force_recovery_fuzz_parity(tmp_path: Path) -> None:
    for name, data in _CORPUS.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text("\n".join(_CORPUS) + "\n", encoding="utf-8")

    raw = run_probe_text("BruteForceRecoveryFuzzProbe", str(tmp_path))
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
        # ERR arm: compare the throw boolean only (runtime exception class names
        # differ between Java and pypdfbox). OK arm: assert verbatim.
        if java_kind == "ERR" and py_kind == "ERR":
            continue
        if java != py:
            mismatches.append(f"\n  case={name}\n    java={java}\n    py  ={py}")

    assert not mismatches, "brute-force-recovery fuzz divergences:" + "".join(mismatches)
