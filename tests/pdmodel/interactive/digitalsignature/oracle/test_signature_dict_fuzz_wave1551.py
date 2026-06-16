"""Differential fuzz audit for signature-dictionary IDENTITY + DATE accessors
vs Apache PDFBox 3.0.7 (wave 1551, agent E). READ / PARSE path only — no
cryptographic verification.

Deliberately disjoint from ``tests/pdmodel/test_sig_dict_fuzz_wave1517.py``,
which already pinned ``get_byte_range`` / ``get_contents`` /
``get_signed_content`` / ``get_contents_from_bytes`` and the
filter/subfilter/name/reason corners. This audit targets the accessors wave
1517 did NOT cover and adds the date-parse path:

* ``get_location()`` / ``get_contact_info()`` — string vs name storage, wrong
  types, absent. Both use ``COSDictionary.get_string`` upstream, so a
  ``COSName`` value yields ``None``.
* ``get_filter()`` / ``get_sub_filter()`` — wrong types (``COSInteger``,
  ``COSArray``), name vs string, absent. Both use ``get_name_as_string``, so a
  name OR a string coerces to text and a non-name/non-string yields ``None``.
* ``get_name()`` / ``get_reason()`` — name-stored, array, integer.
* ``get_sign_date()`` (Calendar parse) — well-formed, partial, malformed,
  name-stored, wrong-type and 60-second ``/M`` values; projected as the
  ``Calendar.getTimeInMillis()`` epoch-ms (UTC) or ``null``.

Both sides are driven on the SAME bytes: the corpus builder writes a one-page
PDF per case whose document catalog carries the mutated signature dictionary
under the custom key ``/SigProbe``, plus a ``manifest.txt`` (one case name per
line, in order) into a tmp dir. The Java probe
(``oracle/probes/SignatureDictFuzzProbe.java``) loads each ``<case>.pdf``, reads
the catalog ``/SigProbe`` entry, wraps it in ``new PDSignature(dict)`` and
projects a stable framed line; this module reads the exact same files and
projects the identical grammar through pypdfbox, then asserts line-for-line
parity.

Line grammar (one per case, manifest order)::

    CASE <name> filter=<v|null> subfilter=<v|null> name=<v|null>
        location=<v|null> reason=<v|null> contact=<v|null>
        signdate=<epochMs|null|ERR:Exc>

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


# --------------------------------------------------------------------- corpus


def _build_corpus() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def sig(**items: COSBase) -> COSDictionary:
        d = COSDictionary()
        d.set_item(_N("Type"), _N("Sig"))
        for k, v in items.items():
            d.set_item(_N(k), v)
        return d

    # ----- /Filter & /SubFilter: name vs string vs wrong type --------------
    cases["filter_name"] = sig(Filter=_N("Adobe.PPKLite"))
    cases["filter_string"] = sig(Filter=COSString("Adobe.PPKLite"))
    cases["filter_int_wrong"] = sig(Filter=COSInteger(3))
    cases["filter_array_wrong"] = sig(Filter=_arr(_N("a"), _N("b")))
    cases["filter_absent"] = sig()
    cases["subfilter_name"] = sig(SubFilter=_N("adbe.pkcs7.detached"))
    cases["subfilter_string"] = sig(SubFilter=COSString("ETSI.CAdES.detached"))
    cases["subfilter_int_wrong"] = sig(SubFilter=COSInteger(7))
    cases["subfilter_absent"] = sig()

    # ----- /Name & /Reason: getString ignores names -----------------------
    cases["name_string"] = sig(Name=COSString("Jane Doe"))
    cases["name_as_name_null"] = sig(Name=_N("Jane"))
    cases["name_int_null"] = sig(Name=COSInteger(1))
    cases["name_array_null"] = sig(Name=_arr(COSString("a")))
    cases["name_absent"] = sig()
    cases["reason_string"] = sig(Reason=COSString("I approve this document"))
    cases["reason_as_name_null"] = sig(Reason=_N("Approval"))
    cases["reason_int_null"] = sig(Reason=COSInteger(9))
    cases["reason_absent"] = sig()

    # ----- /Location: getString -------------------------------------------
    cases["location_string"] = sig(Location=COSString("Cupertino, CA"))
    cases["location_empty"] = sig(Location=COSString(""))
    cases["location_as_name_null"] = sig(Location=_N("Office"))
    cases["location_int_null"] = sig(Location=COSInteger(5))
    cases["location_absent"] = sig()

    # ----- /ContactInfo: getString ----------------------------------------
    cases["contact_string"] = sig(ContactInfo=COSString("jane@example.com"))
    cases["contact_as_name_null"] = sig(ContactInfo=_N("jane"))
    cases["contact_array_null"] = sig(ContactInfo=_arr(COSString("x")))
    cases["contact_absent"] = sig()

    # ----- /M sign date: DateConverter.toCalendar parse -------------------
    cases["date_full_offset"] = sig(M=COSString("D:20230115093045+02'00'"))
    cases["date_full_utc_z"] = sig(M=COSString("D:20230115093045Z"))
    cases["date_no_offset"] = sig(M=COSString("D:20230115093045"))
    cases["date_minutes_only"] = sig(M=COSString("D:202301150930"))
    cases["date_day_only"] = sig(M=COSString("D:20230115"))
    cases["date_year_month"] = sig(M=COSString("D:202301"))
    cases["date_year_only"] = sig(M=COSString("D:2023"))
    cases["date_no_d_prefix"] = sig(M=COSString("20230115093045+02'00'"))
    cases["date_negative_offset"] = sig(M=COSString("D:20230115093045-05'30'"))
    cases["date_sixty_seconds"] = sig(M=COSString("D:20230115093060Z"))
    cases["date_month_zero"] = sig(M=COSString("D:20230015093045Z"))
    cases["date_month_thirteen"] = sig(M=COSString("D:20231315093045Z"))
    cases["date_garbage"] = sig(M=COSString("not a date at all"))
    cases["date_empty"] = sig(M=COSString(""))
    cases["date_as_name_null"] = sig(M=_N("D:20230115"))
    cases["date_int_null"] = sig(M=COSInteger(20230115))
    cases["date_absent"] = sig()

    # ----- a fully populated, well-formed signature dict (sanity) ---------
    cases["full_well_formed"] = sig(
        Filter=_N("Adobe.PPKLite"),
        SubFilter=_N("adbe.pkcs7.detached"),
        Name=COSString("Jane Doe"),
        Location=COSString("Remote"),
        Reason=COSString("Approval"),
        ContactInfo=COSString("jane@example.com"),
        M=COSString("D:20240229120000+00'00'"),
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


def _date_str(sig: PDSignature) -> str:
    """Project ``get_sign_date_as_datetime()`` as the same epoch-ms the Java
    probe emits via ``Calendar.getTimeInMillis()`` (a single UTC instant), or
    ``"null"`` for an absent/unparseable ``/M``."""
    try:
        dt = sig.get_sign_date_as_datetime()
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"
    if dt is None:
        return "null"
    return str(int(dt.timestamp() * 1000))


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    doc = PDDocument.load(str(pdf))
    try:
        cat = doc.get_document_catalog()
        base = cat.get_cos_object().get_dictionary_object(_SIG_PROBE)
        sig = PDSignature(base)

        out = prefix + f"filter={_nz(sig.get_filter())}"
        out += f" subfilter={_nz(sig.get_sub_filter())}"
        out += f" name={_nz(sig.get_name())}"
        out += f" location={_nz(sig.get_location())}"
        out += f" reason={_nz(sig.get_reason())}"
        out += f" contact={_nz(sig.get_contact_info())}"
        out += f" signdate={_date_str(sig)}"
        return out
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
# Defensible divergences pinned here so a future re-run still asserts BOTH
# sides' observed values. Each carries a matching CHANGES.md row (wave 1551).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_signature_dict_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated signature dictionary parses identically on pypdfbox and
    Apache PDFBox 3.0.7: same filter/subfilter/name/location/reason/contact
    identity accessors and same ``/M`` Calendar-parse epoch instant. Divergences
    are pinned in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for cname, sig_dict in corpus.items():
        _write_case_pdf(tmp_path / f"{cname}.pdf", sig_dict)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("SignatureDictFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for cname in corpus:
        py = _python_line(tmp_path, cname)
        java = java_by_name.get(cname, "<missing>")
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
