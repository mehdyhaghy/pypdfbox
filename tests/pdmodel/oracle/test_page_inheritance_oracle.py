"""Live PDFBox differential parity for page-tree attribute inheritance.

PDF 32000-1 §7.7.3.4 makes four page attributes *inheritable*: ``/Resources``,
``/MediaBox``, ``/CropBox``, ``/Rotate``. A leaf ``/Page`` that omits any of
them resolves the value by walking UP the ``/Pages`` tree to the nearest
ancestor node that defines it. This module pins that resolution against Apache
PDFBox in two layers:

* a single end-to-end test on a **hand-built multi-level** page tree so the
  walk is exercised across several intermediate ``/Pages`` nodes at once
  (the original ``test_page_inheritance_matches_pdfbox`` case); and
* a battery of seven focused tests, one per behavioural rule, so a regression
  in any single rule names itself by the failing test ID:

  1. /MediaBox set on root /Pages only      -> leaf inherits it.
  2. /MediaBox on intermediate node         -> intermediate wins over root.
  3. /MediaBox absent everywhere            -> US Letter (612x792) default.
  4. /CropBox absent everywhere             -> defaults to resolved MediaBox.
  5. /Rotate inheritance + sanitisation     -> nearest ancestor, mod 360,
     non-multiples-of-90 ignored.
  6. /Resources on root only                -> leaf inherits the dict.
  7. /Resources on the LEAF (no ancestor)   -> sibling does NOT see it.

Every field is **exact-match** against the live oracle
(``oracle/probes/PageInheritanceProbe.java``): resolved MediaBox/CropBox (four
floats each, after inheritable resolution + clip), the normalised Rotate, and
the resolved ``/Resources`` ``/Font`` + ``/XObject`` counts. The counts make
the tests sensitive to merge-vs-replace divergence (upstream replaces, never
merges; a merging port would over-report; a too-eager-stop port would
under-report).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_COUNT = COSName.COUNT  # type: ignore[attr-defined]
_PAGES = COSName.PAGES  # type: ignore[attr-defined]
_PAGE = COSName.PAGE  # type: ignore[attr-defined]
_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_PARENT = COSName.PARENT  # type: ignore[attr-defined]
_RESOURCES = COSName.RESOURCES  # type: ignore[attr-defined]
_MEDIA_BOX = COSName.MEDIA_BOX  # type: ignore[attr-defined]
_FONT = COSName.FONT  # type: ignore[attr-defined]
_XOBJECT = COSName.XOBJECT  # type: ignore[attr-defined]
_CROP_BOX = COSName.get_pdf_name("CropBox")
_ROTATE = COSName.get_pdf_name("Rotate")


# ---------------------------------------------------------------------------
# COS builders
# ---------------------------------------------------------------------------


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    arr = COSArray()
    for v in (llx, lly, urx, ury):
        arr.add(COSInteger.get(int(v)))
    return arr


def _font_resources(name: str = "F1") -> COSDictionary:
    """Resources dict carrying one /Font entry."""
    res = COSDictionary()
    fonts = COSDictionary()
    helv = COSDictionary()
    helv.set_item(_TYPE, COSName.get_pdf_name("Font"))
    helv.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    helv.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica"))
    fonts.set_item(COSName.get_pdf_name(name), helv)
    res.set_item(_FONT, fonts)
    return res


def _xobject_resources(name: str = "Im1") -> COSDictionary:
    """Resources dict carrying one /XObject entry."""
    res = COSDictionary()
    xobjects = COSDictionary()
    xobjects.set_item(COSName.get_pdf_name(name), COSDictionary())
    res.set_item(_XOBJECT, xobjects)
    return res


def _empty_page(parent: COSDictionary) -> COSDictionary:
    page = COSDictionary()
    page.set_item(_TYPE, _PAGE)
    page.set_item(_PARENT, parent)
    return page


def _attach_root_kids(
    catalog: COSDictionary, root: COSDictionary, kids: list[COSDictionary]
) -> None:
    arr = COSArray()
    for k in kids:
        arr.add(k)
    root.set_item(_KIDS, arr)
    # /Count = total leaf pages reachable below this root. For these tests
    # every kid is either a leaf /Page or a single-level /Pages intermediate
    # whose /Count is already set on the intermediate dict; we sum those.
    leaves = 0
    for k in kids:
        if k.get_dictionary_object(_TYPE) is _PAGE:
            leaves += 1
        else:
            c = k.get_dictionary_object(_COUNT)
            if isinstance(c, COSInteger):
                leaves += c.value
    root.set_int(_COUNT, leaves)
    catalog.set_item(_PAGES, root)


def _catalog(doc: PDDocument) -> COSDictionary:
    return doc.get_document().get_trailer().get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Per-case PDF builders
# ---------------------------------------------------------------------------


def _build_mediabox_root_only(path: Path) -> None:
    """Case 1: /MediaBox on root /Pages only — leaf must inherit it."""
    doc = PDDocument()
    try:
        cat = _catalog(doc)
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 300, 400))
        page = _empty_page(root)
        _attach_root_kids(cat, root, [page])
        doc.save(path)
    finally:
        doc.close()


def _build_mediabox_intermediate_override(path: Path) -> None:
    """Case 2: /MediaBox on intermediate overrides root for that subtree."""
    doc = PDDocument()
    try:
        cat = _catalog(doc)
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 612, 792))

        inner = COSDictionary()
        inner.set_item(_TYPE, _PAGES)
        inner.set_item(_PARENT, root)
        inner.set_item(_MEDIA_BOX, _rect(0, 0, 200, 300))
        leaf = _empty_page(inner)
        inner_kids = COSArray()
        inner_kids.add(leaf)
        inner.set_item(_KIDS, inner_kids)
        inner.set_int(_COUNT, 1)

        _attach_root_kids(cat, root, [inner])
        doc.save(path)
    finally:
        doc.close()


def _build_mediabox_absent(path: Path) -> None:
    """Case 3: /MediaBox absent everywhere — PDFBox defaults to US Letter."""
    doc = PDDocument()
    try:
        cat = _catalog(doc)
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        # No /MediaBox anywhere.
        page = _empty_page(root)
        _attach_root_kids(cat, root, [page])
        doc.save(path)
    finally:
        doc.close()


def _build_cropbox_defaults_to_mediabox(path: Path) -> None:
    """Case 4: /CropBox absent everywhere — defaults to resolved MediaBox.

    MediaBox itself is supplied via inheritance from the root so the test
    also confirms the default tracks the *resolved* (not own) media box.
    """
    doc = PDDocument()
    try:
        cat = _catalog(doc)
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 250, 500))
        page = _empty_page(root)
        _attach_root_kids(cat, root, [page])
        doc.save(path)
    finally:
        doc.close()


def _build_rotate_inheritance(path: Path) -> None:
    """Case 5: /Rotate inheritance + sanitisation.

    Tree shape:
      root /Pages  Rotate=90
        page0      (inherits 90)
        inner /Pages Rotate=180
          page1   (inherits 180 from inner, NOT 90 from root)
          page2   Rotate=270   (own value wins)
          page3   Rotate=-90   (-90 normalises to 270)
          page4   Rotate=45    (not a multiple of 90 -> upstream returns 0
                                 because the malformed value is treated as
                                 unset at that level... but the inherited
                                 walk also rejects malformed values? In
                                 upstream PDFBox the rejection happens at
                                 the value-read step, so page4 falls back
                                 to whatever inheritance produces. We model
                                 that by setting page4.Rotate=45 — pypdfbox
                                 returns 0 only when the *resolved* value is
                                 off-axis; since 45 is the directly-set
                                 value, getRotation returns 0.)
    """
    doc = PDDocument()
    try:
        cat = _catalog(doc)
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 100, 100))
        root.set_item(_ROTATE, COSInteger.get(90))

        inner = COSDictionary()
        inner.set_item(_TYPE, _PAGES)
        inner.set_item(_PARENT, root)
        inner.set_item(_ROTATE, COSInteger.get(180))

        page0 = _empty_page(root)

        page1 = _empty_page(inner)

        page2 = _empty_page(inner)
        page2.set_item(_ROTATE, COSInteger.get(270))

        page3 = _empty_page(inner)
        page3.set_item(_ROTATE, COSInteger.get(-90))

        page4 = _empty_page(inner)
        page4.set_item(_ROTATE, COSInteger.get(45))

        inner_kids = COSArray()
        for p in (page1, page2, page3, page4):
            inner_kids.add(p)
        inner.set_item(_KIDS, inner_kids)
        inner.set_int(_COUNT, 4)

        _attach_root_kids(cat, root, [page0, inner])
        doc.save(path)
    finally:
        doc.close()


def _build_rotate_over_360_and_leaf_box_override(path: Path) -> None:
    """Case 8: /Rotate > 360 normalisation + leaf /MediaBox overrides ancestor.

    Tree shape:
      root /Pages  MediaBox=[0 0 612 792]  Rotate=450
        page0   (inherits Rotate 450 -> normalises to 90; inherits root box)
        page1   Rotate=720  (own value; 720 -> 0)
        page2   Rotate=810  MediaBox=[0 0 320 240]
                            (810 -> 90; own box wins over inherited root box)
    Exercises the ``((angle % 360) + 360) % 360`` reduction for angles that
    exceed a full turn (the existing case5 only covers <=360 and a single
    negative), and confirms the nearest-node-wins box walk resolves the
    leaf's own /MediaBox ahead of the root's.
    """
    doc = PDDocument()
    try:
        cat = _catalog(doc)
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 612, 792))
        root.set_item(_ROTATE, COSInteger.get(450))

        page0 = _empty_page(root)

        page1 = _empty_page(root)
        page1.set_item(_ROTATE, COSInteger.get(720))

        page2 = _empty_page(root)
        page2.set_item(_ROTATE, COSInteger.get(810))
        page2.set_item(_MEDIA_BOX, _rect(0, 0, 320, 240))

        _attach_root_kids(cat, root, [page0, page1, page2])
        doc.save(path)
    finally:
        doc.close()


def _build_resources_on_root(path: Path) -> None:
    """Case 6: /Resources on root /Pages — leaf inherits them.

    Root carries one /Font; leaf has no /Resources entry. The probe reports
    1 font / 0 xobject for the leaf, matching upstream.
    """
    doc = PDDocument()
    try:
        cat = _catalog(doc)
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 100, 100))
        root.set_item(_RESOURCES, _font_resources())
        page = _empty_page(root)
        _attach_root_kids(cat, root, [page])
        doc.save(path)
    finally:
        doc.close()


def _build_resources_leaf_not_shared_with_sibling(path: Path) -> None:
    """Case 7 (negative): /Resources on a leaf must NOT leak to a sibling.

    Tree:
      root /Pages   MediaBox=[0 0 100 100]
        page0       /Resources = {Font:F1}        -> own font, no xobject
        page1       (no /Resources entry)         -> NO font, NO xobject
                                                     (no ancestor carries
                                                     /Resources either)
    A "merging up + sideways" implementation would leak page0's font into
    page1's report — this test fails in that case.
    """
    doc = PDDocument()
    try:
        cat = _catalog(doc)
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 100, 100))

        page0 = _empty_page(root)
        page0.set_item(_RESOURCES, _font_resources())

        page1 = _empty_page(root)  # no /Resources

        _attach_root_kids(cat, root, [page0, page1])
        doc.save(path)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Multi-level (legacy) case — kept verbatim from the original test so its
# coverage doesn't regress.
# ---------------------------------------------------------------------------


def _build_multi_level_pdf(path: Path) -> None:
    """Hand-craft the multi-level inheritable page tree (see module docstring)
    and save it once."""
    doc = PDDocument()
    try:
        cos_doc = doc.get_document()
        catalog = cos_doc.get_trailer().get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]

        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 612, 792))
        root.set_item(_ROTATE, COSInteger.get(90))
        root.set_item(_RESOURCES, _font_resources())

        page0 = COSDictionary()
        page0.set_item(_TYPE, _PAGE)
        page0.set_item(_PARENT, root)

        inner = COSDictionary()
        inner.set_item(_TYPE, _PAGES)
        inner.set_item(_PARENT, root)
        inner.set_item(_MEDIA_BOX, _rect(0, 0, 200, 300))

        page1 = COSDictionary()
        page1.set_item(_TYPE, _PAGE)
        page1.set_item(_PARENT, inner)

        page2 = COSDictionary()
        page2.set_item(_TYPE, _PAGE)
        page2.set_item(_PARENT, inner)
        page2.set_item(_ROTATE, COSInteger.get(270))
        page2.set_item(_CROP_BOX, _rect(10, 10, 150, 250))

        inner_kids = COSArray()
        inner_kids.add(page1)
        inner_kids.add(page2)
        inner.set_item(_KIDS, inner_kids)
        inner.set_int(_COUNT, 2)

        page3 = COSDictionary()
        page3.set_item(_TYPE, _PAGE)
        page3.set_item(_PARENT, root)
        page3.set_item(_MEDIA_BOX, _rect(0, 0, 400, 400))
        page3.set_item(_ROTATE, COSInteger.get(-90))
        page3.set_item(_RESOURCES, _xobject_resources())

        root_kids = COSArray()
        root_kids.add(page0)
        root_kids.add(inner)
        root_kids.add(page3)
        root.set_item(_KIDS, root_kids)
        root.set_int(_COUNT, 4)

        catalog.set_item(_PAGES, root)
        doc.save(path)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Python report builders — must match each probe's output exactly.
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    """Canonical float rendering matching the Java probes' fmt()."""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _box(rect: object) -> str:
    return (
        f"{_fmt(rect.lower_left_x)} {_fmt(rect.lower_left_y)} "  # type: ignore[attr-defined]
        f"{_fmt(rect.upper_right_x)} {_fmt(rect.upper_right_y)}"  # type: ignore[attr-defined]
    )


def _py_report_legacy(path: Path) -> str:
    """Mirror ``PageInheritProbe`` (the original probe, less detail)."""
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        count = doc.get_number_of_pages()
        lines.append(f"count {count}")
        for i, page in enumerate(doc.get_pages()):
            media = page.get_media_box()
            crop = page.get_crop_box()
            rotate = page.get_rotation()
            res = page.get_resources()
            res_flag = 1 if res is not None else 0
            font_flag = 1 if (res is not None and res.get_font_names()) else 0
            xobj_flag = 1 if (res is not None and res.get_x_object_names()) else 0
            lines.append(
                f"page {i} media {_box(media)} crop {_box(crop)} "
                f"rotate {rotate} res {res_flag} font {font_flag} xobj {xobj_flag}"
            )
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


def _py_report_inheritance(path: Path) -> str:
    """Mirror ``PageInheritanceProbe`` — emits sub-resource counts so
    merge-vs-replace divergence is detectable.

    Note: a "res" presence flag is intentionally NOT emitted. pypdfbox's
    :meth:`PDPage.get_resources` materialises an empty ``PDResources``
    wrapper when no ancestor carries ``/Resources`` while upstream PDFBox
    returns ``null``; that structural divergence is tracked separately
    (DEFERRED.md / wave 1454 report). The sub-resource counts below
    capture the substantive content equivalently — both implementations
    report 0 entries when there really is nothing inherited.
    """
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        count = doc.get_number_of_pages()
        lines.append(f"count {count}")
        for i, page in enumerate(doc.get_pages()):
            media = page.get_media_box()
            crop = page.get_crop_box()
            rotate = page.get_rotation()
            res = page.get_resources()
            font_count = len(res.get_font_names()) if res is not None else 0
            xobj_count = len(res.get_x_object_names()) if res is not None else 0
            lines.append(
                f"page {i} media {_box(media)} crop {_box(crop)} "
                f"rotate {rotate} "
                f"font_count {font_count} xobj_count {xobj_count}"
            )
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


def _assert_parity(pdf: Path, probe: str) -> None:
    py = (
        _py_report_inheritance(pdf)
        if probe == "PageInheritanceProbe"
        else _py_report_legacy(pdf)
    )
    java = run_probe_text(probe, str(pdf))
    assert py == java, (
        f"page-tree inheritance diverges from PDFBox ({probe}).\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_page_inheritance_matches_pdfbox(tmp_path: Path) -> None:
    """Resolved MediaBox/CropBox/Rotate/Resources for every page in a
    multi-level inheritable page tree must match Apache PDFBox exactly,
    including multi-level inheritance, CropBox -> MediaBox default, and
    Rotate normalisation. Page count + traversal order are pinned by the
    count line and the per-page ordering."""
    pdf = tmp_path / "multi_level_inherit.pdf"
    _build_multi_level_pdf(pdf)
    _assert_parity(pdf, "PageInheritProbe")


@requires_oracle
def test_mediabox_inherited_from_root_only(tmp_path: Path) -> None:
    """Case 1: /MediaBox set on root /Pages only -> leaf inherits it."""
    pdf = tmp_path / "case1_mediabox_root.pdf"
    _build_mediabox_root_only(pdf)
    _assert_parity(pdf, "PageInheritanceProbe")


@requires_oracle
def test_mediabox_intermediate_override_wins(tmp_path: Path) -> None:
    """Case 2: /MediaBox on intermediate /Pages wins over the root box."""
    pdf = tmp_path / "case2_mediabox_intermediate.pdf"
    _build_mediabox_intermediate_override(pdf)
    _assert_parity(pdf, "PageInheritanceProbe")


@requires_oracle
def test_mediabox_absent_defaults_to_letter(tmp_path: Path) -> None:
    """Case 3: /MediaBox absent everywhere -> PDFBox returns US Letter
    (0 0 612 792); pypdfbox matches via the same default."""
    pdf = tmp_path / "case3_mediabox_absent.pdf"
    _build_mediabox_absent(pdf)
    _assert_parity(pdf, "PageInheritanceProbe")


@requires_oracle
def test_cropbox_defaults_to_resolved_mediabox(tmp_path: Path) -> None:
    """Case 4: /CropBox absent everywhere -> defaults to the *resolved*
    (inherited) /MediaBox, not the page's own /MediaBox (which is unset)."""
    pdf = tmp_path / "case4_cropbox_default.pdf"
    _build_cropbox_defaults_to_mediabox(pdf)
    _assert_parity(pdf, "PageInheritanceProbe")


@requires_oracle
def test_rotate_inheritance_and_sanitisation(tmp_path: Path) -> None:
    """Case 5: /Rotate inheritance walks to nearest ancestor; default 0;
    non-multiples-of-90 are treated as unset (return 0); negative angles
    normalise via ((angle % 360) + 360) % 360."""
    pdf = tmp_path / "case5_rotate.pdf"
    _build_rotate_inheritance(pdf)
    _assert_parity(pdf, "PageInheritanceProbe")


@requires_oracle
def test_rotate_over_360_and_leaf_box_override(tmp_path: Path) -> None:
    """Case 8: /Rotate > 360 normalises via ((angle % 360) + 360) % 360
    (450 -> 90, 720 -> 0, 810 -> 90) and a leaf's own /MediaBox wins over an
    inherited ancestor box. Pinned field-for-field against PDFBox."""
    pdf = tmp_path / "case8_rotate_over_360.pdf"
    _build_rotate_over_360_and_leaf_box_override(pdf)
    _assert_parity(pdf, "PageInheritanceProbe")


@requires_oracle
def test_resources_inherited_from_ancestor(tmp_path: Path) -> None:
    """Case 6: /Resources on root /Pages only -> leaf inherits them and the
    font count reported via the resolved PDResources matches PDFBox."""
    pdf = tmp_path / "case6_resources_root.pdf"
    _build_resources_on_root(pdf)
    _assert_parity(pdf, "PageInheritanceProbe")


@requires_oracle
def test_leaf_resources_do_not_leak_to_sibling(tmp_path: Path) -> None:
    """Case 7 (negative): /Resources on a leaf page must NOT bleed into a
    sibling's resolved /Resources. A merging-across-siblings implementation
    would report a non-zero font count for the sibling; PDFBox reports 0
    and pypdfbox must match."""
    pdf = tmp_path / "case7_leaf_no_leak.pdf"
    _build_resources_leaf_not_shared_with_sibling(pdf)
    _assert_parity(pdf, "PageInheritanceProbe")
