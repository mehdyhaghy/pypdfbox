"""Wave 1305 — ``PDAcroForm.refresh_appearances`` coverage for ``/Btn``
and ``/Ch`` field types.

Wave 1304 shipped the Tx (text-field) branch of
:meth:`PDAcroForm.refresh_appearances`. This wave extends the same
public entry point to actually generate ``/AP /N`` streams for:

* ``/Btn`` checkbox — emits a ZapfDingbats glyph (default ``b"4"`` =
  heavy check; ``b"8"`` = cross when ``/MK /CA = "8"``) centered in
  the widget rect on the on-state, and an empty stream on /Off.
* ``/Btn`` radio button — emits a filled circle on the on-state.
* ``/Btn`` push button — emits the ``/MK /CA`` caption centered in
  the widget rect, with optional /MK /BG / /BC background / border.
* ``/Ch`` combo box — emits the currently-selected value as a single
  flat text line.
* ``/Ch`` list box — emits every option line by line with the
  ``/I`` / ``/V`` selection highlighted (sky-blue rect + white text).

``/Sig`` stays intentionally out of scope — PDFBox itself does not
synthesize visible signature appearances (PDFBOX-3524).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton

_RECT: COSName = COSName.get_pdf_name("Rect")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_AS: COSName = COSName.get_pdf_name("AS")
_OFF: COSName = COSName.get_pdf_name("Off")
_DA: COSName = COSName.get_pdf_name("DA")
_MK: COSName = COSName.get_pdf_name("MK")
_CA: COSName = COSName.get_pdf_name("CA")
_YES: COSName = COSName.get_pdf_name("Yes")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _ap_normal_stream(widget_cos: COSDictionary, *, state: str | None = None) -> COSStream:
    """Resolve ``widget_cos`` → ``/AP /N`` → optional state key → stream."""
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary), "no /AP installed on widget"
    n = ap.get_dictionary_object(_N)
    if state is not None:
        assert isinstance(n, COSDictionary), (
            f"expected /AP /N subdictionary keyed by state, got {type(n).__name__}"
        )
        entry = n.get_dictionary_object(COSName.get_pdf_name(state))
        assert isinstance(entry, COSStream), (
            f"expected /AP /N /{state} to be a stream, got {type(entry).__name__}"
        )
        return entry
    assert isinstance(n, COSStream), (
        f"expected /AP /N to be a stream, got {type(n).__name__}"
    )
    return n


# ---------- /Btn — checkbox ----------


def test_refresh_appearances_checkbox_default_check_glyph() -> None:
    """Checkbox with no ``/MK /CA`` → on-state stream emits the default
    ZapfDingbats heavy-check glyph (``(4) Tj`` against the
    /ZaDb-tagged font resource).
    """
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    form.set_fields([cb])

    form.refresh_appearances()

    on_stream = _ap_normal_stream(cb.get_widgets()[0].get_cos_object(), state="Yes")
    body = on_stream.create_input_stream().read()
    # ZapfDingbats heavy-check glyph (code 0x34 = "4").
    assert b"(4) Tj" in body
    assert b"BT" in body
    assert b"ET" in body


def test_refresh_appearances_checkbox_mk_ca_cross_glyph() -> None:
    """Checkbox with ``/MK /CA = "8"`` → on-state stream emits the
    Acrobat "cross" glyph (``(8) Tj``).
    """
    form = PDAcroForm()
    cb = PDCheckBox(form)
    widget_cos = cb.get_cos_object()
    widget_cos.set_item(_RECT, _rect(0, 0, 20, 20))
    # /MK /CA = "8" — Acrobat-recognised cross glyph code.
    mk = COSDictionary()
    mk.set_string(_CA, "8")
    widget_cos.set_item(_MK, mk)
    form.set_fields([cb])

    form.refresh_appearances()

    on_stream = _ap_normal_stream(cb.get_widgets()[0].get_cos_object(), state="Yes")
    body = on_stream.create_input_stream().read()
    assert b"(8) Tj" in body


def test_refresh_appearances_checkbox_off_state_stream_is_empty() -> None:
    """Checkbox /AP /N /Off renders a stream with no Tj operator (the
    off-state is intentionally a blank box)."""
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    form.set_fields([cb])

    form.refresh_appearances()

    off_stream = _ap_normal_stream(cb.get_widgets()[0].get_cos_object(), state="Off")
    body = off_stream.create_input_stream().read()
    assert b"Tj" not in body


def test_refresh_appearances_checkbox_value_syncs_as_to_on_state() -> None:
    """When the field's /V matches the on-state name, /AS lands on the
    on-state key after :meth:`PDAcroForm.refresh_appearances`. Setting
    /V back to /Off resets /AS to /Off on a second refresh.
    """
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    cb.set_value("Yes")
    form.set_fields([cb])

    form.refresh_appearances()
    assert cb.get_widgets()[0].get_cos_object().get_name(_AS) == "Yes"

    cb.set_value("Off")
    form.refresh_appearances()
    assert cb.get_widgets()[0].get_cos_object().get_name(_AS) == "Off"


# ---------- /Btn — radio button ----------


def test_refresh_appearances_radio_button_on_state_emits_filled_circle() -> None:
    """Radio button on-state emits a vector-path filled circle — moveto
    + 4 cubic-Bezier curves + close + fill.
    """
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    form.set_fields([rb])

    form.refresh_appearances()

    on_stream = _ap_normal_stream(rb.get_widgets()[0].get_cos_object(), state="Yes")
    body = on_stream.create_input_stream().read()
    # Path operators expected for the inscribed-circle approximation.
    assert b" m\n" in body  # moveto
    assert b" c\n" in body  # cubic-Bezier
    assert b"h\n" in body  # close path
    assert b"f\n" in body  # fill
    # No text show — radios use a vector path, not a glyph.
    assert b"Tj" not in body


def test_refresh_appearances_radio_button_off_state_empty() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    form.set_fields([rb])

    form.refresh_appearances()

    off_stream = _ap_normal_stream(rb.get_widgets()[0].get_cos_object(), state="Off")
    body = off_stream.create_input_stream().read()
    # Off-state has no fill, no glyph.
    assert b"Tj" not in body
    assert b" c\n" not in body


# ---------- /Btn — push button ----------


def test_refresh_appearances_push_button_renders_mk_ca_caption() -> None:
    """Push button /AP /N is a single stream (no on/off subdict) whose
    body carries the ``/MK /CA`` caption as flat text.
    """
    form = PDAcroForm()
    pb = PDPushButton(form)
    widget_cos = pb.get_cos_object()
    widget_cos.set_item(_RECT, _rect(0, 0, 100, 30))
    mk = COSDictionary()
    mk.set_string(_CA, "Submit")
    widget_cos.set_item(_MK, mk)
    form.set_fields([pb])

    form.refresh_appearances()

    stream = _ap_normal_stream(pb.get_widgets()[0].get_cos_object())
    body = stream.create_input_stream().read()
    assert b"BT" in body
    assert b"(Submit) Tj" in body
    assert b"ET" in body


def test_refresh_appearances_push_button_without_caption_emits_empty_text() -> None:
    """Push button without ``/MK /CA`` → /AP /N still a stream, no Tj."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    pb.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 30))
    form.set_fields([pb])

    form.refresh_appearances()

    stream = _ap_normal_stream(pb.get_widgets()[0].get_cos_object())
    body = stream.create_input_stream().read()
    assert b"Tj" not in body


# ---------- /Ch — combo box ----------


def test_refresh_appearances_combo_box_renders_selected_value() -> None:
    """Combo box: /AP /N is a single stream containing the selected
    value as text (no per-option highlight — that's list-box-only).
    """
    form = PDAcroForm()
    cb = PDComboBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 20))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    cb.set_options(["alpha", "beta", "gamma"])
    cb.set_value("beta")
    form.set_fields([cb])

    form.refresh_appearances()

    stream = _ap_normal_stream(cb.get_widgets()[0].get_cos_object())
    body = stream.create_input_stream().read()
    assert b"BT" in body
    assert b"(beta) Tj" in body
    assert b"ET" in body
    # Other options must NOT appear — combos render only the selected.
    assert b"alpha" not in body
    assert b"gamma" not in body
    # /Tx BMC marked-content sentinel — required for Acrobat to treat
    # the stream as a form-field appearance.
    assert b"/Tx BMC" in body
    assert b"EMC" in body


def test_refresh_appearances_combo_box_empty_value_no_tj() -> None:
    """Combo box with no /V → BT/ET envelope still emitted, no Tj."""
    form = PDAcroForm()
    cb = PDComboBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 20))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    form.set_fields([cb])

    form.refresh_appearances()

    stream = _ap_normal_stream(cb.get_widgets()[0].get_cos_object())
    body = stream.create_input_stream().read()
    assert b"BT" in body
    assert b"ET" in body
    assert b"Tj" not in body


# ---------- /Ch — list box ----------


def test_refresh_appearances_list_box_renders_all_options_with_selection() -> None:
    """List box: /AP /N contains every option line-by-line. The selected
    row is preceded by a highlight rectangle (sky-blue ``rg`` + ``re``
    + ``f``) and the row glyphs flip to white (``1 1 1 rg``).
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 60))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["one", "two", "three"])
    lb.set_value("two")
    form.set_fields([lb])

    form.refresh_appearances()

    stream = _ap_normal_stream(lb.get_widgets()[0].get_cos_object())
    body = stream.create_input_stream().read()
    # Every option appears.
    assert b"(one) Tj" in body
    assert b"(two) Tj" in body
    assert b"(three) Tj" in body
    # Selection highlight rectangle — fill + rect operator.
    assert b" re\n" in body
    assert b"f\n" in body
    # White text marker for the highlighted row — set-non-stroking RGB
    # to (1, 1, 1).
    assert b"1 1 1 rg" in body
    # /Tx BMC marked-content sentinel.
    assert b"/Tx BMC" in body
    assert b"EMC" in body


def test_refresh_appearances_list_box_multi_select_highlights_two() -> None:
    """Multi-select list box with two selected values → two highlight
    rectangles and two white-text rows.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 90))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["one", "two", "three", "four"])
    lb.set_multi_select(True)
    lb.set_value(["one", "three"])
    form.set_fields([lb])

    form.refresh_appearances()

    stream = _ap_normal_stream(lb.get_widgets()[0].get_cos_object())
    body = stream.create_input_stream().read()
    # Two ``re`` + ``f`` highlight rectangles.
    assert body.count(b" re\n") >= 2
    # Per-row color flips — at least one switch back to default after
    # selection ends.
    assert b"1 1 1 rg" in body
    # Every option appears.
    assert b"(one) Tj" in body
    assert b"(two) Tj" in body
    assert b"(three) Tj" in body
    assert b"(four) Tj" in body


def test_refresh_appearances_list_box_no_selection_no_white_text() -> None:
    """List box with no /V → no highlight rectangle and no white-text
    color switch. All rows render in the /DA default color.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 60))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["one", "two", "three"])
    form.set_fields([lb])

    form.refresh_appearances()

    stream = _ap_normal_stream(lb.get_widgets()[0].get_cos_object())
    body = stream.create_input_stream().read()
    # No highlight fill — no ``re`` followed by ``f`` for selection.
    assert b"1 1 1 rg" not in body
    # All options still present.
    assert b"(one) Tj" in body
    assert b"(two) Tj" in body
    assert b"(three) Tj" in body


# ---------- mixed-field refresh ----------


def test_refresh_appearances_mixed_field_types_all_get_ap() -> None:
    """One call to ``refresh_appearances`` walks every field type in the
    same form and installs /AP on each widget. Smoke test that the
    per-/FT dispatch survives heterogeneous input.
    """
    form = PDAcroForm()

    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    cb.set_value("Yes")

    rb = PDRadioButton(form)
    rb.get_cos_object().set_item(_RECT, _rect(30, 0, 50, 20))
    rb.set_value("Yes")

    pb = PDPushButton(form)
    widget_pb = pb.get_cos_object()
    widget_pb.set_item(_RECT, _rect(60, 0, 160, 30))
    mk = COSDictionary()
    mk.set_string(_CA, "Go")
    widget_pb.set_item(_MK, mk)

    combo = PDComboBox(form)
    widget_combo = combo.get_cos_object()
    widget_combo.set_item(_RECT, _rect(0, 40, 120, 60))
    widget_combo.set_string(_DA, "/Helv 10 Tf 0 g")
    combo.set_options(["alpha", "beta"])
    combo.set_value("alpha")

    listbox = PDListBox(form)
    widget_lb = listbox.get_cos_object()
    widget_lb.set_item(_RECT, _rect(0, 70, 120, 130))
    widget_lb.set_string(_DA, "/Helv 10 Tf 0 g")
    listbox.set_options(["x", "y", "z"])
    listbox.set_value("y")

    form.set_fields([cb, rb, pb, combo, listbox])

    form.refresh_appearances()

    # Checkbox + radio land on subdict /AP /N.
    for btn in (cb, rb):
        widget_cos = btn.get_widgets()[0].get_cos_object()
        ap = widget_cos.get_dictionary_object(_AP)
        assert isinstance(ap, COSDictionary)
        n = ap.get_dictionary_object(_N)
        assert isinstance(n, COSDictionary)
        keys = {k.name for k in n.key_set()}
        assert "Yes" in keys
        assert "Off" in keys
        assert widget_cos.get_name(_AS) == "Yes"

    # Push button / combo / listbox land on a single /AP /N stream.
    for field in (pb, combo, listbox):
        widget_cos = field.get_widgets()[0].get_cos_object()
        stream = _ap_normal_stream(widget_cos)
        assert stream.create_input_stream().read()  # non-empty body


def test_refresh_appearances_subset_only_rebuilds_listed_fields() -> None:
    """``refresh_appearances([target])`` skips unlisted fields — the
    sentinel /AP on ``other`` survives the call.
    """
    form = PDAcroForm()

    target = PDCheckBox(form)
    target.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))

    other = PDCheckBox(form)
    other.get_cos_object().set_item(_RECT, _rect(30, 0, 50, 20))

    # Pre-seed ``other`` with a sentinel /AP that must not be touched.
    sentinel_stream = COSStream()
    sentinel_stream.set_raw_data(b"SENTINEL")
    sentinel_n = COSDictionary()
    sentinel_n.set_item(_YES, sentinel_stream)
    sentinel_ap = COSDictionary()
    sentinel_ap.set_item(_N, sentinel_n)
    other.get_widgets()[0].get_cos_object().set_item(_AP, sentinel_ap)

    form.set_fields([target, other])

    form.refresh_appearances([target])

    # ``target`` got a real stream — no sentinel.
    target_n = (
        target.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
    )
    assert isinstance(target_n, COSDictionary)
    target_yes = target_n.get_dictionary_object(_YES)
    assert isinstance(target_yes, COSStream)
    assert target_yes is not sentinel_stream

    # ``other`` was untouched — sentinel survived.
    other_ap = other.get_widgets()[0].get_cos_object().get_dictionary_object(_AP)
    assert other_ap is sentinel_ap
    assert other_ap.get_dictionary_object(_N) is sentinel_n
    assert sentinel_stream.to_raw_byte_array() == b"SENTINEL"
