"""Differential fuzz audit for signature-dictionary read / parse leniency vs
Apache PDFBox 3.0.7 (wave 1517, agent E). READ / PARSE path only — no
cryptographic verification.

Complements the well-formed signature parity suites (round-trip field
accessors, byte-range arithmetic of a genuinely signed PDF) — none of which
exercise the MALFORMED subset this audit targets:

* ``get_byte_range()``: absent; odd length; 2 / 6 entries; an element that is a
  float (truncated via ``intValue()``); a non-number element (substituted with
  ``-1``); negative values; an empty array.
* ``get_contents()``: absent / a ``COSString`` (hex or literal) / a wrong type
  (``COSName``, ``COSInteger``, ``COSArray``) — wrong type yields empty.
* ``get_signed_content(bytes)``: the monotonic-cursor ``COSFilterInputStream``
  stitch over the document's own bytes for in-bounds, out-of-bounds,
  overlapping and out-of-order ranges, plus odd-length ranges.
* ``get_contents_from_bytes(bytes)``: the ``begin = a+b+1``,
  ``len = c-begin-1`` hex-window arithmetic and its ``<...>`` delimiter strip.
* identity accessors ``get_filter`` ``get_sub_filter`` ``get_name``
  ``get_reason`` — name vs string storage, wrong types, absent.

Both sides are driven on the SAME bytes: the corpus builder writes a one-page
PDF per case whose document catalog carries the mutated signature dictionary
under the custom key ``/SigProbe``, plus a ``manifest.txt`` (one case name per
line, in order) into a tmp dir. The Java probe
(``oracle/probes/SigDictFuzzProbe.java``) loads each ``<case>.pdf``, reads the
catalog ``/SigProbe`` entry, wraps it in ``new PDSignature(dict)`` and projects
a stable framed line over the document's own raw bytes; this module reads the
exact same files and projects the identical grammar through pypdfbox, then
asserts line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> br=<csv|empty> contents=<hex|empty> filter=<v|null>
        subfilter=<v|null> name=<v|null> reason=<v|null>
        signed=<len|ERR:Exc> window=<hex|ERR:Exc>

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/interactive/digitalsignature/pd_signature.py``; a defensible
divergence is pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_SIG_PROBE = _N("SigProbe")


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _ints(*vals: int) -> COSArray:
    return _arr(*(COSInteger(v) for v in vals))


def _hexstr(data: bytes) -> COSString:
    s = COSString(data)
    s.set_force_hex_form(True)
    return s


# --------------------------------------------------------------------- corpus


def _build_corpus() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def sig(**items: COSBase) -> COSDictionary:
        d = COSDictionary()
        d.set_item(_N("Type"), _N("Sig"))
        for k, v in items.items():
            d.set_item(_N(k), v)
        return d

    # ----- /ByteRange shape corners ----------------------------------------
    cases["br_absent"] = sig()
    cases["br_empty_array"] = sig(ByteRange=_arr())
    cases["br_well_formed"] = sig(ByteRange=_ints(0, 10, 30, 20))
    cases["br_two_entries"] = sig(ByteRange=_ints(0, 10))
    cases["br_six_entries"] = sig(ByteRange=_ints(0, 5, 10, 5, 20, 5))
    cases["br_odd_three"] = sig(ByteRange=_ints(0, 10, 30))
    cases["br_odd_one"] = sig(ByteRange=_ints(0))
    cases["br_float_element"] = sig(
        ByteRange=_arr(COSInteger(0), COSFloat(10.9), COSInteger(30), COSInteger(20))
    )
    cases["br_name_element"] = sig(
        ByteRange=_arr(COSInteger(0), _N("Bad"), COSInteger(30), COSInteger(20))
    )
    cases["br_string_element"] = sig(
        ByteRange=_arr(
            COSInteger(0), COSString("10"), COSInteger(30), COSInteger(20)
        )
    )
    cases["br_negative"] = sig(ByteRange=_ints(0, 10, -5, 20))
    cases["br_all_negative"] = sig(ByteRange=_ints(-1, -1, -1, -1))
    cases["br_not_an_array"] = sig(ByteRange=COSInteger(7))
    cases["br_name_value"] = sig(ByteRange=_N("Whoops"))

    # ----- /Contents shape corners -----------------------------------------
    cases["contents_absent"] = sig()
    cases["contents_hex"] = sig(Contents=_hexstr(b"\xde\xad\xbe\xef"))
    cases["contents_literal"] = sig(Contents=COSString(b"abc"))
    cases["contents_empty"] = sig(Contents=COSString(b""))
    cases["contents_name_wrong_type"] = sig(Contents=_N("notastring"))
    cases["contents_int_wrong_type"] = sig(Contents=COSInteger(5))
    cases["contents_array_wrong_type"] = sig(Contents=_ints(1, 2, 3))

    # ----- identity accessors: name vs string, wrong type ------------------
    cases["filter_as_name"] = sig(Filter=_N("Adobe.PPKLite"))
    cases["filter_as_string"] = sig(Filter=COSString("Adobe.PPKLite"))
    cases["subfilter_as_name"] = sig(SubFilter=_N("adbe.pkcs7.detached"))
    cases["name_string"] = sig(Name=COSString("Jane Doe"))
    cases["name_wrong_type_name"] = sig(Name=_N("nope"))
    cases["reason_string"] = sig(Reason=COSString("I approve"))
    cases["reason_wrong_type_int"] = sig(Reason=COSInteger(9))

    # ----- getSignedContent / getContents(byte[]) windows ------------------
    # In-bounds: two small ranges over the file's own bytes.
    cases["window_inbounds"] = sig(
        ByteRange=_ints(0, 8, 40, 8), Contents=_hexstr(b"\x01\x02")
    )
    # Range overruns the file (large second length).
    cases["window_overrun"] = sig(
        ByteRange=_ints(0, 8, 40, 10_000_000), Contents=_hexstr(b"\x01\x02")
    )
    # Overlapping / out-of-order: second range starts BEFORE first ends.
    cases["window_overlap"] = sig(
        ByteRange=_ints(0, 50, 10, 50), Contents=_hexstr(b"\x01\x02")
    )
    # Out-of-order: second range entirely before first.
    cases["window_reversed"] = sig(
        ByteRange=_ints(60, 10, 0, 10), Contents=_hexstr(b"\x01\x02")
    )
    # Odd-length range used by getSignedContent (length/2 pairing drops last).
    cases["window_odd_three"] = sig(
        ByteRange=_ints(0, 8, 40), Contents=_hexstr(b"\x01\x02")
    )
    # Negative start.
    cases["window_neg_start"] = sig(
        ByteRange=_ints(-4, 8, 40, 8), Contents=_hexstr(b"\x01\x02")
    )
    # Zero-length ranges.
    cases["window_zero_len"] = sig(
        ByteRange=_ints(0, 0, 0, 0), Contents=_hexstr(b"\x01\x02")
    )
    # Second range overruns the file end (start in-bounds, len too big).
    cases["window_len_overruns"] = sig(
        ByteRange=_ints(0, 4, 8, 20), Contents=_hexstr(b"\x01\x02")
    )
    # Second range start lands at file end + tiny len (skip-past-EOF).
    cases["window_start_past_end"] = sig(
        ByteRange=_ints(0, 4, 50, 1), Contents=_hexstr(b"\x01\x02")
    )
    # /Contents window arithmetic where br[2] is far past EOF: the clamping
    # ByteArrayInputStream reads only the bytes that exist.
    cases["window_br2_past_eof"] = sig(
        ByteRange=_ints(0, 10, 99999, 10), Contents=_hexstr(b"\x01\x02")
    )

    return cases


def _write_case_pdf(path: Path, sig_dict: COSDictionary) -> None:
    """Build a one-page PDF whose catalog carries ``sig_dict`` under
    ``/SigProbe``."""
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.get_document_catalog().get_cos_object().set_item(_SIG_PROBE, sig_dict)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _nz(s: str | None) -> str:
    return "null" if s is None else s


def _hex(b: bytes | None) -> str:
    # pypdfbox returns ``None`` where upstream returns an empty array (a
    # documented Pythonic null-sentinel divergence). Project ``None`` as
    # "empty" so it lines up with upstream's zero-length-array projection.
    if b is None or len(b) == 0:
        return "empty"
    return b.hex()


def _java_exc(exc: Exception) -> str:
    """Map a pypdfbox exception to the Java exception simple-name the probe
    reports for the same failure."""
    if isinstance(exc, IndexError):
        return "IndexOutOfBoundsException"
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _normalize(line: str) -> str:
    """Collapse Java's index-out-of-bounds subclass spelling onto the family
    name. Python's single :class:`IndexError` cannot distinguish
    ``ArrayIndexOutOfBoundsException`` (the specific ``int[]`` index access in
    ``getContents``) from its supertype ``IndexOutOfBoundsException``; both are
    the same out-of-range error, so the comparison treats them as equal."""
    return line.replace(
        "ArrayIndexOutOfBoundsException", "IndexOutOfBoundsException"
    )


def _br_str(sig: PDSignature) -> str:
    br = sig.get_byte_range()
    if not br:
        return "empty"
    return ",".join(str(int(x)) for x in br)


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    doc = PDDocument.load(str(pdf))
    try:
        file_bytes = pdf.read_bytes()
        cat = doc.get_document_catalog()
        base = cat.get_cos_object().get_dictionary_object(_SIG_PROBE)
        sig = PDSignature(base)

        out = prefix + f"br={_br_str(sig)}"
        out += f" contents={_hex(sig.get_contents())}"
        out += f" filter={_nz(sig.get_filter())}"
        out += f" subfilter={_nz(sig.get_sub_filter())}"
        out += f" name={_nz(sig.get_name())}"
        out += f" reason={_nz(sig.get_reason())}"

        try:
            signed = str(len(sig.get_signed_content(file_bytes)))
        except Exception as e:  # noqa: BLE001
            signed = f"ERR:{_java_exc(e)}"
        out += f" signed={signed}"

        try:
            window = _hex(sig.get_contents_from_bytes(file_bytes))
        except Exception as e:  # noqa: BLE001
            window = f"ERR:{_java_exc(e)}"
        out += f" window={window}"
        return out
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
# Defensible divergences pinned here so a future re-run still asserts BOTH
# sides' observed values. Each carries a matching CHANGES.md row (wave 1517).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_sig_dict_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated signature dictionary parses identically on pypdfbox and
    Apache PDFBox 3.0.7: same /ByteRange array, same /Contents bytes, same
    identity accessors, same signed-content length and same /Contents hex
    window over the document's own bytes. Divergences are pinned in
    ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for cname, sig_dict in corpus.items():
        _write_case_pdf(tmp_path / f"{cname}.pdf", sig_dict)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("SigDictFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for cname in corpus:
        py = _normalize(_python_line(tmp_path, cname))
        java = _normalize(java_by_name.get(cname, "<missing>"))
        if cname in _PINNED:
            py_override, java_override, _reason = _PINNED[cname]
            if py != py_override:
                mismatches.append(
                    f"{cname}: pinned-py drift\n  expected {py_override}\n"
                    f"  actual   {py}"
                )
            if java != java_override:
                mismatches.append(
                    f"{cname}: pinned-java drift\n  expected {java_override}\n"
                    f"  actual   {java}"
                )
            continue
        if py != java:
            mismatches.append(f"{cname}:\n  java {java}\n  py   {py}")

    assert not mismatches, "signature-dict fuzz divergences:\n" + "\n".join(
        mismatches
    )
