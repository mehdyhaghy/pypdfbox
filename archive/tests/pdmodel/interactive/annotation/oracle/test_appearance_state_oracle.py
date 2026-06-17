"""Live Apache PDFBox differential parity for the WIDGET /AS appearance-state
COERCION + FALLBACK behaviour on checkbox fields (wave 1448).

Surface under test (cross-module — ``pypdfbox/pdmodel/interactive/annotation/``
+ ``pypdfbox/pdmodel/interactive/form/``):

  * :class:`PDAnnotation.get_appearance_state` / ``set_appearance_state``
    round-trip — the literal ``/AS`` value, no fallback;
  * :class:`PDAppearanceEntry.get_sub_dictionary` — the on-state key the
    renderer actually resolves when ``/AS`` points at a key that does or
    does NOT exist in the ``/AP /N`` sub-dictionary;
  * :class:`PDCheckBox.is_checked` / ``get_on_value`` — must match PDFBox
    regardless of whether ``/AS`` is valid, references a missing key, or is
    absent altogether (spec default ``Off`` for checkboxes).

Why this is a NON-colliding surface
------------------------------------
Wave 1434 (``WidgetApProbe`` / ``test_widget_appearance_oracle.py``) probed
the WIDGET /AS + /AP sub-dict keying on the **valid** state path: ``/AS=On``,
``/AP /N`` has ``{Off, On}``, on-state ``/BBox`` is the one keyed by ``/AS``.
It does NOT touch the **invalid-/AS** (key not in sub-dict) or
**absent-/AS** cases, nor the ``PDCheckBox.isChecked`` accessor that bridges
the field /V to the widget on-state.

The fixture is built ONCE by pypdfbox (no upstream resource carries this exact
shape) and saved to ``tmp_path``; the same file is then read by BOTH
implementations, so the build itself is part of the differential surface.

High-value invariants
---------------------
  * ``get_appearance_state()`` returns the LITERAL stored ``/AS`` name —
    PDFBox does NOT coerce a missing-key value to ``Off``;
  * the resolved on-state (sub-dict ``get(/AS)``) is ``None`` when the
    ``/AS`` key is absent from the sub-dict (invalid case);
  * ``PDCheckBox.isChecked()`` compares the field ``/V`` against
    ``getOnValue()`` (the first non-``Off`` key in the sub-dict), so the
    ``/AS`` literal does NOT affect ``isChecked`` — it stays driven by
    ``/V``;
  * an absent ``/AS`` reports ``None`` from ``get_appearance_state`` but
    ``getValue()`` still defaults to ``Off`` (spec default).

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "AppearanceStateProbe"

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FORMTYPE = COSName.get_pdf_name("FormType")
_BBOX = COSName.get_pdf_name("BBox")
_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_AS = COSName.get_pdf_name("AS")
_FT = COSName.get_pdf_name("FT")
_T = COSName.get_pdf_name("T")
_BTN = COSName.get_pdf_name("Btn")
_FF = COSName.get_pdf_name("Ff")
_OFF = COSName.get_pdf_name("Off")
_YES = COSName.get_pdf_name("Yes")


# --------------------------------------------------------------------------- #
# pypdfbox fixture builder — three checkboxes covering valid / invalid /
# absent /AS. The fixture is the differential surface (both sides load it).
# --------------------------------------------------------------------------- #
def _ap_stream() -> COSStream:
    """A minimal valid appearance form-XObject stream."""
    s = COSStream()
    s.set_item(_TYPE, COSName.get_pdf_name("XObject"))
    s.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    s.set_int(_FORMTYPE, 1)
    s.set_item(
        _BBOX,
        COSArray([COSFloat(0), COSFloat(0), COSFloat(20), COSFloat(20)]),
    )
    with s.create_output_stream() as out:
        out.write(b"q Q\n")
    return s


def _checkbox_field(name: str, as_value: str | None) -> COSDictionary:
    """Build a single-widget-shortcut checkbox field dictionary.

    ``/FT /Btn`` + neither push nor radio flag = checkbox. The field
    dictionary doubles as the widget annotation (``/Subtype /Widget``)
    per the PDF spec's single-widget merge optimisation, so no /Kids
    is needed. ``/AP /N`` carries the standard ``{Yes, Off}`` state
    keys. ``as_value`` controls /AS:
      * "Yes"     — valid (matches an /AP /N key)
      * "Unknown" — invalid (key not in /AP /N)
      * None      — absent (no /AS at all)
    """
    field = COSDictionary()
    field.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    field.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    field.set_name(_FT, "Btn")
    field.set_string(_T, name)
    field.set_int(_FF, 0)
    # /Rect required for a valid widget annotation.
    field.set_item(
        COSName.get_pdf_name("Rect"),
        COSArray([COSFloat(50), COSFloat(700), COSFloat(70), COSFloat(720)]),
    )
    # /AP /N with the standard {Yes, Off} state keys.
    ap = COSDictionary()
    n_sub = COSDictionary()
    n_sub.set_item(_YES, _ap_stream())
    n_sub.set_item(_OFF, _ap_stream())
    ap.set_item(_N, n_sub)
    field.set_item(_AP, ap)
    if as_value is not None:
        field.set_item(_AS, COSName.get_pdf_name(as_value))
    return field


def _build_fixture(path: Path) -> None:
    """Three checkboxes: valid /AS, invalid /AS, absent /AS — all on one
    page, all attached to the document's AcroForm."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        cat = doc.get_document_catalog()
        form = PDAcroForm(doc)
        cat.set_acro_form(form)
        form = cat.get_acro_form()  # re-read after the cache reset

        cb_a = _checkbox_field("cbA", "Yes")
        cb_b = _checkbox_field("cbB", "Unknown")
        cb_c = _checkbox_field("cbC", None)

        # Attach each widget dict to the page's /Annots; the same dict also
        # appears in the form's /Fields. The single-widget merge means one
        # COS dict plays both roles.
        page_annots = page.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Annots")
        )
        if not isinstance(page_annots, COSArray):
            page_annots = COSArray()
            page.get_cos_object().set_item(
                COSName.get_pdf_name("Annots"), page_annots
            )
        for cb in (cb_a, cb_b, cb_c):
            page_annots.add(cb)

        fields = form.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Fields")
        )
        if not isinstance(fields, COSArray):
            fields = COSArray()
            form.get_cos_object().set_item(
                COSName.get_pdf_name("Fields"), fields
            )
        for cb in (cb_a, cb_b, cb_c):
            fields.add(cb)

        doc.save(str(path))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Java probe driver
# --------------------------------------------------------------------------- #
def _parse_java(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        if raw.startswith("FIELD "):
            current = {"FIELD": raw[len("FIELD ") :]}
        elif raw == "END":
            assert current is not None
            records.append(current)
            current = None
        elif current is not None:
            key, _, value = raw.partition(" ")
            current[key] = value
    return records


def _java_records(path: Path) -> list[dict[str, str]]:
    return _parse_java(run_probe_text(_PROBE, "read", str(path)))


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors AppearanceStateProbe exactly
# --------------------------------------------------------------------------- #
def _sub_keys(entry) -> str:
    if entry is None or not entry.is_sub_dictionary():
        return "-"
    keys = sorted(entry.get_sub_dictionary().keys())
    return " ".join(keys) if keys else "-"


def _resolved_key(widget: PDAnnotationWidget, normal) -> str:
    if normal is None:
        return "none"
    if not normal.is_sub_dictionary():
        return "none" if normal.get_appearance_stream() is None else "-"
    state = widget.get_appearance_state()
    if state is None:
        return "none"
    stream = normal.get_sub_dictionary().get(state)
    if stream is None:
        return "none"
    return state


def _py_checkbox_facts(field: PDCheckBox) -> dict[str, str]:
    widget = field.get_widgets()[0]
    state = widget.get_appearance_state()
    ap = widget.get_appearance()
    normal = ap.get_normal_appearance() if ap is not None else None
    return {
        "FIELD": field.get_fully_qualified_name(),
        "AS": "none" if state is None else state,
        "APKEYS": _sub_keys(normal),
        "RESOLVED": _resolved_key(widget, normal),
        "VALUE": field.get_value(),
        "ONVALUE": field.get_on_value(),
        "ISCHECKED": "1" if field.is_checked() else "0",
    }


def _py_records(path: Path) -> list[dict[str, str]]:
    doc = PDDocument.load(str(path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None
        out: list[dict[str, str]] = []
        for field in form.get_field_tree():
            if isinstance(field, PDCheckBox):
                out.append(_py_checkbox_facts(field))
        return out
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_appearance_state_facts_match_pdfbox(tmp_path: Path) -> None:
    """Every canonical fact pypdfbox reports for each checkbox equals what
    Apache PDFBox reports on the same pypdfbox-built fixture — across
    valid / invalid / absent ``/AS``. Covers ``get_appearance_state``,
    ``/AP /N`` sub-dict keys, resolved on-state key, ``getValue``,
    ``getOnValue``, ``isChecked``."""
    fixture = tmp_path / "appearance_state.pdf"
    _build_fixture(fixture)

    java = _java_records(fixture)
    py = _py_records(fixture)

    assert len(java) == 3, f"unexpected checkbox count: {len(java)}"
    assert len(py) == len(java)
    assert py == java


@requires_oracle
def test_valid_as_resolves_to_matching_subdict_key(tmp_path: Path) -> None:
    """Checkbox (a) — ``/AS = Yes`` matches the ``Yes`` key in ``/AP /N``.
    Both implementations report ``AS = Yes`` and RESOLVED = ``Yes`` (the
    sub-dict map lookup succeeded). The widget's ``/V`` is unset so
    ``getValue`` returns the spec default ``Off`` — and ``isChecked`` is
    therefore ``0`` since ``"Off" != "Yes"``."""
    fixture = tmp_path / "appearance_state.pdf"
    _build_fixture(fixture)
    java = _java_records(fixture)
    py = _py_records(fixture)

    assert py[0]["AS"] == java[0]["AS"] == "Yes"
    assert py[0]["APKEYS"] == java[0]["APKEYS"] == "Off Yes"
    assert py[0]["RESOLVED"] == java[0]["RESOLVED"] == "Yes"
    assert py[0]["VALUE"] == java[0]["VALUE"] == "Off"
    assert py[0]["ONVALUE"] == java[0]["ONVALUE"] == "Yes"
    # /V == "Off", on-value == "Yes" -> not checked.
    assert py[0]["ISCHECKED"] == java[0]["ISCHECKED"] == "0"


@requires_oracle
def test_invalid_as_returns_literal_and_resolved_none(tmp_path: Path) -> None:
    """**The high-value case.** Checkbox (b) — ``/AS = Unknown`` references
    a key NOT in ``/AP /N`` (keys are still ``{Yes, Off}``). PDFBox returns
    the literal ``Unknown`` from ``getAppearanceState()`` — it does NOT
    coerce to ``Off`` — and the sub-dict lookup misses so the resolved
    on-state stream is ``None``. ``isChecked`` is still driven by ``/V``
    vs ``getOnValue``, so the bogus ``/AS`` does NOT make the checkbox
    appear checked."""
    fixture = tmp_path / "appearance_state.pdf"
    _build_fixture(fixture)
    java = _java_records(fixture)
    py = _py_records(fixture)

    # 1. AS is the LITERAL stored value (no coercion).
    assert py[1]["AS"] == java[1]["AS"] == "Unknown"
    # 2. /AP /N keys unchanged.
    assert py[1]["APKEYS"] == java[1]["APKEYS"] == "Off Yes"
    # 3. Sub-dict lookup misses -> RESOLVED is "none".
    assert py[1]["RESOLVED"] == java[1]["RESOLVED"] == "none"
    # 4. /V default "Off"; isChecked compares /V against on-value Yes.
    assert py[1]["VALUE"] == java[1]["VALUE"] == "Off"
    assert py[1]["ONVALUE"] == java[1]["ONVALUE"] == "Yes"
    assert py[1]["ISCHECKED"] == java[1]["ISCHECKED"] == "0"


@requires_oracle
def test_absent_as_reports_none_and_value_defaults_off(tmp_path: Path) -> None:
    """Checkbox (c) — no ``/AS`` entry at all. ``getAppearanceState``
    returns ``None`` under both implementations; ``getValue`` still
    defaults to the spec ``Off`` so ``isChecked`` stays ``0``."""
    fixture = tmp_path / "appearance_state.pdf"
    _build_fixture(fixture)
    java = _java_records(fixture)
    py = _py_records(fixture)

    assert py[2]["AS"] == java[2]["AS"] == "none"
    assert py[2]["APKEYS"] == java[2]["APKEYS"] == "Off Yes"
    # /AS missing -> sub-dict lookup is not performed, RESOLVED is "none".
    assert py[2]["RESOLVED"] == java[2]["RESOLVED"] == "none"
    # /V default "Off" -> not checked.
    assert py[2]["VALUE"] == java[2]["VALUE"] == "Off"
    assert py[2]["ONVALUE"] == java[2]["ONVALUE"] == "Yes"
    assert py[2]["ISCHECKED"] == java[2]["ISCHECKED"] == "0"


@requires_oracle
def test_set_appearance_state_round_trip_preserves_invalid_key(
    tmp_path: Path,
) -> None:
    """``set_appearance_state`` writes whatever literal name the caller
    passes — even a key that does NOT appear in the widget's ``/AP /N``
    sub-dictionary — and ``get_appearance_state`` returns that literal
    back. Mirrors PDFBox's ``setAppearanceState(String)`` /
    ``getAppearanceState()`` contract: no validation against /AP keys,
    no coercion to ``Off``. This is the round-trip that lets producers
    pre-stage future state names before the appearance streams exist."""
    fixture = tmp_path / "appearance_state_roundtrip.pdf"
    _build_fixture(fixture)

    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None
        cb = form.get_field("cbA")
        assert isinstance(cb, PDCheckBox)
        widget = cb.get_widgets()[0]

        # Pre-condition — fixture wrote /AS = Yes.
        assert widget.get_appearance_state() == "Yes"

        # Set to a key NOT present in the /AP /N sub-dict; the literal
        # round-trips through both ``set_appearance_state`` overloads.
        widget.set_appearance_state("Future")
        assert widget.get_appearance_state() == "Future"

        widget.set_appearance_state(COSName.get_pdf_name("AlsoFuture"))
        assert widget.get_appearance_state() == "AlsoFuture"

        # Clearing /AS — ``None`` round-trips to ``None``.
        widget.set_appearance_state(None)
        assert widget.get_appearance_state() is None
    finally:
        doc.close()


@requires_oracle
def test_widget_set_to_existing_subdict_key_resolves(tmp_path: Path) -> None:
    """When ``set_appearance_state`` writes a key that DOES exist in
    ``/AP /N``, the on-state stream resolves through the sub-dict lookup
    — same as the fixture's valid case but reached via the setter API.
    Demonstrates the setter's parity with the in-file fact."""
    fixture = tmp_path / "appearance_state_setter.pdf"
    _build_fixture(fixture)

    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None
        cb = form.get_field("cbB")  # the invalid-/AS fixture entry
        assert isinstance(cb, PDCheckBox)
        widget = cb.get_widgets()[0]

        # Pre: invalid /AS. RESOLVED is None.
        ap = widget.get_appearance()
        normal = ap.get_normal_appearance()
        assert normal.get_sub_dictionary().get(
            widget.get_appearance_state()
        ) is None

        # Flip to a valid key.
        widget.set_appearance_state("Yes")
        assert widget.get_appearance_state() == "Yes"
        # Now the sub-dict lookup hits.
        assert normal.get_sub_dictionary().get(
            widget.get_appearance_state()
        ) is not None
    finally:
        doc.close()
