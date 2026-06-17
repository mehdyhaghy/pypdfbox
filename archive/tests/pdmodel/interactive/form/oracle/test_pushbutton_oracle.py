"""Live Apache PDFBox differential parity tests for ``PDPushButton`` field +
``/MK`` appearance-characteristics captions (wave 1451).

Surface under test (``pypdfbox/pdmodel/interactive/form/``):

  * :class:`PDPushButton` — a ``/FT /Btn`` field with the ``FLAG_PUSHBUTTON``
    bit set. Unlike check / radio buttons it holds no value (``/V``) and
    instead exposes click-only behaviour through its widget's ``/MK``
    appearance characteristics — the normal (``/CA``), rollover (``/RC``)
    and alternate / down (``/AC``) captions.
  * :class:`pypdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary`
    accessors ``get_normal_caption`` / ``get_rollover_caption`` /
    ``get_alternate_caption`` reached via
    ``PDAnnotationWidget.get_appearance_characteristics()``.

Each test emits canonical, deterministic facts via the Java
``PushButtonProbe`` (``oracle/probes/PushButtonProbe.java``, compiled against
the pinned pdfbox-app-3.0.7 jar) and via pypdfbox's typed field API, and
asserts the two are identical.

The fixture is built at runtime through pypdfbox — the build itself is part
of the differential surface, since PDFBox must be able to recognise a
push-button field constructed by pypdfbox.

Decorated ``@requires_oracle`` so the tests skip on machines without
Java + jar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
_FORM_FIXTURES = _FIXTURES / "pdmodel" / "interactive" / "form"
_BASIC = _FORM_FIXTURES / "AcroFormsBasicFields.pdf"

_PROBE = "PushButtonProbe"

_CA: COSName = COSName.get_pdf_name("CA")
_RC: COSName = COSName.get_pdf_name("RC")
_AC: COSName = COSName.get_pdf_name("AC")
_MK: COSName = COSName.get_pdf_name("MK")


# --------------------------------------------------------------------------- #
# Java probe driver
# --------------------------------------------------------------------------- #
def _java_read(path: Path, *names: str) -> dict[str, dict[str, str]]:
    """Run the probe in READ mode; parse its records into ``{name: facts}``.

    Each line is ``<name>\\t<kind>\\t<k=v>\\t<k=v>...``.
    """
    text = run_probe_text(_PROBE, "read", str(path), *names)
    out: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        name = parts[0]
        facts: dict[str, str] = {"kind": parts[1] if len(parts) > 1 else "<missing>"}
        for col in parts[2:]:
            key, _, value = col.partition("=")
            facts[key] = value
        out[name] = facts
    return out


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors PushButtonProbe.pushButtonFacts
# --------------------------------------------------------------------------- #
def _esc(value: str | None) -> str:
    if value is None:
        return "<null>"
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _py_pushbutton_facts(field: PDPushButton) -> dict[str, str]:
    widgets = field.get_widgets()
    widget_count = len(widgets)
    normal_caption = "<none>"
    rollover_caption = "<none>"
    alternate_caption = "<none>"
    if widget_count > 0:
        widget = widgets[0]
        mk = widget.get_appearance_characteristics()
        if mk is None:
            field_cos = field.get_cos_object()
            mk_dict = field_cos.get_dictionary_object(_MK)
            if isinstance(mk_dict, COSDictionary):
                # Local import keeps the top-level annotation dep narrow;
                # ``noqa: PLC0415`` covers the deliberate non-top placement.
                from pypdfbox.pdmodel.interactive.annotation import (  # noqa: PLC0415
                    PDAppearanceCharacteristicsDictionary,
                )

                mk = PDAppearanceCharacteristicsDictionary(mk_dict)
        if mk is not None:
            ca = mk.get_normal_caption()
            rc = mk.get_rollover_caption()
            ac = mk.get_alternate_caption()
            if ca is not None:
                normal_caption = ca
            if rc is not None:
                rollover_caption = rc
            if ac is not None:
                alternate_caption = ac
    return {
        "kind": "pushbutton",
        "isPushbutton": "1" if field.is_push_button() else "0",
        "isRadio": "1" if field.is_radio_button() else "0",
        "fieldType": _esc(field.get_field_type()),
        "value": _esc(field.get_value()),
        "valueAsString": _esc(field.get_value_as_string()),
        "defaultValue": _esc(field.get_default_value()),
        "widgetCount": str(widget_count),
        "normalCaption": _esc(normal_caption),
        "rolloverCaption": _esc(rollover_caption),
        "alternateCaption": _esc(alternate_caption),
    }


def _py_read(path: Path, name: str) -> dict[str, str]:
    doc = PDDocument.load(str(path))
    try:
        field = doc.get_document_catalog().get_acro_form().get_field(name)
        assert field is not None, f"field {name!r} not found"
        assert isinstance(field, PDPushButton), (
            f"field {name!r} dispatched to {type(field).__name__}, not PDPushButton"
        )
        return _py_pushbutton_facts(field)
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Fixture builders (no upstream fixture carries /CA + /RC + /AC together)
# --------------------------------------------------------------------------- #
def _build_pushbutton(
    path: Path,
    *,
    name: str = "SubmitButton",
    ca: str | None = "Click",
    rc: str | None = "Hover",
    ac: str | None = "Pressed",
) -> None:
    """Build a single-page PDF carrying one push-button widget with the
    requested ``/MK /CA`` / ``/RC`` / ``/AC`` captions populated on the
    widget."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)
        pb = PDPushButton(form)
        pb.set_partial_name(name)
        widget = pb.get_widgets()[0]
        widget.set_rectangle(PDRectangle(50, 500, 100, 30))
        widget.set_page(page)
        mk = COSDictionary()
        if ca is not None:
            mk.set_string(_CA, ca)
        if rc is not None:
            mk.set_string(_RC, rc)
        if ac is not None:
            mk.set_string(_AC, ac)
        if ca is not None or rc is not None or ac is not None:
            widget.get_cos_object().set_item(_MK, mk)
        page.get_annotations().append(widget)
        form.set_fields([pb])
        doc.save(str(path))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Parity tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_pushbutton_read_parity_full_captions(tmp_path: Path) -> None:
    """Build a push-button via pypdfbox with all three /MK captions populated;
    every fact PDFBox reports must equal what pypdfbox reports — both must see
    ``isPushbutton=1``, ``fieldType=Btn``, ``CA="Click"`` / ``RC="Hover"`` /
    ``AC="Pressed"``."""
    fixture = tmp_path / "pushbutton_full.pdf"
    _build_pushbutton(fixture, ca="Click", rc="Hover", ac="Pressed")

    java = _java_read(fixture, "SubmitButton")["SubmitButton"]
    py = _py_read(fixture, "SubmitButton")
    assert py == java
    assert py["isPushbutton"] == "1"
    assert py["isRadio"] == "0"
    assert py["fieldType"] == "Btn"
    assert py["normalCaption"] == "Click"
    assert py["rolloverCaption"] == "Hover"
    assert py["alternateCaption"] == "Pressed"
    # Push buttons never carry a /V; both impls must surface empty strings.
    assert py["value"] == ""
    assert py["valueAsString"] == ""
    assert py["defaultValue"] == ""


@requires_oracle
@pytest.mark.parametrize(
    ("ca", "rc", "ac"),
    [
        ("Click", None, None),
        ("Click", "Hover", None),
        ("Click", None, "Pressed"),
        (None, None, None),
    ],
)
def test_pushbutton_read_parity_partial_captions(
    tmp_path: Path,
    ca: str | None,
    rc: str | None,
    ac: str | None,
) -> None:
    """Each subset of /MK captions round-trips identically under both
    implementations — absent keys read as ``<none>`` on both sides, present
    keys read as the same string."""
    fixture = tmp_path / f"pushbutton_{ca}_{rc}_{ac}.pdf"
    _build_pushbutton(fixture, ca=ca, rc=rc, ac=ac)

    java = _java_read(fixture, "SubmitButton")["SubmitButton"]
    py = _py_read(fixture, "SubmitButton")
    assert py == java
    assert py["isPushbutton"] == "1"
    assert py["normalCaption"] == (ca if ca is not None else "<none>")
    assert py["rolloverCaption"] == (rc if rc is not None else "<none>")
    assert py["alternateCaption"] == (ac if ac is not None else "<none>")


@requires_oracle
def test_pushbutton_upstream_fixture_read_parity() -> None:
    """The upstream AcroFormsBasicFields fixture carries a bare push-button
    (no /MK captions). pypdfbox + PDFBox must agree on every fact, including
    the absent captions all reading as ``<none>``."""
    java = _java_read(_BASIC, "PushButton")["PushButton"]
    py = _py_read(_BASIC, "PushButton")
    assert py == java
    assert py["isPushbutton"] == "1"
    assert py["isRadio"] == "0"
    assert py["fieldType"] == "Btn"


@requires_oracle
def test_pushbutton_no_value_state(tmp_path: Path) -> None:
    """A push button has no value — ``get_value`` / ``get_default_value`` /
    ``get_value_as_string`` all return empty strings. Both implementations
    must agree on this click-only invariant."""
    fixture = tmp_path / "pushbutton_novalue.pdf"
    _build_pushbutton(fixture, ca="Submit", rc=None, ac=None)

    java = _java_read(fixture, "SubmitButton")["SubmitButton"]
    py = _py_read(fixture, "SubmitButton")
    assert py == java
    # Both impls report empty strings — the click-only invariant.
    assert py["value"] == ""
    assert py["valueAsString"] == ""
    assert py["defaultValue"] == ""
