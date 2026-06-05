"""Live Apache PDFBox differential for PDButton value-reader semantics when
/V or /DV is a COSString (or missing) — wave 1486.

Pins that ``PDButton.get_value`` / ``get_default_value`` only read an
``instanceof COSName`` token, matching upstream PDFBox 3.0.7. A COSString /V
reads back as "Off"; a COSString /DV reads back as "". Emits the same facts
via the Java ``ButtonCosStringValueProbe`` and via pypdfbox and asserts parity.

Decorated ``@requires_oracle`` so it skips on machines without Java + jar.
"""
from __future__ import annotations

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from tests.oracle.harness import requires_oracle, run_probe_text

_V = COSName.get_pdf_name("V")
_DV = COSName.get_pdf_name("DV")


def _pypdfbox_facts() -> dict[str, str]:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_V, COSString("string-value"))
    cb.get_cos_object().set_item(_DV, COSString("default-value"))
    facts = {
        "value_cosstring": cb.get_value(),
        "default_cosstring": cb.get_default_value(),
    }
    cb.get_cos_object().remove_item(_V)
    facts["value_missing"] = cb.get_value()
    cb.get_cos_object().set_name(_V, "Yes")
    facts["value_cosname"] = cb.get_value()
    return facts


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value
    return out


@requires_oracle
def test_button_cosstring_value_matches_oracle() -> None:
    oracle = _parse(run_probe_text("ButtonCosStringValueProbe"))
    assert oracle == _pypdfbox_facts()
    # Spot-check the load-bearing facts explicitly.
    assert oracle["value_cosstring"] == "Off"
    assert oracle["default_cosstring"] == ""
    assert oracle["value_missing"] == "Off"
    assert oracle["value_cosname"] == "Yes"
