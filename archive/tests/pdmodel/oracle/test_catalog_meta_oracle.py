"""Live PDFBox differential parity for the *secondary* document-catalog
metadata surface.

Does pypdfbox's :class:`PDDocumentCatalog` (plus :class:`PDOutputIntent` /
:class:`PDMarkInfo`) read the same secondary catalog metadata out of a PDF as
Apache PDFBox? This complements ``test_catalog_oracle.py`` (the primary
property dump — version / page layout / page mode / viewer prefs) by focusing
on the entries that carry conformance + accessibility + portfolio metadata:

* ``/OutputIntents`` — the PDF/A ``GTS_PDFA1`` intent array, including the
  per-intent ``/S`` subtype, ``/OutputConditionIdentifier``, ``/Info`` and the
  ``/DestOutputProfile`` ICC stream (presence).
* ``/MarkInfo`` — ``/Marked`` (tagged PDF), ``/UserProperties``, ``/Suspects``.
* ``/Lang`` — document language.
* ``/Metadata`` — XMP stream presence.
* ``/StructTreeRoot`` — presence (interplays with ``/MarkInfo /Marked``).
* ``/Collection`` — the portable-collection (portfolio) ``/View`` mode. PDFBox
  3.0.7 has no typed ``PDCollection`` accessor on the catalog, so both sides
  read ``/Collection /View`` straight off the raw catalog dictionary; pypdfbox
  surfaces the ``/Collection`` dictionary via
  :meth:`PDDocumentCatalog.get_collection`.

The Java side is ``oracle/probes/CatalogMetaProbe.java``: it loads a PDF and
emits a canonical, line-oriented dump of every entry above. Here we build a PDF
that sets all of them (via pypdfbox), reproduce the identical dump from
pypdfbox, and assert it matches byte-for-byte.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_mark_info import (
    PDMarkInfo,
)
from pypdfbox.pdmodel.graphics.color import PDOutputIntent
from tests.oracle.harness import requires_oracle, run_probe_text

_COLLECTION = COSName.get_pdf_name("Collection")
_VIEW = COSName.get_pdf_name("View")
_D = COSName.get_pdf_name("D")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]

# A tiny but valid sRGB-flavoured ICC profile is hard to hand-assemble; the
# /DestOutputProfile parity case only checks *presence* (has-profile), so we
# embed a minimal byte blob carrying the ICC "acsp" magic at offset 36 and an
# explicit num_components so PDOutputIntent does not need to sniff the header.
_FAKE_ICC = (b"\x00" * 16 + b"RGB " + b"\x00" * 16 + b"acsp") + b"\x00" * 80

_XMP = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b"</rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
)


def _b(value: bool) -> str:
    return "true" if value else "false"


def _s(value: str | None) -> str:
    return "null" if value is None else value


def _build_pdf(out_path: Path) -> None:
    """Build a one-page PDF carrying the full secondary-metadata set:
    a GTS_PDFA1 /OutputIntent (conditionId / info / ICC profile), /MarkInfo
    /Marked true, /Lang, an XMP /Metadata stream, a /StructTreeRoot, and a
    /Collection portfolio with /View /D."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()

        # /OutputIntents: one GTS_PDFA1 intent with conditionId + info + ICC.
        intent = PDOutputIntent(doc, _FAKE_ICC, num_components=3)
        intent.set_output_condition_identifier("sRGB")
        intent.set_info("sRGB IEC61966-2.1")
        cat.add_output_intent(intent)

        # /MarkInfo /Marked true (tagged PDF).
        mark = PDMarkInfo()
        mark.set_marked(True)
        cat.set_mark_info(mark)

        # /Lang.
        cat.set_language("en-US")

        # /Metadata XMP stream.
        cat.set_metadata(PDMetadata(doc, _XMP))

        # /StructTreeRoot — minimal dictionary so the presence check fires.
        struct = COSDictionary()
        struct.set_item(_TYPE, COSName.get_pdf_name("StructTreeRoot"))
        cat.get_cos_object().set_item(
            COSName.get_pdf_name("StructTreeRoot"), struct
        )

        # /Collection portfolio with /View /D (details view).
        collection = COSDictionary()
        collection.set_item(_TYPE, _COLLECTION)
        collection.set_item(_VIEW, _D)
        cat.set_collection(collection)

        doc.save(out_path)
    finally:
        doc.close()


def _py_dump(fixture: Path) -> str:
    """Reproduce the line-oriented dump CatalogMetaProbe.java emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        cat = doc.get_document_catalog()

        # /OutputIntents
        intents = cat.get_output_intents()
        lines.append(f"outputIntents.count={len(intents)}")
        for i, oi in enumerate(intents):
            lines.append(f"outputIntent[{i}].subtype={_s(oi.get_subtype())}")
            lines.append(
                f"outputIntent[{i}].conditionId="
                f"{_s(oi.get_output_condition_identifier())}"
            )
            lines.append(f"outputIntent[{i}].info={_s(oi.get_info())}")
            lines.append(
                f"outputIntent[{i}].hasProfile="
                f"{_b(oi.get_dest_output_intent() is not None)}"
            )

        # /MarkInfo
        mark = cat.get_mark_info()
        lines.append(f"markInfo.present={_b(mark is not None)}")
        lines.append(
            f"markInfo.isMarked={_b(mark is not None and mark.is_marked())}"
        )
        lines.append(
            "markInfo.userProperties="
            f"{_b(mark is not None and mark.uses_user_properties())}"
        )
        lines.append(
            f"markInfo.suspects={_b(mark is not None and mark.is_suspect())}"
        )

        # /Lang
        lines.append(f"language={_s(cat.get_language())}")

        # /Metadata
        lines.append(f"metadata.present={_b(cat.get_metadata() is not None)}")

        # /StructTreeRoot
        lines.append(
            "structTreeRoot.present="
            f"{_b(cat.get_structure_tree_root() is not None)}"
        )

        # /Collection /View
        coll = cat.get_collection()
        lines.append(f"collection.present={_b(coll is not None)}")
        view: str | None = None
        if coll is not None:
            view_base = coll.get_dictionary_object(_VIEW)
            if isinstance(view_base, COSName):
                view = view_base.get_name()
        lines.append(f"collection.view={_s(view)}")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
def test_catalog_meta_matches_pdfbox(tmp_path: Path) -> None:
    """Built fixture: GTS_PDFA1 /OutputIntent + /MarkInfo /Marked + /Lang +
    /Metadata + /StructTreeRoot + /Collection /View /D — every secondary
    catalog metadata accessor compared against PDFBox."""
    pdf = tmp_path / "catalog_meta.pdf"
    _build_pdf(pdf)
    java = run_probe_text("CatalogMetaProbe", str(pdf))
    py = _py_dump(pdf)
    assert py == java, (
        "secondary catalog metadata diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
