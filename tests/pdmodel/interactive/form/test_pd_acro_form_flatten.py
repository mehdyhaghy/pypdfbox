from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDNonTerminalField,
    PDTextField,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------- helpers ----------


def _make_form_xobject(bbox: tuple[float, float, float, float]) -> COSStream:
    """Build a minimal Form XObject stream with the given /BBox."""
    s = COSStream()
    s.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    s.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    s.set_item(COSName.get_pdf_name("FormType"), COSName.get_pdf_name("1"))
    arr = COSArray()
    from pypdfbox.cos import COSFloat

    for v in bbox:
        arr.add(COSFloat(float(v)))
    s.set_item(COSName.get_pdf_name("BBox"), arr)
    # Body — a couple of operators so the stream is non-empty (does not
    # need to be valid graphics; the flattener only references it).
    s.set_raw_data(b"q Q\n")
    return s


def _attach_widget(
    field_dict: COSDictionary,
    page: PDPage,
    rect: tuple[float, float, float, float],
    appearance: COSStream | None,
) -> COSDictionary:
    """Build a merged-widget field dict (no /Kids — field acts as widget),
    attach to ``page``'s /Annots and seed /AP /N."""
    field_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    field_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    arr = COSArray()
    from pypdfbox.cos import COSFloat

    for v in rect:
        arr.add(COSFloat(float(v)))
    field_dict.set_item(COSName.get_pdf_name("Rect"), arr)
    field_dict.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    if appearance is not None:
        ap = COSDictionary()
        ap.set_item(COSName.get_pdf_name("N"), appearance)
        field_dict.set_item(COSName.get_pdf_name("AP"), ap)
    # /Annots on page
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    if not isinstance(annots, COSArray):
        annots = COSArray()
        page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    annots.add(field_dict)
    return field_dict


def _make_document_with_form() -> tuple[PDDocument, PDAcroForm]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    doc.add_page(page)
    catalog = doc.get_document_catalog()
    form = PDAcroForm(doc)
    catalog.set_acro_form(form)
    return doc, form


def _page_contents_bytes(page: PDPage) -> bytes:
    return page.get_contents()


# ---------- tests ----------


def test_flatten_single_widget_appends_form_to_page_and_drops_acro_form() -> None:
    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    text = PDTextField(form)
    text.set_partial_name("name")
    appearance = _make_form_xobject((0.0, 0.0, 200.0, 50.0))
    _attach_widget(
        text.get_cos_object(),
        page,
        (100.0, 100.0, 300.0, 150.0),
        appearance,
    )
    form.set_fields([text])

    form.flatten()

    # /AcroForm gone from catalog.
    assert doc.get_document_catalog().get_acro_form() is None
    # /Annots on the page is now empty.
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert isinstance(annots, COSArray)
    assert annots.size() == 0
    # /Resources /XObject contains exactly one entry referencing our form.
    res = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
    assert isinstance(res, COSDictionary)
    xo = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
    assert isinstance(xo, COSDictionary)
    keys = list(xo.key_set())
    assert len(keys) == 1
    name = keys[0].name
    assert xo.get_dictionary_object(name) is appearance
    # Page content stream contains a Do operator referencing it.
    contents = _page_contents_bytes(page)
    assert f"/{name} Do".encode("ascii") in contents
    # And the canonical q ... cm ... Q wrapper is present.
    assert b"q " in contents
    assert b" cm " in contents
    assert b" Q" in contents


def test_flatten_two_widgets_same_page_get_unique_names() -> None:
    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    field_a = PDTextField(form)
    field_a.set_partial_name("a")
    ap_a = _make_form_xobject((0.0, 0.0, 100.0, 20.0))
    _attach_widget(field_a.get_cos_object(), page, (50.0, 50.0, 150.0, 70.0), ap_a)
    field_b = PDTextField(form)
    field_b.set_partial_name("b")
    ap_b = _make_form_xobject((0.0, 0.0, 100.0, 20.0))
    _attach_widget(field_b.get_cos_object(), page, (50.0, 100.0, 150.0, 120.0), ap_b)
    form.set_fields([field_a, field_b])

    form.flatten()

    res = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
    assert isinstance(res, COSDictionary)
    xo = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
    assert isinstance(xo, COSDictionary)
    keys = sorted(k.name for k in xo.key_set())
    assert len(keys) == 2
    assert len(set(keys)) == 2  # truly unique
    # Both Do operators referenced in the content stream.
    contents = _page_contents_bytes(page)
    for k in keys:
        assert f"/{k} Do".encode("ascii") in contents


def test_flatten_widget_without_appearance_is_skipped_no_error() -> None:
    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    field = PDTextField(form)
    field.set_partial_name("missing_ap")
    # No appearance — pass appearance=None.
    _attach_widget(field.get_cos_object(), page, (10.0, 10.0, 60.0, 30.0), None)
    form.set_fields([field])

    form.flatten()  # must not raise.

    # The widget IS removed from /Annots even though it had no drawable
    # appearance — matches upstream PDFBox, whose flatten removes every mapped
    # widget regardless of whether an /AP /N was rendered (verified against the
    # live oracle in tests/.../oracle/test_flatten_oracle.py). A leftover
    # interactive widget after flatten would be a bug.
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert isinstance(annots, COSArray)
    assert annots.size() == 0
    # No XObject was registered (nothing was drawn for the appearance-less
    # widget).
    res = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
    if isinstance(res, COSDictionary):
        xo = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
        if isinstance(xo, COSDictionary):
            assert xo.size() == 0
    # /AcroForm is still removed when fields=None (caller asked for "all").
    assert doc.get_document_catalog().get_acro_form() is None


def test_flatten_two_pages_each_get_their_own_appended_stream() -> None:
    doc = PDDocument()
    page_a = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page_b = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    doc.add_page(page_a)
    doc.add_page(page_b)
    form = PDAcroForm(doc)
    doc.get_document_catalog().set_acro_form(form)

    field_a = PDTextField(form)
    field_a.set_partial_name("on_a")
    ap_a = _make_form_xobject((0.0, 0.0, 80.0, 20.0))
    _attach_widget(field_a.get_cos_object(), page_a, (10.0, 10.0, 90.0, 30.0), ap_a)

    field_b = PDTextField(form)
    field_b.set_partial_name("on_b")
    ap_b = _make_form_xobject((0.0, 0.0, 80.0, 20.0))
    _attach_widget(field_b.get_cos_object(), page_b, (10.0, 10.0, 90.0, 30.0), ap_b)
    form.set_fields([field_a, field_b])

    form.flatten()

    # Each page got its own XObject + Do reference.
    for page, ap in ((page_a, ap_a), (page_b, ap_b)):
        res = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
        assert isinstance(res, COSDictionary)
        xo = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
        assert isinstance(xo, COSDictionary)
        names = list(xo.key_set())
        assert len(names) == 1
        assert xo.get_dictionary_object(names[0]) is ap
        contents = page.get_contents()
        assert f"/{names[0].name} Do".encode("ascii") in contents
        annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
        assert isinstance(annots, COSArray)
        assert annots.size() == 0


def test_flatten_refresh_appearances_true_invokes_refresh_path() -> None:
    """When ``refresh_appearances=True``, flatten dispatches through
    :meth:`refresh_appearances` (which calls
    ``PDTerminalField.construct_appearances`` on every terminal) before
    flattening. The lite ``construct_appearances`` is a debug-logged
    no-op, so the call must succeed without raising."""
    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    field = PDTextField(form)
    field.set_partial_name("name")
    appearance = _make_form_xobject((0.0, 0.0, 100.0, 20.0))
    _attach_widget(field.get_cos_object(), page, (10.0, 10.0, 110.0, 30.0), appearance)
    form.set_fields([field])

    form.flatten(refresh_appearances=True)  # must not raise.
    assert doc.get_document_catalog().get_acro_form() is None


def test_flatten_subset_keeps_other_fields_and_acro_form() -> None:
    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    keep = PDTextField(form)
    keep.set_partial_name("keep")
    keep_ap = _make_form_xobject((0.0, 0.0, 50.0, 10.0))
    _attach_widget(keep.get_cos_object(), page, (10.0, 10.0, 60.0, 20.0), keep_ap)

    flat = PDTextField(form)
    flat.set_partial_name("flat")
    flat_ap = _make_form_xobject((0.0, 0.0, 50.0, 10.0))
    _attach_widget(flat.get_cos_object(), page, (70.0, 10.0, 120.0, 20.0), flat_ap)
    form.set_fields([keep, flat])

    form.flatten(fields=[flat])

    # /AcroForm survives.
    assert doc.get_document_catalog().get_acro_form() is not None
    # /Fields shrunk to just `keep`.
    fields_now = form.get_fields()
    assert [f.get_partial_name() for f in fields_now] == ["keep"]
    # `keep`'s widget is still in /Annots.
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert isinstance(annots, COSArray)
    assert annots.size() == 1
    # Only the flattened form was appended.
    contents = page.get_contents()
    res = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
    assert isinstance(res, COSDictionary)
    xo = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
    assert isinstance(xo, COSDictionary)
    names = list(xo.key_set())
    assert len(names) == 1
    assert xo.get_dictionary_object(names[0]) is flat_ap
    assert f"/{names[0].name} Do".encode("ascii") in contents


def test_flatten_subset_removes_nested_terminal_from_parent_kids() -> None:
    """A nested terminal field flattened via the subset arm must be removed
    from its *parent's* ``/Kids`` array — not just the root ``/Fields``.

    Mirrors upstream ``PDAcroForm.removeFields`` (line 853): a field with a
    parent is removed from ``parent.getCOSObject().getCOSArray(KIDS)``.
    Before this fix the port only scanned the root ``/Fields`` array, so a
    nested terminal stayed behind as a dangling, widget-less ``/Kids`` entry
    after its widget was stripped from ``/Annots`` — a real divergence
    (wave 1506, agent C)."""
    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    parent = PDNonTerminalField(form)
    parent.set_partial_name("group")

    # Build the nested terminal as a raw COS dict in the parent's /Kids so
    # the field-tree walk (get_field) wires the parent reference correctly,
    # matching how a parsed document presents the hierarchy.
    child_dict = COSDictionary()
    child_dict.set_string(COSName.get_pdf_name("T"), "kid")
    child_dict.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Tx"))
    child_dict.set_item(COSName.get_pdf_name("Parent"), parent.get_cos_object())
    appearance = _make_form_xobject((0.0, 0.0, 100.0, 20.0))
    _attach_widget(child_dict, page, (10.0, 10.0, 110.0, 30.0), appearance)

    kids = COSArray()
    kids.add(child_dict)
    parent.get_cos_object().set_item(COSName.get_pdf_name("Kids"), kids)
    form.set_fields([parent])

    child = form.get_field("group.kid")
    assert child is not None
    assert child.get_parent() is not None

    form.flatten(fields=[child])

    # The nested terminal is gone from the parent's /Kids (upstream parity).
    kids_after = parent.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Kids"))
    assert kids_after is None or kids_after.size() == 0
    # Widget removed from the page /Annots.
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert annots is None or annots.size() == 0
    # The parent field itself survives in the root /Fields (only the child
    # was requested for flatten); /AcroForm survives a partial flatten.
    assert doc.get_document_catalog().get_acro_form() is not None
    root_fields = form.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Fields"))
    assert isinstance(root_fields, COSArray)
    assert root_fields.size() == 1
    assert root_fields.get_object(0) is parent.get_cos_object()
    # The appearance was baked onto the page.
    contents = page.get_contents()
    assert b" Do" in contents


def test_flatten_hidden_widget_is_not_drawn_but_still_removed() -> None:
    """A hidden widget (``/F`` bit 2) must NOT have its appearance baked into
    the page content — but it is still removed from ``/Annots``.

    Mirrors upstream ``PDAcroForm.flatten``: the per-widget draw is gated on
    ``isVisibleAnnotation`` (``!isInvisible() && !isHidden()``) while the
    ``/Annots`` removal happens for every mapped widget regardless. Before
    this fix the port baked a hidden field's appearance into the visible page
    content (wave 1506, agent C)."""
    from pypdfbox.cos import COSInteger

    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    field = PDTextField(form)
    field.set_partial_name("hidden")
    appearance = _make_form_xobject((0.0, 0.0, 100.0, 20.0))
    _attach_widget(field.get_cos_object(), page, (10.0, 10.0, 110.0, 30.0), appearance)
    # Mark the widget hidden (/F bit 2).
    field.get_cos_object().set_item(COSName.get_pdf_name("F"), COSInteger.get(2))
    form.set_fields([field])

    form.flatten()

    # No appearance baked: the page either has no XObject resource or an empty
    # one (the hidden widget's form was not registered).
    res = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
    if isinstance(res, COSDictionary):
        xo = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
        assert xo is None or (isinstance(xo, COSDictionary) and xo.size() == 0)
    # No Do operator appended.
    assert b" Do" not in page.get_contents()
    # But the hidden widget is still removed from /Annots (upstream parity).
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert annots is None or annots.size() == 0


def test_flatten_invisible_widget_is_not_drawn_but_still_removed() -> None:
    """An invisible widget (``/F`` bit 1) is likewise not drawn but is removed
    from ``/Annots`` (upstream ``isVisibleAnnotation`` gate)."""
    from pypdfbox.cos import COSInteger

    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    field = PDTextField(form)
    field.set_partial_name("invisible")
    appearance = _make_form_xobject((0.0, 0.0, 100.0, 20.0))
    _attach_widget(field.get_cos_object(), page, (10.0, 10.0, 110.0, 30.0), appearance)
    field.get_cos_object().set_item(COSName.get_pdf_name("F"), COSInteger.get(1))
    form.set_fields([field])

    form.flatten()

    assert b" Do" not in page.get_contents()
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert annots is None or annots.size() == 0


def test_flatten_checkbox_uses_as_state_to_pick_appearance() -> None:
    """When /AP /N is a state subdictionary, /AS selects which stream."""
    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    field = PDTextField(form)  # PDTextField is fine for this test — we
    # poke the widget /AP /N straight at a state dict; the field type
    # only governs /FT, which flatten ignores.
    field.set_partial_name("box")
    field.get_cos_object().set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    field.get_cos_object().set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    from pypdfbox.cos import COSFloat

    rect = COSArray()
    for v in (5.0, 5.0, 25.0, 25.0):
        rect.add(COSFloat(v))
    field.get_cos_object().set_item(COSName.get_pdf_name("Rect"), rect)
    field.get_cos_object().set_item(COSName.get_pdf_name("P"), page.get_cos_object())

    on_stream = _make_form_xobject((0.0, 0.0, 20.0, 20.0))
    off_stream = _make_form_xobject((0.0, 0.0, 20.0, 20.0))
    n_states = COSDictionary()
    n_states.set_item(COSName.get_pdf_name("Yes"), on_stream)
    n_states.set_item(COSName.get_pdf_name("Off"), off_stream)
    ap = COSDictionary()
    ap.set_item(COSName.get_pdf_name("N"), n_states)
    field.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)
    field.get_cos_object().set_item(COSName.get_pdf_name("AS"), COSName.get_pdf_name("Yes"))

    annots = COSArray()
    annots.add(field.get_cos_object())
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    form.set_fields([field])
    form.flatten()

    res = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
    assert isinstance(res, COSDictionary)
    xo = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
    assert isinstance(xo, COSDictionary)
    names = list(xo.key_set())
    assert len(names) == 1
    # Should have picked the /Yes stream, not /Off.
    assert xo.get_dictionary_object(names[0]) is on_stream


def test_flatten_cyclic_non_terminal_subtree_returns_without_recursing() -> None:
    form = PDAcroForm()
    root = PDNonTerminalField(form)
    root.set_partial_name("root")

    child = COSDictionary()
    child.set_string(COSName.get_pdf_name("T"), "child")
    child_kids = COSArray()
    child_kids.add(root.get_cos_object())
    child.set_item(COSName.get_pdf_name("Kids"), child_kids)

    root_kids = COSArray()
    root_kids.add(child)
    root.get_cos_object().set_item(COSName.get_pdf_name("Kids"), root_kids)
    form.set_fields([root])

    # The cycle guard inside _collect_terminals must let flatten complete
    # without infinite recursion (the point of this test).
    form.flatten(fields=[root])

    # Upstream PDAcroForm.removeFields removes every *passed* field from its
    # array regardless of whether any widget was rendered — a root-level
    # field with no parent is dropped from /Fields. The cyclic subtree never
    # yields a flattenable terminal, but `root` is still removed (mirrors
    # upstream removeFields([root])).
    fields = form.get_fields()
    assert len(fields) == 0
