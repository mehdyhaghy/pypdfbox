"""Live PDFBox differential parity for page-tree attribute inheritance.

PDF 32000-1 §7.7.3.4 makes four page attributes *inheritable*: ``/Resources``,
``/MediaBox``, ``/CropBox``, ``/Rotate``. A leaf ``/Page`` that omits any of
them resolves the value by walking UP the ``/Pages`` tree to the nearest
ancestor node that defines it. This module pins that resolution against Apache
PDFBox on a **hand-built multi-level** page tree so the walk is exercised
across several intermediate ``/Pages`` nodes (not just a single parent):

    root /Pages          MediaBox=[0 0 612 792]  Rotate=90  Resources{Font}
      ├─ page 0          (omits everything → inherits all from root)
      ├─ inner /Pages    MediaBox=[0 0 200 300]  (overrides MediaBox subtree)
      │    ├─ page 1     (inherits inner MediaBox, root Rotate+Resources;
      │    │              omits CropBox → CropBox defaults to inner MediaBox)
      │    └─ page 2     Rotate=270  CropBox=[10 10 150 250]  (overrides
      │                   Rotate; explicit CropBox clipped to inner MediaBox)
      └─ page 3          MediaBox=[0 0 400 400]  Rotate=-90  Resources{XObject}
                          (overrides MediaBox+Rotate+Resources; -90 normalises
                           to 270; no CropBox → defaults to own MediaBox)

Every field is **exact-match** against the live oracle
(``oracle/probes/PageInheritProbe.java``): resolved MediaBox/CropBox (four
floats each, after inheritable resolution + clip), the normalised Rotate, and
the resolved ``/Resources`` font/xobject presence. A mismatch on any field —
inheritance stopping at the wrong ancestor, ignored inheritance, wrong CropBox
default, wrong Rotate normalisation, wrong page count or traversal order — is a
real bug.
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


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    arr = COSArray()
    for v in (llx, lly, urx, ury):
        arr.add(COSInteger.get(int(v)))
    return arr


def _font_resources() -> COSDictionary:
    """Resources dict carrying one /Font entry (no real font needed — the
    probe only checks key presence)."""
    res = COSDictionary()
    fonts = COSDictionary()
    helv = COSDictionary()
    helv.set_item(_TYPE, COSName.get_pdf_name("Font"))
    helv.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    helv.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica"))
    fonts.set_item(COSName.get_pdf_name("F1"), helv)
    res.set_item(_FONT, fonts)
    return res


def _xobject_resources() -> COSDictionary:
    """Resources dict carrying one /XObject entry (a trivial form xobject is
    not needed — only key presence is probed, so an empty sub-dict suffices)."""
    res = COSDictionary()
    xobjects = COSDictionary()
    # A bare dictionary entry is enough for getXObjectNames() to report the
    # key; the probe never instantiates the xobject.
    xobjects.set_item(COSName.get_pdf_name("Im1"), COSDictionary())
    res.set_item(_XOBJECT, xobjects)
    return res


def _build_multi_level_pdf(path: Path) -> None:
    """Hand-craft the multi-level inheritable page tree described in the
    module docstring and save it once."""
    doc = PDDocument()
    try:
        cos_doc = doc.get_document()
        catalog = cos_doc.get_trailer().get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]

        # ---- root /Pages: MediaBox + Rotate + Resources ----
        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 612, 792))
        root.set_item(_ROTATE, COSInteger.get(90))
        root.set_item(_RESOURCES, _font_resources())

        # ---- page 0: inherits everything from root ----
        page0 = COSDictionary()
        page0.set_item(_TYPE, _PAGE)
        page0.set_item(_PARENT, root)

        # ---- inner /Pages: overrides MediaBox for its subtree ----
        inner = COSDictionary()
        inner.set_item(_TYPE, _PAGES)
        inner.set_item(_PARENT, root)
        inner.set_item(_MEDIA_BOX, _rect(0, 0, 200, 300))

        # ---- page 1: inherits inner MediaBox + root Rotate/Resources;
        #              no CropBox -> defaults to inner MediaBox ----
        page1 = COSDictionary()
        page1.set_item(_TYPE, _PAGE)
        page1.set_item(_PARENT, inner)

        # ---- page 2: overrides Rotate to 270; explicit CropBox clipped to
        #              inner MediaBox (10 10 150 250 stays inside 0 0 200 300) -
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

        # ---- page 3: overrides MediaBox + Rotate(-90 -> 270) + Resources ----
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


def _fmt(value: float) -> str:
    """Canonical float rendering matching ``PageInheritProbe.fmt``."""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _box(rect: object) -> str:
    return (
        f"{_fmt(rect.lower_left_x)} {_fmt(rect.lower_left_y)} "  # type: ignore[attr-defined]
        f"{_fmt(rect.upper_right_x)} {_fmt(rect.upper_right_y)}"  # type: ignore[attr-defined]
    )


def _py_report(path: Path) -> str:
    """Rebuild the canonical report ``PageInheritProbe`` emits, field-for-field."""
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


@requires_oracle
def test_page_inheritance_matches_pdfbox(tmp_path: Path) -> None:
    """Resolved MediaBox/CropBox/Rotate/Resources for every page in a
    multi-level inheritable page tree must match Apache PDFBox exactly,
    including multi-level inheritance, CropBox→MediaBox default, and Rotate
    normalisation. Page count + traversal order are pinned by the count line
    and the per-page ordering."""
    pdf = tmp_path / "multi_level_inherit.pdf"
    _build_multi_level_pdf(pdf)

    java = run_probe_text("PageInheritProbe", str(pdf))
    py = _py_report(pdf)

    assert py == java, (
        "page-tree attribute inheritance diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
