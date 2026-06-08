"""Differential fuzz audit for :class:`PDDocumentInformation` (the trailer
``/Info`` dictionary) accessor leniency over a MALFORMED Info dict vs Apache
PDFBox 3.0.7 (wave 1516, agent E).

Complements the well-formed info-accessor oracle suite
(``test_info_accessor_round_trip_oracle``, ``test_info_xmp_oracle``,
``test_metadata_oracle``) — none of which exercise the mistyped / malformed
``/Info`` subset this audit targets:

* ``/Title`` ``/Author`` ``/Subject`` ``/Keywords`` ``/Creator`` ``/Producer``
  as a string (spec form) vs a name vs a wrong type (number / array / dict) vs
  missing — the accessors delegate to ``COSDictionary.get_string``, which
  accepts ONLY a COSString and returns ``None`` for a name / number / array /
  dict / absent entry;
* ``/CreationDate`` ``/ModDate`` as a valid PDF date string
  (``D:20240101120000+05'00'``), a partial date, a malformed date, a non-string
  (number / name), and missing — ``get_creation_date`` /
  ``get_modification_date`` delegate to ``COSDictionary.get_date`` -> the
  faithful DateConverter port (lenient parse; ``None`` for a non-COSString or
  an unparseable date);
* ``/Trapped`` name enum (``/True`` / ``/False`` / ``/Unknown`` / unknown name
  / as a COSString / wrong type / missing) — ``get_trapped`` delegates to
  ``COSDictionary.get_name_as_string``, which accepts a COSName OR a COSString
  and returns ``None`` otherwise;
* custom metadata (``get_custom_metadata_value`` / ``get_metadata_keys``)
  including a custom key colliding with a standard one and a non-string custom
  value.

Both sides are driven on the SAME bytes: the corpus builder mutates the trailer
``/Info`` dictionary of a one-page document so the saved PDF's Info dict IS the
fuzzed dict, writes one ``<case>.pdf`` per case plus a ``manifest.txt`` into a
tmp dir. The Java probe (``oracle/probes/DocInfoFuzzProbe.java``) loads each
``<case>.pdf`` and projects a stable framed line; this module reads the exact
same files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> title=<str|null|ERR:X> author=<str|null|ERR:X>
        producer=<str|null|ERR:X> creationdate=<epochMillis|null|ERR:X>
        moddate=<epochMillis|null|ERR:X> trapped=<str|null|ERR:X>
        customkeys=<k1,k2,...|-> custom_Foo=<str|null|ERR:X>
        custom_Title=<str|null|ERR:X>

The date cells report UTC epoch milliseconds (``getTimeInMillis()`` on the Java
side; ``datetime.timestamp() * 1000`` on the Python side) so a timezone-aware
date compares numerically regardless of how each stack models the zone.

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/pd_document_information.py``; a defensible divergence is
pinned in ``_PINNED`` with a matching CHANGES.md row.
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
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name

_VALID_DATE = "D:20240101120000+05'00'"


# --------------------------------------------------------------------- corpus
#
# Each entry is a callable that mutates the trailer /Info dictionary in place.


def _set(info: COSDictionary, key: str, value: COSBase) -> None:
    info.set_item(_N(key), value)


def _build_corpus() -> dict[str, object]:
    c: dict[str, object] = {}

    # ---- bare Info dict: every probed entry absent ----
    c["bare_info"] = lambda info: None

    # ---- string fields as the spec COSString form ----
    c["title_string"] = lambda info: _set(info, "Title", COSString("My Title"))
    c["author_string"] = lambda info: _set(info, "Author", COSString("Jane"))
    c["producer_string"] = lambda info: _set(
        info, "Producer", COSString("pypdfbox")
    )
    c["subject_string"] = lambda info: _set(
        info, "Subject", COSString("Topic")
    )
    c["keywords_string"] = lambda info: _set(
        info, "Keywords", COSString("a,b,c")
    )
    c["creator_string"] = lambda info: _set(
        info, "Creator", COSString("Editor")
    )

    # ---- string fields as a NAME (lenient? -> getString rejects) ----
    c["title_is_name"] = lambda info: _set(info, "Title", _N("MyTitle"))
    c["author_is_name"] = lambda info: _set(info, "Author", _N("Jane"))
    c["producer_is_name"] = lambda info: _set(info, "Producer", _N("Prod"))

    # ---- string fields as wrong types (number / array / dict) ----
    c["title_is_number"] = lambda info: _set(info, "Title", COSInteger(42))
    c["title_is_array"] = lambda info: _set(info, "Title", COSArray())
    c["title_is_dict"] = lambda info: _set(info, "Title", COSDictionary())
    c["author_is_number"] = lambda info: _set(info, "Author", COSInteger(7))

    # ---- /CreationDate /ModDate: valid / partial / malformed / non-string ----
    c["creationdate_valid"] = lambda info: _set(
        info, "CreationDate", COSString(_VALID_DATE)
    )
    c["moddate_valid"] = lambda info: _set(
        info, "ModDate", COSString(_VALID_DATE)
    )
    c["creationdate_partial_ym"] = lambda info: _set(
        info, "CreationDate", COSString("D:202403")
    )
    c["creationdate_no_prefix"] = lambda info: _set(
        info, "CreationDate", COSString("20240101120000Z")
    )
    c["creationdate_malformed"] = lambda info: _set(
        info, "CreationDate", COSString("not a date")
    )
    c["creationdate_empty"] = lambda info: _set(
        info, "CreationDate", COSString("")
    )
    c["creationdate_leap_second"] = lambda info: _set(
        info, "CreationDate", COSString("D:20240101235960Z")
    )
    c["creationdate_is_number"] = lambda info: _set(
        info, "CreationDate", COSInteger(20240101)
    )
    c["creationdate_is_name"] = lambda info: _set(
        info, "CreationDate", _N("D:20240101")
    )

    # ---- /Trapped name enum + lenient COSString + wrong type ----
    c["trapped_true"] = lambda info: info.set_item(_N("Trapped"), _N("True"))
    c["trapped_false"] = lambda info: info.set_item(_N("Trapped"), _N("False"))
    c["trapped_unknown"] = lambda info: info.set_item(
        _N("Trapped"), _N("Unknown")
    )
    c["trapped_unknown_name"] = lambda info: info.set_item(
        _N("Trapped"), _N("Maybe")
    )
    c["trapped_as_string"] = lambda info: _set(
        info, "Trapped", COSString("True")
    )
    c["trapped_is_number"] = lambda info: _set(
        info, "Trapped", COSInteger(1)
    )
    c["trapped_is_array"] = lambda info: _set(info, "Trapped", COSArray())

    # ---- custom metadata: plain, colliding-with-standard, non-string value ----
    c["custom_plain"] = lambda info: _set(info, "Foo", COSString("bar"))
    c["custom_and_standard"] = _custom_and_standard
    c["custom_value_is_number"] = lambda info: _set(
        info, "Foo", COSInteger(99)
    )
    c["custom_value_is_name"] = lambda info: _set(info, "Foo", _N("baz"))
    c["custom_collide_title_string"] = lambda info: _set(
        info, "Title", COSString("via custom")
    )

    # ---- a fully populated, well-formed Info dict (sanity baseline) ----
    c["full_well_formed"] = _full_well_formed

    return c


def _custom_and_standard(info: COSDictionary) -> None:
    """A custom key alongside a standard one — exercises the sorted
    ``getMetadataKeys()`` union."""
    info.set_item(_N("Title"), COSString("T"))
    info.set_item(_N("Author"), COSString("A"))
    info.set_item(_N("Foo"), COSString("bar"))
    info.set_item(_N("Zeta"), COSString("z"))


def _full_well_formed(info: COSDictionary) -> None:
    info.set_item(_N("Title"), COSString("Title"))
    info.set_item(_N("Author"), COSString("Author"))
    info.set_item(_N("Subject"), COSString("Subject"))
    info.set_item(_N("Keywords"), COSString("kw"))
    info.set_item(_N("Creator"), COSString("Creator"))
    info.set_item(_N("Producer"), COSString("Producer"))
    info.set_item(_N("CreationDate"), COSString(_VALID_DATE))
    info.set_item(_N("ModDate"), COSString(_VALID_DATE))
    info.set_item(_N("Trapped"), _N("True"))
    info.set_item(_N("Foo"), COSString("custom"))


# --------------------------------------------------------------------- corpus io


def _write_case_pdf(path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        info = doc.get_document_information().get_cos_object()
        mutate(info)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _exc(e: Exception) -> str:
    if isinstance(e, OSError):
        return "ERR:IOException"
    return f"ERR:{type(e).__name__}"


def _str_cell(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        v = fn()
        return "null" if v is None else v
    except Exception as e:  # noqa: BLE001 — mirror the probe's catch-all
        return _exc(e)


def _date_cell(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        v = fn()
        if v is None:
            return "null"
        # Java reports getTimeInMillis() (UTC epoch millis). A timezone-aware
        # Python datetime's POSIX timestamp is the same instant; * 1000 to
        # millis, truncated to an int.
        return str(int(v.timestamp() * 1000))
    except Exception as e:  # noqa: BLE001
        return _exc(e)


def _keys_cell(info: PDDocumentInformation) -> str:
    try:
        keys = info.get_metadata_keys()  # already sorted
        return ",".join(keys) if keys else "-"
    except Exception as e:  # noqa: BLE001
        return _exc(e)


def _custom_cell(info: PDDocumentInformation, field: str) -> str:
    try:
        v = info.get_custom_metadata_value(field)
        return "null" if v is None else v
    except Exception as e:  # noqa: BLE001
        return _exc(e)


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001
        return prefix + f"LOAD:{type(e).__name__}"
    try:
        info = doc.get_document_information()
        return prefix + (
            f"title={_str_cell(info.get_title)} "
            f"author={_str_cell(info.get_author)} "
            f"producer={_str_cell(info.get_producer)} "
            f"creationdate={_date_cell(info.get_creation_date)} "
            f"moddate={_date_cell(info.get_modification_date)} "
            f"trapped={_str_cell(info.get_trapped)} "
            f"customkeys={_keys_cell(info)} "
            f"custom_Foo={_custom_cell(info, 'Foo')} "
            f"custom_Title={_custom_cell(info, 'Title')}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_doc_info_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed /Info dict resolves (or fails to resolve) identically on
    pypdfbox and Apache PDFBox 3.0.7: same per-accessor cell, same date epoch,
    same trapped enum, same sorted metadata-key union. Divergences are pinned
    explicitly in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, mutate in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", mutate)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("DocInfoFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in corpus:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, (
        "PDDocumentInformation accessor fuzz divergences:\n"
        + "\n".join(mismatches)
    )
