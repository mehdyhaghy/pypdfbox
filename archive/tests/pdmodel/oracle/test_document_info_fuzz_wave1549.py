"""In-memory differential fuzz for :class:`PDDocumentInformation` (the trailer
``/Info`` dictionary) vs Apache PDFBox 3.0.7 (wave 1549, agent E).

Deliberately distinct from the file-based read-only ``test_doc_info_fuzz_wave1516``:
that sibling saves a one-page PDF whose trailer Info dict is the fuzzed dict and
reloads it (so save/reload normalises the raw COSString date and name forms).
This audit wraps ``PDDocumentInformation(cos_dict)`` directly with NO save/reload
round-trip — testing the wrapper layer in isolation — AND exercises the mutating
setters (``set_title``, ``set_creation_date``, ``set_trapped``,
``set_custom_metadata_value``) and re-reads the result.

Fuzz angles NOT covered by wave 1516:

* direct in-memory construction (no save/reload) so a COSString that happens to
  be a valid date string is read exactly as stored;
* the full string-field surface — ``Subject`` / ``Keywords`` / ``Creator``
  (1516 only projected title / author / producer);
* rich ``/CreationDate`` / ``/ModDate`` variants: negative TZ offset, ``Z``
  suffix, zero-offset apostrophe form, year-only, year-month, year-month-day,
  no-prefix, ISO-8601, leading whitespace, lowercase ``d:`` prefix;
* set/get round-trips: ``set_title`` -> ``get_title``, ``set_creation_date`` ->
  ``get_creation_date`` (epoch millis), ``set_trapped("True")`` ->
  ``get_trapped``, ``set_custom_metadata_value`` ->
  ``get_custom_metadata_value``, ``set_title(None)`` clears;
* ``set_trapped("garbage")`` exception parity — upstream raises
  ``IllegalArgumentException``, pypdfbox raises ``ValueError``; both normalise
  to ``ERR:IllegalArgument`` in the projection so the cross-language exception
  compares.

Both sides build the SAME ``COSDictionary`` from the same fixed case list and
project the identical framed grammar. Java is ground truth.

Line grammar (one per case, fixed order)::

    CASE <name> title=<v> author=<v> subject=<v> keywords=<v> creator=<v>
        producer=<v> cdate=<millis|null|ERR> mdate=<millis|null|ERR>
        trapped=<v> keys=<k,k|-> custom_X=<v>

where each ``v`` is the string value, ``null``, or ``ERR:<type>``. The date
cells report UTC epoch milliseconds (Java ``getTimeInMillis()`` / Python
``datetime.timestamp() * 1000``).
"""

from __future__ import annotations

import datetime as _dt

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


# Fixed case order — mirrors DocumentInfoFuzzProbe.CASES verbatim.
_CASES: tuple[str, ...] = (
    "bare",
    "all_strings",
    "subject_is_name",
    "keywords_is_number",
    "creator_is_array",
    "title_empty_string",
    "title_unicode",
    "cdate_pos_offset",
    "cdate_neg_offset",
    "cdate_z_suffix",
    "cdate_zero_offset_apos",
    "cdate_year_only",
    "cdate_year_month",
    "cdate_ymd",
    "cdate_no_prefix_z",
    "cdate_iso8601",
    "cdate_leading_ws",
    "cdate_lower_prefix",
    "cdate_garbage",
    "cdate_is_number",
    "mdate_pos_offset",
    "trapped_true_name",
    "trapped_false_name",
    "trapped_unknown_name",
    "trapped_string",
    "trapped_bogus_name",
    "trapped_number",
    "custom_mix",
    "custom_value_number",
    "set_title_roundtrip",
    "set_title_then_clear",
    "set_creationdate_roundtrip",
    "set_trapped_true_roundtrip",
    "set_trapped_garbage",
    "set_custom_roundtrip",
    "set_custom_then_null",
)


def _build(name: str) -> COSDictionary:
    """Construct the fuzzed /Info COSDictionary for a case (mirror of the
    Java ``build`` switch)."""
    d = COSDictionary()
    if name == "bare":
        pass
    elif name == "all_strings":
        d.set_item(_N("Title"), COSString("T"))
        d.set_item(_N("Author"), COSString("A"))
        d.set_item(_N("Subject"), COSString("S"))
        d.set_item(_N("Keywords"), COSString("K"))
        d.set_item(_N("Creator"), COSString("C"))
        d.set_item(_N("Producer"), COSString("P"))
    elif name == "subject_is_name":
        d.set_item(_N("Subject"), _N("S"))
    elif name == "keywords_is_number":
        d.set_item(_N("Keywords"), COSInteger.get(5))
    elif name == "creator_is_array":
        d.set_item(_N("Creator"), COSArray())
    elif name == "title_empty_string":
        d.set_item(_N("Title"), COSString(""))
    elif name == "title_unicode":
        d.set_item(_N("Title"), COSString("café ☃"))
    elif name == "cdate_pos_offset":
        d.set_item(_N("CreationDate"), COSString("D:20240101120000+05'00'"))
    elif name == "cdate_neg_offset":
        d.set_item(_N("CreationDate"), COSString("D:20240101120000-08'30'"))
    elif name == "cdate_z_suffix":
        d.set_item(_N("CreationDate"), COSString("D:20240101120000Z"))
    elif name == "cdate_zero_offset_apos":
        d.set_item(_N("CreationDate"), COSString("D:20240101120000+00'00'"))
    elif name == "cdate_year_only":
        d.set_item(_N("CreationDate"), COSString("D:2024"))
    elif name == "cdate_year_month":
        d.set_item(_N("CreationDate"), COSString("D:202406"))
    elif name == "cdate_ymd":
        d.set_item(_N("CreationDate"), COSString("D:20240615"))
    elif name == "cdate_no_prefix_z":
        d.set_item(_N("CreationDate"), COSString("20240101120000Z"))
    elif name == "cdate_iso8601":
        d.set_item(_N("CreationDate"), COSString("2024-03-15T12:00:00Z"))
    elif name == "cdate_leading_ws":
        d.set_item(_N("CreationDate"), COSString("  D:20240101120000Z"))
    elif name == "cdate_lower_prefix":
        d.set_item(_N("CreationDate"), COSString("d:20240101120000Z"))
    elif name == "cdate_garbage":
        d.set_item(_N("CreationDate"), COSString("xyz"))
    elif name == "cdate_is_number":
        d.set_item(_N("CreationDate"), COSInteger.get(20240101))
    elif name == "mdate_pos_offset":
        d.set_item(_N("ModDate"), COSString("D:19991231235959+02'00'"))
    elif name == "trapped_true_name":
        d.set_item(_N("Trapped"), _N("True"))
    elif name == "trapped_false_name":
        d.set_item(_N("Trapped"), _N("False"))
    elif name == "trapped_unknown_name":
        d.set_item(_N("Trapped"), _N("Unknown"))
    elif name == "trapped_string":
        d.set_item(_N("Trapped"), COSString("True"))
    elif name == "trapped_bogus_name":
        d.set_item(_N("Trapped"), _N("Sometimes"))
    elif name == "trapped_number":
        d.set_item(_N("Trapped"), COSInteger.get(1))
    elif name == "custom_mix":
        d.set_item(_N("Title"), COSString("T"))
        d.set_item(_N("Foo"), COSString("bar"))
        d.set_item(_N("Zeta"), COSString("z"))
        d.set_item(_N("Alpha"), COSString("a"))
    elif name == "custom_value_number":
        d.set_item(_N("Foo"), COSInteger.get(7))
    return d


def _mutate(info: PDDocumentInformation, name: str) -> None:
    """Apply post-construction setter mutations (mirror of Java ``mutate``)."""
    if name == "set_title_roundtrip":
        info.set_title("Hello")
    elif name == "set_title_then_clear":
        info.set_title("Hello")
        info.set_title(None)
    elif name == "set_creationdate_roundtrip":
        # Java: Calendar GMT+05:00, 2022-06-01 09:30:00 -> +05:00 instant.
        tz = _dt.timezone(_dt.timedelta(hours=5))
        info.set_creation_date(_dt.datetime(2022, 6, 1, 9, 30, 0, tzinfo=tz))
    elif name == "set_trapped_true_roundtrip":
        info.set_trapped("True")
    elif name == "set_trapped_garbage":
        info.set_trapped("garbage")
    elif name == "set_custom_roundtrip":
        info.set_custom_metadata_value("MyKey", "MyVal")
    elif name == "set_custom_then_null":
        info.set_custom_metadata_value("MyKey", "MyVal")
        info.set_custom_metadata_value("MyKey", None)


def _custom_field(name: str) -> str:
    if name in ("set_custom_roundtrip", "set_custom_then_null"):
        return "MyKey"
    return "Foo"


def _exc(e: Exception) -> str:
    # Python ValueError <-> Java IllegalArgumentException.
    if isinstance(e, ValueError):
        return "ERR:IllegalArgument"
    if isinstance(e, OSError):
        return "ERR:IOException"
    return f"ERR:{type(e).__name__}"


def _s(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        v = fn()
        return "null" if v is None else v
    except Exception as e:  # noqa: BLE001 — mirror probe catch-all
        return _exc(e)


def _date(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        v = fn()
        if v is None:
            return "null"
        return str(int(v.timestamp() * 1000))
    except Exception as e:  # noqa: BLE001
        return _exc(e)


def _python_line(name: str) -> str:
    info = PDDocumentInformation(_build(name))
    mut_err: str | None = None
    try:
        _mutate(info, name)
    except Exception as e:  # noqa: BLE001
        mut_err = _exc(e)
    trapped = mut_err if mut_err is not None else _s(info.get_trapped)
    try:
        keys = info.get_metadata_keys()
        keys_cell = ",".join(keys) if keys else "-"
    except Exception as e:  # noqa: BLE001
        keys_cell = _exc(e)
    return (
        f"CASE {name} "
        f"title={_s(info.get_title)} "
        f"author={_s(info.get_author)} "
        f"subject={_s(info.get_subject)} "
        f"keywords={_s(info.get_keywords)} "
        f"creator={_s(info.get_creator)} "
        f"producer={_s(info.get_producer)} "
        f"cdate={_date(info.get_creation_date)} "
        f"mdate={_date(info.get_modification_date)} "
        f"trapped={trapped} "
        f"keys={keys_cell} "
        f"custom_X="
        f"{_s(lambda: info.get_custom_metadata_value(_custom_field(name)))}"
    )


# name -> (python_line, java_line, reason) for defensible divergences.
_PINNED: dict[str, tuple[str, str, str]] = {}


@requires_oracle
def test_document_info_fuzz_matches_pdfbox() -> None:
    """Every in-memory /Info dict and setter round-trip resolves identically on
    pypdfbox and Apache PDFBox 3.0.7: same per-accessor cell, same date epoch,
    same trapped enum, same sorted metadata-key union, same exception class.
    Divergences are pinned in ``_PINNED`` with a matching CHANGES.md row."""
    raw = run_probe_text("DocumentInfoFuzzProbe")
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(_CASES), (
        f"probe emitted {len(java_lines)} lines for {len(_CASES)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in _CASES:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, (
        "PDDocumentInformation in-memory fuzz divergences:\n"
        + "\n".join(mismatches)
    )
