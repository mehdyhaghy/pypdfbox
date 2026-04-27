from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import (
    PDActionJavaScript,
    PDFormFieldAdditionalActions,
)
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDFieldStub
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_KIDS: COSName = COSName.get_pdf_name("Kids")
_AA: COSName = COSName.get_pdf_name("AA")
_PARENT: COSName = COSName.get_pdf_name("Parent")


# ---------- get_widgets() typed wrapping ----------


def test_get_widgets_returns_pd_annotation_widget_for_single_widget_field() -> None:
    """When ``/Kids`` is absent the field itself acts as the widget — must
    still come back wrapped as :class:`PDAnnotationWidget`, not a raw dict.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    widgets = tf.get_widgets()
    assert len(widgets) == 1
    assert isinstance(widgets[0], PDAnnotationWidget)
    assert widgets[0].get_cos_object() is tf.get_cos_object()


def test_get_widgets_returns_pd_annotation_widget_per_kid() -> None:
    form = PDAcroForm()
    field = COSDictionary()
    first = COSDictionary()
    second = COSDictionary()
    field.set_item(_KIDS, COSArray([first, second]))

    tf = PDFieldStub(form, field)
    widgets = tf.get_widgets()
    assert len(widgets) == 2
    assert all(isinstance(w, PDAnnotationWidget) for w in widgets)
    assert widgets[0].get_cos_object() is first
    assert widgets[1].get_cos_object() is second


def test_get_widgets_skips_non_dict_kids_entries() -> None:
    form = PDAcroForm()
    field = COSDictionary()
    valid = COSDictionary()
    # COSArray accepts heterogeneous elements; non-dict entries are ignored.
    field.set_item(_KIDS, COSArray([valid]))

    tf = PDFieldStub(form, field)
    widgets = tf.get_widgets()
    assert len(widgets) == 1
    assert widgets[0].get_cos_object() is valid


# ---------- set_widgets() round-trip ----------


def test_set_widgets_writes_kids_array_and_wires_parent() -> None:
    form = PDAcroForm()
    tf = PDFieldStub(form)
    w1 = PDAnnotationWidget()
    w2 = PDAnnotationWidget()

    tf.set_widgets([w1, w2])

    kids = tf.get_cos_object().get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    assert kids.size() == 2
    assert kids.get_object(0) is w1.get_cos_object()
    assert kids.get_object(1) is w2.get_cos_object()
    # Each widget's /Parent points back at the field.
    assert w1.get_cos_object().get_dictionary_object(_PARENT) is tf.get_cos_object()
    assert w2.get_cos_object().get_dictionary_object(_PARENT) is tf.get_cos_object()


def test_set_widgets_round_trip_via_get_widgets() -> None:
    form = PDAcroForm()
    tf = PDFieldStub(form)
    widgets = [PDAnnotationWidget(), PDAnnotationWidget(), PDAnnotationWidget()]
    tf.set_widgets(widgets)

    fetched = tf.get_widgets()
    assert len(fetched) == 3
    assert all(isinstance(w, PDAnnotationWidget) for w in fetched)
    fetched_cos = [w.get_cos_object() for w in fetched]
    expected_cos = [w.get_cos_object() for w in widgets]
    assert fetched_cos == expected_cos


def test_set_widgets_replaces_existing_kids() -> None:
    form = PDAcroForm()
    tf = PDFieldStub(form)
    tf.set_widgets([PDAnnotationWidget(), PDAnnotationWidget()])
    new_widget = PDAnnotationWidget()
    tf.set_widgets([new_widget])

    kids = tf.get_cos_object().get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    assert kids.size() == 1
    assert kids.get_object(0) is new_widget.get_cos_object()


# ---------- set_actions() typed override ----------


def test_set_actions_round_trip_with_pd_form_field_additional_actions() -> None:
    form = PDAcroForm()
    tf = PDFieldStub(form)
    actions = PDFormFieldAdditionalActions()
    js = PDActionJavaScript()
    js.set_action("event.value = event.value.toUpperCase();")
    actions.set_k(js)

    tf.set_actions(actions)

    stored = tf.get_cos_object().get_dictionary_object(_AA)
    assert stored is actions.get_cos_object()

    resolved = tf.get_actions()
    assert isinstance(resolved, PDFormFieldAdditionalActions)
    resolved_action = resolved.get_k()
    assert isinstance(resolved_action, PDActionJavaScript)
    assert resolved_action.get_action() == "event.value = event.value.toUpperCase();"


def test_set_actions_none_removes_aa() -> None:
    form = PDAcroForm()
    tf = PDFieldStub(form)
    actions = PDFormFieldAdditionalActions()
    tf.set_actions(actions)
    assert tf.get_cos_object().contains_key(_AA)

    tf.set_actions(None)
    assert not tf.get_cos_object().contains_key(_AA)
    assert tf.get_actions() is None


# ---------- apply_change / construct_appearances are callable ----------


def test_apply_change_is_callable_no_op() -> None:
    form = PDAcroForm()
    tf = PDFieldStub(form)
    # Must not raise — appearance regeneration is deferred.
    assert tf.apply_change() is None


def test_construct_appearances_is_callable_no_op() -> None:
    form = PDAcroForm()
    tf = PDFieldStub(form)
    assert tf.construct_appearances() is None


def test_apply_change_logs_deferred_message(caplog) -> None:
    import logging

    form = PDAcroForm()
    tf = PDFieldStub(form)
    with caplog.at_level(
        logging.DEBUG, logger="pypdfbox.pdmodel.interactive.form.pd_terminal_field"
    ):
        tf.apply_change()
    assert any("deferred" in r.message for r in caplog.records)


def test_construct_appearances_logs_deferred_message(caplog) -> None:
    import logging

    form = PDAcroForm()
    tf = PDFieldStub(form)
    with caplog.at_level(
        logging.DEBUG, logger="pypdfbox.pdmodel.interactive.form.pd_terminal_field"
    ):
        tf.construct_appearances()
    assert any("deferred" in r.message for r in caplog.records)
