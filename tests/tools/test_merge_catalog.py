"""Catalog metadata preservation tests for ``pypdfbox merge``."""
from __future__ import annotations

from pathlib import Path

from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDViewerPreferences
from pypdfbox.pdmodel.common import PDMetadata
from pypdfbox.tools import cli


def _build_pdf_with_catalog_entries(
    path: Path,
    *,
    language: str,
    layout: str,
    mode: str,
    title: str,
    hide_toolbar: bool,
) -> Path:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.set_language(language)
        catalog.set_page_layout(layout)
        catalog.set_page_mode(mode)

        prefs = PDViewerPreferences()
        prefs.set_hide_toolbar(hide_toolbar)
        prefs.set_display_doc_title(True)
        catalog.set_viewer_preferences(prefs)

        catalog.set_metadata(PDMetadata(f"<x:xmpmeta>{title}</x:xmpmeta>"))
        doc.save(path)
    finally:
        doc.close()
    return path


def test_merge_preserves_first_simple_catalog_entries(tmp_path: Path) -> None:
    a = _build_pdf_with_catalog_entries(
        tmp_path / "a.pdf",
        language="en-US",
        layout="TwoColumnLeft",
        mode="UseOutlines",
        title="source-a",
        hide_toolbar=True,
    )
    b = _build_pdf_with_catalog_entries(
        tmp_path / "b.pdf",
        language="fr-FR",
        layout="SinglePage",
        mode="UseThumbs",
        title="source-b",
        hide_toolbar=False,
    )
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(["merge", "-i", str(a), str(b), "-o", str(out)])
    assert rc == 0

    with PDDocument.load(out) as merged:
        catalog = merged.get_document_catalog()
        # Wave 1506: /Lang, /ViewerPreferences and /PageLayout are merged
        # ONLY inside the structure-tree arm (upstream appendDocument runs
        # mergeLanguage/mergeViewerPreferences/mergeMarkInfo inside
        # `if (mergeStructTree)`; there is no /PageLayout merge at all).
        # These untagged sources therefore carry none of them.
        cos_catalog = catalog.get_cos_object()
        assert cos_catalog.get_item(COSName.get_pdf_name("Lang")) is None
        assert cos_catalog.get_item(COSName.get_pdf_name("PageLayout")) is None
        assert cos_catalog.get_item(
            COSName.get_pdf_name("ViewerPreferences")
        ) is None
        # /PageMode is the documented pypdfbox enhancement (upstream's
        # getPageMode bakes the spec default, making its guard dead code).
        assert catalog.get_page_mode() == "UseOutlines"

        metadata = catalog.get_metadata()
        assert metadata is not None
        assert metadata.get_metadata_as_string() == "<x:xmpmeta>source-a</x:xmpmeta>"
