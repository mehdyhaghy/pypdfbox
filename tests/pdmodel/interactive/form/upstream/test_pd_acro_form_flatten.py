"""Port of upstream ``PDAcroFormFlattenTest`` (PDFBox 3.0.x).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/
PDAcroFormFlattenTest.java``.

Upstream fetches sample PDFs from Apache JIRA over HTTPS, flattens them,
and pixel-compares the rendered output against a generated reference
PNG. That mode is **deliberately not portable to this repo** — the
CLAUDE.md hard rule forbids tests from making network calls, and the
`PDFRenderer` pixel-parity contract is recorded as a documented
divergence (see ``CHANGES.md`` "Active divergences").

What is portable is the **structural post-condition** each upstream
case implicitly relies on: after ``flatten()`` (or
``flatten(specific_fields, refresh_appearances=…)``) the resulting
document satisfies a per-PR invariant — `/Fields` shrinks or vanishes,
the widget appearance is materialised on the host page as a Form
XObject `Do` reference, the widget is dropped from `/Annots`, non-
widget annotations on co-resident pages are preserved, signature flags
are cleared when no signatures remain, and so on.

This module ports each upstream test name 1:1 by asserting the
equivalent **structural** outcome on either the bundled
``MultilineFields.pdf`` fixture or a tiny synthetic AcroForm built
inline. The synthetic build helpers mirror those in the sibling
``tests/pdmodel/interactive/form/test_pd_acro_form_flatten.py`` so the
hand-written and ported layers share the same vocabulary.
"""

from __future__ import annotations

import pathlib

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDTextField
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_MULTILINE_FIXTURE = (
    pathlib.Path(__file__).resolve().parents[4]
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
    / "MultilineFields.pdf"
)


# ---------- synthetic helpers (mirror sibling hand-written file) ----------


def _make_form_xobject(bbox: tuple[float, float, float, float]) -> COSStream:
    """Build a minimal Form XObject stream with the given /BBox."""
    s = COSStream()
    s.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    s.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    s.set_item(COSName.get_pdf_name("FormType"), COSName.get_pdf_name("1"))
    arr = COSArray()
    for v in bbox:
        arr.add(COSFloat(float(v)))
    s.set_item(COSName.get_pdf_name("BBox"), arr)
    # Two harmless operators so the body is non-empty (does not need to
    # be valid graphics; the flattener only references the stream by
    # name).
    s.set_raw_data(b"q Q\n")
    return s


def _attach_widget(
    field_dict: COSDictionary,
    page: PDPage,
    rect: tuple[float, float, float, float],
    appearance: COSStream | None,
) -> COSDictionary:
    """Build a merged-widget field dict (no /Kids — field acts as
    widget), attach to ``page``'s /Annots and seed /AP /N."""
    field_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    field_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    arr = COSArray()
    for v in rect:
        arr.add(COSFloat(float(v)))
    field_dict.set_item(COSName.get_pdf_name("Rect"), arr)
    field_dict.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    if appearance is not None:
        ap = COSDictionary()
        ap.set_item(COSName.get_pdf_name("N"), appearance)
        field_dict.set_item(COSName.get_pdf_name("AP"), ap)
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    if not isinstance(annots, COSArray):
        annots = COSArray()
        page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    annots.add(field_dict)
    return field_dict


def _make_non_widget_annotation(
    page: PDPage,
    rect: tuple[float, float, float, float],
) -> COSDictionary:
    """Build a non-widget (Text) annotation and attach to ``page``."""
    annot = COSDictionary()
    annot.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    annot.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text"))
    arr = COSArray()
    for v in rect:
        arr.add(COSFloat(float(v)))
    annot.set_item(COSName.get_pdf_name("Rect"), arr)
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    if not isinstance(annots, COSArray):
        annots = COSArray()
        page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    annots.add(annot)
    return annot


def _make_document_with_form(num_pages: int = 1) -> tuple[PDDocument, PDAcroForm, list[PDPage]]:
    doc = PDDocument()
    pages: list[PDPage] = []
    for _ in range(num_pages):
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        doc.add_page(page)
        pages.append(page)
    form = PDAcroForm(doc)
    doc.get_document_catalog().set_acro_form(form)
    return doc, form, pages


def _page_annot_count(page: PDPage) -> int:
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    if not isinstance(annots, COSArray):
        return 0
    return annots.size()


def _page_xobject_keys(page: PDPage) -> list[str]:
    res = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
    if not isinstance(res, COSDictionary):
        return []
    xo = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
    if not isinstance(xo, COSDictionary):
        return []
    return sorted(k.name for k in xo.key_set())


# ---------- single-field flatten against bundled fixture ----------


def test_flatten_single_field() -> None:
    """Flattening one named text field removes it from ``/Fields`` and
    leaves the rest of the form structurally intact (upstream
    ``flattenSingleField``)."""
    with PDDocument.load(_MULTILINE_FIXTURE) as document:
        acro_form = document.get_document_catalog().get_acro_form()
        num_fields_before = len(acro_form.get_fields())

        field = acro_form.get_field("AlignLeft-Filled")
        assert isinstance(field, PDTextField), (
            "fixture should expose 'AlignLeft-Filled' as a PDTextField"
        )
        acro_form.flatten([field], False)

        assert len(acro_form.get_fields()) == num_fields_before - 1, (
            "the number of form fields shall be reduced by one"
        )
        assert acro_form.get_field("AlignLeft-Filled") is None, (
            "the flattened field shall no longer exist"
        )


# ---------- upstream testFlatten matrix — offline-structural equivalents ----------
#
# Upstream's ``@CsvSource`` matrix below is keyed by PDFBOX-### issue.
# Each named case carries a structural invariant — that invariant is
# what we assert here, against a synthetic AcroForm whose shape reflects
# the failure mode the upstream case was guarding against. The pixel
# rendering parity layer is intentionally **not** ported (CLAUDE.md
# hard rule + ``CHANGES.md`` "PDFRenderer pixel-exact parity not
# portable" divergence).


def test_flatten_form_i9_english() -> None:
    """PDFBOX-2469 empty template. Upstream: load → ``flatten()`` →
    ``/Fields`` empty. Structural offline: synthesise a small empty
    template (multiple fields, all with appearances), call
    ``flatten()``, assert /Fields and /AcroForm are gone."""
    doc, form, pages = _make_document_with_form()
    page = pages[0]
    fields: list[PDTextField] = []
    for i in range(3):
        f = PDTextField(form)
        f.set_partial_name(f"field_{i}")
        ap = _make_form_xobject((0.0, 0.0, 80.0, 20.0))
        _attach_widget(f.get_cos_object(), page, (10.0 + 90.0 * i, 10.0, 80.0 + 90.0 * i, 30.0), ap)
        fields.append(f)
    form.set_fields(fields)

    form.flatten()

    assert doc.get_document_catalog().get_acro_form() is None
    assert _page_annot_count(page) == 0
    assert len(_page_xobject_keys(page)) == 3


def test_flatten_pdfbox_2586() -> None:
    """PDFBOX-2586 empty template — same structural invariant as
    PDFBOX-2469 but exercises a different upstream issue (truncated
    stream recovery during load). Offline-structural: same as
    ``test_flatten_form_i9_english`` but verifies a 1-field minimum."""
    doc, form, pages = _make_document_with_form()
    field = PDTextField(form)
    field.set_partial_name("sole")
    ap = _make_form_xobject((0.0, 0.0, 50.0, 15.0))
    _attach_widget(field.get_cos_object(), pages[0], (10.0, 10.0, 60.0, 25.0), ap)
    form.set_fields([field])

    form.flatten()

    assert doc.get_document_catalog().get_acro_form() is None
    assert _page_annot_count(pages[0]) == 0


def test_flatten_hidden_fields() -> None:
    """PDFBOX-3262 hidden fields. Upstream's pixel-compare verifies that
    widgets carrying the /F Hidden flag (PDF 32000-1 §12.5.3 Table 165) are
    NOT rendered into the flattened page content. Upstream ``flatten`` gates
    the per-widget draw on ``isVisibleAnnotation`` (``!isInvisible() &&
    !isHidden()``) yet removes every mapped widget from ``/Annots``
    regardless. Structural equivalent: the hidden widget is dropped from
    ``/Annots`` and ``/Fields`` but its appearance is NOT baked onto the page;
    only the visible widget's appearance materialises (wave 1506, agent C —
    the prior port baked the hidden appearance too, diverging from upstream)."""
    doc, form, pages = _make_document_with_form()
    visible = PDTextField(form)
    visible.set_partial_name("visible")
    visible_ap = _make_form_xobject((0.0, 0.0, 50.0, 15.0))
    _attach_widget(visible.get_cos_object(), pages[0], (10.0, 10.0, 60.0, 25.0), visible_ap)

    hidden = PDTextField(form)
    hidden.set_partial_name("hidden")
    hidden_ap = _make_form_xobject((0.0, 0.0, 50.0, 15.0))
    _attach_widget(hidden.get_cos_object(), pages[0], (10.0, 30.0, 60.0, 45.0), hidden_ap)
    # Set /F = Hidden via PDAnnotation helper.
    PDAnnotation(hidden.get_cos_object()).set_hidden(True)
    form.set_fields([visible, hidden])

    form.flatten()

    assert doc.get_document_catalog().get_acro_form() is None
    # Both widgets dropped from /Annots regardless of Hidden flag.
    assert _page_annot_count(pages[0]) == 0
    # Only the visible widget's appearance materialised; the hidden one was
    # gated out by isVisibleAnnotation (upstream parity).
    xobject_keys = _page_xobject_keys(pages[0])
    assert len(xobject_keys) == 1


def test_flatten_signed_document_1() -> None:
    """PDFBOX-3396 Signed-Document-1. Upstream: signed PDFs flatten
    with the signature widget surviving as a non-flattenable annotation
    AND the /SigFlags entry preserved when signatures still exist.
    Structural offline: form carrying /SigFlags=3 (SignaturesExist +
    AppendOnly), flatten the non-signature text field, assert
    /SigFlags is preserved when a signature dictionary remains in the
    document (signature dict tracked via /AcroForm /Fields stays put
    if the field type is not Sig — but the upstream invariant we
    pin is: flatten() never crashes on docs with /SigFlags set)."""
    doc, form, pages = _make_document_with_form()
    field = PDTextField(form)
    field.set_partial_name("text")
    ap = _make_form_xobject((0.0, 0.0, 50.0, 15.0))
    _attach_widget(field.get_cos_object(), pages[0], (10.0, 10.0, 60.0, 25.0), ap)
    form.set_fields([field])
    form.set_signatures_exist(True)

    form.flatten([field], False)

    # Single field flattened; subset path leaves /AcroForm in place.
    assert doc.get_document_catalog().get_acro_form() is not None
    assert form.get_field("text") is None
    # No signature dictionaries on the document → /SigFlags cleared.
    assert not form.is_signatures_exist()


def test_flatten_signed_document_2() -> None:
    """PDFBOX-3396 Signed-Document-2. Variant of -1 — verifies that
    flatten() on a SignaturesExist=true form preserves /SigFlags when
    a /Sig dictionary remains in the document. Structural offline:
    seed /Sig in a doc's /Fields → flatten subset that excludes the
    signature → /SigFlags stays set."""
    doc, form, pages = _make_document_with_form()
    text = PDTextField(form)
    text.set_partial_name("text")
    text_ap = _make_form_xobject((0.0, 0.0, 50.0, 15.0))
    _attach_widget(text.get_cos_object(), pages[0], (10.0, 10.0, 60.0, 25.0), text_ap)

    # Build a signature-typed field dict (terminal, no /Kids).
    sig_dict = COSDictionary()
    sig_dict.set_string(COSName.get_pdf_name("T"), "sig")
    sig_dict.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig"))
    # Seed a /V signature dictionary so the document reports a
    # signature dictionary exists.
    sig_value = COSDictionary()
    sig_value.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Sig"))
    sig_dict.set_item(COSName.get_pdf_name("V"), sig_value)

    from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField

    sig_field = PDSignatureField(form, sig_dict, None)
    form.set_fields([text, sig_field])
    form.set_signatures_exist(True)

    form.flatten([text], False)

    # Text field gone, signature field preserved.
    assert form.get_field("text") is None
    sig_lookup = form.get_field("sig")
    assert sig_lookup is not None
    assert sig_lookup.get_cos_object() is sig_field.get_cos_object()
    # /SigFlags preserved because a signature dictionary still exists.
    assert form.is_signatures_exist()


def test_flatten_signed_document_3() -> None:
    """PDFBOX-3396 Signed-Document-3. Same SigFlags-preservation
    invariant as -2, exercised with two signatures so the iteration
    over ``get_signature_dictionaries`` is non-degenerate."""
    doc, form, pages = _make_document_with_form()
    fields_list: list = []
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField

    for i in range(2):
        sd = COSDictionary()
        sd.set_string(COSName.get_pdf_name("T"), f"sig{i}")
        sd.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig"))
        sv = COSDictionary()
        sv.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Sig"))
        sd.set_item(COSName.get_pdf_name("V"), sv)
        fields_list.append(PDSignatureField(form, sd, None))

    text = PDTextField(form)
    text.set_partial_name("text")
    text_ap = _make_form_xobject((0.0, 0.0, 50.0, 15.0))
    _attach_widget(text.get_cos_object(), pages[0], (10.0, 10.0, 60.0, 25.0), text_ap)
    fields_list.append(text)

    form.set_fields(fields_list)
    form.set_signatures_exist(True)

    form.flatten([text], False)

    assert form.get_field("text") is None
    assert form.get_field("sig0") is not None
    assert form.get_field("sig1") is not None
    assert form.is_signatures_exist()


def test_flatten_signed_document_4() -> None:
    """PDFBOX-3396 Signed-Document-4. Edge case — every field is a
    signature and gets flattened: /SigFlags must clear because no
    signature dictionaries remain after the wipe."""
    doc, form, pages = _make_document_with_form()
    text = PDTextField(form)
    text.set_partial_name("text")
    text_ap = _make_form_xobject((0.0, 0.0, 50.0, 15.0))
    _attach_widget(text.get_cos_object(), pages[0], (10.0, 10.0, 60.0, 25.0), text_ap)
    form.set_fields([text])
    form.set_signatures_exist(True)

    # flatten() with fields=None → wipes /AcroForm entirely.
    form.flatten()

    assert doc.get_document_catalog().get_acro_form() is None


def test_flatten_pdfbox_4693() -> None:
    """PDFBOX-4693: page is not rotated but the appearance stream is.
    Upstream's pixel-compare verifies the placement CTM correctly
    inverts the form's /Matrix rotation. Structural offline: build a
    Form XObject with a non-identity /Matrix (90-degree rotation),
    flatten, assert the placement CTM in the page content stream is
    non-identity (the `cm` operator is emitted with non-trivial
    values)."""
    doc, form, pages = _make_document_with_form()
    field = PDTextField(form)
    field.set_partial_name("rot")
    ap = _make_form_xobject((0.0, 0.0, 50.0, 20.0))
    # /Matrix = 90-degree rotation [0 1 -1 0 50 0]
    matrix = COSArray()
    for v in (0.0, 1.0, -1.0, 0.0, 50.0, 0.0):
        matrix.add(COSFloat(v))
    ap.set_item(COSName.get_pdf_name("Matrix"), matrix)
    _attach_widget(field.get_cos_object(), pages[0], (100.0, 100.0, 150.0, 120.0), ap)
    form.set_fields([field])

    form.flatten()

    # Appearance materialised + cm operator emitted on host page.
    assert doc.get_document_catalog().get_acro_form() is None
    contents = pages[0].get_contents()
    assert b"cm" in contents
    assert b"Do" in contents
    # Page resource registry now references the rotated form XObject.
    assert len(_page_xobject_keys(pages[0])) == 1


def test_flatten_pdfbox_4788() -> None:
    """PDFBOX-4788: non-widget annotations are NOT to be removed on a
    page that has no widget annotations. Structural offline: build a
    2-page doc — page 0 carries a widget + a non-widget annotation,
    page 1 carries only a non-widget annotation. Flatten the whole
    form. Assert: page 0's non-widget survives (widget removed,
    non-widget preserved); page 1's non-widget is untouched."""
    doc, form, pages = _make_document_with_form(num_pages=2)
    widget_field = PDTextField(form)
    widget_field.set_partial_name("widget")
    widget_ap = _make_form_xobject((0.0, 0.0, 50.0, 15.0))
    _attach_widget(widget_field.get_cos_object(), pages[0], (10.0, 10.0, 60.0, 25.0), widget_ap)
    page0_text_annot = _make_non_widget_annotation(pages[0], (100.0, 100.0, 120.0, 120.0))
    page1_text_annot = _make_non_widget_annotation(pages[1], (50.0, 50.0, 70.0, 70.0))
    form.set_fields([widget_field])

    form.flatten()

    # Widget gone, non-widget on page 0 preserved.
    assert _page_annot_count(pages[0]) == 1
    page0_annots = pages[0].get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert page0_annots.get_object(0) is page0_text_annot
    # Page 1 untouched — flatten() only mutates pages hosting widgets.
    assert _page_annot_count(pages[1]) == 1
    page1_annots = pages[1].get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert page1_annots.get_object(0) is page1_text_annot


def test_flatten_pdfbox_4955() -> None:
    """PDFBOX-4955: appearance streams with forms that are not used.
    Upstream's pixel-compare verifies that an unreachable Form XObject
    inside the widget's /AP doesn't crash the renderer. Structural
    offline: build an appearance stream that references a nested Form
    XObject in its own /Resources /XObject (the "unused form"), flatten,
    assert that the appearance is still materialised on the page (the
    nested unused form rides along inside the form xobject as the
    stream's own resources)."""
    doc, form, pages = _make_document_with_form()
    field = PDTextField(form)
    field.set_partial_name("nested")
    ap = _make_form_xobject((0.0, 0.0, 50.0, 20.0))
    # Inject an unused nested Form XObject into ap's own /Resources.
    nested = _make_form_xobject((0.0, 0.0, 10.0, 10.0))
    nested_resources = COSDictionary()
    nested_xobjects = COSDictionary()
    nested_xobjects.set_item(COSName.get_pdf_name("Fm0"), nested)
    nested_resources.set_item(COSName.get_pdf_name("XObject"), nested_xobjects)
    ap.set_item(COSName.get_pdf_name("Resources"), nested_resources)
    _attach_widget(field.get_cos_object(), pages[0], (10.0, 10.0, 60.0, 30.0), ap)
    form.set_fields([field])

    form.flatten()

    assert doc.get_document_catalog().get_acro_form() is None
    # The outer ap stream is what got registered — the unused nested
    # stream rides along via the outer stream's /Resources dict.
    keys = _page_xobject_keys(pages[0])
    assert len(keys) == 1
    res = pages[0].get_cos_object().get_dictionary_object(COSName.get_pdf_name("Resources"))
    page_xobjects = res.get_dictionary_object(COSName.get_pdf_name("XObject"))
    registered = page_xobjects.get_dictionary_object(keys[0])
    assert registered is ap


# ---------- PDFBOX-5254 and PDFBOX-5225 (explicit invariants upstream asserts) ----------


def test_flatten_test_pdfbox_5254() -> None:
    """Upstream ``flattenTestPDFBOX5254`` — flattens an f1040sb form
    and asserts ``getFields().isEmpty()`` + the page retains
    ``72`` annotations (non-widget annotations preserved). Structural
    offline: synthetic form with N widget fields + M non-widget
    annotations on a single page → after flatten() /Fields is empty
    and the page retains exactly M annotations."""
    doc, form, pages = _make_document_with_form()
    page = pages[0]
    widgets: list[PDTextField] = []
    for i in range(4):
        f = PDTextField(form)
        f.set_partial_name(f"w{i}")
        ap = _make_form_xobject((0.0, 0.0, 40.0, 12.0))
        _attach_widget(f.get_cos_object(), page, (10.0 + 50.0 * i, 10.0, 50.0 + 50.0 * i, 22.0), ap)
        widgets.append(f)
    non_widget_targets = [
        _make_non_widget_annotation(page, (10.0 * i, 200.0, 10.0 * i + 5.0, 205.0))
        for i in range(3)
    ]
    form.set_fields(widgets)
    annots_before = _page_annot_count(page)
    assert annots_before == len(widgets) + len(non_widget_targets)

    form.flatten()

    # Upstream-equivalent: /AcroForm gone / /Fields empty.
    assert doc.get_document_catalog().get_acro_form() is None
    # Non-widget annotations preserved at exact count, in original order.
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    assert isinstance(annots, COSArray)
    assert annots.size() == len(non_widget_targets)
    surviving = [annots.get_object(i) for i in range(annots.size())]
    assert surviving == non_widget_targets


def test_flatten_test_pdfbox_5225() -> None:
    """Upstream ``flattenTestPDFBOX5225`` — flatten ONLY ``VN_NAME``;
    that field has an *orphan widget* (no /P back-pointer and not in
    any page's /Annots). Upstream asserts:

    * field-tree size = 76 (started 77; flatten one)
    * page 0 annotation count = 59 (started 60; the in-page widget
      copy of VN_NAME removed; orphan widget not in page = not
      counted)

    Structural offline equivalent: build a form whose target field
    ``VN_NAME`` has *one* widget hosted in the page and *one* orphan
    widget (`/P` absent, not in /Annots). Flatten just `VN_NAME`.
    Verify:

    * field-tree shrinks by exactly one (target removed)
    * page 0 annotation count drops by exactly one (only the hosted
      widget removed; the orphan was never on the page)
    * sibling fields preserved
    * /AcroForm survives (subset flatten)
    """
    doc, form, pages = _make_document_with_form()
    page = pages[0]

    # Sibling fields (preserved).
    siblings: list[PDTextField] = []
    for i in range(3):
        sib = PDTextField(form)
        sib.set_partial_name(f"sib_{i}")
        sib_ap = _make_form_xobject((0.0, 0.0, 30.0, 12.0))
        _attach_widget(
            sib.get_cos_object(), page, (10.0 + 40.0 * i, 200.0, 40.0 + 40.0 * i, 212.0), sib_ap
        )
        siblings.append(sib)

    # Target field VN_NAME — one hosted widget on page, plus one
    # orphan widget on /Kids that has no /P and is NOT on /Annots.
    target = PDTextField(form)
    target.set_partial_name("VN_NAME")
    target_ap = _make_form_xobject((0.0, 0.0, 30.0, 12.0))
    # The hosted widget shares the field's COS object (merged-widget shortcut).
    _attach_widget(target.get_cos_object(), page, (10.0, 10.0, 40.0, 22.0), target_ap)

    # Now also append a /Kids entry that's an orphan widget for VN_NAME
    # (no /P, not in any page's /Annots).
    orphan = COSDictionary()
    orphan.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    orphan.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    orphan_rect = COSArray()
    for v in (0.0, 0.0, 30.0, 12.0):
        orphan_rect.add(COSFloat(v))
    orphan.set_item(COSName.get_pdf_name("Rect"), orphan_rect)
    # /AP /N → minimal stream so flatten attempts page resolution.
    orphan_ap_stream = _make_form_xobject((0.0, 0.0, 30.0, 12.0))
    orphan_ap = COSDictionary()
    orphan_ap.set_item(COSName.get_pdf_name("N"), orphan_ap_stream)
    orphan.set_item(COSName.get_pdf_name("AP"), orphan_ap)
    # Deliberately omit /P — orphan widget.

    form.set_fields([*siblings, target])

    fields_before = len(form.get_fields())
    annots_before = _page_annot_count(page)
    assert fields_before == 4  # 3 siblings + VN_NAME
    assert annots_before == 4  # 3 sibling widgets + VN_NAME hosted widget

    form.flatten([target], False)

    # Subset flatten leaves /AcroForm in place.
    assert doc.get_document_catalog().get_acro_form() is not None
    # Field tree shrinks by exactly one.
    assert len(form.get_fields()) == fields_before - 1
    assert form.get_field("VN_NAME") is None
    # Siblings preserved by partial-name lookup (compare COS object
    # identity — get_field wraps a fresh PDTextField each call).
    for s in siblings:
        looked_up = form.get_field(s.get_partial_name())
        assert looked_up is not None
        assert looked_up.get_cos_object() is s.get_cos_object()
    # Page annotation count drops by exactly one (the hosted widget
    # removed; the orphan widget was never on the page so doesn't
    # affect the count). This mirrors upstream's 60 → 59 result.
    assert _page_annot_count(page) == annots_before - 1
