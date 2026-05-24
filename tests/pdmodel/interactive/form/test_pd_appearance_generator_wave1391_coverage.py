"""Wave 1391 — close residual missing-line coverage in pd_appearance_generator."""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _parse_rv_color,
    _RichTextRun,
    _strip_xhtml_ns,
)
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT = COSName.get_pdf_name("Rect")
_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_DA = COSName.get_pdf_name("DA")
_RV = COSName.get_pdf_name("RV")
_MK = COSName.get_pdf_name("MK")
_R = COSName.get_pdf_name("R")
_BG = COSName.get_pdf_name("BG")
_CA_NAME = COSName.get_pdf_name("CA")
_FONT = COSName.get_pdf_name("Font")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _appearance_body(widget_cos: COSDictionary) -> bytes:
    ap = PDAppearanceDictionary(widget_cos.get_dictionary_object(_AP))
    n = ap.get_normal_appearance()
    assert n is not None
    return n.get_cos_object().create_input_stream().read()


def test_strip_xhtml_ns_drops_namespace_prefix() -> None:
    assert _strip_xhtml_ns("{http://www.w3.org/1999/xhtml}P") == "p"


def test_strip_xhtml_ns_passthrough_when_no_namespace() -> None:
    assert _strip_xhtml_ns("P") == "p"


def test_parse_rv_color_odd_length_hex_returns_none() -> None:
    assert _parse_rv_color("#abcd") is None
    assert _parse_rv_color("#abcde") is None
    assert _parse_rv_color("#abcdef0") is None
    assert _parse_rv_color("#abcdef01") is None


def test_parse_rv_color_hsla_drops_alpha() -> None:
    result = _parse_rv_color("hsla(0, 100%, 50%, 0.5)")
    assert result is not None
    r, g, b = result
    assert r == pytest.approx(1.0)


def test_parse_rv_color_hsl_third_segment_path() -> None:
    assert _parse_rv_color("hsl(60, 100%, 25%)") is not None


def test_parse_rv_color_hsl_hue_wraps_above_one() -> None:
    result = _parse_rv_color("hsl(288, 100%, 50%)")
    assert result is not None
    r, _, b = result
    assert r > 0.5 and b > 0.5


class _NoGetter:
    get_rich_text_value = "not callable"


class _RaisingGetter:
    def get_rich_text_value(self) -> str:
        raise RuntimeError("boom")


def test_resolve_rich_text_value_none_when_not_callable() -> None:
    assert PDAppearanceGenerator._resolve_rich_text_value(_NoGetter()) is None  # type: ignore[arg-type]


def test_resolve_rich_text_value_none_when_getter_raises() -> None:
    assert PDAppearanceGenerator._resolve_rich_text_value(_RaisingGetter()) is None  # type: ignore[arg-type]


def test_combo_box_with_rotation_swaps_bbox() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 40))
    cos.set_string(_DA, "/Helv 10 Tf 0 0 0 rg")
    mk = COSDictionary()
    mk.set_int(_R, 90)
    cos.set_item(_MK, mk)
    cb.set_options(["alpha", "beta"])
    cb.set_value(["alpha"])
    PDAppearanceGenerator().generate(cb)
    widget_cos = cb.get_widgets()[0].get_cos_object()
    n = PDAppearanceDictionary(widget_cos.get_dictionary_object(_AP)).get_normal_appearance()
    assert n is not None
    bbox = n.get_cos_object().get_dictionary_object(COSName.get_pdf_name("BBox"))
    flat = bbox.to_float_array()
    assert flat[2] == pytest.approx(40.0)


def test_listbox_with_rotation_swaps_bbox() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 40))
    cos.set_string(_DA, "/Helv 10 Tf 0 0 0 rg")
    mk = COSDictionary()
    mk.set_int(_R, 270)
    cos.set_item(_MK, mk)
    lb.set_options(["one", "two"])
    lb.set_value(["one"])
    PDAppearanceGenerator().generate(lb)


def test_combo_box_iterative_auto_size() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 60, 20))
    cos.set_string(_DA, "/Helv 0 Tf 0 0 0 rg")
    cb.set_options(["AVeryLongChoiceLabel"])
    cb.set_value(["AVeryLongChoiceLabel"])
    PDAppearanceGenerator().generate(cb)
    body = _appearance_body(cb.get_widgets()[0].get_cos_object())
    assert b" Tf\n" in body


def test_rich_text_widget_with_rotation_swaps_bbox() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    mk = COSDictionary()
    mk.set_int(_R, 90)
    cos.set_item(_MK, mk)
    tf.set_value("fb")
    cos.set_string(_RV, "<body><p>hello</p></body>")
    PDAppearanceGenerator().generate(tf)


def test_rich_text_widget_invalid_rect_removes_ap() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 100))
    tf.set_value("seed")
    PDAppearanceGenerator().generate(tf)
    widget_cos = tf.get_widgets()[0].get_cos_object()
    assert isinstance(widget_cos.get_dictionary_object(_AP), COSDictionary)
    cos.set_item(_RECT, COSArray([COSFloat(0.0)]))
    cos.set_string(_RV, "<body><p>hello</p></body>")
    PDAppearanceGenerator().generate(tf)
    assert widget_cos.get_dictionary_object(_AP) is None


def test_rich_text_widget_zero_width_returns_early() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 0, 50))
    tf.set_value("seed")
    cos.set_string(_RV, "<body><p>hi</p></body>")
    PDAppearanceGenerator().generate(tf)


def test_rich_text_runs_with_background_color() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(
        _RV, '<body><p><span style="background-color:#ff0">hi</span></p></body>'
    )
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf.get_widgets()[0].get_cos_object())
    assert b"(hi)" in body


def test_rich_text_runs_with_text_rise() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(_RV, "<body><p>x<sup>2</sup></p></body>")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf.get_widgets()[0].get_cos_object())
    assert b" Ts\n" in body


def test_rich_text_runs_color_transition() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(
        _RV, '<body><p>a<span style="color:#f00">b</span>c</p></body>'
    )
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf.get_widgets()[0].get_cos_object())
    assert body.count(b" rg\n") >= 2


def test_rich_text_runs_line_break_emits_t_star() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 80))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(_RV, "<body><p>line1<br/>line2</p></body>")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf.get_widgets()[0].get_cos_object())
    assert b"T*\n" in body


def test_rich_text_runs_text_mode_reopen_with_rise() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 80))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(
        _RV,
        '<body><p><sup>x<span style="background-color:#f00">y</span>z</sup></p></body>',
    )
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf.get_widgets()[0].get_cos_object())
    assert body.count(b" Ts\n") >= 2


def test_rich_text_widget_existing_ap_dict_preserved() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("a")
    PDAppearanceGenerator().generate(tf)
    widget_cos = tf.get_widgets()[0].get_cos_object()
    first_ap = widget_cos.get_dictionary_object(_AP)
    cos.set_string(_RV, "<body><p>hi</p></body>")
    PDAppearanceGenerator().generate(tf)
    assert widget_cos.get_dictionary_object(_AP) is first_ap


def test_rich_text_helvetica_family() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(
        _RV, '<body><p><span style="font-family:helvetica"><b>z</b></span></p></body>'
    )
    PDAppearanceGenerator().generate(tf)


def test_rich_text_unknown_family_with_bold() -> None:
    gen = PDAppearanceGenerator()
    base = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    run = _RichTextRun(text="x", bold=True, font_family="Wingdings")
    assert gen._resolve_rich_text_font(base, None, run) is not None  # noqa: SLF001


def test_font_variant_name_unknown_family_returns_none() -> None:
    assert PDAppearanceGenerator._font_variant_name("dingbats", False, False) is None


def test_font_variant_name_helvetica_bold_italic() -> None:
    assert (
        PDAppearanceGenerator._font_variant_name("Helvetica", True, True)
        == Standard14Fonts.HELVETICA_BOLD_OBLIQUE
    )


def test_font_variant_name_helvetica_bold() -> None:
    assert (
        PDAppearanceGenerator._font_variant_name("Helvetica", True, False)
        == Standard14Fonts.HELVETICA_BOLD
    )


def test_font_variant_name_helvetica_italic() -> None:
    assert (
        PDAppearanceGenerator._font_variant_name("Helvetica", False, True)
        == Standard14Fonts.HELVETICA_OBLIQUE
    )


def test_font_variant_name_times_plain_returns_roman() -> None:
    assert (
        PDAppearanceGenerator._font_variant_name("Times", False, False) == "Times-Roman"
    )


def test_resolve_rich_text_font_variant_none_returns_base() -> None:
    gen = PDAppearanceGenerator()
    base = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    orig = PDAppearanceGenerator._font_variant_name

    def _patched(family: str, bold: bool, italic: bool) -> str | None:
        if family.lower() == "times":
            return None
        return orig(family, bold, italic)

    PDAppearanceGenerator._font_variant_name = staticmethod(_patched)  # type: ignore[method-assign]
    try:
        run = _RichTextRun(text="x", font_family="times")
        font = gen._resolve_rich_text_font(base, None, run)  # noqa: SLF001
        assert font is base
    finally:
        PDAppearanceGenerator._font_variant_name = staticmethod(orig)  # type: ignore[method-assign]


def test_resolve_rich_text_font_variant_not_in_std14() -> None:
    gen = PDAppearanceGenerator()
    base = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    orig = PDAppearanceGenerator._font_variant_name

    def _patched(family: str, bold: bool, italic: bool) -> str | None:
        return "NotAStandard14Font"

    PDAppearanceGenerator._font_variant_name = staticmethod(_patched)  # type: ignore[method-assign]
    try:
        run = _RichTextRun(text="x", font_family="times")
        font = gen._resolve_rich_text_font(base, None, run)  # noqa: SLF001
        assert font is base
    finally:
        PDAppearanceGenerator._font_variant_name = staticmethod(orig)  # type: ignore[method-assign]


def test_resolve_rich_text_font_helvetica_no_bi() -> None:
    gen = PDAppearanceGenerator()
    base = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    run = _RichTextRun(text="x", font_family="helvetica")
    assert gen._resolve_rich_text_font(base, "Helv", run) is not None  # noqa: SLF001


def test_rich_text_times_bold_italic() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(
        _RV, '<body><p><span style="font-family:Times"><b><i>x</i></b></span></p></body>'
    )
    PDAppearanceGenerator().generate(tf)


def test_rich_text_times_bold() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(
        _RV, '<body><p><span style="font-family:Times"><b>x</b></span></p></body>'
    )
    PDAppearanceGenerator().generate(tf)


def test_rich_text_times_italic() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(
        _RV, '<body><p><span style="font-family:Times"><i>x</i></span></p></body>'
    )
    PDAppearanceGenerator().generate(tf)


def test_rich_text_courier_all_variants() -> None:
    for tags in ("<b><i>x</i></b>", "<b>x</b>", "<i>x</i>", "x"):
        form = PDAcroForm()
        tf = PDTextField(form)
        cos = tf.get_cos_object()
        cos.set_item(_RECT, _rect(0, 0, 200, 60))
        cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
        tf.set_value("fb")
        cos.set_string(
            _RV,
            f'<body><p><span style="font-family:Courier">{tags}</span></p></body>',
        )
        PDAppearanceGenerator().generate(tf)


def test_rich_text_infer_from_courier_da() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/Cour 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(_RV, "<body><p><b>x</b></p></body>")
    PDAppearanceGenerator().generate(tf)


def test_rich_text_infer_from_times_da() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 60))
    cos.set_string(_DA, "/TiRo 12 Tf 0 0 0 rg")
    tf.set_value("fb")
    cos.set_string(_RV, "<body><p><b>x</b></p></body>")
    PDAppearanceGenerator().generate(tf)


class _NamedFontCourier:
    def get_name(self) -> str:
        return "Courier"


def test_infer_font_family_from_get_name_courier() -> None:
    assert (
        PDAppearanceGenerator._infer_font_family(_NamedFontCourier(), None)  # type: ignore[arg-type]
        == "Courier"
    )


def test_infer_font_family_get_name_returns_non_string() -> None:
    class _BadFont:
        def get_name(self) -> int:
            return 42  # type: ignore[return-value]

    assert (
        PDAppearanceGenerator._infer_font_family(_BadFont(), None)  # type: ignore[arg-type]
        is None
    )


def test_wrap_lines_paragraph_get_lines_raises() -> None:
    from pypdfbox.pdmodel.interactive.form import plain_text as pt_mod

    class _BadParagraph:
        def __init__(self, text: str) -> None:
            self._text = text

        def get_text(self) -> str:
            return self._text

        def get_lines(self, font, size, width):  # type: ignore[no-untyped-def]
            raise OSError("simulated")

    class _PatchedPlainText:
        def __init__(self, text: str) -> None:
            self._text = text

        def get_paragraphs(self) -> list[_BadParagraph]:
            return [_BadParagraph(line) for line in self._text.split("\n")]

    orig = pt_mod.PlainText
    pt_mod.PlainText = _PatchedPlainText  # type: ignore[misc]
    try:
        gen = PDAppearanceGenerator()
        font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        out = gen._wrap_lines("hello\nworld", font, 12.0, 200.0)  # noqa: SLF001
        assert out == ["hello", "world"]
    finally:
        pt_mod.PlainText = orig  # type: ignore[misc]


def test_text_widget_narrow_rect_keeps_lines() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 3, 100))
    cos.set_string(_DA, "/Helv 8 Tf 0 0 0 rg")
    tf.set_multiline(True)
    tf.set_value("hello\nworld")
    PDAppearanceGenerator().generate(tf)


def test_push_button_with_rotation_swaps_bbox() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    cos = pb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 80, 30))
    mk = COSDictionary()
    mk.set_int(_R, 90)
    mk.set_string(_CA_NAME, "Click")
    cos.set_item(_MK, mk)
    PDAppearanceGenerator().generate(pb)


def test_push_button_rollover_skipped_when_no_signal() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    cos = pb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 50, 20))
    mk = COSDictionary()
    mk.set_string(_CA_NAME, "Press")
    cos.set_item(_MK, mk)
    PDAppearanceGenerator().generate(pb)
    widget_cos = pb.get_widgets()[0].get_cos_object()
    ap_cos = widget_cos.get_dictionary_object(_AP)
    assert ap_cos.get_dictionary_object(COSName.get_pdf_name("R")) is None
    assert ap_cos.get_dictionary_object(COSName.get_pdf_name("D")) is None


def test_push_button_rollover_emitted_when_bg_present() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    cos = pb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 60, 20))
    mk = COSDictionary()
    mk.set_string(_CA_NAME, "Click")
    mk.set_item(_BG, COSArray([COSFloat(0.5), COSFloat(0.5), COSFloat(0.5)]))
    cos.set_item(_MK, mk)
    PDAppearanceGenerator().generate(pb)
    widget_cos = pb.get_widgets()[0].get_cos_object()
    ap_cos = widget_cos.get_dictionary_object(_AP)
    assert ap_cos.get_dictionary_object(COSName.get_pdf_name("R")) is not None
    assert ap_cos.get_dictionary_object(COSName.get_pdf_name("D")) is not None


def test_push_button_rollover_skips_when_rect_missing() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    cos = pb.get_cos_object()
    mk = COSDictionary()
    mk.set_item(_BG, COSArray([COSFloat(0.5), COSFloat(0.5), COSFloat(0.5)]))
    cos.set_item(_MK, mk)
    PDAppearanceGenerator().generate(pb)


def test_push_button_down_skips_when_rect_zero() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    cos = pb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 0, 20))
    mk = COSDictionary()
    mk.set_item(_BG, COSArray([COSFloat(0.5), COSFloat(0.5), COSFloat(0.5)]))
    cos.set_item(_MK, mk)
    PDAppearanceGenerator().generate(pb)


def test_signature_widget_with_rotation_swaps_bbox() -> None:
    form = PDAcroForm()
    sig = PDSignatureField(form)
    cos = sig.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 40))
    mk = COSDictionary()
    mk.set_int(_R, 90)
    cos.set_item(_MK, mk)
    PDAppearanceGenerator().generate(sig)


class _RaisingAcroFormField:
    def get_acro_form(self) -> object:
        raise RuntimeError("no acroform")


def test_resolve_font_for_field_swallows_acro_form_error() -> None:
    gen = PDAppearanceGenerator()
    font = gen._resolve_font_for_field(_RaisingAcroFormField(), "Helv", None)  # type: ignore[arg-type]  # noqa: SLF001
    assert font is not None


class _WidgetNoCos:
    @property
    def get_cos_object(self):  # type: ignore[no-untyped-def]
        raise AttributeError("no cos")


def test_lookup_font_in_widget_appearance_returns_none_for_no_cos() -> None:
    key = COSName.get_pdf_name("Helv")
    assert (
        PDAppearanceGenerator._lookup_font_in_widget_appearance(_WidgetNoCos(), key)  # type: ignore[arg-type]
        is None
    )


class _WidgetRaisingPage:
    def __init__(self) -> None:
        self._cos = COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._cos

    def get_page(self) -> object:
        raise RuntimeError("no page")


def test_lookup_font_in_widget_page_swallows_get_page_error() -> None:
    key = COSName.get_pdf_name("Helv")
    assert (
        PDAppearanceGenerator._lookup_font_in_widget_page(_WidgetRaisingPage(), key)  # type: ignore[arg-type]
        is None
    )


def _make_appearance_cs() -> PDAppearanceContentStream:
    stream_cos = COSStream()
    stream_cos.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream_cos.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    stream_cos.set_int(COSName.get_pdf_name("FormType"), 1)
    stream_cos.set_item(
        COSName.get_pdf_name("BBox"),
        COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(10.0), COSFloat(10.0)]),
    )
    return PDAppearanceContentStream(PDAppearanceStream(stream_cos))


def test_register_font_alias_no_alias_is_noop() -> None:
    with _make_appearance_cs() as cs:
        font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        PDAppearanceGenerator._register_font_alias(cs, font, None)


def test_register_font_alias_existing_different_font_skips_clobber() -> None:
    with _make_appearance_cs() as cs:
        helv = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        courier = PDFontFactory.create_default_font(Standard14Fonts.COURIER)
        PDAppearanceGenerator._register_font_alias(cs, helv, "Helv")
        PDAppearanceGenerator._register_font_alias(cs, courier, "Helv")
        resources = cs.get_resources()
        font_sub = resources.get_cos_object().get_dictionary_object(_FONT)
        helv_entry = font_sub.get_dictionary_object(COSName.get_pdf_name("Helv"))
        assert helv_entry is helv.get_cos_object()


def test_register_font_alias_same_font_is_idempotent() -> None:
    with _make_appearance_cs() as cs:
        helv = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        PDAppearanceGenerator._register_font_alias(cs, helv, "Helv")
        PDAppearanceGenerator._register_font_alias(cs, helv, "Helv")


def test_iterative_auto_size_clamps_to_minimum() -> None:
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    size = PDAppearanceGenerator._iterative_auto_size(font, "A" * 40, 1.0, 10.0)
    assert size == PDAppearanceGenerator.MINIMUM_FONT_SIZE


def test_resolve_widget_rotation_negative() -> None:
    widget_cos = COSDictionary()
    mk = COSDictionary()
    mk.set_int(_R, -90)
    widget_cos.set_item(_MK, mk)
    assert PDAppearanceGenerator._resolve_widget_rotation(widget_cos) == 270


def test_resolve_widget_rotation_non_multiple_of_90() -> None:
    widget_cos = COSDictionary()
    mk = COSDictionary()
    mk.set_int(_R, 45)
    widget_cos.set_item(_MK, mk)
    assert PDAppearanceGenerator._resolve_widget_rotation(widget_cos) == 0
