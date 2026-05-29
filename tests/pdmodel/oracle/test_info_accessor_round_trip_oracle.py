"""Live PDFBox differential parity for the PDDocumentInformation accessor +
round-trip surface.

Distinct from ``test_metadata_oracle`` / ``test_info_xmp_oracle`` (read-only on
existing fixtures) and from the writer's null-stamping save contract (wave
1451): here we drive ``PDDocumentInformation`` SETTERS — every standard field
plus a custom key and timezone-bearing dates set through the typed
``set_creation_date`` / ``set_modification_date`` accessors — then ``save`` the
document, reload it, and assert pypdfbox reads back exactly what Apache PDFBox
does via ``oracle/probes/InfoAccessorRoundTripProbe.java``.

Two layers are compared per field so both the value AND the serialised byte
form are pinned:

1. **Typed getters** — strings verbatim (a missing key renders ``NULL``); the
   typed date getters render as ``<epoch-millis>@<offset-min>`` so Java's
   ``Calendar`` and pypdfbox's ``datetime`` compare repr-independently.

2. **Raw stored date string** — the exact ``D:YYYYMMDDHHmmSS+HH'mm'`` bytes the
   setter wrote (read back as a raw ``COSString``), so a divergence in date
   FORMATTING (e.g. ``Z00'00'`` vs ``+00'00'`` at offset 0) is caught even
   though both parse to the same instant.

The probe sets a creation date east of UTC (+02:00) and a modification date
west of UTC (-05:00) so the explicit offset is carried both ways through the
formatter on each side.
"""

from __future__ import annotations

import datetime as _dt

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_US = "\x1f"


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _fmt_calendar(date: _dt.datetime | None) -> str:
    """Mirror the probe's ``<epoch-millis>@<offset-min>`` rendering."""
    if date is None:
        return "NULL"
    epoch_millis = int(date.timestamp() * 1000)
    offset = date.utcoffset() or _dt.timedelta(0)
    offset_minutes = int(offset.total_seconds()) // 60
    return f"{epoch_millis}@{offset_minutes}"


def _at(epoch_millis: int, offset_minutes: int) -> _dt.datetime:
    """A fixed-offset timezone-aware datetime at ``epoch_millis``.

    Matches the probe's ``GregorianCalendar`` in a ``SimpleTimeZone`` of
    ``offset_minutes`` east of UTC (no DST)."""
    tz = _dt.timezone(_dt.timedelta(minutes=offset_minutes))
    return _dt.datetime.fromtimestamp(epoch_millis / 1000, tz=tz)


def _raw_date(info, key: str) -> str:
    base = info.get_cos_object().get_dictionary_object(COSName.get_pdf_name(key))
    if isinstance(base, COSString):
        return base.get_string()
    return "NULL"


def _py_round_trip(out_path) -> str:
    """Build the same line-oriented report the probe emits, via pypdfbox."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        info = doc.get_document_information()
        info.set_title("Round-Trip Title éè")
        info.set_author("Ada Lovelace")
        info.set_subject("Differential parity")
        info.set_keywords("pdf, info, oracle")
        info.set_creator("InfoAccessorRoundTripProbe")
        info.set_producer("pypdfbox-oracle")
        info.set_trapped("True")
        info.set_creation_date(_at(1700000000000, 120))
        info.set_modification_date(_at(1700003600000, -300))
        info.set_custom_metadata_value("AppBuild", "42.7")
        info.set_custom_metadata_value("Reviewer", "M. Haghy")
        doc.save(str(out_path))
    finally:
        doc.close()

    lines: list[str] = []
    doc = PDDocument.load(out_path)
    try:
        info = doc.get_document_information()
        lines.append(f"Title={_nz(info.get_title())}")
        lines.append(f"Author={_nz(info.get_author())}")
        lines.append(f"Subject={_nz(info.get_subject())}")
        lines.append(f"Keywords={_nz(info.get_keywords())}")
        lines.append(f"Creator={_nz(info.get_creator())}")
        lines.append(f"Producer={_nz(info.get_producer())}")
        lines.append(f"Trapped={_nz(info.get_trapped())}")
        lines.append(f"CreationDate={_fmt_calendar(info.get_creation_date())}")
        lines.append(f"ModDate={_fmt_calendar(info.get_modification_date())}")
        lines.append(f"CreationDateRaw={_raw_date(info, 'CreationDate')}")
        lines.append(f"ModDateRaw={_raw_date(info, 'ModDate')}")
        lines.append(f"custom.AppBuild={_nz(info.get_custom_metadata_value('AppBuild'))}")
        lines.append(f"custom.Reviewer={_nz(info.get_custom_metadata_value('Reviewer'))}")
        keys = sorted(info.get_metadata_keys())
        lines.append("keys=" + _US.join(keys))
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
def test_info_accessor_round_trip_matches_pdfbox(tmp_path) -> None:
    java_out = run_probe_text(
        "InfoAccessorRoundTripProbe", str(tmp_path / "java.pdf")
    )
    py_out = _py_round_trip(tmp_path / "py.pdf")
    assert py_out == java_out, (
        "PDDocumentInformation accessor round-trip diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py_out}\n--- java ---\n{java_out}"
    )
