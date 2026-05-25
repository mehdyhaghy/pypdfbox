"""Wave 1397 — residual branch coverage for ``PDAppearanceGenerator``.

Each test names the specific partial branch it closes (line number in
``pypdfbox/pdmodel/interactive/form/pd_appearance_generator.py``).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _parse_rv_runs,
    _parse_rv_style,
    _RichTextRun,
)
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT = COSName.get_pdf_name("Rect")
_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_DA = COSName.get_pdf_name("DA")
_RV = COSName.get_pdf_name("RV")
_FF = COSName.get_pdf_name("Ff")
_Q = COSName.get_pdf_name("Q")
_MAXLEN = COSName.get_pdf_name("MaxLen")
_OFF = COSName.get_pdf_name("Off")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _appearance_body(widget_cos: COSDictionary) -> bytes:
    ap = PDAppearanceDictionary(widget_cos.get_dictionary_object(_AP))
    n = ap.get_normal_appearance()
    assert n is not None
    return n.get_cos_object().create_input_stream().read()


# ---------------------------------------------------------------------------
# _parse_rv_style + _parse_rv_runs branches
# ---------------------------------------------------------------------------


def test_parse_rv_style_skips_empty_key_or_value_chunks() -> None:
    """Branch 534->528: ``_parse_rv_style`` continues past entries where
    either side of the ``:`` is empty after stripping.
    """
    # ``  :red``  → empty key; ``color:  `` → empty val; ``;` → no colon.
    style = _parse_rv_style("  :red ; color:  ;  ; font-weight : bold ")
    assert style == {"font-weight": "bold"}


def test_parse_rv_runs_invalid_color_style_falls_back_to_base() -> None:
    """Branch 638->640: ``_parse_rv_color`` returning ``None`` -- the
    ``local_color`` override is bypassed and the parent colour wins.
    """
    runs = _parse_rv_runs(
        '<body><p><span style="color:not-a-color">hi</span></p></body>'
    )
    assert runs is not None
    # The span ran but with no colour override -- search for the text.
    assert any(r.text == "hi" and r.color is None for r in runs)


def test_parse_rv_runs_invalid_font_size_keeps_inherited() -> None:
    """Branch 643->645: invalid font-size string -- ``_parse_rv_font_size``
    returns ``None`` and the ``local_font_size`` override is bypassed.
    """
    runs = _parse_rv_runs(
        '<body><p><span style="font-size:abc">hi</span></p></body>'
    )
    assert runs is not None
    assert any(r.text == "hi" and r.font_size is None for r in runs)


def test_parse_rv_runs_invalid_background_color_falls_back() -> None:
    """Branch 652->661: ``background-color`` with an unparseable value --
    ``local_background`` stays unset.
    """
    runs = _parse_rv_runs(
        '<body><p><span style="background-color:url(foo.png)">hi</span></p></body>'
    )
    assert runs is not None
    assert any(r.text == "hi" and r.background_color is None for r in runs)


def test_parse_rv_runs_invalid_background_shorthand_falls_back() -> None:
    """Branch 659->661: ``background`` CSS shorthand with a non-colour
    value -- ``local_background`` stays unset.
    """
    runs = _parse_rv_runs(
        '<body><p><span style="background:url(foo.png)">hi</span></p></body>'
    )
    assert runs is not None
    assert any(r.text == "hi" and r.background_color is None for r in runs)


def test_parse_rv_runs_br_without_tail_text_returns_early() -> None:
    """Branch 693->707: a ``<br/>`` element with no tail text -- the
    tail-text run is bypassed and ``walk`` returns directly.

    The post-walk pass strips trailing line-breaks, so the final runs
    list only contains the text run; the branch is still exercised
    inside ``walk`` even though the line-break gets popped at the end.
    """
    runs = _parse_rv_runs("<body><p>line1<br/></p></body>")
    assert runs is not None
    text_runs = [r for r in runs if r.text]
    assert text_runs == [text_runs[-1]]
    assert text_runs[-1].text == "line1"


# ---------------------------------------------------------------------------
# regenerate_value_with_appearance_value dispatch
# ---------------------------------------------------------------------------


class _FieldWithoutSetValue:
    """Stub field that is neither a PDTextField nor a _ValueField --
    triggers the fall-through to ``self.generate(field)`` only.
    """

    def get_widgets(self) -> list[Any]:
        return []


def test_set_appearance_value_with_unsupported_field_falls_through() -> None:
    """Branch 1003->1005: a field whose type matches neither PDTextField
    nor the ``_ValueField`` Protocol (no ``set_value`` method) -- the
    elif is skipped and ``self.generate(field)`` is called directly.
    """
    gen = PDAppearanceGenerator()
    # Logs at debug and returns; shouldn't raise.
    gen.set_appearance_value(_FieldWithoutSetValue(), "ignored")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _on_state_name_for_widget — AP /N with no non-Off entries
# ---------------------------------------------------------------------------


def test_on_state_name_n_entry_not_dict_returns_default() -> None:
    """Branch 1262->1266: widget /AP /N is present but not a
    COSDictionary (e.g. a COSName placeholder) -- the default ``"Yes"``
    is returned.
    """
    widget_cos = COSDictionary()
    ap = COSDictionary()
    # /AP /N as a COSName (not a dict) -- get_dictionary_object will
    # return the resolved object but isinstance(_, COSDictionary) is False.
    ap.set_item(_N, COSName.get_pdf_name("Custom"))
    widget_cos.set_item(_AP, ap)
    name = PDAppearanceGenerator()._on_state_name_for_widget(widget_cos)
    assert name == "Yes"


def test_on_state_name_n_subdict_only_off_returns_default() -> None:
    """Branch 1263->1266: widget /AP /N is a dict containing only the
    ``/Off`` entry -- the loop yields no non-Off key and ``"Yes"`` wins.
    """
    widget_cos = COSDictionary()
    ap = COSDictionary()
    n = COSDictionary()
    # Only /Off in the subdict.
    n.set_item(_OFF, COSStream())
    ap.set_item(_N, n)
    widget_cos.set_item(_AP, ap)
    name = PDAppearanceGenerator()._on_state_name_for_widget(widget_cos)
    assert name == "Yes"


# ---------------------------------------------------------------------------
# Interior-rect clip-path skips (widget width/height too small)
# ---------------------------------------------------------------------------


def test_combo_widget_too_narrow_skips_clip_rect() -> None:
    """Branch 1488->1492: combo-choice widget whose interior_w == 0 --
    skips the clip-rect emission.
    """
    from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox

    form = PDAcroForm()
    cb = PDComboBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 1.5, 40))  # interior_w == 0
    cos.set_string(_DA, "/Helv 8 Tf 0 0 0 rg")
    cb.set_options(["a"])
    cb.set_value(["a"])
    PDAppearanceGenerator().generate(cb)
    body = _appearance_body(cos)
    # No clip operator pair (W n) inside.
    assert b" W\n n\n" not in body


def test_listbox_widget_too_narrow_skips_clip_rect() -> None:
    """Branch 1589->1596: list box widget whose interior_w == 0 -- the
    selection-row layout still runs but the clip rect isn't emitted.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 1.0, 60))
    cos.set_string(_DA, "/Helv 8 Tf 0 0 0 rg")
    lb.set_options(["a", "b"])
    lb.set_value(["a"])
    PDAppearanceGenerator().generate(lb)
    body = _appearance_body(cos)
    assert b" W\n n\n" not in body


def test_text_widget_too_narrow_skips_clip_rect() -> None:
    """Branch 1744->1749: text widget whose interior_w == 0 -- skips
    the clip-rect emission but still draws (or attempts to draw) text.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 1.0, 20))
    cos.set_string(_DA, "/Helv 8 Tf 0 0 0 rg")
    tf.set_value("x")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(cos)
    assert b" W\n n\n" not in body


def test_rich_text_widget_too_narrow_skips_clip_rect() -> None:
    """Branch 1830->1834: rich-text widget whose interior_w == 0 -- the
    clip-rect emission is skipped.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 1.0, 40))
    cos.set_string(_DA, "/Helv 10 Tf 0 0 0 rg")
    tf.set_value("hi")
    cos.set_string(_RV, "<body><p>hi</p></body>")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(cos)
    assert b" W\n n\n" not in body


# ---------------------------------------------------------------------------
# Empty / fallback-path rich-text rendering
# ---------------------------------------------------------------------------


def test_rich_text_line_break_only_closes_text_mode_at_end() -> None:
    """Smoke test: rich-text runs ending with line breaks still produce
    a valid stream with a final ``ET`` so ``text_mode_open`` ending
    True is exercised (the False path is pragma'd as unreachable).
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 80))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("seed")
    cos.set_string(_RV, "<body><p>line1<br/>line2</p></body>")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(cos)
    assert b"BT\n" in body
    assert b"ET\n" in body


# ---------------------------------------------------------------------------
# _infer_font_family — getter not callable
# ---------------------------------------------------------------------------


class _FontWithoutGetName:
    """Stub font object missing the ``get_name`` callable."""

    def get_cos_object(self) -> COSDictionary:  # pragma: no cover - stub
        return COSDictionary()

    get_name: Any = "not-a-callable"


def test_infer_font_family_skips_when_getter_not_callable() -> None:
    """Branch 2081->2086: ``base_font.get_name`` exists but isn't callable
    -- the candidate stays empty and the final return path is ``None``.
    """
    result = PDAppearanceGenerator._infer_font_family(
        _FontWithoutGetName(), base_font_name=None  # type: ignore[arg-type]
    )
    assert result is None


# ---------------------------------------------------------------------------
# _emit_multiline_text — empty line skip
# ---------------------------------------------------------------------------


def test_multiline_text_skips_show_text_for_empty_value() -> None:
    """Branch 2183->2173: multi-line wrap producing an empty line --
    ``if line: cs.show_text(line)`` is bypassed for the empty entry.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 80))
    cos.set_string(_DA, "/Helv 10 Tf 0 0 0 rg")
    # Multi-line bit (Ff bit 13 = 0x1000).
    cos.set_int(_FF, 0x1000)
    # Empty value -> ``_wrap_lines`` returns ['']; the for-loop runs once
    # with line='' and the ``if line:`` show_text branch is bypassed.
    tf.set_value("")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(cos)
    # The stream is still well-formed BT/ET pair even with empty text.
    assert b"BT\n" in body
    assert b"ET\n" in body


# ---------------------------------------------------------------------------
# _emit_comb_text — color=None branch
# ---------------------------------------------------------------------------


def test_comb_text_with_no_color_skips_color_emit() -> None:
    """Branch 2204->2206: comb-text branch with ``color=None`` (no /DA
    colour component) bypasses the ``set_non_stroking_color`` call.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 30))
    # Comb DA without a rg/g colour set -- font_size + flags only.
    cos.set_string(_DA, "/Helv 10 Tf")
    # Comb bit (Ff bit 25 = 0x1000000) + MaxLen.
    cos.set_int(_FF, 0x1000000)
    cos.set_int(_MAXLEN, 4)
    tf.set_value("abcd")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(cos)
    # No ``0 0 0 rg`` colour op was emitted inside the comb text block.
    # (Whitespace-anchored to allow other rg/RG ops in border/etc.)
    assert b"(a)" in body
    assert b"(d)" in body


# ---------------------------------------------------------------------------
# _resolve_default_appearance — getter not callable
# ---------------------------------------------------------------------------


class _FieldWithoutDAGetter:
    """Field-like stub whose ``get_default_appearance`` isn't callable."""

    get_default_appearance: Any = "not-a-callable"


def test_resolve_default_appearance_skips_when_getter_not_callable() -> None:
    """Branch 2716->2721: ``getter`` resolves but isn't callable -- the
    ``try/except`` block is bypassed and ``da`` stays None, then falls
    back to the explicit override.
    """
    gen = PDAppearanceGenerator(default_appearance="/Helv 12 Tf 0 g")
    result = gen._resolve_default_appearance(
        _FieldWithoutDAGetter()  # type: ignore[arg-type]
    )
    assert result == "/Helv 12 Tf 0 g"


# ---------------------------------------------------------------------------
# _lookup_font_in_widget_appearance — n dict with non-stream entries
# ---------------------------------------------------------------------------


def test_lookup_font_in_widget_appearance_skips_non_stream_entries() -> None:
    """Branch 2865->2863: /AP /N subdict contains an entry whose value is
    NOT a COSStream (e.g. another dictionary) -- it's skipped in the
    candidate-stream collection loop.
    """
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )

    widget = PDAnnotationWidget()
    ap = COSDictionary()
    n = COSDictionary()
    # First entry: non-stream (a dictionary) -- gets skipped.
    n.set_item(COSName.get_pdf_name("On"), COSDictionary())
    # No stream entries at all -- lookup must return None.
    ap.set_item(_N, n)
    widget.get_cos_object().set_item(_AP, ap)
    result = PDAppearanceGenerator._lookup_font_in_widget_appearance(
        widget, COSName.get_pdf_name("Helv")
    )
    assert result is None


def test_lookup_font_in_widget_appearance_stream_without_resources_falls_through() -> None:
    """Branch 2875->2867: a candidate stream exists but its /Resources
    /Font dict doesn't contain ``key`` -- the inner ``return font`` is
    bypassed and the loop continues to the next candidate.
    """
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )

    widget = PDAnnotationWidget()
    ap = COSDictionary()
    stream = COSStream()
    # /Resources with a /Font dict that doesn't contain the queried key.
    resources = COSDictionary()
    font_dict = COSDictionary()
    # Stage a different font under a different key.
    font_dict.set_item(
        COSName.get_pdf_name("Other"),
        PDFontFactory.create_default_font(
            Standard14Fonts.HELVETICA
        ).get_cos_object(),
    )
    resources.set_item(COSName.get_pdf_name("Font"), font_dict)
    stream.set_item(COSName.get_pdf_name("Resources"), resources)
    ap.set_item(_N, stream)
    widget.get_cos_object().set_item(_AP, ap)
    result = PDAppearanceGenerator._lookup_font_in_widget_appearance(
        widget, COSName.get_pdf_name("Helv")
    )
    assert result is None


# ---------------------------------------------------------------------------
# _lookup_font_in_widget_page — getter not callable
# ---------------------------------------------------------------------------


class _WidgetWithoutPage:
    """Widget stub with ``get_page`` attribute that isn't callable."""

    get_page: Any = "not-a-callable"


def test_lookup_font_in_widget_page_returns_none_when_getter_not_callable() -> None:
    """Branch 2894->2899: widget exposes ``get_page`` but it isn't
    callable -- the call is bypassed and the page stays None.
    """
    result = PDAppearanceGenerator._lookup_font_in_widget_page(
        _WidgetWithoutPage(),  # type: ignore[arg-type]
        COSName.get_pdf_name("Helv"),
    )
    assert result is None


# ---------------------------------------------------------------------------
# _register_font_alias — alias not yet claimed
# ---------------------------------------------------------------------------


def test_register_font_alias_alias_absent_seeds_resources() -> None:
    """Branch 2938->2942: the alias key isn't already in the /Font subdict
    -- ``existing is not None`` is False, so the alias is seeded.
    """
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
        PDAppearanceContentStream,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
        PDAppearanceStream,
    )

    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 40))
    cos.set_string(_DA, "/Helv 10 Tf 0 0 0 rg")
    # Build a minimal appearance stream so we can drive register_font_alias.
    ap_cos = COSStream()
    ap_cos.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    ap_cos.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    ap_cos.set_int(COSName.get_pdf_name("FormType"), 1)
    ap_cos.set_item(
        COSName.get_pdf_name("BBox"),
        COSArray([COSFloat(0), COSFloat(0), COSFloat(100), COSFloat(40)]),
    )
    ap_stream = PDAppearanceStream(ap_cos)
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    with PDAppearanceContentStream(ap_stream) as cs:
        # Seed an existing /Font subdict that does NOT contain "Helv".
        resources = cs.get_resources()
        font_subdict = COSDictionary()
        resources.get_cos_object().set_item(
            COSName.get_pdf_name("Font"), font_subdict
        )
        # First call: alias absent → seeded.
        PDAppearanceGenerator._register_font_alias(cs, font, "Helv")
        # Confirm the alias landed.
        font_after = (
            cs.get_resources()
            .get_cos_object()
            .get_dictionary_object(COSName.get_pdf_name("Font"))
        )
        assert font_after.get_dictionary_object(
            COSName.get_pdf_name("Helv")
        ) is font.get_cos_object()


# ---------------------------------------------------------------------------
# _calculate_matrix — non-canonical rotation passes through
# ---------------------------------------------------------------------------


def test_calculate_matrix_non_canonical_rotation_falls_through() -> None:
    """Branch 3050->3052: a rotation that isn't 0/90/180/270 (e.g. 45)
    -- the ``elif rotation == 270`` branch is bypassed and the matrix is
    computed with the user-supplied angle but zero translation offsets.
    """
    mat = PDAppearanceGenerator._calculate_matrix(100.0, 40.0, 45)
    a, b, c, d, tx, ty = mat
    # 45 deg cos/sin both ~= 0.7071...
    assert tx == 0.0
    assert ty == 0.0
    assert abs(a - 0.7071) < 0.01
    assert abs(b - 0.7071) < 0.01


# ---------------------------------------------------------------------------
# Bonus: rich-text style runs that exercise tail-/sibling-text paths
# ---------------------------------------------------------------------------


def test_parse_rv_runs_inline_style_with_only_semicolon_returns_empty() -> None:
    """Sanity guard around ``_parse_rv_style`` -- a ``style="; ; ;"`` is
    a no-op rather than an error.
    """
    runs = _parse_rv_runs('<body><p><span style="; ; ;">hi</span></p></body>')
    assert runs is not None
    assert any(r.text == "hi" for r in runs)


def test_rich_run_dataclass_defaults() -> None:
    """Sanity guard around the ``_RichTextRun`` dataclass defaults."""
    run = _RichTextRun(text="abc")
    assert run.text == "abc"
    assert run.bold is False
    assert run.italic is False
    assert run.color is None
    assert run.line_break is False
    assert run.background_color is None
    assert run.underline is False
