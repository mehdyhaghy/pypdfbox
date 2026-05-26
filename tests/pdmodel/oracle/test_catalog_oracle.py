"""Live PDFBox differential parity for the document-catalog property surface.

Does pypdfbox's :class:`PDDocumentCatalog` (plus
:class:`PDViewerPreferences` / :class:`PDMarkInfo`) read the same catalog-level
properties out of a PDF as Apache PDFBox?

The Java side is ``oracle/probes/CatalogProbe.java``: it loads a PDF and emits
a canonical, line-oriented dump of every catalog property the pypdfbox surface
exposes — ``/Version`` override, ``/PageLayout``, ``/PageMode``, ``/Lang``,
``/OpenAction`` kind, the ``/MarkInfo`` flags (marked / userProperties /
suspects), the ``/ViewerPreferences`` sub-flags (hide* / fitWindow /
centerWindow / displayDocTitle / nonFullScreenPageMode / direction),
``/OutputIntents`` count, and presence of ``/PageLabels`` / ``/AcroForm`` /
``/StructTreeRoot``.

Here we reproduce the identical dump from pypdfbox and assert it matches
byte-for-byte.

**Default-applying reads.** Java's ``PDDocumentCatalog.getPageLayout()`` /
``getPageMode()`` bake the PDF 32000-1 §7.7.3.3 Table 28 spec default into the
getter (``SinglePage`` / ``UseNone``) and never return null. pypdfbox's
``get_page_layout()`` / ``get_page_mode()`` keep a more tolerant ``None``
posture to distinguish "explicit" from "default", so the reproducer uses
``get_page_layout_or_default()`` / ``get_page_mode_or_default()`` — the
upstream-compatible default-applying reads — to mirror Java exactly.

Likewise the ``/ViewerPreferences`` name-valued getters
(``getNonFullScreenPageMode`` → ``UseNone``, ``getReadingDirection`` → ``L2R``)
bake in spec defaults on both sides when the dictionary exists but the entry is
absent; ``CatalogProbe`` prints ``NULL`` only when the whole
``/ViewerPreferences`` dictionary is missing, which the reproducer mirrors.

**Fixtures** span the natural variety we care about: a tagged PDF/A-3A file with
``/Lang``, ``/MarkInfo /Marked``, a ``/ViewerPreferences`` dict
(``DisplayDocTitle``), one ``/OutputIntent`` and a ``/StructTreeRoot``
(``PDFA3A``); an AcroForm-only file (``AcroFormForMerge``); an outline file with
a destination-array ``/OpenAction`` and ``/Lang`` (``with_outline``); a file
carrying a catalog ``/Version`` override plus ``/PageLabels``
(``page_labels_styles``); an Acrobat file with an action-dictionary
``/OpenAction`` plus ``/MarkInfo`` + ``/PageLabels`` + ``/AcroForm`` +
``/StructTreeRoot`` (``PDFBOX-5811``); a plain file with no interesting catalog
entries (``BidiSample``); and a pypdfbox-built fixture that explicitly sets
``/PageLayout``, ``/PageMode``, ``/Lang``, every ``/ViewerPreferences`` flag and
the ``/MarkInfo`` flags to NON-default values so every property is exercised
away from its default (``built_all_props``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.page_layout import PageLayout
from pypdfbox.pdmodel.page_mode import PageMode
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
_OPEN_ACTION = COSName.get_pdf_name("OpenAction")

# (relative fixture path, human label)
_CASES = [
    ("multipdf/PDFA3A.pdf", "tagged_pdfa_lang_outputintent"),
    ("multipdf/AcroFormForMerge.pdf", "acroform_only"),
    ("pdmodel/with_outline.pdf", "outline_openaction_array_lang"),
    ("pdmodel/page_labels_styles.pdf", "version_override_pagelabels"),
    ("multipdf/PDFBOX-5811-362972.pdf", "acrobat_openaction_dict_full"),
    ("text/BidiSample.pdf", "plain_no_catalog_extras"),
]


def _b(value: bool) -> str:
    return "true" if value else "false"


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _py_catalog(fixture: Path) -> str:
    """Build the same line-oriented catalog dump CatalogProbe.java emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        cat = doc.get_document_catalog()

        lines.append(f"version={_nz(cat.get_version())}")
        # Java bakes the spec default into the getter — mirror with the
        # default-applying reads.
        lines.append(f"pageLayout={cat.get_page_layout_or_default().value}")
        lines.append(f"pageMode={cat.get_page_mode_or_default().value}")
        lines.append(f"lang={_nz(cat.get_language())}")

        # /OpenAction kind: action dictionary vs destination array.
        from pypdfbox.cos import COSArray, COSDictionary

        oa = cat.get_cos_object().get_dictionary_object(_OPEN_ACTION)
        if isinstance(oa, COSDictionary):
            oa_kind = "DICTIONARY"
        elif isinstance(oa, COSArray):
            oa_kind = "ARRAY"
        else:
            oa_kind = "NULL"
        lines.append(f"openAction={oa_kind}")

        # /MarkInfo
        mark_info = cat.get_mark_info()
        lines.append(f"markInfo.present={_b(mark_info is not None)}")
        if mark_info is not None:
            lines.append(f"markInfo.marked={_b(mark_info.is_marked())}")
            lines.append(
                f"markInfo.userProperties={_b(mark_info.uses_user_properties())}"
            )
            lines.append(f"markInfo.suspects={_b(mark_info.is_suspect())}")
        else:
            lines.append("markInfo.marked=false")
            lines.append("markInfo.userProperties=false")
            lines.append("markInfo.suspects=false")
        lines.append(
            f"isTagged={_b(mark_info is not None and mark_info.is_marked())}"
        )

        # /ViewerPreferences sub-flags
        vp = cat.get_viewer_preferences()
        lines.append(f"viewerPrefs.present={_b(vp is not None)}")
        if vp is not None:
            lines.append(f"viewerPrefs.hideToolbar={_b(vp.hide_toolbar())}")
            lines.append(f"viewerPrefs.hideMenubar={_b(vp.hide_menubar())}")
            lines.append(f"viewerPrefs.hideWindowUI={_b(vp.hide_window_ui())}")
            lines.append(f"viewerPrefs.fitWindow={_b(vp.fit_window())}")
            lines.append(f"viewerPrefs.centerWindow={_b(vp.center_window())}")
            lines.append(
                f"viewerPrefs.displayDocTitle={_b(vp.display_doc_title())}"
            )
            lines.append(
                "viewerPrefs.nonFullScreenPageMode="
                f"{_nz(vp.get_non_full_screen_page_mode())}"
            )
            lines.append(
                f"viewerPrefs.direction={_nz(vp.get_reading_direction())}"
            )
        else:
            lines.append("viewerPrefs.hideToolbar=false")
            lines.append("viewerPrefs.hideMenubar=false")
            lines.append("viewerPrefs.hideWindowUI=false")
            lines.append("viewerPrefs.fitWindow=false")
            lines.append("viewerPrefs.centerWindow=false")
            lines.append("viewerPrefs.displayDocTitle=false")
            lines.append("viewerPrefs.nonFullScreenPageMode=NULL")
            lines.append("viewerPrefs.direction=NULL")

        lines.append(f"outputIntents={len(cat.get_output_intents())}")
        lines.append(f"hasPageLabels={_b(cat.get_page_labels() is not None)}")
        lines.append(f"hasAcroForm={_b(cat.get_acro_form() is not None)}")
        lines.append(
            f"hasStructTreeRoot={_b(cat.get_struct_tree_root() is not None)}"
        )
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize(
    ("rel_path", "label"),
    _CASES,
    ids=[c[1] for c in _CASES],
)
def test_catalog_matches_pdfbox(rel_path: str, label: str) -> None:
    fixture = _FIXTURES / rel_path
    java = run_probe_text("CatalogProbe", str(fixture))
    py = _py_catalog(fixture)
    assert py == java, (
        f"{label}: document-catalog properties diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


def _build_all_props_pdf(out_path: Path) -> None:
    """Build a one-page PDF that sets EVERY catalog property exercised by the
    probe to a NON-default value, so the parity check covers the away-from-
    default branch of each accessor on both sides."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()

        cat.set_version("1.7")
        cat.set_page_layout(PageLayout.TWO_COLUMN_LEFT)
        cat.set_page_mode(PageMode.USE_OUTLINES)
        cat.set_language("en-US")

        # /MarkInfo: all three flags true.
        cat.set_document_marked(True)
        cat.set_user_properties(True)
        cat.set_suspects(True)

        # /ViewerPreferences: every boolean flag true + non-default names.
        vp = PDViewerPreferences()
        vp.set_hide_toolbar(True)
        vp.set_hide_menubar(True)
        vp.set_hide_window_ui(True)
        vp.set_fit_window(True)
        vp.set_center_window(True)
        vp.set_display_doc_title(True)
        vp.set_non_full_screen_page_mode(
            PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseThumbs
        )
        vp.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
        cat.set_viewer_preferences(vp)

        doc.save(out_path)
    finally:
        doc.close()


@requires_oracle
def test_catalog_built_all_props_matches_pdfbox(tmp_path: Path) -> None:
    """Built fixture: PageLayout / PageMode / Lang / every ViewerPreferences
    flag / every MarkInfo flag set to non-default values, so each accessor is
    exercised off its default and compared against PDFBox."""
    pdf = tmp_path / "built_all_props.pdf"
    _build_all_props_pdf(pdf)
    java = run_probe_text("CatalogProbe", str(pdf))
    py = _py_catalog(pdf)
    assert py == java, (
        "built_all_props: document-catalog properties diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
