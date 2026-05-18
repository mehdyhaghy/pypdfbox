"""Wave 1349 coverage-boost tests for ``PDButton``.

Targets:

* ``get_on_value`` instance-method alias (line 298).
* ``update_by_value`` widget rejection branches when ``/AP`` is
  missing/non-dict or ``/N`` is missing/non-dict (lines 317, 320).
* ``update_by_option`` short-circuit when ``value`` is not in the
  export-values list (lines 376-377).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton

_AP = COSName.get_pdf_name("AP")
_AS = COSName.get_pdf_name("AS")
_KIDS = COSName.get_pdf_name("Kids")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_OPT = COSName.get_pdf_name("Opt")
_V = COSName.get_pdf_name("V")


def _widget_with_states(*states: str) -> PDAnnotationWidget:
    normal = COSDictionary()
    for state in states:
        normal.set_item(COSName.get_pdf_name(state), COSDictionary())
    ap = COSDictionary()
    ap.set_item(_N, normal)
    widget = PDAnnotationWidget()
    widget.get_cos_object().set_item(_AP, ap)
    return widget


def _bare_widget() -> PDAnnotationWidget:
    """Widget with no ``/AP`` entry — exercises the missing-AP branch."""
    return PDAnnotationWidget()


def _widget_with_non_dict_ap() -> PDAnnotationWidget:
    """Widget whose ``/AP`` is a COSString — exercises the wrong-type
    ``/AP`` branch in :meth:`PDButton.update_by_value`."""
    widget = PDAnnotationWidget()
    widget.get_cos_object().set_item(_AP, COSString("not-a-dict"))
    return widget


def _widget_with_non_dict_n() -> PDAnnotationWidget:
    """Widget whose ``/AP /N`` is not a dictionary — exercises the
    wrong-type ``/N`` branch."""
    ap = COSDictionary()
    ap.set_item(_N, COSString("not-a-dict"))
    widget = PDAnnotationWidget()
    widget.get_cos_object().set_item(_AP, ap)
    return widget


def _install_widgets(button: PDButton, *widgets: PDAnnotationWidget) -> None:
    kids = COSArray()
    for w in widgets:
        kids.add(w.get_cos_object())
    button.get_cos_object().set_item(_KIDS, kids)


# ---- get_on_value (instance method alias) ---------------------------------


def test_get_on_value_instance_alias_delegates_to_index_lookup() -> None:
    """Line 298 — the instance-method form of ``get_on_value`` forwards
    to :meth:`get_on_value_at_index`. Exercised on the base
    :class:`PDButton` (subclasses such as ``PDCheckBox`` override the
    zero-arg form, but the parent alias still needs coverage)."""
    form = PDAcroForm()
    button = PDButton(form)
    _install_widgets(button, _widget_with_states("Yes", "Off"))
    # Direct call through the instance — matches upstream private
    # ``getOnValue(int)``.
    assert button.get_on_value(0) == "Yes"
    # Out-of-range index returns "" via get_on_value_at_index.
    assert button.get_on_value(5) == ""


# ---- update_by_value defensive branches -----------------------------------


def test_update_by_value_skips_widget_with_missing_ap() -> None:
    """Line 317 — widget whose ``/AP`` is missing/non-dict is skipped
    silently; the next widget (with a valid ``/AP``) still drives the
    field's ``/V``."""
    form = PDAcroForm()
    button = PDButton(form)
    good = _widget_with_states("Yes", "Off")
    _install_widgets(button, _bare_widget(), good)

    button.update_by_value("Yes")

    # The good widget had /AS updated to the matched key.
    assert good.get_cos_object().get_dictionary_object(_AS) == COSName.get_pdf_name("Yes")
    # Field /V set to the COSName for the matched key.
    assert button.get_cos_object().get_dictionary_object(_V) == COSName.get_pdf_name("Yes")


def test_update_by_value_skips_widget_with_non_dict_ap() -> None:
    """Line 317 (non-dict path) — ``/AP`` present but the wrong COS
    type is also skipped."""
    form = PDAcroForm()
    button = PDButton(form)
    good = _widget_with_states("Yes", "Off")
    _install_widgets(button, _widget_with_non_dict_ap(), good)

    button.update_by_value("Yes")
    assert good.get_cos_object().get_dictionary_object(_AS) == COSName.get_pdf_name("Yes")


def test_update_by_value_skips_widget_with_non_dict_n() -> None:
    """Line 320 — ``/AP`` is a dictionary but its ``/N`` entry isn't;
    the widget is skipped without raising."""
    form = PDAcroForm()
    button = PDButton(form)
    good = _widget_with_states("Yes", "Off")
    _install_widgets(button, _widget_with_non_dict_n(), good)

    button.update_by_value("Yes")
    assert good.get_cos_object().get_dictionary_object(_AS) == COSName.get_pdf_name("Yes")


# ---- update_by_option no-match short-circuit ------------------------------


def test_update_by_option_value_not_in_options_returns_silently() -> None:
    """Lines 376-377 — when ``value`` is absent from ``/Opt``,
    ``update_by_option`` returns without touching any widget."""
    form = PDAcroForm()
    button = PDButton(form)
    widget0 = _widget_with_states("0", "Off")
    widget1 = _widget_with_states("1", "Off")
    _install_widgets(button, widget0, widget1)
    button.set_export_values(["foo", "bar"])

    # Sanity: matching path normally updates /AS.
    button.update_by_option("foo")
    assert widget0.get_cos_object().get_dictionary_object(_AS) == COSName.get_pdf_name("0")

    # Reset the /AS for the no-match assertion below.
    widget0.get_cos_object().remove_item(_AS)
    widget1.get_cos_object().remove_item(_AS)
    button.get_cos_object().remove_item(_V)

    # No-match path: "missing" is not in the options list -> return.
    button.update_by_option("missing")
    assert widget0.get_cos_object().get_dictionary_object(_AS) is None
    assert widget1.get_cos_object().get_dictionary_object(_AS) is None
    assert button.get_cos_object().get_dictionary_object(_V) is None
