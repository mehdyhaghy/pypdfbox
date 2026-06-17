"""Live PDFBox differential fuzz for ``PDPage`` page-box / rotation / user-unit
/ annotation ACCESSORS (wave 1552, agent B).

Complements the existing page-box corpora, each of which leaves a slice
unexercised:

* ``test_page_box_oracle.py`` / ``test_page_user_unit_box_oracle.py`` — explicit
  in-spec boxes, the absent-box default chain, the full-overflow clip, and the
  ``/UserUnit`` non-positive clamp.
* ``test_rotate_norm_oracle.py`` — integer ``/Rotate`` normalisation.
* ``test_page_inheritance_fuzz_wave1515.py`` — the inherited-attribute walk plus
  a first pass of malformed boxes (2-entry / non-numeric / inverted /
  positive-huge MediaBox; fully-overflowing CropBox; off-axis / negative /
  over-360 integer Rotate; non-numeric-name UserUnit; non-array Annots).

This module drills into the ACCESSOR edge cases none of the above reach, every
row pinned BOTH-SIDES against the Apache PDFBox 3.0.7 oracle
(``oracle/probes/PageBoxAccessorFuzzProbe.java``):

* ``/MediaBox`` zero-area (degenerate), single-entry / empty array, over-long
  (5+ entries truncated to 4), and negative-huge magnitude (the
  ``-Integer.MAX_VALUE`` clamp arm — wave 1515 only pinned the positive arm).
* ``/CropBox`` wrong-type (a dictionary -> default to MediaBox), one corner
  outside the MediaBox (partial clip / intersection), inverted-then-clipped.
* ``/BleedBox`` ``/TrimBox`` ``/ArtBox`` wrong-type (not an array -> fall back
  to resolved CropBox), zero-area and inverted explicit boxes.
* ``/Rotate`` non-integral float (90.7 truncates to 90, 269.5), off-axis float
  (45.0), huge multiple (3600 / -3600), numeric COSString ("90"), boolean.
* ``/UserUnit`` huge, numeric COSString, boolean.
* ``/Annots`` empty array, wrong-type variants (dict / integer / name), a null
  member (skipped), and a non-dict member (exception-vs-skip parity pin).

Fixtures are built programmatically (one PDF per case + ``manifest.txt``) so we
control the exact COS layout; both sides read identical bytes.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
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


def _widget_annot() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _N("Annot"))
    d.set_item(_N("Subtype"), _N("Text"))
    d.set_item(_N("Rect"), _rect(0, 0, 10, 10))
    return d


def _make_doc_with_leaf(leaf_items: dict[COSName, COSBase]) -> PDDocument:
    """Build a one-page document whose leaf /Page carries ``leaf_items``.

    The root /Pages is always a valid pages node carrying a default MediaBox so
    the page is loadable and a box-less leaf still resolves (the inherited
    MediaBox path is exercised in wave 1515 — here it's just scaffolding so the
    leaf-level malformations are the only variable)."""
    doc = PDDocument()
    cat = doc.get_document().get_trailer().get_dictionary_object(_ROOT)  # type: ignore[attr-defined]

    root = COSDictionary()
    root.set_item(_TYPE, _PAGES)
    root.set_item(_MEDIA_BOX, _rect(0, 0, 300, 400))

    leaf = COSDictionary()
    leaf.set_item(_TYPE, _PAGE)
    for k, v in leaf_items.items():
        leaf.set_item(k, v)
    leaf.set_item(_PARENT, root)

    kids = COSArray()
    kids.add(leaf)
    root.set_item(_KIDS, kids)
    root.set_int(_COUNT, 1)
    cat.set_item(_PAGES, root)
    return doc


# --------------------------------------------------------------------- corpus


def _build_corpus(case_dir: Path) -> list[str]:
    """Write one PDF per case; return case names in manifest order."""
    names: list[str] = []

    def emit(name: str, leaf: dict[COSName, COSBase]) -> None:
        doc = _make_doc_with_leaf(leaf)
        try:
            doc.save(str(case_dir / f"{name}.pdf"))
        finally:
            doc.close()
        names.append(name)

    # ---- MediaBox: degenerate / arity / negative-huge ----
    # Zero-area: x0 == x1. min/max normalisation leaves a 0-width rect.
    emit("media_zero_width", {_MEDIA_BOX: _rect(100, 0, 100, 400)})
    # Zero-area: y0 == y1.
    emit("media_zero_height", {_MEDIA_BOX: _rect(0, 50, 300, 50)})
    # Single entry -> Arrays.copyOf zero-pads to [v,0,0,0].
    one = COSArray()
    one.add(COSFloat(123.0))
    emit("media_one_entry", {_MEDIA_BOX: one})
    # Empty array -> all four zero -> (0,0,0,0).
    emit("media_empty_array", {_MEDIA_BOX: COSArray()})
    # Over-long (6 entries) -> truncated to first 4.
    over = COSArray()
    for v in (10, 20, 110, 220, 999, 888):
        over.add(COSFloat(float(v)))
    emit("media_six_entries", {_MEDIA_BOX: over})
    # Negative-huge magnitude -> -Integer.MAX_VALUE clamp arm.
    emit("media_negative_huge", {_MEDIA_BOX: _rect(-1e12, -1e12, 100, 200)})

    # ---- CropBox: wrong-type / partial-clip / inverted ----
    # CropBox is a dictionary, not an array -> upstream defaults to MediaBox.
    emit(
        "crop_wrong_type_dict",
        {_MEDIA_BOX: _rect(0, 0, 300, 400), _CROP_BOX: COSDictionary()},
    )
    # One corner outside MediaBox -> partial clip (intersection with media).
    emit(
        "crop_partial_outside",
        {_MEDIA_BOX: _rect(0, 0, 300, 400), _CROP_BOX: _rect(50, 50, 500, 350)},
    )
    # Inverted CropBox fully inside -> PDRectangle normalises corners, no clip.
    emit(
        "crop_inverted_inside",
        {_MEDIA_BOX: _rect(0, 0, 300, 400), _CROP_BOX: _rect(200, 300, 50, 100)},
    )

    # ---- Bleed/Trim/Art: wrong-type fallback / zero-area / inverted ----
    # Each wrong-type box (a name) -> falls back to resolved CropBox (=media).
    emit(
        "bleed_wrong_type",
        {_MEDIA_BOX: _rect(0, 0, 300, 400), _BLEED_BOX: _N("nope")},
    )
    emit(
        "trim_wrong_type",
        {_MEDIA_BOX: _rect(0, 0, 300, 400), _TRIM_BOX: COSInteger.get(5)},
    )
    emit(
        "art_wrong_type",
        {_MEDIA_BOX: _rect(0, 0, 300, 400), _ART_BOX: COSDictionary()},
    )
    # Zero-area explicit ArtBox.
    emit(
        "art_zero_area",
        {_MEDIA_BOX: _rect(0, 0, 300, 400), _ART_BOX: _rect(10, 10, 10, 200)},
    )
    # Inverted TrimBox inside media -> corner-normalised, no clip.
    emit(
        "trim_inverted_inside",
        {_MEDIA_BOX: _rect(0, 0, 300, 400), _TRIM_BOX: _rect(150, 250, 40, 60)},
    )

    # ---- Rotate: float / off-axis / huge / string / boolean ----
    # Non-integral float that truncates to a multiple of 90.
    emit("rotate_float_90_7", {_ROTATE: COSFloat(90.7)})
    # Non-integral float truncating to a non-multiple of 90 -> 0.
    emit("rotate_float_269_5", {_ROTATE: COSFloat(269.5)})
    # Off-axis float.
    emit("rotate_float_45", {_ROTATE: COSFloat(45.0)})
    # Huge positive multiple of 90 -> normalises to 0.
    emit("rotate_3600", {_ROTATE: COSInteger.get(3600)})
    # Huge negative multiple of 90 -> normalises to 0.
    emit("rotate_neg_3600", {_ROTATE: COSInteger.get(-3600)})
    # Numeric string "90" -> not a COSNumber -> treated as unset -> 0.
    emit("rotate_string_90", {_ROTATE: COSString("90")})
    # Boolean -> not a COSNumber -> 0.
    emit("rotate_boolean", {_ROTATE: COSBoolean.TRUE})

    # ---- UserUnit: huge / string / boolean ----
    emit("userunit_huge", {_USER_UNIT: COSFloat(1000000.0)})
    emit("userunit_string", {_USER_UNIT: COSString("2.0")})
    emit("userunit_boolean", {_USER_UNIT: COSBoolean.TRUE})

    # ---- Annots: empty / wrong-type / null member / non-dict member ----
    emit("annots_empty_array", {_ANNOTS: COSArray()})
    emit("annots_wrong_type_dict", {_ANNOTS: COSDictionary()})
    emit("annots_wrong_type_int", {_ANNOTS: COSInteger.get(3)})
    emit("annots_wrong_type_name", {_ANNOTS: _N("nope")})
    # A null member is skipped by both sides (upstream `if (item == null)`).
    null_member = COSArray()
    null_member.add(_widget_annot())
    null_member.add(COSNull.NULL)
    null_member.add(_widget_annot())
    emit("annots_null_member", {_ANNOTS: null_member})
    # A non-dict member: upstream createAnnotation throws IOException; pypdfbox
    # raises TypeError at the same control-flow point (normalised in the cell).
    nondict_member = COSArray()
    nondict_member.add(_widget_annot())
    nondict_member.add(COSInteger.get(7))
    emit("annots_nondict_member", {_ANNOTS: nondict_member})

    # ---- combination: malformed boxes + rotation + resources ----
    emit(
        "combo_short_box_rotate_res",
        {
            _MEDIA_BOX: one,  # reuse short array shape (zero-padded)
            _ROTATE: COSFloat(180.0),
            _RESOURCES: _font_resources(),
            _CROP_BOX: _rect(-10, -10, 50, 50),
        },
    )

    return names


# ----------------------------------------------------- Python-side projection


def _fmt(v: float) -> str:
    """612.0 -> '612' but 612.5 -> '612.5' (mirror probe's Java fmt)."""
    if v == int(v):
        return str(int(v))
    return str(float(v))


def _rect_str(r) -> str:  # type: ignore[no-untyped-def]
    return (
        f"{_fmt(r.lower_left_x)},{_fmt(r.lower_left_y)},"
        f"{_fmt(r.upper_right_x)},{_fmt(r.upper_right_y)}"
    )


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _box_cell(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return _rect_str(fn())
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"


def _rotate_cell(page: PDPage) -> str:
    try:
        return str(page.get_rotation())
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"


def _userunit_cell(page: PDPage) -> str:
    try:
        return _fmt(page.get_user_unit())
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"


def _resources_cell(page: PDPage) -> str:
    try:
        res = page.get_resources()
        return "null" if res is None else "present"
    except Exception as e:  # noqa: BLE001
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
    except Exception as e:  # noqa: BLE001
        return f"ERR:{_java_exc(e)}"


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001
        cls = _java_exc(e)
        return prefix + (
            f"mediabox=LOAD:{cls} cropbox=LOAD bleedbox=LOAD trimbox=LOAD "
            "artbox=LOAD rotate=LOAD userunit=LOAD resources=LOAD annots=LOAD"
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
            f"annots={_annots_cell(page)}"
        )
    finally:
        doc.close()


# ----------------------------------------------------------------------- test


@requires_oracle
def test_page_box_accessor_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed/edge page-box / rotation / user-unit / annotation case
    must project identically to Apache PDFBox 3.0.7. A mismatch on any row is a
    real parity bug in a ``PDPage`` accessor."""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    names = _build_corpus(case_dir)
    (case_dir / "manifest.txt").write_text("\n".join(names) + "\n", encoding="utf-8")

    java = run_probe_text("PageBoxAccessorFuzzProbe", str(case_dir))
    java_lines = {
        line.split(" ", 2)[1]: line
        for line in java.splitlines()
        if line.startswith("CASE ")
    }

    mismatches: list[str] = []
    for name in names:
        py = _python_line(case_dir, name)
        jv = java_lines.get(name, "<missing>")
        if py != jv:
            mismatches.append(f"[{name}]\n  py:   {py}\n  java: {jv}")

    assert not mismatches, "PDPage accessor parity diverged:\n" + "\n".join(mismatches)


@requires_oracle
def test_page_box_accessor_fuzz_case_count(tmp_path: Path) -> None:
    """Guard the corpus size so a future edit can't silently drop cases."""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    names = _build_corpus(case_dir)
    assert len(names) == 31
    assert len(set(names)) == len(names)
