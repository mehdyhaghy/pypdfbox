"""Wave 1304 — direct content-stream assertions for
``PDAcroForm.refresh_appearances``.

The earlier waves shipped the appearance generator and wired
``refresh_appearances`` into ``PDTerminalField.construct_appearances``;
these tests assert the exact ``/AP /N`` content-stream shape produced by
:class:`PDAppearanceGenerator` for ``/FT /Tx`` text fields — the
beachhead field-type the wave-1304 work was scoped to. ``/Btn`` /
``/Ch`` / ``/Sig`` are covered indirectly by the existing
``test_pd_appearance_generator*`` suites; this file pins the
text-specific operator sequence (``BT … /F0 12 Tf … (value) Tj ET``)
that downstream consumers rely on.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument

_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_RECT = COSName.get_pdf_name("Rect")


def _make_form() -> tuple[PDDocument, PDAcroForm]:
    doc = PDDocument()
    form = PDAcroForm(doc)
    doc.get_document_catalog().set_acro_form(form)
    return doc, form


def _make_text_field(
    form: PDAcroForm,
    *,
    name: str,
    value: str,
    rect: tuple[float, float, float, float],
    da: str = "/Helv 12 Tf 0 g",
    quadding: int | None = None,
) -> PDTextField:
    field = PDTextField(form)
    field.set_partial_name(name)
    field.set_default_appearance(da)
    field.set_value(value)
    if quadding is not None:
        field.set_q(quadding)
    widget = field.get_widgets()[0]
    rect_arr = COSArray(
        [COSFloat(rect[0]), COSFloat(rect[1]), COSFloat(rect[2]), COSFloat(rect[3])]
    )
    widget.get_cos_object().set_item(_RECT, rect_arr)
    return field


def _appearance_body(field: PDTextField) -> str:
    widget_cos = field.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert ap is not None, "refresh_appearances did not install /AP"
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream), f"/AP /N must be a stream, got {type(n).__name__}"
    return n.to_raw_byte_array().decode("ascii", errors="replace")


def test_refresh_appearances_text_field_emits_tj_with_value() -> None:
    """Tx field with /V "Hello", /DA "/Helv 12 Tf 0 g", /Rect [10 10 100 30] →
    the new /AP /N stream contains ``BT … /F0 12 Tf … (Hello) Tj ET``."""
    _doc, form = _make_form()
    field = _make_text_field(
        form,
        name="name",
        value="Hello",
        rect=(10.0, 10.0, 100.0, 30.0),
        da="/Helv 12 Tf 0 g",
    )
    form.set_fields([field])

    form.refresh_appearances()

    body = _appearance_body(field)
    # Operator sequence — the test pins the order Acrobat / Reader rely on.
    assert "BT" in body
    assert "/F0 12 Tf" in body
    assert "(Hello) Tj" in body
    assert "ET" in body
    # /Tx BMC marked-content sentinel — required for Acrobat to recognise
    # the stream as a form-field appearance (PDF 32000-1 §14.6.2).
    assert "/Tx BMC" in body
    assert "EMC" in body


def test_refresh_appearances_text_field_quadding_centered_shifts_x() -> None:
    """``/Q 1`` (centered) → the text x-offset is greater than the
    left-aligned baseline (2.0pt), so the same string lands further to
    the right inside the same rect."""
    _doc, form_left = _make_form()
    left = _make_text_field(
        form_left,
        name="left",
        value="Hello",
        rect=(10.0, 10.0, 100.0, 30.0),
        da="/Helv 12 Tf 0 g",
        quadding=0,
    )
    form_left.set_fields([left])
    form_left.refresh_appearances()
    left_body = _appearance_body(left)

    _doc2, form_center = _make_form()
    centered = _make_text_field(
        form_center,
        name="center",
        value="Hello",
        rect=(10.0, 10.0, 100.0, 30.0),
        da="/Helv 12 Tf 0 g",
        quadding=1,
    )
    form_center.set_fields([centered])
    form_center.refresh_appearances()
    centered_body = _appearance_body(centered)

    # Both bodies emit a ``<x> <y> Td`` move; the centered x must be
    # strictly greater than the left-aligned 2.0pt baseline.
    def _extract_td_x(body: str) -> float:
        for line in body.splitlines():
            line = line.strip()
            if line.endswith(" Td"):
                parts = line.split()
                return float(parts[0])
        raise AssertionError(f"no Td operator in body:\n{body}")

    left_x = _extract_td_x(left_body)
    center_x = _extract_td_x(centered_body)
    assert left_x == 2.0, f"left-aligned baseline x must be 2.0, got {left_x}"
    assert center_x > left_x, (
        f"centered x ({center_x}) must be > left-aligned x ({left_x})"
    )


def test_refresh_appearances_text_field_right_aligned_shifts_x_further() -> None:
    """``/Q 2`` (right-aligned) → x-offset is strictly greater than both
    left (0) and centered (1) for the same string in the same rect."""
    _doc, form_right = _make_form()
    right = _make_text_field(
        form_right,
        name="right",
        value="Hi",
        rect=(10.0, 10.0, 100.0, 30.0),
        da="/Helv 12 Tf 0 g",
        quadding=2,
    )
    form_right.set_fields([right])
    form_right.refresh_appearances()
    body = _appearance_body(right)

    # Extract Td x — must be the rightmost positive value possible
    # (anchor + (interior_w - text_w)).
    for line in body.splitlines():
        line = line.strip()
        if line.endswith(" Td"):
            parts = line.split()
            x = float(parts[0])
            assert x > 2.0, f"right-aligned x must exceed left baseline, got {x}"
            break
    else:
        raise AssertionError(f"no Td operator in body:\n{body}")


def test_refresh_appearances_text_field_empty_value_emits_no_tj() -> None:
    """Tx field with empty /V → /AP /N is a content stream WITH the
    ``BT … ET`` envelope (Acrobat tolerates that) but WITHOUT a
    ``(…) Tj`` show-text operator."""
    _doc, form = _make_form()
    field = _make_text_field(
        form,
        name="empty",
        value="",
        rect=(10.0, 10.0, 100.0, 30.0),
        da="/Helv 12 Tf 0 g",
    )
    form.set_fields([field])

    form.refresh_appearances()

    body = _appearance_body(field)
    assert "BT" in body
    assert "ET" in body
    # No glyphs drawn — the show-text operator must be absent.
    assert " Tj" not in body
    assert "/Tx BMC" in body
    assert "EMC" in body


def test_refresh_appearances_text_field_color_propagates() -> None:
    """/DA non-black color tokens propagate as set-non-stroking ops in
    the regenerated stream."""
    _doc, form = _make_form()
    field = _make_text_field(
        form,
        name="red",
        value="Hello",
        rect=(10.0, 10.0, 100.0, 30.0),
        da="/Helv 12 Tf 1 0 0 rg",
    )
    form.set_fields([field])

    form.refresh_appearances()

    body = _appearance_body(field)
    # Red — components 1 0 0 followed by ``rg`` (non-stroking RGB).
    assert "1 0 0 rg" in body


def test_refresh_appearances_walks_subset_when_fields_supplied() -> None:
    """When ``fields=[…]`` is supplied, only those fields' appearances
    are rebuilt; un-listed fields keep their pre-existing /AP entry
    untouched."""
    _doc, form = _make_form()
    target = _make_text_field(
        form,
        name="target",
        value="Hello",
        rect=(10.0, 10.0, 100.0, 30.0),
        da="/Helv 12 Tf 0 g",
    )
    other = _make_text_field(
        form,
        name="other",
        value="World",
        rect=(10.0, 40.0, 100.0, 60.0),
        da="/Helv 12 Tf 0 g",
    )
    form.set_fields([target, other])

    # Pre-seed ``other``'s widget with a sentinel /AP that we will assert
    # untouched after the subset refresh.
    from pypdfbox.cos import COSDictionary

    sentinel_n = COSStream()
    sentinel_n.set_raw_data(b"SENTINEL")
    sentinel_ap = COSDictionary()
    sentinel_ap.set_item(_N, sentinel_n)
    other.get_widgets()[0].get_cos_object().set_item(_AP, sentinel_ap)

    form.refresh_appearances([target])

    # ``target`` got a fresh appearance stream — sentinel bytes must NOT
    # be present.
    target_body = _appearance_body(target)
    assert "(Hello) Tj" in target_body
    assert b"SENTINEL" not in target_body.encode("ascii", errors="replace")

    # ``other`` was untouched — sentinel survives.
    other_n = other.get_widgets()[0].get_cos_object().get_dictionary_object(_AP)
    assert other_n is sentinel_ap
    assert other_n.get_dictionary_object(_N) is sentinel_n
    assert sentinel_n.to_raw_byte_array() == b"SENTINEL"


def test_flatten_with_refresh_appearances_true_rebuilds_then_flattens() -> None:
    """End-to-end: ``flatten(refresh_appearances=True)`` regenerates
    every widget's /AP from /V before stamping the page contents. The
    AcroForm catalog entry is dropped once the whole form has been
    flattened."""
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    page = PDPage()
    doc.add_page(page)
    form = PDAcroForm(doc)
    doc.get_document_catalog().set_acro_form(form)

    field = _make_text_field(
        form,
        name="name",
        value="Hello",
        rect=(10.0, 10.0, 100.0, 30.0),
        da="/Helv 12 Tf 0 g",
    )
    # Wire the widget to the page so flatten can find its host.
    widget_cos = field.get_widgets()[0].get_cos_object()
    widget_cos.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    widget_cos.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget")
    )
    widget_cos.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    annots = COSArray()
    annots.add(widget_cos)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    form.set_fields([field])

    form.flatten(refresh_appearances=True)

    # /AcroForm dropped — flatten took the whole-form path.
    assert doc.get_document_catalog().get_acro_form() is None
