"""Live Apache PDFBox differential isolating the COSStream filter in PDButton
on-value discovery — wave 1488.

Pins, against the pinned PDFBox 3.0.7 jar, that ``PDButton.getOnValueForWidget``
and ``PDCheckBox.getOnValue`` only surface a ``/AP /N`` state whose VALUE is a
``COSStream`` — because upstream iterates
``normalAppearance.getSubDictionary().keySet()`` and
``PDAppearanceEntry.getSubDictionary`` filters to stream-valued keys. A ``/N``
holding a non-stream placeholder (a plain dict or a name) contributes no
on-value.

The wave-1487 ``ButtonCheckValueProbe`` deliberately used COSStream on-states
to satisfy this filter; the ``ButtonOnValueFilterProbe`` here instead builds
non-stream placeholders to pin the filter itself. pypdfbox builds the identical
shapes and produces the same facts; the test asserts byte-for-byte parity.

Decorated ``@requires_oracle`` so it skips on machines without Java + jar.
"""
from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from tests.oracle.harness import requires_oracle, run_probe_text

_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")


def _ap(n: COSDictionary) -> COSDictionary:
    ap = COSDictionary()
    ap.set_item(_N, n)
    return ap


def _join(values: object) -> str:
    return "|".join(values)  # type: ignore[arg-type]


def _pypdfbox_facts() -> dict[str, str]:
    form = PDAcroForm()
    facts: dict[str, str] = {}

    # Case A: /N on-state is a COSStream (normal).
    a = PDCheckBox(form)
    a_n = COSDictionary()
    a_n.set_item(COSName.get_pdf_name("Yes"), COSStream())
    a_n.set_item(_OFF, COSStream())
    a.get_cos_object().set_item(_AP, _ap(a_n))
    facts["a_onvalue"] = a.get_on_value()
    facts["a_onvalues"] = _join(a.get_on_values())

    # Case B: /N on-state is a plain COSDictionary placeholder.
    b = PDCheckBox(form)
    b_n = COSDictionary()
    b_n.set_item(COSName.get_pdf_name("Yes"), COSDictionary())
    b_n.set_item(_OFF, COSStream())
    b.get_cos_object().set_item(_AP, _ap(b_n))
    facts["b_onvalue"] = b.get_on_value()
    facts["b_onvalues"] = _join(b.get_on_values())

    # Case C: /N on-state is a COSName placeholder.
    c = PDCheckBox(form)
    c_n = COSDictionary()
    c_n.set_item(COSName.get_pdf_name("Yes"), COSName.get_pdf_name("ref"))
    c_n.set_item(_OFF, COSStream())
    c.get_cos_object().set_item(_AP, _ap(c_n))
    facts["c_onvalue"] = c.get_on_value()
    facts["c_onvalues"] = _join(c.get_on_values())

    # Case D: /N mixes a non-stream key (first) + a stream key.
    d = PDCheckBox(form)
    d_n = COSDictionary()
    d_n.set_item(COSName.get_pdf_name("Aaa"), COSDictionary())
    d_n.set_item(COSName.get_pdf_name("Bbb"), COSStream())
    d_n.set_item(_OFF, COSStream())
    d.get_cos_object().set_item(_AP, _ap(d_n))
    facts["d_onvalue"] = d.get_on_value()
    facts["d_onvalues"] = _join(d.get_on_values())

    # Case E: /N has only non-stream placeholders -> no on-value.
    e = PDCheckBox(form)
    e_n = COSDictionary()
    e_n.set_item(COSName.get_pdf_name("Yes"), COSDictionary())
    e_n.set_item(_OFF, COSDictionary())
    e.get_cos_object().set_item(_AP, _ap(e_n))
    facts["e_onvalue"] = e.get_on_value()
    facts["e_onvalues"] = _join(e.get_on_values())
    return facts


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value
    return out


@requires_oracle
def test_button_on_value_filter_matches_oracle() -> None:
    oracle = _parse(run_probe_text("ButtonOnValueFilterProbe"))
    assert oracle == _pypdfbox_facts()
    # Spot-check the load-bearing facts: only stream-valued states surface.
    assert oracle["a_onvalue"] == "Yes"
    assert oracle["b_onvalue"] == ""  # dict placeholder skipped
    assert oracle["c_onvalue"] == ""  # name placeholder skipped
    assert oracle["d_onvalue"] == "Bbb"  # non-stream "Aaa" skipped
    assert oracle["e_onvalue"] == ""  # all placeholders -> empty
    # AP-less-equivalent (no stream states) -> getOnValues holds only "".
    assert oracle["e_onvalues"] == ""
