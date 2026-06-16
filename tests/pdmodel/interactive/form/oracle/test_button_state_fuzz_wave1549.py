"""Live Apache PDFBox differential for BUTTON ON/OFF STATE RESOLUTION — wave 1549.

Distinct from the existing button oracle probes:

  * ``ButtonCheckValueProbe`` / ``ButtonOnValueFilterProbe`` pin ``checkValue``
    strictness and the ``COSStream`` ``getSubDictionary`` filter that decides
    which ``/AP /N`` keys are on-values;
  * ``RadioGroupProbe`` drives a fixture-loaded radio group's selected
    export / index / unison facts.

This probe instead pins how ``/AS``, ``/V``, ``check()`` / ``un_check()`` and
``set_value`` interact to resolve the active appearance state of malformed /
edge in-memory button fields:

  * ``/AS`` pointing at a key absent from ``/AP /N`` (echoed verbatim by
    ``get_appearance_state``; ``is_checked`` ignores ``/AS`` and compares
    ``get_value()`` against ``get_on_value()``);
  * a ``/V`` name disagreeing with a stale ``/AS`` (``construct_appearances``
    re-syncs ``/AS`` to ``/V`` when the key exists in ``/N``);
  * ``/V`` stored as ``COSString`` rather than ``COSName`` -> ``get_value()``
    falls back to ``"Off"``;
  * the ``check()`` / ``un_check()`` round trip read back through
    ``get_value`` / ``/AS`` / ``is_checked``;
  * a checkbox whose ``/AP /N`` has TWO stream on-keys — ``get_on_values``
    surfaces only the FIRST per widget, so the second key is rejected by the
    strict ``set_value``;
  * ``check()`` on an AP-less fresh box (on-value ``""`` -> ``is_checked``
    becomes True with an empty ``/V`` and an untouched ``/AS``);
  * a radio group where two widgets share an on-state and several are non-Off
    (``get_selected_index`` returns the FIRST non-Off ``/AS``);
  * the ``/Opt`` index path's resolved ``/AS`` (``set_value_by_index``);
  * ``set_value("Off")`` clearing every widget ``/AS``;
  * ``set_value`` of an on-value whose key no widget carries (``/AS`` -> Off,
    ``/V`` -> the raw resolved name);
  * ``RadiosInUnison`` ``/Ff`` bit toggling;
  * ``set_value`` rejecting / accepting a name vs ``get_on_values``.

The Java ``ButtonStateFuzzProbe`` builds the identical field shapes in memory
and emits labelled fact lines (a null ``/AS`` renders as the literal token
``"null"``, an empty string as the empty token, booleans as ``0`` / ``1``,
exceptions as ``"IllegalArgumentException"``). pypdfbox reproduces the same
facts; the test asserts dict parity.

Decorated ``@requires_oracle`` so it skips on machines without Java + jar.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from tests.oracle.harness import requires_oracle, run_probe_text

_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_V = COSName.get_pdf_name("V")
_AS = COSName.get_pdf_name("AS")
_KIDS = COSName.get_pdf_name("Kids")


def _normal_ap(on_state: str) -> COSDictionary:
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name(on_state), COSStream())
    n.set_item(_OFF, COSStream())
    ap = COSDictionary()
    ap.set_item(_N, n)
    return ap


def _widget_with_ap(on_state: str) -> COSDictionary:
    w = COSDictionary()
    w.set_item(_AP, _normal_ap(on_state))
    return w


def _widget_with_ap_as(on_state: str, as_state: str) -> COSDictionary:
    w = _widget_with_ap(on_state)
    w.set_item(_AS, COSName.get_pdf_name(as_state))
    return w


def _b(value: bool) -> str:
    return "1" if value else "0"


def _join(values: object) -> str:
    return "|".join(values)  # type: ignore[arg-type]


def _as(button: PDButton) -> str:
    """First widget's raw ``/AS``, ``"null"`` when absent (mirrors the probe)."""
    state = button.get_widgets()[0].get_appearance_state()
    return "null" if state is None else state


def _widget_as(button: PDButton) -> str:
    parts = []
    for w in button.get_widgets():
        state = w.get_appearance_state()
        parts.append("null" if state is None else state)
    return "|".join(parts)


def _widget_ons(button: PDButton) -> str:
    parts = []
    for w in button.get_widgets():
        parts.append(PDButton.get_on_value_for_widget(w))
    return "|".join(parts)


def _try_set(button: PDButton, value: str) -> str:
    try:
        button.set_value(value)
        return "ok"
    except ValueError:
        return "IllegalArgumentException"


def _pypdfbox_facts() -> dict[str, str]:
    form = PDAcroForm()
    facts: dict[str, str] = {}

    # Case 1: /AS points at a key absent from /AP /N.
    c1 = PDCheckBox(form)
    c1.get_cos_object().set_item(_AP, _normal_ap("Yes"))
    c1.get_widgets()[0].set_appearance_state("Ghost")
    facts["c1_as"] = _as(c1)
    facts["c1_onvalue"] = c1.get_on_value()
    facts["c1_value"] = c1.get_value()
    facts["c1_checked"] = _b(c1.is_checked())

    # Case 2: /V name matches on-state, /AS still stale until construct.
    c2 = PDCheckBox(form)
    c2.get_cos_object().set_item(_AP, _normal_ap("Yes"))
    c2.get_widgets()[0].set_appearance_state("Off")
    c2.get_cos_object().set_item(_V, COSName.get_pdf_name("Yes"))
    facts["c2_value"] = c2.get_value()
    facts["c2_as_before"] = _as(c2)
    facts["c2_checked"] = _b(c2.is_checked())
    c2.construct_appearances()
    facts["c2_as_after"] = _as(c2)

    # Case 3: /V as COSString -> get_value() == "Off".
    c3 = PDCheckBox(form)
    c3.get_cos_object().set_item(_AP, _normal_ap("Yes"))
    c3.get_cos_object().set_item(_V, COSString("Yes"))
    facts["c3_value"] = c3.get_value()
    facts["c3_checked"] = _b(c3.is_checked())

    # Case 4: check() then un_check() round trip.
    c4 = PDCheckBox(form)
    c4.get_cos_object().set_item(_AP, _normal_ap("On"))
    c4.check()
    facts["c4_after_check_value"] = c4.get_value()
    facts["c4_after_check_as"] = _as(c4)
    facts["c4_after_check_checked"] = _b(c4.is_checked())
    c4.un_check()
    facts["c4_after_uncheck_value"] = c4.get_value()
    facts["c4_after_uncheck_as"] = _as(c4)
    facts["c4_after_uncheck_checked"] = _b(c4.is_checked())

    # Case 5: /AP /N with Off + two stream on-keys; only the FIRST is an
    # on-value, so setting the second is rejected.
    c5 = PDCheckBox(form)
    n5 = COSDictionary()
    n5.set_item(_OFF, COSStream())
    n5.set_item(COSName.get_pdf_name("Aaa"), COSStream())
    n5.set_item(COSName.get_pdf_name("Bbb"), COSStream())
    ap5 = COSDictionary()
    ap5.set_item(_N, n5)
    c5.get_cos_object().set_item(_AP, ap5)
    facts["c5_onvalue"] = c5.get_on_value()
    facts["c5_onvalues"] = _join(c5.get_on_values())
    facts["c5_set_bbb"] = _try_set(c5, "Bbb")
    c5.set_value("Aaa")
    facts["c5_value"] = c5.get_value()
    facts["c5_as"] = _as(c5)
    facts["c5_checked"] = _b(c5.is_checked())

    # Case 6: AP-less fresh checkbox: check() sets the "" on-value.
    c6 = PDCheckBox(form)
    facts["c6_onvalue"] = c6.get_on_value()
    facts["c6_value_before"] = c6.get_value()
    facts["c6_checked_before"] = _b(c6.is_checked())
    c6.check()
    facts["c6_value_after"] = c6.get_value()
    facts["c6_as_after"] = _as(c6)
    facts["c6_checked_after"] = _b(c6.is_checked())

    # Case 7: radio group, three kids; two widgets share on-state "A".
    r7 = PDRadioButton(form)
    kids7 = COSArray()
    kids7.add(_widget_with_ap_as("A", "Off"))
    kids7.add(_widget_with_ap_as("B", "B"))
    kids7.add(_widget_with_ap_as("A", "A"))
    r7.get_cos_object().set_item(_KIDS, kids7)
    facts["r7_onvalues"] = _join(r7.get_on_values())
    facts["r7_widgeton"] = _widget_ons(r7)
    facts["r7_selectedindex"] = str(r7.get_selected_index())

    # Case 8: radio with /Opt export values; set_value_by_index.
    r8 = PDRadioButton(form)
    kids8 = COSArray()
    kids8.add(_widget_with_ap("0"))
    kids8.add(_widget_with_ap("1"))
    r8.get_cos_object().set_item(_KIDS, kids8)
    r8.set_export_values(["export0", "export1"])
    r8.set_value_by_index(1)
    facts["r8_value"] = r8.get_value()
    facts["r8_widgetas"] = _widget_as(r8)
    facts["r8_selectedindex"] = str(r8.get_selected_index())
    facts["r8_selectedexport"] = _join(r8.get_selected_export_values())

    # Case 9: radio set_value("Off") clears all widget /AS.
    r9 = PDRadioButton(form)
    kids9 = COSArray()
    kids9.add(_widget_with_ap_as("X", "X"))
    kids9.add(_widget_with_ap_as("Y", "Off"))
    r9.get_cos_object().set_item(_KIDS, kids9)
    r9.set_value("Off")
    facts["r9_value"] = r9.get_value()
    facts["r9_widgetas"] = _widget_as(r9)
    facts["r9_selectedindex"] = str(r9.get_selected_index())

    # Case 10: RadiosInUnison flag toggling.
    r10 = PDRadioButton(form)
    facts["r10_unison_default"] = _b(r10.is_radios_in_unison())
    r10.set_radios_in_unison(True)
    facts["r10_unison_set"] = _b(r10.is_radios_in_unison())
    facts["r10_ff"] = str(r10.get_field_flags())

    # Case 11: set_value(name) via /Opt with no matching /AP key on any widget.
    r11 = PDRadioButton(form)
    kids11 = COSArray()
    kids11.add(_widget_with_ap("w0"))
    kids11.add(_widget_with_ap("w1"))
    r11.get_cos_object().set_item(_KIDS, kids11)
    r11.set_export_values(["optA", "optB"])
    r11.set_value("optA")
    facts["r11_value"] = r11.get_value()
    facts["r11_widgetas"] = _widget_as(r11)
    facts["r11_selectedindex"] = str(r11.get_selected_index())

    # Case 12: set_value of a non-on-value raises; valid name resolves /AS + /V.
    c12 = PDCheckBox(form)
    c12.get_cos_object().set_item(_AP, _normal_ap("Yes"))
    facts["c12_set_bad"] = _try_set(c12, "Nope")
    facts["c12_set_yes"] = _try_set(c12, "Yes")
    facts["c12_after_value"] = c12.get_value()
    facts["c12_after_as"] = _as(c12)
    return facts


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value
    return out


@requires_oracle
def test_button_state_fuzz_matches_oracle() -> None:
    oracle = _parse(run_probe_text("ButtonStateFuzzProbe"))
    assert oracle == _pypdfbox_facts()

    # Spot-check the load-bearing state-resolution facts.
    # /AS echoes a ghost key; is_checked ignores /AS (Off vs Yes on-value).
    assert oracle["c1_as"] == "Ghost"
    assert oracle["c1_checked"] == "0"
    # /V name overrides stale /AS for get_value + is_checked; construct re-syncs.
    assert oracle["c2_checked"] == "1"
    assert oracle["c2_as_before"] == "Off"
    assert oracle["c2_as_after"] == "Yes"
    # COSString /V is not a COSName -> "Off".
    assert oracle["c3_value"] == "Off"
    assert oracle["c3_checked"] == "0"
    # check()/un_check() round trip.
    assert oracle["c4_after_check_value"] == "On"
    assert oracle["c4_after_check_as"] == "On"
    assert oracle["c4_after_uncheck_as"] == "Off"
    assert oracle["c4_after_uncheck_checked"] == "0"
    # Only the FIRST stream on-key is an on-value.
    assert oracle["c5_onvalues"] == "Aaa"
    assert oracle["c5_set_bbb"] == "IllegalArgumentException"
    assert oracle["c5_as"] == "Aaa"
    # AP-less check(): empty on-value, untouched /AS, but is_checked True.
    assert oracle["c6_value_after"] == ""
    assert oracle["c6_as_after"] == "null"
    assert oracle["c6_checked_after"] == "1"
    # get_selected_index = first non-Off /AS (widget index 1).
    assert oracle["r7_selectedindex"] == "1"
    # /Opt index path resolves widget[1] on-state + export.
    assert oracle["r8_value"] == "export1"
    assert oracle["r8_widgetas"] == "Off|1"
    assert oracle["r8_selectedexport"] == "export1"
    # set_value("Off") clears every /AS.
    assert oracle["r9_widgetas"] == "Off|Off"
    assert oracle["r9_selectedindex"] == "-1"
    # RadiosInUnison bit.
    assert oracle["r10_unison_default"] == "0"
    assert oracle["r10_unison_set"] == "1"
    # /Opt option -> widget[0] on-value "w0".
    assert oracle["r11_value"] == "w0"
    assert oracle["r11_widgetas"] == "w0|Off"
    # Strict set_value: bad rejected, good resolves.
    assert oracle["c12_set_bad"] == "IllegalArgumentException"
    assert oracle["c12_set_yes"] == "ok"
    assert oracle["c12_after_as"] == "Yes"
