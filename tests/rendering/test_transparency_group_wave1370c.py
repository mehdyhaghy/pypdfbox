"""Transparency-group rendering tests extending the existing isolation
/ knockout coverage in
:mod:`tests.rendering.test_pdf_renderer_knockout_isolation`.

This file focuses on the corner cases that aren't directly covered:

* ``/Group`` with no ``/S`` entry — must NOT be treated as a transparency
  group (treated as a plain form XObject).
* ``/Group/S`` with an unknown name — defensive: must not raise, must
  not treat as transparency group.
* Nested transparency groups: a group inside a group.
* ``/CS`` entries other than DeviceRGB (DeviceCMYK / DeviceGray) — must
  be accepted (and logged + ignored by the lite renderer).
* The ``_is_transparency_group`` classifier helper across input shapes.
* Transparency group with ``/I true`` and ``/K`` not present — the
  default (``False``) knockout behavior is followed.
"""
from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 12,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


def _build_form(content: bytes, bbox_size: float = 100.0) -> PDFormXObject:
    stream = COSStream()
    stream.set_raw_data(content)
    form = PDFormXObject(stream)
    form.set_b_box(PDRectangle(0.0, 0.0, bbox_size, bbox_size))
    return form


# ---------------------------------------------------------------------------
# classifier — _is_transparency_group
# ---------------------------------------------------------------------------


def test_is_transparency_group_returns_false_for_form_without_group() -> None:
    form = _build_form(b"")
    assert PDFRenderer._is_transparency_group(form) is False


def test_is_transparency_group_returns_false_for_group_without_s() -> None:
    """A form with /Group but no /S entry is not a transparency group."""
    form = _build_form(b"")
    group = COSDictionary()
    # Intentionally do NOT set /S.
    group.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB"))
    form.set_group(group)
    assert PDFRenderer._is_transparency_group(form) is False


def test_is_transparency_group_returns_false_for_unknown_s_subtype() -> None:
    """A /Group/S that is not /Transparency must not be classified as a
    transparency group."""
    form = _build_form(b"")
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("FooBar"))
    form.set_group(group)
    assert PDFRenderer._is_transparency_group(form) is False


def test_is_transparency_group_handles_non_dict_group() -> None:
    """A /Group entry that's not a dict (defensive against malformed
    PDFs) must not crash; treat as non-group."""

    class _Form:
        def get_group(self):
            return "not a dict"

        is_transparency_group = None  # absent on this stub

    # The helper preferred get_group(); falling through to direct dict
    # inspection should refuse the non-dict and return False.
    assert PDFRenderer._is_transparency_group(_Form()) is False


def test_is_transparency_group_helper_method_short_circuits() -> None:
    """If the form exposes a callable ``is_transparency_group``, the
    classifier defers to it."""

    class _Form:
        def is_transparency_group(self) -> bool:
            return True

        def get_group(self):
            return None  # would normally yield False without override

    assert PDFRenderer._is_transparency_group(_Form()) is True


def test_is_transparency_group_helper_handles_exceptions() -> None:
    """If ``is_transparency_group`` raises, the classifier must fall
    back to the dict inspection path rather than propagating the error."""

    class _Form:
        def is_transparency_group(self) -> bool:
            raise RuntimeError("boom")

        def get_group(self):
            d = COSDictionary()
            d.set_item(
                COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
            )
            return d

    assert PDFRenderer._is_transparency_group(_Form()) is True


# ---------------------------------------------------------------------------
# rendering — non-group form still paints
# ---------------------------------------------------------------------------


def test_form_without_group_renders_as_plain_form() -> None:
    """A form XObject without /Group should render through the plain
    form path (no transparency-group buffering) and still produce
    visible pixels."""
    doc, page = _make_doc(50.0, 50.0)
    form = _build_form(b"1 0 0 rg\n10 10 30 30 re\nf\n", bbox_size=50.0)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((25, 25))
    assert _is_close(inside, (255, 0, 0), tol=20), inside


# ---------------------------------------------------------------------------
# /CS entries — DeviceGray + DeviceCMYK + Lab + ICCBased
# ---------------------------------------------------------------------------


def test_transparency_group_with_device_gray_cs_renders() -> None:
    """A transparency group with /CS /DeviceGray should still paint —
    the lite renderer composes in sRGB and logs/ignores the CS hint."""
    doc, page = _make_doc(50.0, 50.0)
    form = _build_form(b"1 0 0 rg\n10 10 30 30 re\nf\n", bbox_size=50.0)
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    group.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceGray"))
    form.set_group(group)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((25, 25))
    assert _is_close(inside, (255, 0, 0), tol=30), inside


def test_transparency_group_with_device_cmyk_cs_renders() -> None:
    doc, page = _make_doc(50.0, 50.0)
    form = _build_form(b"0 1 0 rg\n10 10 30 30 re\nf\n", bbox_size=50.0)
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    group.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceCMYK"))
    form.set_group(group)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((25, 25))
    assert _is_close(inside, (0, 255, 0), tol=30), inside


def test_transparency_group_with_lab_array_cs_renders() -> None:
    """/CS may also be an array form like [/CalRGB <<...>>]. The lite
    renderer accepts the entry verbatim and logs / ignores."""
    doc, page = _make_doc(50.0, 50.0)
    form = _build_form(b"0 0 1 rg\n10 10 30 30 re\nf\n", bbox_size=50.0)
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("Lab"))
    lab_params = COSDictionary()
    white = COSArray()
    for v in (0.9505, 1.0, 1.0890):
        white.add(COSFloat(v))
    lab_params.set_item(COSName.get_pdf_name("WhitePoint"), white)
    cs_array.add(lab_params)
    group.set_item(COSName.get_pdf_name("CS"), cs_array)
    form.set_group(group)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((25, 25))
    assert _is_close(inside, (0, 0, 255), tol=30), inside


# ---------------------------------------------------------------------------
# nested transparency groups
# ---------------------------------------------------------------------------


def test_nested_transparency_groups_render_both_paints() -> None:
    """An outer transparency group containing an inner transparency
    group should paint both shapes when both are opaque."""
    doc, page = _make_doc(100.0, 100.0)

    # Inner form: green 30x30 rect at (10, 10).
    inner = _build_form(b"0 1 0 rg\n10 10 30 30 re\nf\n", bbox_size=100.0)
    inner_group = COSDictionary()
    inner_group.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
    )
    inner.set_group(inner_group)

    # Outer form: contains a red 20x20 rect at (50, 50) AND invokes the inner.
    outer_resources = PDResources()
    outer_resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Inner"),
        inner.get_cos_object(),
    )
    outer = _build_form(
        b"1 0 0 rg\n50 50 20 20 re\nf\n"
        b"q\n/Inner Do\nQ\n",
        bbox_size=100.0,
    )
    outer.set_resources(outer_resources)
    outer_group = COSDictionary()
    outer_group.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
    )
    outer.set_group(outer_group)

    page_resources = PDResources()
    page.set_resources(page_resources)
    page_resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Outer"),
        outer.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/Outer Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Green from inner: PDF (10..40, 10..40) → PIL (10..40, 60..90).
    green = img.getpixel((25, 75))
    # Red from outer: PDF (50..70, 50..70) → PIL (50..70, 30..50).
    red = img.getpixel((60, 40))
    assert _is_close(green, (0, 255, 0), tol=30), green
    assert _is_close(red, (255, 0, 0), tol=30), red


# ---------------------------------------------------------------------------
# /I and /K defaults
# ---------------------------------------------------------------------------


def test_transparency_group_with_i_true_and_no_k_uses_default_no_knockout() -> None:
    """``/I true`` alone (no /K) should behave as non-knockout — both
    shapes inside the group remain visible (red painted first, green
    overlapping on top)."""
    doc, page = _make_doc(100.0, 100.0)
    form_stream = COSStream()
    form_stream.set_raw_data(
        b"1 0 0 rg\n20 20 40 40 re\nf\n"
        b"0 1 0 rg\n40 40 40 40 re\nf\n"
    )
    form = PDFormXObject(form_stream)
    form.set_b_box(PDRectangle(0.0, 0.0, 100.0, 100.0))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    group.set_item(COSName.get_pdf_name("I"), COSBoolean.get(True))
    # /K explicitly NOT set — should default to False.
    form.set_group(group)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Red-only PIL (30, 70) — red square's lower-left region.
    red = img.getpixel((30, 70))
    # Green-only PIL (70, 30) — green square's upper-right region.
    green = img.getpixel((70, 30))
    assert _is_close(red, (255, 0, 0), tol=20), red
    assert _is_close(green, (0, 255, 0), tol=20), green


def test_transparency_group_with_only_s_renders_baseline() -> None:
    """A transparency group with just /S=/Transparency (no /I, no /K, no
    /CS) is the simplest possible declaration; render must work."""
    doc, page = _make_doc(60.0, 60.0)
    form_stream = COSStream()
    form_stream.set_raw_data(
        b"0.5 0 0.5 rg\n10 10 40 40 re\nf\n"
    )
    form = PDFormXObject(form_stream)
    form.set_b_box(PDRectangle(0.0, 0.0, 60.0, 60.0))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    form.set_group(group)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((25, 30))
    # ~purple (0.5, 0, 0.5) → (128, 0, 128).
    assert _is_close(inside, (128, 0, 128), tol=40), inside
