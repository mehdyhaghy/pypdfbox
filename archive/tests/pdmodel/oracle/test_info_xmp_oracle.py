"""Live PDFBox differential parity for the /Info ↔ XMP /Metadata read split.

PDFBox keeps two independent metadata surfaces on a document and does NOT
auto-sync them:

* ``getDocumentInformation()`` reads the trailer ``/Info`` dictionary — the
  eight standard keys plus arbitrary custom keys.
* ``getDocumentCatalog().getMetadata()`` reads the catalog ``/Metadata`` XMP
  stream, parsed via ``DomXmpParser`` into typed schemas.

This module builds (via pypdfbox) one PDF that deliberately sets *different*
values in the two surfaces — ``/Info`` ``/Title`` = ``"InfoTitle"`` while XMP
``dc:title`` = ``"XmpTitle"``, and likewise for producer / creator / dates —
then asserts, against Apache PDFBox's own accessors (the ``InfoXmpProbe`` Java
probe), that:

1. every ``/Info`` getter matches PDFBox (including a custom key
   ``getCustomMetadataValue("AppBuild")`` and the sorted ``getMetadataKeys``
   set), with the ``D:`` date strings parsed to the same absolute instant; and
2. the XMP-parsed ``dc:title`` / ``dc:creator`` / ``xmp:createDate`` /
   ``pdf:producer`` match PDFBox's typed schema reads; and
3. critically, the ``/Info`` ``/Title`` (``"InfoTitle"``) is *not* equal to the
   XMP ``dc:title`` (``"XmpTitle"``) on *either* engine — proving each accessor
   reads its own source with no accidental cross-sync.

**Date normalisation.** ``/Info`` dates come from PDFBox's typed
``getCreationDate()`` ``Calendar`` getter; XMP dates from ``getCreateDate()``.
Both render as ``<epoch-millis>@<offset-minutes>`` (absolute instant + explicit
zone offset) so Java's ``Calendar`` and pypdfbox's ``datetime`` compare without
depending on how either side formats a wall-clock string.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from tests.oracle.harness import requires_oracle, run_probe_text

# US (0x1f) — the list/key separator both probe and helper use so a comma or
# other punctuation inside a value never confuses item boundaries.
_US = "\x1f"

# Deliberately divergent values across the two surfaces. /Info Title differs
# from XMP dc:title; /Info Producer differs from XMP pdf:Producer; /Info Author
# differs from XMP dc:creator; the two date instants differ as well.
_INFO_TITLE = "InfoTitle"
_INFO_AUTHOR = "InfoAuthor"
_INFO_SUBJECT = "InfoSubject"
_INFO_KEYWORDS = "alpha,beta"
_INFO_CREATOR = "InfoCreator"
_INFO_PRODUCER = "InfoProducer"
_INFO_APPBUILD = "build-4242"

_XMP_TITLE = "XmpTitle"
_XMP_CREATOR = "XmpCreator"
_XMP_PRODUCER = "XmpProducer"

# /Info CreationDate: 2021-05-25 18:09:32 +02:00 -> D:20210525180932+02'00'
# (the canonical PDF date string the parser must turn into the right instant).
_INFO_CREATION_DATE = _dt.datetime(
    2021, 5, 25, 18, 9, 32, tzinfo=_dt.timezone(_dt.timedelta(hours=2))
)
# /Info ModDate: 2022-11-03 07:15:00 -05:00.
_INFO_MOD_DATE = _dt.datetime(
    2022, 11, 3, 7, 15, 0, tzinfo=_dt.timezone(_dt.timedelta(hours=-5))
)

# XMP xmp:CreateDate: a deliberately different instant + zone from /Info.
_XMP_CREATE_DATE = "2019-01-02T03:04:05+09:00"

# Literal XMP packet. dc:title (Alt/LangAlt), dc:creator (Seq), xmp:CreateDate
# (Simple date), pdf:Producer (Simple text) — the four typed reads the test
# exercises. Values intentionally diverge from the /Info dictionary.
_XMP_PACKET = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    '    <rdf:Description rdf:about=""\n'
    '        xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
    '        xmlns:xmp="http://ns.adobe.com/xap/1.0/"\n'
    '        xmlns:pdf="http://ns.adobe.com/pdf/1.3/">\n'
    "      <dc:title>\n"
    "        <rdf:Alt>\n"
    f'          <rdf:li xml:lang="x-default">{_XMP_TITLE}</rdf:li>\n'
    "        </rdf:Alt>\n"
    "      </dc:title>\n"
    "      <dc:creator>\n"
    "        <rdf:Seq>\n"
    f"          <rdf:li>{_XMP_CREATOR}</rdf:li>\n"
    "        </rdf:Seq>\n"
    "      </dc:creator>\n"
    f"      <xmp:CreateDate>{_XMP_CREATE_DATE}</xmp:CreateDate>\n"
    f"      <pdf:Producer>{_XMP_PRODUCER}</pdf:Producer>\n"
    "    </rdf:Description>\n"
    "  </rdf:RDF>\n"
    "</x:xmpmeta>\n"
    '<?xpacket end="w"?>'
).encode("utf-8")


def _build_pdf(path: Path) -> None:
    """Build a single-page PDF carrying divergent /Info + /Metadata."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())

        info = PDDocumentInformation()
        info.set_title(_INFO_TITLE)
        info.set_author(_INFO_AUTHOR)
        info.set_subject(_INFO_SUBJECT)
        info.set_keywords(_INFO_KEYWORDS)
        info.set_creator(_INFO_CREATOR)
        info.set_producer(_INFO_PRODUCER)
        info.set_creation_date(_INFO_CREATION_DATE)
        info.set_modification_date(_INFO_MOD_DATE)
        info.set_custom_metadata_value("AppBuild", _INFO_APPBUILD)
        doc.set_document_information(info)

        metadata = PDMetadata(doc, _XMP_PACKET)
        doc.get_document_catalog().set_metadata(metadata)

        doc.save(str(path))
    finally:
        doc.close()


def _fmt_instant(dt: _dt.datetime | None) -> str:
    """``<epoch-millis>@<offset-minutes>`` — matches InfoXmpProbe.fmtCalendar.

    A ``None`` instant renders as the literal ``NULL``.
    """
    if dt is None:
        return "NULL"
    epoch_millis = int(dt.timestamp() * 1000)
    offset = dt.utcoffset()
    offset_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    return f"{epoch_millis}@{offset_minutes}"


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _py_report(path: Path) -> str:
    """Build the same line-oriented report InfoXmpProbe.java emits."""
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        info = doc.get_document_information()
        lines.append(f"info Title={_nz(info.get_title())}")
        lines.append(f"info Author={_nz(info.get_author())}")
        lines.append(f"info Subject={_nz(info.get_subject())}")
        lines.append(f"info Keywords={_nz(info.get_keywords())}")
        lines.append(f"info Creator={_nz(info.get_creator())}")
        lines.append(f"info Producer={_nz(info.get_producer())}")
        lines.append(f"info CreationDate={_fmt_instant(info.get_creation_date())}")
        lines.append(f"info ModDate={_fmt_instant(info.get_modification_date())}")
        lines.append(
            f"info custom.AppBuild={_nz(info.get_custom_metadata_value('AppBuild'))}"
        )
        lines.append(f"info keys={_US.join(sorted(info.get_metadata_keys()))}")

        catalog = doc.get_document_catalog()
        metadata = catalog.get_metadata()
        if metadata is None:
            lines.append("xmp NONE")
        else:
            packet = metadata.export_xmp_metadata()
            meta = DomXmpParser().parse(packet)

            dc_title = None
            dc_creator = None
            dc = meta.get_dublin_core_schema()
            if dc is not None:
                dc_title = dc.get_title()
                creators = dc.get_creators()
                if creators is not None:
                    dc_creator = _US.join(creators)
            lines.append(f"xmp dc.title={_nz(dc_title)}")
            lines.append(f"xmp dc.creator={_nz(dc_creator)}")

            create_date = None
            xb = meta.get_xmp_basic_schema()
            if xb is not None:
                create_date = xb.get_create_date_value()
            lines.append(f"xmp xmp.createDate={_fmt_instant(create_date)}")

            pdf_producer = None
            ap = meta.get_adobe_pdf_schema()
            if ap is not None:
                pdf_producer = ap.get_producer()
            lines.append(f"xmp pdf.producer={_nz(pdf_producer)}")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
def test_info_xmp_read_split_matches_pdfbox(tmp_path: Path) -> None:
    """/Info getters + XMP typed reads match PDFBox, each from its own source."""
    pdf = tmp_path / "info_xmp_split.pdf"
    _build_pdf(pdf)

    java = run_probe_text("InfoXmpProbe", str(pdf))
    py = _py_report(pdf)
    assert py == java, (
        "Info/XMP read surface diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
def test_info_title_not_synced_to_xmp_title(tmp_path: Path) -> None:
    """The /Info Title and XMP dc:title stay distinct on both engines.

    A reader that accidentally cross-synced the two surfaces would collapse
    ``InfoTitle`` and ``XmpTitle`` into one value; this guards against that.
    """
    pdf = tmp_path / "info_xmp_split.pdf"
    _build_pdf(pdf)

    java = run_probe_text("InfoXmpProbe", str(pdf))
    java_lines = dict(
        line.split("=", 1) for line in java.splitlines() if "=" in line
    )
    # PDFBox: each surface reports its own title, and they differ.
    assert java_lines["info Title"] == _INFO_TITLE
    assert java_lines["xmp dc.title"] == _XMP_TITLE
    assert java_lines["info Title"] != java_lines["xmp dc.title"]

    # pypdfbox: same split, no cross-sync.
    doc = PDDocument.load(pdf)
    try:
        info_title = doc.get_document_information().get_title()
        metadata = doc.get_document_catalog().get_metadata()
        assert metadata is not None
        meta = DomXmpParser().parse(metadata.export_xmp_metadata())
        xmp_title = meta.get_dublin_core_schema().get_title()
    finally:
        doc.close()
    assert info_title == _INFO_TITLE
    assert xmp_title == _XMP_TITLE
    assert info_title != xmp_title
