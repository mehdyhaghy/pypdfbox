"""Live Apache PDFBox differential for PDButton strict checkValue + the
empty-string membership in getOnValues for AP-less widgets — wave 1487.

Pins, against the pinned PDFBox 3.0.7 jar:

  * ``getOnValues`` includes the empty string ``""`` (unconditionally added by
    upstream for every widget that lacks a usable ``/AP /N`` on-state), and
    preserves ``LinkedHashSet`` insertion order;
  * ``checkValue`` is strict — it raises ``IllegalArgumentException`` (mapped to
    ``ValueError`` in pypdfbox) for a name that is neither ``"Off"`` nor an
    on-value, and accepts ``""`` for an AP-less button;
  * the ``/Opt`` export-values path dedups + preserves order;
  * ``setDefaultValue`` routes through the same strict check.

The Java ``ButtonCheckValueProbe`` builds the field shapes in memory and emits
labelled fact lines (an empty on-state renders as the empty token, so a set
``{"", "Accepted"}`` prints as ``"|Accepted"``). pypdfbox builds the identical
shapes and produces the same facts; the test asserts byte-for-byte parity.

Decorated ``@requires_oracle`` so it skips on machines without Java + jar.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from tests.oracle.harness import requires_oracle, run_probe_text

_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_KIDS = COSName.get_pdf_name("Kids")


def _normal_ap(on_state: str) -> COSDictionary:
    """A /AP dict whose /N subdict has /Off and ``on_state`` as COSStreams.

    pypdfbox's get_on_value_for_widget iterates the /N keys directly, so a
    COSStream value is not strictly required on this side — but we mirror the
    probe (which needs streams to satisfy upstream's getSubDictionary filter)
    so the two object graphs are identical.
    """
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


def _join(values: object) -> str:
    return "|".join(values)  # type: ignore[arg-type]


def _try_check(button: PDButton, value: str) -> str:
    try:
        button.check_value(value)
        return "ok"
    except ValueError:
        return "IllegalArgumentException"


def _try_set_default(button: PDButton, value: str) -> str:
    try:
        button.set_default_value(value)
        return "ok"
    except ValueError:
        return "IllegalArgumentException"


def _pypdfbox_facts() -> dict[str, str]:
    form = PDAcroForm()
    facts: dict[str, str] = {}

    # Case 1: checkbox with a single /AP /N on-state "Yes".
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_AP, _normal_ap("Yes"))
    facts["cb_onvalues"] = _join(cb.get_on_values())
    facts["cb_check_yes"] = _try_check(cb, "Yes")
    facts["cb_check_off"] = _try_check(cb, "Off")
    facts["cb_check_maybe"] = _try_check(cb, "Maybe")

    # Case 2: kids — two with NO /AP, one "Accepted".
    grp = PDCheckBox(form)
    kids = COSArray()
    kids.add(COSDictionary())
    kids.add(_widget_with_ap("Accepted"))
    kids.add(COSDictionary())
    grp.get_cos_object().set_item(_KIDS, kids)
    facts["grp_onvalues"] = _join(grp.get_on_values())
    facts["grp_check_accepted"] = _try_check(grp, "Accepted")
    facts["grp_check_empty"] = _try_check(grp, "")
    facts["grp_check_off"] = _try_check(grp, "Off")
    facts["grp_check_nope"] = _try_check(grp, "Nope")

    # Case 3: AP-less single-widget checkbox -> onValues holds "".
    bare = PDCheckBox(form)
    bare_kids = COSArray()
    bare_kids.add(COSDictionary())
    bare.get_cos_object().set_item(_KIDS, bare_kids)
    facts["bare_onvalues"] = _join(bare.get_on_values())
    facts["bare_getonvalue"] = bare.get_on_value()
    facts["bare_check_empty"] = _try_check(bare, "")
    facts["bare_check_yes"] = _try_check(bare, "Yes")

    # Case 4: /Opt export-values radio, dedup + order.
    rb = PDRadioButton(form)
    rb.set_export_values(["e1", "e2", "e1"])
    facts["opt_onvalues"] = _join(rb.get_on_values())
    facts["opt_check_e1"] = _try_check(rb, "e1")
    facts["opt_check_e2"] = _try_check(rb, "e2")
    facts["opt_check_off"] = _try_check(rb, "Off")
    facts["opt_check_bad"] = _try_check(rb, "zzz")

    # Case 5: setDefaultValue routes through strict checkValue.
    dv = PDCheckBox(form)
    dv.get_cos_object().set_item(_AP, _normal_ap("On"))
    facts["dv_set_on"] = _try_set_default(dv, "On")
    facts["dv_set_bad"] = _try_set_default(dv, "Bad")
    return facts


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value
    return out


@requires_oracle
def test_button_check_value_matches_oracle() -> None:
    oracle = _parse(run_probe_text("ButtonCheckValueProbe"))
    assert oracle == _pypdfbox_facts()
    # Spot-check the load-bearing facts.
    assert oracle["cb_onvalues"] == "Yes"
    assert oracle["cb_check_maybe"] == "IllegalArgumentException"
    # Empty-string membership: AP-less widgets contribute "" (printed empty).
    assert oracle["grp_onvalues"] == "|Accepted"
    assert oracle["grp_check_empty"] == "ok"
    assert oracle["grp_check_nope"] == "IllegalArgumentException"
    assert oracle["bare_onvalues"] == ""
    assert oracle["bare_check_empty"] == "ok"
    assert oracle["bare_check_yes"] == "IllegalArgumentException"
    # /Opt dedup + order.
    assert oracle["opt_onvalues"] == "e1|e2"
    assert oracle["opt_check_bad"] == "IllegalArgumentException"
    # setDefaultValue is strict.
    assert oracle["dv_set_on"] == "ok"
    assert oracle["dv_set_bad"] == "IllegalArgumentException"
