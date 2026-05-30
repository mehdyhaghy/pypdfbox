"""Live PDFBox differential parity for the document-catalog viewer-level
metadata surface.

Does pypdfbox's :class:`PDViewerPreferences` (plus the catalog's
``/PageLayout`` / ``/PageMode`` / ``/Lang`` / ``/Version`` accessors) read the
same viewer-preference values out of a PDF as Apache PDFBox 3.0.7?

The Java side is ``oracle/probes/ViewerPrefsProbe.java``: it loads a PDF and
emits a canonical, line-oriented dump of every viewer-preference getter
(``hideToolbar`` … ``displayDocTitle``, the four name-valued enum getters
``nonFullScreenPageMode`` / ``direction`` / ``printScaling`` / ``duplex``, and
the raw ``/NumCopies`` integer + ``/PrintPageRange`` flat-int array that
PDFBox 3.0.7 has no getter for) plus the catalog ``pageLayout`` / ``pageMode`` /
``lang`` / ``version``.

Here we reproduce the identical dump from pypdfbox and assert it matches
byte-for-byte.

**Spec-default reads (the high-value cases).** PDFBox 3.0.7 bakes the PDF
32000-1 §12.2 Table 150 / §7.7.3.3 Table 28 defaults straight into the getters:

* ``getNonFullScreenPageMode()`` → ``UseNone`` when ``/NonFullScreenPageMode``
  is absent.
* ``getReadingDirection()`` → ``L2R`` when ``/Direction`` is absent.
* ``getPrintScaling()`` → ``AppDefault`` when ``/PrintScaling`` is absent.
* ``getDuplex()`` → ``null`` (NO spec default) when ``/Duplex`` is absent.
* the six booleans → ``false`` when absent.
* ``getPageLayout()`` → ``SinglePage`` / ``getPageMode()`` → ``UseNone`` when
  the catalog entry is absent.

pypdfbox's getters mirror each of those exactly; the reproducer uses
``get_page_layout_or_default()`` / ``get_page_mode_or_default()`` (the
upstream-compatible default-applying reads) so the comparison is apples-to-
apples. ``/NumCopies`` and ``/PrintPageRange`` have no upstream getter, so both
sides read them off the raw COS dictionary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSNumber, COSString
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences
from tests.oracle.harness import requires_oracle, run_probe_text

_NUM_COPIES = COSName.get_pdf_name("NumCopies")
_PRINT_PAGE_RANGE = COSName.get_pdf_name("PrintPageRange")


def _b(value: bool) -> str:
    return "true" if value else "false"


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _py_viewer_prefs(fixture: Path) -> str:
    """Build the same line-oriented dump ViewerPrefsProbe.java emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        cat = doc.get_document_catalog()
        vp = cat.get_viewer_preferences()
        lines.append(f"present={_b(vp is not None)}")
        if vp is not None:
            lines.append(f"hideToolbar={_b(vp.hide_toolbar())}")
            lines.append(f"hideMenubar={_b(vp.hide_menubar())}")
            lines.append(f"hideWindowUI={_b(vp.hide_window_ui())}")
            lines.append(f"fitWindow={_b(vp.fit_window())}")
            lines.append(f"centerWindow={_b(vp.center_window())}")
            lines.append(f"displayDocTitle={_b(vp.display_doc_title())}")
            lines.append(
                f"nonFullScreenPageMode={_nz(vp.get_non_full_screen_page_mode())}"
            )
            lines.append(f"direction={_nz(vp.get_reading_direction())}")
            lines.append(f"printScaling={_nz(vp.get_print_scaling())}")
            lines.append(f"duplex={_nz(vp.get_duplex())}")

            # /NumCopies and /PrintPageRange: read off the raw dictionary,
            # exactly as the Java probe does (no upstream getter in 3.0.7).
            vp_dict = vp.get_cos_object()
            num_copies = vp_dict.get_dictionary_object(_NUM_COPIES)
            if isinstance(num_copies, COSNumber):
                lines.append(f"numCopies={num_copies.int_value()}")
            else:
                lines.append("numCopies=NULL")

            ppr = vp_dict.get_dictionary_object(_PRINT_PAGE_RANGE)
            if isinstance(ppr, COSArray):
                parts: list[str] = []
                for i in range(ppr.size()):
                    el = ppr.get_object(i)
                    if isinstance(el, COSNumber):
                        parts.append(str(el.int_value()))
                    else:
                        parts.append("?")
                lines.append("printPageRange=" + ",".join(parts))
            else:
                lines.append("printPageRange=NULL")
        else:
            lines.append("hideToolbar=false")
            lines.append("hideMenubar=false")
            lines.append("hideWindowUI=false")
            lines.append("fitWindow=false")
            lines.append("centerWindow=false")
            lines.append("displayDocTitle=false")
            lines.append("nonFullScreenPageMode=NULL")
            lines.append("direction=NULL")
            lines.append("printScaling=NULL")
            lines.append("duplex=NULL")
            lines.append("numCopies=NULL")
            lines.append("printPageRange=NULL")

        # Java bakes the spec default into the catalog getters — mirror with
        # the default-applying reads.
        lines.append(f"pageLayout={cat.get_page_layout_or_default().value}")
        lines.append(f"pageMode={cat.get_page_mode_or_default().value}")
        lines.append(f"lang={_nz(cat.get_language())}")
        lines.append(f"version={_nz(cat.get_version())}")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


def _build_representative_pdf(out_path: Path) -> None:
    """Build a one-page PDF setting a representative viewer-preferences dict
    (several booleans true, a NonFullScreenPageMode, Direction R2L,
    PrintScaling None, Duplex, NumCopies 3, a PrintPageRange array), plus the
    catalog /PageLayout TwoColumnLeft, /PageMode UseOutlines, /Lang en-US."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()

        cat.set_page_layout("TwoColumnLeft")
        cat.set_page_mode("UseOutlines")
        cat.set_language("en-US")

        vp = PDViewerPreferences()
        vp.set_hide_toolbar(True)
        vp.set_hide_menubar(True)
        vp.set_fit_window(True)
        vp.set_display_doc_title(True)
        vp.set_non_full_screen_page_mode(
            PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines
        )
        vp.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
        vp.set_print_scaling(PDViewerPreferences.PRINT_SCALING.None_)
        vp.set_duplex(PDViewerPreferences.DUPLEX.DuplexFlipLongEdge)
        vp.set_num_copies(3)
        vp.set_print_page_range_pairs([(1, 1), (3, 5)])
        cat.set_viewer_preferences(vp)

        doc.save(out_path)
    finally:
        doc.close()


@requires_oracle
def test_viewer_prefs_representative_matches_pdfbox(tmp_path: Path) -> None:
    """Representative built fixture: every boolean / enum / numeric / array
    viewer preference set to a non-default value, plus catalog page-layout /
    page-mode / lang, compared against PDFBox 3.0.7."""
    pdf = tmp_path / "viewer_prefs_representative.pdf"
    _build_representative_pdf(pdf)
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, (
        "representative: viewer preferences diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


def _build_empty_viewer_prefs_pdf(out_path: Path) -> None:
    """Build a PDF whose /ViewerPreferences dictionary is PRESENT but EMPTY,
    so every getter must fall back to its spec default — the high-value
    absent-key cases (UseNone / L2R / AppDefault / null-duplex / false-flags)."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()
        cat.set_viewer_preferences(PDViewerPreferences())
        doc.save(out_path)
    finally:
        doc.close()


@requires_oracle
def test_viewer_prefs_empty_dict_defaults_match_pdfbox(tmp_path: Path) -> None:
    """Empty-but-present /ViewerPreferences dict: every getter falls back to
    its spec default. Confirms pypdfbox bakes the same defaults PDFBox does —
    booleans false, nonFullScreenPageMode UseNone, direction L2R, printScaling
    AppDefault, duplex NULL, numCopies/printPageRange NULL."""
    pdf = tmp_path / "viewer_prefs_empty.pdf"
    _build_empty_viewer_prefs_pdf(pdf)
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, (
        "empty_dict_defaults: viewer-pref defaults diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


def _build_no_viewer_prefs_pdf(out_path: Path) -> None:
    """Build a plain PDF with NO /ViewerPreferences dictionary at all, so the
    whole-dictionary-absent branch (present=false) plus the catalog default
    page layout/mode (SinglePage / UseNone) is exercised."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        doc.save(out_path)
    finally:
        doc.close()


@requires_oracle
def test_viewer_prefs_absent_matches_pdfbox(tmp_path: Path) -> None:
    """No /ViewerPreferences dictionary: present=false on both sides, and the
    catalog page-layout/page-mode getters return the spec defaults
    (SinglePage / UseNone)."""
    pdf = tmp_path / "viewer_prefs_absent.pdf"
    _build_no_viewer_prefs_pdf(pdf)
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, (
        "absent: viewer-pref absence handling diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
@pytest.mark.parametrize(
    "page_layout",
    [
        "SinglePage",
        "OneColumn",
        "TwoColumnLeft",
        "TwoColumnRight",
        "TwoPageLeft",
        "TwoPageRight",
    ],
)
def test_page_layout_enum_mapping_matches_pdfbox(
    tmp_path: Path, page_layout: str
) -> None:
    """Every /PageLayout name maps to the identical enum string on both
    sides."""
    pdf = tmp_path / f"layout_{page_layout}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        doc.get_document_catalog().set_page_layout(page_layout)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, f"page_layout {page_layout}: diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize(
    "page_mode",
    [
        "UseNone",
        "UseOutlines",
        "UseThumbs",
        "FullScreen",
        "UseOC",
        "UseAttachments",
    ],
)
def test_page_mode_enum_mapping_matches_pdfbox(
    tmp_path: Path, page_mode: str
) -> None:
    """Every /PageMode name maps to the identical enum string on both
    sides."""
    pdf = tmp_path / f"mode_{page_mode}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        doc.get_document_catalog().set_page_mode(page_mode)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, f"page_mode {page_mode}: diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize(
    "nfs_mode",
    ["UseNone", "UseOutlines", "UseThumbs", "UseOC"],
)
def test_non_full_screen_page_mode_enum_mapping_matches_pdfbox(
    tmp_path: Path, nfs_mode: str
) -> None:
    """Every /NonFullScreenPageMode enum token maps identically on both
    sides."""
    pdf = tmp_path / f"nfs_{nfs_mode}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_non_full_screen_page_mode(nfs_mode)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, f"nonFullScreenPageMode {nfs_mode}: diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize(
    "duplex",
    ["Simplex", "DuplexFlipShortEdge", "DuplexFlipLongEdge"],
)
def test_duplex_enum_mapping_matches_pdfbox(tmp_path: Path, duplex: str) -> None:
    """Every /Duplex enum token maps identically on both sides (no spec
    default — absence yields NULL, exercised in the empty-dict test)."""
    pdf = tmp_path / f"duplex_{duplex}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_duplex(duplex)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, f"duplex {duplex}: diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize("print_scaling", ["None", "AppDefault"])
def test_print_scaling_enum_mapping_matches_pdfbox(
    tmp_path: Path, print_scaling: str
) -> None:
    """Every /PrintScaling enum token maps identically on both sides."""
    pdf = tmp_path / f"scaling_{print_scaling}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_print_scaling(print_scaling)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, f"printScaling {print_scaling}: diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize(
    "direction",
    ["L2R", "R2L"],
)
def test_direction_enum_mapping_matches_pdfbox(
    tmp_path: Path, direction: str
) -> None:
    """Both /Direction enum tokens map identically on both sides."""
    pdf = tmp_path / f"direction_{direction}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_reading_direction(direction)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    assert py == java, f"direction {direction}: diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize(
    ("pairs", "expected_csv"),
    [
        ([(1, 1)], "1,1"),
        ([(1, 5)], "1,5"),
        ([(1, 1), (3, 5)], "1,1,3,5"),
        ([(2, 4), (7, 9), (11, 11)], "2,4,7,9,11,11"),
    ],
    ids=["single_page", "single_range", "two_ranges", "three_ranges"],
)
def test_print_page_range_round_trips_through_pdfbox(
    tmp_path: Path, pairs: list[tuple[int, int]], expected_csv: str
) -> None:
    """/PrintPageRange set via pypdfbox is read back by PDFBox as the exact
    flat-integer array (a set-then-read-via-PDFBox round-trip)."""
    pdf = tmp_path / "ppr.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_print_page_range_pairs(pairs)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    assert f"printPageRange={expected_csv}\n" in java
    py = _py_viewer_prefs(pdf)
    assert py == java, f"printPageRange {pairs}: diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize("num_copies", [1, 2, 3, 99])
def test_num_copies_round_trips_through_pdfbox(
    tmp_path: Path, num_copies: int
) -> None:
    """/NumCopies set via pypdfbox is read back by PDFBox as the same integer
    (a set-then-read-via-PDFBox round-trip)."""
    pdf = tmp_path / "numcopies.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_num_copies(num_copies)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    assert f"numCopies={num_copies}\n" in java
    py = _py_viewer_prefs(pdf)
    assert py == java, f"numCopies {num_copies}: diverges from PDFBox"


@requires_oracle
def test_all_booleans_round_trip_through_pdfbox(tmp_path: Path) -> None:
    """All six boolean viewer-preference flags set true via pypdfbox read back
    true via PDFBox (set-then-read-via-PDFBox round-trip)."""
    pdf = tmp_path / "bools.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_hide_toolbar(True)
        vp.set_hide_menubar(True)
        vp.set_hide_window_ui(True)
        vp.set_fit_window(True)
        vp.set_center_window(True)
        vp.set_display_doc_title(True)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    py = _py_viewer_prefs(pdf)
    for flag in (
        "hideToolbar",
        "hideMenubar",
        "hideWindowUI",
        "fitWindow",
        "centerWindow",
        "displayDocTitle",
    ):
        assert f"{flag}=true\n" in java
    assert py == java, "all-booleans round-trip diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize(
    "bogus_name",
    ["BogusLayout", "singlepage", "UseNone", ""],
    ids=["unknown", "wrong_case", "valid_mode_token", "empty"],
)
def test_unrecognised_page_layout_falls_back_to_single_page(
    tmp_path: Path, bogus_name: str
) -> None:
    """A present-but-unrecognised (or empty) /PageLayout name: PDFBox 3.0.7
    logs and falls back to SinglePage (see PDDocumentCatalog.getPageLayout()
    — IllegalArgumentException from PageLayout.fromString is caught, and an
    empty string short-circuits). pypdfbox's get_page_layout() returns None for
    the same input, so get_page_layout_or_default() must yield SinglePage to
    match Java. Pins the unrecognised-name read path the enum-mapping tests
    (which only write valid tokens) never reach."""
    pdf = tmp_path / f"bogus_layout_{bogus_name or 'empty'}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()
        cat.get_cos_object().set_item(
            COSName.get_pdf_name("PageLayout"), COSName.get_pdf_name(bogus_name)
        )
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    assert "pageLayout=SinglePage\n" in java
    py = _py_viewer_prefs(pdf)
    assert py == java, f"bogus /PageLayout {bogus_name!r}: diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize(
    "bogus_name",
    ["BogusMode", "usenone", "SinglePage"],
    ids=["unknown", "wrong_case", "valid_layout_token"],
)
def test_unrecognised_page_mode_falls_back_to_use_none(
    tmp_path: Path, bogus_name: str
) -> None:
    """A present-but-unrecognised /PageMode name: PDFBox 3.0.7 catches the
    IllegalArgumentException from PageMode.fromString and returns UseNone.
    pypdfbox's get_page_mode() returns None, so get_page_mode_or_default()
    must yield UseNone to match. Pins the unrecognised-name read path."""
    pdf = tmp_path / f"bogus_mode_{bogus_name}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()
        cat.get_cos_object().set_item(
            COSName.get_pdf_name("PageMode"), COSName.get_pdf_name(bogus_name)
        )
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    assert "pageMode=UseNone\n" in java
    py = _py_viewer_prefs(pdf)
    assert py == java, f"bogus /PageMode {bogus_name!r}: diverges from PDFBox"


@requires_oracle
def test_page_layout_mode_as_cos_string_matches_pdfbox(tmp_path: Path) -> None:
    """Malformed producer output occasionally stores /PageLayout and /PageMode
    as a COSString rather than the spec-correct COSName. PDFBox 3.0.7's
    COSDictionary.getNameAsString accepts both, so getPageLayout()/getPageMode()
    still resolve the enum. pypdfbox's get_page_layout()/get_page_mode() also
    accept a COSString — this pins that tolerance against the oracle."""
    pdf = tmp_path / "string_valued_layout_mode.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()
        cat.get_cos_object().set_item(
            COSName.get_pdf_name("PageLayout"), COSString("TwoColumnRight")
        )
        cat.get_cos_object().set_item(
            COSName.get_pdf_name("PageMode"), COSString("UseThumbs")
        )
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsProbe", str(pdf))
    assert "pageLayout=TwoColumnRight\n" in java
    assert "pageMode=UseThumbs\n" in java
    py = _py_viewer_prefs(pdf)
    assert py == java, "COSString-valued /PageLayout|/PageMode diverges from PDFBox"


def test_print_page_range_pairs_decode_round_trip() -> None:
    """Pure-Python sanity: the (start, end) pair encode/decode helpers are
    each other's inverse and write COSInteger pairs (no oracle needed)."""
    vp = PDViewerPreferences()
    vp.set_print_page_range_pairs([(1, 1), (3, 5)])
    arr = vp.get_print_page_range()
    assert isinstance(arr, COSArray)
    assert arr.size() == 4
    assert all(isinstance(arr.get_object(i), COSInteger) for i in range(4))
    assert vp.get_print_page_range_pairs() == [(1, 1), (3, 5)]
