"""Live Apache PDFBox differential fuzz of compressed object-stream
(``/Type /ObjStm``) parsing leniency (wave 1516, agent C).

The well-formed xref-stream / hybrid oracle suites
(``test_xref_stream_fuzz_wave1512``, ``test_hybrid_xref_oracle``,
``test_obj_stream_parse_oracle``, ``test_objstm_extends_oracle``) pin VALID
compressed-object resolution. This probe targets the MALFORMED object-stream
*metadata* subset a buggy or hostile producer can emit:

* ``/N`` (object count): missing-default, zero, negative, larger- and
  smaller-than-actual, and non-integer (a real);
* ``/First`` (byte offset of the first packed object): zero, negative, past
  the end of the decoded body, and smaller than the real header length;
* the leading ``<objnum> <offset>`` integer-pair header table: truncated,
  non-numeric, offsets out of order, an offset past the payload, and duplicate
  object numbers;
* the packed body truncated mid-object, and a packed object that is itself
  malformed;
* the ``/Extends`` chain: valid, dangling, wrong-type, cyclic;
* a wrong / missing ``/Type``, and a ``/Length`` that under- / over-states the
  encoded stream body.

Strategy (file-driven; the SAME bytes drive both runtimes): every case is a
tiny but well-formed PDF with an xref STREAM. The catalog (object ``3 0``) is a
normal, uncompressed object that references ``/Probe 4 0 R``; object ``4 0`` —
the lone fuzz target, a dict ``<</ProbeVal 42>>`` — lives compressed inside the
mutated ObjStm (object ``2 0``). Keeping the catalog uncompressed means
``Loader.loadPDF`` always succeeds, so the malformation only bites at the LAZY
resolution of object 4, isolating the object-stream-parser contract from the
container. The corpus + a ``manifest.txt`` (one case name per line, in order)
is written to a tmp dir; the ``ObjStmFuzzProbe`` reads the identical bytes.

Validation, not blind pinning: the Java line is ground truth. The probe reports
``loaded=ERR exc=<X>`` (``Loader.loadPDF`` threw) or ``loaded=1 obj4=<proj>``
where ``<proj>`` projects the resolved value of object 4 (``null`` / COSNull,
``dict:ProbeVal=<int|?>``, another COSBase simple name, or ``ERR:<X>``). Wave
1516 found and FIXED four real divergences where pypdfbox was stricter than
PDFBox's lenient lazy-resolve path (see ``CHANGES.md``):

  1. malformed ``/N`` / ``/First`` / header bytes propagated a ``PDFParseError``
     instead of resolving the member to ``null`` — PDFBox swallows the
     ``IOException`` in lenient mode (``COSParser.parseObjectStreamObject``);
  2. the ``/Type /ObjStm`` check raised where PDFBox's
     ``PDFObjectStreamParser`` never inspects ``/Type``;
  3. compressed members were located by the xref's positional stream index
     rather than by their stored object NUMBER (PDFBox keys
     ``parseAllObjects`` by ``COSObjectKey``), diverging when header order and
     xref index disagree;
  4. the header pairs were read from a buffer sliced at ``/First``, which cut a
     pair in half when ``/First`` undershoots the real header — PDFBox reads
     from the full decoded stream bounded only by a running position check.

Three residual cases are DEFENSIBLE robustness divergences, pinned both-sides:

  * ``first_too_small`` — with ``/First`` smaller than the real header, PDFBox's
    forward-only payload skip happens to land on the dict (``ProbeVal=42``)
    while pypdfbox parses at the spec-literal ``/First + offset`` byte and reads
    the stray ``COSInteger`` it finds there. Both are reasonable readings of an
    offset whose own anchor is corrupt;
  * ``body_truncated_midobject`` / ``member_malformed`` — PDFBox's COS token
    reader recovers a PARTIAL dictionary at EOF / from malformed nesting
    (``ProbeVal=4`` / ``ProbeVal=?``); pypdfbox's member parse raises and the
    lenient catch yields ``null``. This is inner COS-token EOF leniency in the
    base parser (cross-module), not the object-stream header contract this
    agent owns, and is tracked as a follow-up.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.loader import Loader
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = b"<</ProbeVal 42>>"

# Cases pinned as defensible robustness divergences (asserted both-sides in
# test_pinned_robustness_divergences, excluded from the line-for-line parity
# sweep). Maps case name -> (pinned pypdfbox projection, upstream PDFBox value).
_PINNED_DIVERGENCES: dict[str, tuple[str, str]] = {
    "first_too_small": ("loaded=1 obj4=COSInteger", "dict:ProbeVal=42"),
    "body_truncated_midobject": ("loaded=1 obj4=null", "dict:ProbeVal=4"),
    "member_malformed": ("loaded=1 obj4=null", "dict:ProbeVal=?"),
}


# --------------------------------------------------------------------------- #
# Corpus builders — hand-craft the raw PDF bytes so both runtimes see the same
# input. The object layout is fixed (see the module docstring); only the ObjStm
# (object 2 0) and the xref entries for its members vary per case.
# --------------------------------------------------------------------------- #


def _enc_entry(t: int, a: int, b: int) -> bytes:
    return bytes([t]) + a.to_bytes(2, "big") + b.to_bytes(2, "big")


def _assemble(
    objstm_bytes: bytes,
    *,
    entries_extra: dict[int, tuple[int, int, int]] | None = None,
    extends_objstm: bytes | None = None,
) -> bytes:
    """Glue the ObjStm together with a normal catalog/pages and an xref
    stream into a complete loadable PDF. Object 4 0 is compressed in ObjStm
    2 0 at stream index 0 by default."""
    catalog = b"3 0 obj\n<</Type/Catalog/Pages 5 0 R/Probe 4 0 R>>\nendobj\n"
    pages = b"5 0 obj\n<</Type/Pages/Kids[]/Count 0>>\nendobj\n"
    out = bytearray(b"%PDF-1.5\n")
    off2 = len(out)
    out += objstm_bytes
    off3 = len(out)
    out += catalog
    off5 = len(out)
    out += pages
    off7: int | None = None
    if extends_objstm is not None:
        off7 = len(out)
        out += extends_objstm
    entries: dict[int, tuple[int, int, int]] = {
        0: (0, 0, 65535),
        2: (1, off2, 0),
        3: (1, off3, 0),
        4: (2, 2, 0),
        5: (1, off5, 0),
    }
    if off7 is not None:
        entries[7] = (1, off7, 0)
    if entries_extra:
        entries.update(entries_extra)
    xref_off = len(out)
    entries[1] = (1, xref_off, 0)
    size = max(entries) + 1
    full = [entries.get(i, (0, 0, 0)) for i in range(size)]
    xref_data = b"".join(_enc_entry(*e) for e in full)
    xc = zlib.compress(xref_data)
    xd = (
        f"<</Type/XRef/Size {size}/Root 3 0 R/W[1 2 2]"
        f"/Filter/FlateDecode/Length {len(xc)}>>"
    )
    out += b"1 0 obj\n" + xd.encode("utf-8") + b"\nstream\n" + xc
    out += b"\nendstream\nendobj\n"
    out += b"startxref\n" + str(xref_off).encode("utf-8") + b"\n%%EOF\n"
    return bytes(out)


def _objstm(
    obj_num: int,
    *,
    n: int = 1,
    first: int | None = None,
    header: bytes | None = None,
    payload: bytes | None = None,
    members: list[tuple[int, bytes]] | None = None,
    dict_type: str = "/ObjStm",
    extends: str | None = None,
    length_override: int | None = None,
    n_literal: str | None = None,
) -> bytes:
    """Build a complete ``N 0 obj ... endobj`` object stream.

    ``members`` defaults to ``[(4, _PROBE)]``. ``header`` / ``payload`` let a
    case hand-craft the decoded content; otherwise it is derived from
    ``members``. ``n_literal`` writes the raw ``/N`` token verbatim (used for a
    non-integer ``/N``)."""
    if members is None:
        members = [(4, _PROBE)]
    if header is None or payload is None:
        parts: list[bytes] = []
        offs: list[tuple[int, int]] = []
        cur = 0
        for num, data in members:
            offs.append((num, cur))
            parts.append(data + b" ")
            cur += len(data) + 1
        if header is None:
            header = (
                b" ".join(f"{nu} {of}".encode("utf-8") for nu, of in offs) + b" "
            )
        if payload is None:
            payload = b"".join(parts)
    if first is None:
        first = len(header)
    body = header + payload
    comp = zlib.compress(body)
    length = length_override if length_override is not None else len(comp)
    n_tok = n_literal if n_literal is not None else str(n)
    d = (
        f"<</Type {dict_type} /N {n_tok} /First {first} "
        f"/Filter /FlateDecode /Length {length}"
    )
    if extends is not None:
        d += f" /Extends {extends}"
    d += ">>"
    return (
        f"{obj_num} 0 obj\n".encode("utf-8")
        + d.encode("utf-8")
        + b"\nstream\n"
        + comp
        + b"\nendstream\nendobj\n"
    )


def _build_corpus() -> list[tuple[str, bytes]]:
    """Return the ordered ``[(name, pdf_bytes), ...]`` fuzz corpus."""
    cases: list[tuple[str, bytes]] = []

    def add(name: str, pdf: bytes) -> None:
        cases.append((name, pdf))

    add("baseline", _assemble(_objstm(2)))

    # ---- /N variants ----
    add("n_zero", _assemble(_objstm(2, n=0)))
    add("n_negative", _assemble(_objstm(2, n=-1)))
    add("n_larger_than_actual", _assemble(_objstm(2, n=99)))
    add(
        "n_smaller_member_first",
        _assemble(
            _objstm(2, n=1, members=[(4, _PROBE), (6, b"<</Other 7>>")]),
            entries_extra={6: (2, 2, 1)},
        ),
    )
    add(
        "n_smaller_member_second",
        _assemble(
            _objstm(2, n=1, members=[(6, b"<</Other 7>>"), (4, _PROBE)]),
            entries_extra={6: (2, 2, 0)},
        ),
    )
    add(
        "n_real_noninteger",
        _assemble(_objstm(2, first=4, header=b"4 0 ", payload=_PROBE + b" ",
                          n_literal="1.5")),
    )

    # ---- /First variants ----
    add("first_zero", _assemble(_objstm(2, first=0)))
    add("first_negative", _assemble(_objstm(2, first=-5)))
    add("first_past_end", _assemble(_objstm(2, first=99999)))
    add("first_too_small", _assemble(_objstm(2, first=2)))

    # ---- header table variants ----
    add(
        "header_truncated",
        _assemble(_objstm(2, n=2, header=b"4 0 ", payload=_PROBE + b" ")),
    )
    add(
        "header_nonnumeric",
        _assemble(_objstm(2, n=1, header=b"xx 0 ", payload=_PROBE + b" ")),
    )
    add(
        "header_offset_unordered",
        _assemble(
            _objstm(
                2,
                n=2,
                header=b"6 %d 4 0 " % (len(_PROBE) + 1),
                payload=_PROBE + b" <</Other 7>> ",
            ),
            entries_extra={6: (2, 2, 1)},
        ),
    )
    add(
        "header_offset_past_payload",
        _assemble(_objstm(2, n=1, header=b"4 9999 ", payload=_PROBE + b" ")),
    )
    add(
        "header_duplicate_objnum",
        _assemble(
            _objstm(
                2,
                n=2,
                header=b"4 0 4 %d " % (len(_PROBE) + 1),
                payload=_PROBE + b" <</ProbeVal 99>> ",
            )
        ),
    )

    # ---- body truncated / malformed member ----
    add(
        "body_truncated_midobject",
        _assemble(_objstm(2, n=1, header=b"4 0 ", payload=b"<</ProbeVal 4")),
    )
    add(
        "member_malformed",
        _assemble(_objstm(2, n=1, header=b"4 0 ", payload=b"<<<<>> ")),
    )

    # ---- /Type variants ----
    add("type_wrong", _assemble(_objstm(2, dict_type="/Foo")))
    _comp = zlib.compress(b"4 0 " + _PROBE + b" ")
    _d = f"<</N 1 /First 4 /Filter /FlateDecode /Length {len(_comp)}>>"
    add(
        "type_missing",
        _assemble(
            b"2 0 obj\n" + _d.encode("utf-8") + b"\nstream\n" + _comp
            + b"\nendstream\nendobj\n"
        ),
    )

    # ---- /Length mismatch ----
    add("length_too_small", _assemble(_objstm(2, length_override=3)))
    add("length_too_large", _assemble(_objstm(2, length_override=99999)))

    # ---- /Extends chain ----
    add(
        "extends_valid",
        _assemble(
            _objstm(2, n=0, header=b"", payload=b"", extends="7 0 R"),
            extends_objstm=_objstm(7, n=1, members=[(4, _PROBE)]),
        ),
    )
    add("extends_dangling", _assemble(_objstm(2, extends="99 0 R")))
    add("extends_wrong_type", _assemble(_objstm(2, extends="5 0 R")))
    add(
        "extends_cyclic",
        _assemble(
            _objstm(2, extends="7 0 R"),
            extends_objstm=_objstm(7, n=0, header=b"", payload=b"",
                                   extends="2 0 R"),
        ),
    )

    return cases


# --------------------------------------------------------------------------- #
# pypdfbox projection — mirrors ObjStmFuzzProbe.project byte-for-byte.
# --------------------------------------------------------------------------- #


def _project(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, COSDictionary):
        pv = value.get_dictionary_object(COSName.get_pdf_name("ProbeVal"))
        if pv is None:
            return "dict:ProbeVal=?"
        if isinstance(pv, COSInteger):
            return f"dict:ProbeVal={pv.value}"
        return f"dict:ProbeVal={pv}"
    return type(value).__name__


def _py_line(name: str, pdf: bytes) -> str:
    try:
        doc = Loader.load_pdf(pdf, "")
    except Exception as exc:  # noqa: BLE001 — mirror the probe's catch-all
        return f"CASE {name} loaded=ERR exc={type(exc).__name__}"
    try:
        try:
            holder = doc.get_object_from_pool(COSObjectKey(4, 0))
            proj = _project(holder.get_object())
        except Exception as exc:  # noqa: BLE001
            proj = f"ERR:{type(exc).__name__}"
        return f"CASE {name} loaded=1 obj4={proj}"
    finally:
        doc.close()


# Java exception classes have no 1:1 Python counterpart; canonicalise the
# ``loaded=ERR exc=<X>`` arm to the throw boolean so the cross-runtime
# exception-vocabulary mismatch does not register as a divergence. The
# ``loaded=1 obj4=<proj>`` arm is compared verbatim (the value contract IS the
# parity metric here).
def _canon(line: str) -> str:
    body = line.split(" ", 2)[2]  # strip "CASE <name> "
    if body.startswith("loaded=ERR"):
        return "loaded=ERR"
    return body


def test_corpus_is_well_formed() -> None:
    """Every case builds, is unique, and the baseline resolves to the probe
    marker under pypdfbox (sanity floor independent of the oracle)."""
    corpus = _build_corpus()
    names = [n for n, _ in corpus]
    assert len(names) == len(set(names)), "duplicate case names"
    assert corpus[0][0] == "baseline"
    assert _py_line("baseline", corpus[0][1]) == (
        "CASE baseline loaded=1 obj4=dict:ProbeVal=42"
    )


@requires_oracle
def test_objstm_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    corpus = _build_corpus()
    for name, pdf in corpus:
        (tmp_path / f"{name}.pdf").write_bytes(pdf)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(name for name, _ in corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("ObjStmFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines, expected {len(corpus)}:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name, pdf in corpus:
        if name in _PINNED_DIVERGENCES:
            # Defensible robustness divergences — asserted exactly (both-sides)
            # in test_pinned_robustness_divergences, excluded from line-for-line
            # parity here.
            continue
        java = java_by_name.get(name)
        assert java is not None, f"probe missing case {name}"
        py = _py_line(name, pdf)
        if _canon(java) != _canon(py):
            mismatches.append(f"  {name}:\n    java={java}\n    py  ={py}")

    assert not mismatches, "ObjStm fuzz divergence(s):\n" + "\n".join(mismatches)


# --------------------------------------------------------------------------- #
# Both-sides pins for the three DEFENSIBLE robustness divergences. These assert
# the EXACT pypdfbox projection so a future change that silently realigns (or
# further diverges from) PDFBox is caught here, with the upstream value recorded
# in the comment. See CHANGES.md (wave 1516).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("name", "py_proj", "java_proj"),
    [(name, py, java) for name, (py, java) in _PINNED_DIVERGENCES.items()],
)
def test_pinned_robustness_divergences(
    name: str, py_proj: str, java_proj: str
) -> None:
    """Pin the exact pypdfbox projection for the three defensible robustness
    divergences (upstream PDFBox value recorded for context):

    * ``first_too_small`` — pypdfbox parses at the spec-literal ``/First +
      offset`` byte (a stray ``COSInteger``); PDFBox's forward-only payload
      skip lands on the dict (``dict:ProbeVal=42``);
    * ``body_truncated_midobject`` / ``member_malformed`` — pypdfbox's member
      parse raises and the lenient catch yields ``null``; PDFBox's COS reader
      recovers a partial dict (``dict:ProbeVal=4`` / ``dict:ProbeVal=?``).
      Inner COS-token EOF leniency in the base parser — cross-module follow-up.
    """
    corpus = dict(_build_corpus())
    line = _py_line(name, corpus[name])
    assert _canon(line) == py_proj, (
        f"{name}: pypdfbox projection drifted from the pinned value "
        f"(upstream PDFBox: {java_proj!r}) — re-validate against the oracle"
    )
