"""Live PDFBox differential parity for document metadata + page labels + XMP.

Three exact-match surfaces, all asserted byte-for-byte against Apache PDFBox's
own accessors via ``oracle/probes/MetaProbe.java``:

1. **/Info dictionary** — the eight standard keys (``Title``, ``Author``,
   ``Subject``, ``Keywords``, ``Creator``, ``Producer``, ``CreationDate``,
   ``ModDate``). String fields compare verbatim; a missing key renders as the
   literal ``NULL``.

2. **Page labels** — the per-page computed label from
   ``PDPageLabels.getLabelsByPageIndices()`` (Java) /
   ``PDPageLabels.get_labels_by_page_indices()`` (python), one line per page.
   Omitted entirely when the catalog has no ``/PageLabels`` entry.

3. **XMP metadata packet** — the byte length and SHA-1 hex of the raw XMP
   packet returned by ``PDMetadata.exportXMPMetadata()`` (Java) /
   ``PDMetadata.export_xmp_metadata()`` (python). ``xmp NONE`` when the catalog
   carries no ``/Metadata`` stream.

**Date normalisation.** Java's ``getCreationDate()`` returns a ``Calendar``;
pypdfbox's returns a timezone-aware ``datetime``. Both representations are
normalised to the identical wall-clock ISO-8601 string
``YYYY-MM-DDTHH:MM:SS+HH:MM`` (offset rendered in minutes, no ``Z`` form) so
the comparison exercises the real date-parsing getters on both sides while
staying representation-agnostic. A genuinely wrong parsed instant still fails;
only the textual representation is normalised.

**Fixtures** are chosen to vary every surface: Acrobat-produced files with full
info dicts + XMP + decimal labels (``PDFBOX-5811``, ``PDFBOX-4417-001031``,
``PDFBOX-5762``), an XMP-bearing writer file with no page labels and both date
zones (``pdfwriter/unencrypted``), a LibreOffice file with a partial info dict
and no XMP at all (``with_outline``), a ``Z``-timezone file (``BidiSample``),
and a pypdfbox-built fixture exercising every non-decimal label style — Roman,
prefixed-decimal, and letters (``page_labels_styles``), and a pypdfbox-built
fixture whose XMP packet is ``/FlateDecode``-compressed so the metadata decode
path is exercised on both sides before hashing (``metadata_flate_xmp``).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# (relative fixture path, human label)
_CASES = [
    ("multipdf/PDFBOX-5811-362972.pdf", "acrobat_full_info_xmp"),
    ("multipdf/PDFBOX-4417-001031.pdf", "distiller_info_xmp_labels"),
    ("multipdf/PDFBOX-5762-722238.pdf", "distiller_short_title"),
    ("pdfwriter/unencrypted.pdf", "acrobat_no_labels_two_zones"),
    ("pdmodel/with_outline.pdf", "libreoffice_partial_no_xmp"),
    ("text/BidiSample.pdf", "quartz_z_timezone"),
    ("pdmodel/page_labels_styles.pdf", "pypdfbox_label_styles"),
    ("pdmodel/metadata_flate_xmp.pdf", "pypdfbox_flate_xmp"),
]

# Standard /Info keys, in the exact order MetaProbe.java emits them.
_INFO_FIELDS = [
    "Title",
    "Author",
    "Subject",
    "Keywords",
    "Creator",
    "Producer",
]


def _iso(date: _dt.datetime | None) -> str:
    """Normalise a parsed PDF date to MetaProbe's canonical ISO-8601 form.

    Mirrors ``MetaProbe.isoDate``: ``YYYY-MM-DDTHH:MM:SS+HH:MM`` with the UTC
    offset rendered in minutes (no ``Z`` shorthand). A ``None`` instant (key
    absent or unparseable) renders as the literal ``NULL``.
    """
    if date is None:
        return "NULL"
    offset = date.utcoffset() or _dt.timedelta(0)
    off_min = int(offset.total_seconds()) // 60
    sign = "-" if off_min < 0 else "+"
    abs_min = abs(off_min)
    return (
        f"{date.year:04d}-{date.month:02d}-{date.day:02d}"
        f"T{date.hour:02d}:{date.minute:02d}:{date.second:02d}"
        f"{sign}{abs_min // 60:02d}:{abs_min % 60:02d}"
    )


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _py_metadata(fixture: Path) -> str:
    """Build the same line-oriented metadata report MetaProbe.java emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        info = doc.get_document_information()
        getters = {
            "Title": info.get_title,
            "Author": info.get_author,
            "Subject": info.get_subject,
            "Keywords": info.get_keywords,
            "Creator": info.get_creator,
            "Producer": info.get_producer,
        }
        for field in _INFO_FIELDS:
            lines.append(f"info {field}={_nz(getters[field]())}")
        lines.append(f"info CreationDate={_iso(info.get_creation_date())}")
        lines.append(f"info ModDate={_iso(info.get_modification_date())}")

        catalog = doc.get_document_catalog()
        labels = catalog.get_page_labels()
        if labels is not None:
            by_index = labels.get_labels_by_page_indices()
            for i, label in enumerate(by_index):
                lines.append(f"label {i}={_nz(label)}")

        metadata = catalog.get_metadata()
        if metadata is None:
            lines.append("xmp NONE")
        else:
            packet = metadata.export_xmp_metadata()
            lines.append(f"xmp {len(packet)} {hashlib.sha1(packet).hexdigest()}")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize(
    ("rel_path", "label"),
    _CASES,
    ids=[c[1] for c in _CASES],
)
def test_metadata_matches_pdfbox(rel_path: str, label: str) -> None:
    fixture = _FIXTURES / rel_path
    java = run_probe_text("MetaProbe", str(fixture))
    py = _py_metadata(fixture)
    assert py == java, (
        f"{label}: document metadata diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
