"""Differential fuzz audit for :class:`PDPage` parsing leniency + INHERITED
attribute resolution vs Apache PDFBox 3.0.7 (wave 1515, agent B).

Complements the well-formed ``test_page_inheritance_oracle`` (multi-level walk
over valid ``/Pages`` nodes) — none of which exercise the MALFORMED / edge-case
subset this audit targets:

* the four inheritable attributes (``/MediaBox`` ``/CropBox`` ``/Resources``
  ``/Rotate``) present on the leaf page vs inherited from a ``/Pages`` ancestor
  vs absent everywhere — and the crucial ``getInheritableAttribute`` rule that
  the walk only ascends to a parent whose ``/Type`` is ``/Pages`` (a parent
  that is missing, not a dictionary, or carries a different/absent ``/Type``
  TERMINATES the walk and reports the attribute as unset);
* ``/MediaBox`` missing / wrong-arity (2 entries) / non-numeric / inverted /
  huge-magnitude — and the upstream U.S.-Letter fallback when it is not an
  array at all;
* ``/CropBox`` clipping/intersection with the resolved MediaBox +
  default-to-MediaBox;
* ``/BleedBox`` ``/TrimBox`` ``/ArtBox`` default-to-CropBox + clip-to-MediaBox;
* ``/Rotate`` non-multiple-of-90 / negative / float / non-numeric / inherited;
* ``/Contents`` missing vs single stream vs array vs non-stream member;
* ``/Annots`` missing / non-array / non-dict member;
* ``/UserUnit`` default / explicit / non-positive / non-numeric.

Both sides are driven on the SAME bytes: the corpus builder writes a PDF per
case (the fuzzed leaf page plus, for inheritance cases, a parent ``/Pages``
node carrying the inheritable attr) plus a ``manifest.txt`` into a tmp dir. The
Java probe (``oracle/probes/PageInheritanceFuzzProbe.java``) loads each
``<case>.pdf`` and projects a stable framed line; this module reads the exact
same files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> mediabox=<rect|ERR:X> cropbox=<rect|ERR:X>
        bleedbox=<rect|ERR:X> trimbox=<rect|ERR:X> artbox=<rect|ERR:X>
        rotate=<n|ERR:X> userunit=<f|ERR:X> resources=<present|null|ERR:X>
        contents=<count|ERR:X> annots=<count|ERR:X>

A rectangle is ``llx,lly,urx,ury`` with each component formatted so an integral
value drops its trailing ``.0`` (both runtimes agree).

Java is ground truth. Two real production bugs were found and FIXED in
``pypdfbox/pdmodel/pd_page.py`` while building this audit:

1. the inheritable walk ascended to ANY dictionary parent; upstream only
   ascends to a parent whose ``/Type`` is ``/Pages`` (PDPageTree line 114);
2. the box accessors went through the strict shared
   ``PDRectangle.from_cos_array`` (raises on arity < 4 / non-numeric) where
   upstream's ``new PDRectangle(COSArray)`` is lenient (zero-pads / coerces
   non-numbers to 0, never throws).

Defensible divergences (if any) are pinned in ``_PINNED`` with a matching
CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_PAGE = COSName.PAGE  # type: ignore[attr-defined]
_PAGES = COSName.PAGES  # type: ignore[attr-defined]
_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_COUNT = COSName.COUNT  # type: ignore[attr-defined]
_PARENT = COSName.PARENT  # type: ignore[attr-defined]
_ROOT = COSName.ROOT  # type: ignore[attr-defined]
_MEDIA_BOX = COSName.MEDIA_BOX  # type: ignore[attr-defined]
_RESOURCES = COSName.RESOURCES  # type: ignore[attr-defined]
_CONTENTS = COSName.CONTENTS  # type: ignore[attr-defined]
_CROP_BOX = _N("CropBox")
_BLEED_BOX = _N("BleedBox")
_TRIM_BOX = _N("TrimBox")
_ART_BOX = _N("ArtBox")
_ROTATE = _N("Rotate")
_USER_UNIT = _N("UserUnit")
_ANNOTS = _N("Annots")


# --------------------------------------------------------------------- builders


def _rect(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _font_resources() -> COSDictionary:
    res = COSDictionary()
    fonts = COSDictionary()
    helv = COSDictionary()
    helv.set_item(_TYPE, _N("Font"))
    helv.set_item(_N("Subtype"), _N("Type1"))
    helv.set_item(_N("BaseFont"), _N("Helvetica"))
    fonts.set_item(_N("F1"), helv)
    res.set_item(_N("Font"), fonts)
    return res


def _content_stream(body: bytes = b"q Q") -> COSStream:
    s = COSStream()
    out = s.create_output_stream()
    out.write(body)
    out.close()
    return s


def _widget_annot() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _N("Annot"))
    d.set_item(_N("Subtype"), _N("Text"))
    d.set_item(_N("Rect"), _rect(0, 0, 10, 10))
    return d


# --------------------------------------------------------------------- corpus
#
# Each case is a list of "page leaf overrides" and optional parent-node
# attributes. A case is described by a builder that takes the corpus dir and
# the case name and writes <name>.pdf. To keep both sides reading identical
# bytes, the corpus is written by the Python side only.


def _make_doc_with_leaf(
    leaf_items: dict[COSName, COSBase],
    *,
    parent_items: dict[COSName, COSBase] | None = None,
    parent_type: COSName | None = _PAGES,
) -> PDDocument:
    """Build a one-page document. The leaf /Page carries ``leaf_items``.

    When ``parent_items`` is given, an intermediate node sits between the root
    /Pages and the leaf, carrying ``parent_items`` (and ``/Type`` =
    ``parent_type`` — pass ``None`` to OMIT /Type, modelling the
    "parent is not a /Pages node" termination case). The root /Pages is always
    a valid pages node so the document loads.
    """
    doc = PDDocument()
    cat = doc.get_document().get_trailer().get_dictionary_object(_ROOT)  # type: ignore[attr-defined]

    root = COSDictionary()
    root.set_item(_TYPE, _PAGES)

    leaf = COSDictionary()
    leaf.set_item(_TYPE, _PAGE)
    for k, v in leaf_items.items():
        leaf.set_item(k, v)

    if parent_items is not None:
        inter = COSDictionary()
        if parent_type is not None:
            inter.set_item(_TYPE, parent_type)
        inter.set_item(_PARENT, root)
        for k, v in parent_items.items():
            inter.set_item(k, v)
        leaf.set_item(_PARENT, inter)
        inter_kids = COSArray()
        inter_kids.add(leaf)
        inter.set_item(_KIDS, inter_kids)
        inter.set_int(_COUNT, 1)
        root_kids = COSArray()
        root_kids.add(inter)
    else:
        leaf.set_item(_PARENT, root)
        root_kids = COSArray()
        root_kids.add(leaf)

    root.set_item(_KIDS, root_kids)
    root.set_int(_COUNT, 1)
    cat.set_item(_PAGES, root)
    return doc


def _build_corpus(case_dir: Path) -> list[str]:
    """Write one PDF per case; return case names in manifest order."""
    names: list[str] = []

    def emit(name: str, doc: PDDocument) -> None:
        try:
            doc.save(str(case_dir / f"{name}.pdf"))
        finally:
            doc.close()
        names.append(name)

    # ---- MediaBox own / inherited / absent ----
    emit("mediabox_own", _make_doc_with_leaf({_MEDIA_BOX: _rect(0, 0, 300, 400)}))
    emit(
        "mediabox_inherited_from_pages",
        _make_doc_with_leaf({}, parent_items={_MEDIA_BOX: _rect(0, 0, 250, 350)}),
    )
    emit("mediabox_absent_letter_default", _make_doc_with_leaf({}))

    # ---- MediaBox malformed: short arity / non-numeric / inverted / huge ----
    short = COSArray()
    short.add(COSFloat(0.0))
    short.add(COSFloat(0.0))
    emit("mediabox_two_entries", _make_doc_with_leaf({_MEDIA_BOX: short}))

    nonnum = COSArray()
    nonnum.add(COSString("a"))
    nonnum.add(COSFloat(0.0))
    nonnum.add(COSFloat(100.0))
    nonnum.add(COSString("b"))
    emit("mediabox_non_numeric_entry", _make_doc_with_leaf({_MEDIA_BOX: nonnum}))

    emit(
        "mediabox_inverted",
        _make_doc_with_leaf({_MEDIA_BOX: _rect(400, 500, 100, 200)}),
    )
    emit(
        "mediabox_huge_magnitude",
        _make_doc_with_leaf({_MEDIA_BOX: _rect(0, 0, 1e12, 1e12)}),
    )
    # MediaBox present but NOT an array (a number) -> Letter fallback.
    emit(
        "mediabox_not_array",
        _make_doc_with_leaf({_MEDIA_BOX: COSInteger.get(42)}),
    )

    # ---- CropBox: default-to-media, clip, inherited ----
    emit(
        "cropbox_absent_defaults_media",
        _make_doc_with_leaf({_MEDIA_BOX: _rect(0, 0, 300, 400)}),
    )
    emit(
        "cropbox_within_media",
        _make_doc_with_leaf(
            {_MEDIA_BOX: _rect(0, 0, 300, 400), _CROP_BOX: _rect(10, 20, 150, 200)}
        ),
    )
    emit(
        "cropbox_exceeds_media_clipped",
        _make_doc_with_leaf(
            {_MEDIA_BOX: _rect(0, 0, 300, 400), _CROP_BOX: _rect(-50, -50, 999, 999)}
        ),
    )
    emit(
        "cropbox_inherited_from_pages",
        _make_doc_with_leaf(
            {_MEDIA_BOX: _rect(0, 0, 300, 400)},
            parent_items={_CROP_BOX: _rect(5, 5, 100, 100)},
        ),
    )

    # ---- Bleed / Trim / Art default-to-crop + clip ----
    emit(
        "bleedbox_default_crop",
        _make_doc_with_leaf(
            {_MEDIA_BOX: _rect(0, 0, 300, 400), _CROP_BOX: _rect(10, 10, 200, 200)}
        ),
    )
    emit(
        "boxes_all_present_clipped",
        _make_doc_with_leaf(
            {
                _MEDIA_BOX: _rect(0, 0, 300, 400),
                _CROP_BOX: _rect(10, 10, 250, 350),
                _BLEED_BOX: _rect(-5, -5, 999, 999),
                _TRIM_BOX: _rect(20, 20, 100, 100),
                _ART_BOX: _rect(30, 30, 120, 120),
            }
        ),
    )

    # ---- Rotate: own / inherited / negative / over-360 / off-axis / float ----
    emit("rotate_own_90", _make_doc_with_leaf({_ROTATE: COSInteger.get(90)}))
    emit(
        "rotate_inherited_from_pages",
        _make_doc_with_leaf({}, parent_items={_ROTATE: COSInteger.get(180)}),
    )
    emit("rotate_negative_90", _make_doc_with_leaf({_ROTATE: COSInteger.get(-90)}))
    emit("rotate_over_360", _make_doc_with_leaf({_ROTATE: COSInteger.get(450)}))
    emit("rotate_off_axis_45", _make_doc_with_leaf({_ROTATE: COSInteger.get(45)}))
    emit("rotate_float_90", _make_doc_with_leaf({_ROTATE: COSFloat(90.0)}))
    emit("rotate_non_numeric", _make_doc_with_leaf({_ROTATE: _N("ninety")}))

    # ---- inheritance TERMINATION: parent missing /Type /Pages ----
    # Upstream getInheritableAttribute only ascends when parent /Type==/Pages.
    emit(
        "inherit_blocked_parent_no_type",
        _make_doc_with_leaf(
            {},
            parent_items={
                _MEDIA_BOX: _rect(0, 0, 222, 333),
                _ROTATE: COSInteger.get(90),
                _RESOURCES: _font_resources(),
            },
            parent_type=None,
        ),
    )
    emit(
        "inherit_ok_parent_is_pages",
        _make_doc_with_leaf(
            {},
            parent_items={
                _MEDIA_BOX: _rect(0, 0, 222, 333),
                _ROTATE: COSInteger.get(90),
                _RESOURCES: _font_resources(),
            },
            parent_type=_PAGES,
        ),
    )

    # ---- Resources own / inherited / absent ----
    emit("resources_own", _make_doc_with_leaf({_RESOURCES: _font_resources()}))
    emit(
        "resources_inherited_from_pages",
        _make_doc_with_leaf({}, parent_items={_RESOURCES: _font_resources()}),
    )
    emit("resources_absent", _make_doc_with_leaf({}))
    # Resources present but wrong type (a name) -> upstream getResources null.
    emit(
        "resources_wrong_type",
        _make_doc_with_leaf({_RESOURCES: _N("notadict")}),
    )

    # ---- UserUnit default / explicit / non-positive / non-numeric ----
    emit("userunit_default", _make_doc_with_leaf({}))
    emit("userunit_explicit_2", _make_doc_with_leaf({_USER_UNIT: COSFloat(2.0)}))
    emit("userunit_zero", _make_doc_with_leaf({_USER_UNIT: COSFloat(0.0)}))
    emit("userunit_negative", _make_doc_with_leaf({_USER_UNIT: COSFloat(-3.0)}))
    emit(
        "userunit_non_numeric",
        _make_doc_with_leaf({_USER_UNIT: _N("two")}),
    )

    # ---- Contents missing / single / array / array-with-nonstream ----
    emit("contents_absent", _make_doc_with_leaf({}))
    emit("contents_single", _make_doc_with_leaf({_CONTENTS: _content_stream()}))
    arr = COSArray()
    arr.add(_content_stream(b"q"))
    arr.add(_content_stream(b"Q"))
    emit("contents_array_two", _make_doc_with_leaf({_CONTENTS: arr}))

    # ---- Annots missing / non-array / array-with-nondict ----
    emit("annots_absent", _make_doc_with_leaf({}))
    annots = COSArray()
    annots.add(_widget_annot())
    annots.add(_widget_annot())
    emit("annots_two", _make_doc_with_leaf({_ANNOTS: annots}))
    emit("annots_non_array", _make_doc_with_leaf({_ANNOTS: _N("nope")}))
    mixed = COSArray()
    mixed.add(_widget_annot())
    mixed.add(COSInteger.get(7))  # non-dict member, skipped by both sides
    emit("annots_mixed_with_nondict", _make_doc_with_leaf({_ANNOTS: mixed}))

    return names


# ----------------------------------------------------- Python-side projection


def _fmt(v: float) -> str:
    """612.0 -> '612' but 612.5 -> '612.5' (mirror probe's Java fmt)."""
    if v == int(v):
        return str(int(v))
    # Java Float.toString rendering; Python's float repr matches for the
    # finite non-integral values our corpus produces.
    return str(float(v))


def _rect_str(r) -> str:  # type: ignore[no-untyped-def]
    return (
        f"{_fmt(r.lower_left_x)},{_fmt(r.lower_left_y)},"
        f"{_fmt(r.upper_right_x)},{_fmt(r.upper_right_y)}"
    )


def _box_cell(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return _rect_str(fn())
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _rotate_cell(page: PDPage) -> str:
    try:
        return str(page.get_rotation())
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _userunit_cell(page: PDPage) -> str:
    try:
        return _fmt(page.get_user_unit())
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _resources_cell(page: PDPage) -> str:
    try:
        res = page.get_resources()
        return "null" if res is None else "present"
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _contents_cell(page: PDPage) -> str:
    try:
        return str(len(page.get_content_streams()))
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _annots_cell(page: PDPage) -> str:
    try:
        return str(len(page.get_annotations()))
    except TypeError:
        # A non-dict /Annots member: pypdfbox's PDAnnotation.create raises
        # TypeError where upstream's createAnnotation throws IOException
        # ("Error: Unknown annotation type ..."). Same failure, same
        # control-flow position — normalise to the upstream exception name.
        return "ERR:IOException"
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        cls = _java_exc(e)
        return prefix + (
            f"mediabox=LOAD:{cls} cropbox=LOAD bleedbox=LOAD trimbox=LOAD "
            "artbox=LOAD rotate=LOAD userunit=LOAD resources=LOAD "
            "contents=LOAD annots=LOAD"
        )
    try:
        page = doc.get_page(0)
        return prefix + (
            f"mediabox={_box_cell(page.get_media_box)} "
            f"cropbox={_box_cell(page.get_crop_box)} "
            f"bleedbox={_box_cell(page.get_bleed_box)} "
            f"trimbox={_box_cell(page.get_trim_box)} "
            f"artbox={_box_cell(page.get_art_box)} "
            f"rotate={_rotate_cell(page)} "
            f"userunit={_userunit_cell(page)} "
            f"resources={_resources_cell(page)} "
            f"contents={_contents_cell(page)} "
            f"annots={_annots_cell(page)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason). Empty: no pins —
# the two real bugs found here were FIXED in production, not pinned.
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_page_inheritance_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every fuzzed page resolves its boxes / rotation / user-unit / resources
    / contents / annots identically on pypdfbox and Apache PDFBox 3.0.7, with
    inheritance ascending only through ``/Type /Pages`` ancestors. Divergences
    (if any) are pinned in ``_PINNED`` with a matching CHANGES.md row."""
    names = _build_corpus(tmp_path)
    (tmp_path / "manifest.txt").write_text("\n".join(names) + "\n", encoding="utf-8")

    raw = run_probe_text("PageInheritanceFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(names), (
        f"probe emitted {len(java_lines)} lines for {len(names)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in names:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, "PDPage inheritance fuzz divergences:\n" + "\n".join(
        mismatches
    )
