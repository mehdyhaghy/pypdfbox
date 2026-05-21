"""Wave 1375 — close the "custom-embedded /DA fonts not honoured" deviation.

Verifies that :class:`PDAppearanceGenerator` resolves the source ``/DA``
font alias through the full three-tier chain documented in upstream
``AppearanceGeneratorHelper`` / ``PDDefaultAppearanceString``:

1. AcroForm ``/DR /Font`` — canonical location for ``/DA`` aliases.
2. Widget ``/AP /N /Resources /Font`` — per-widget override.
3. Page ``/Resources /Font`` — last legal location.

Then falls back to the Standard 14 alias-mapped font. Each layer's font
COSDictionary must round-trip through the regenerated appearance stream
(same object identity in the appearance ``/Resources /Font``, ``/<alias>``
preserved in the emitted ``Tf`` token).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_resources import PDResources

_RECT: COSName = COSName.get_pdf_name("Rect")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_DA: COSName = COSName.get_pdf_name("DA")
_FONT: COSName = COSName.get_pdf_name("Font")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_TYPE: COSName = COSName.get_pdf_name("Type")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _build_custom_font_dict(base_name: str = "Times-Bold") -> COSDictionary:
    """Build a minimal Type1 font dictionary backed by a Standard 14 face.

    Using a Standard 14 backing font means the font reports usable
    metrics via :meth:`PDFont.get_average_font_width`, so the iterative
    auto-size loop in :meth:`PDAppearanceGenerator._regenerate_text_widget`
    has something to measure against. The dictionary itself is what
    callers register under a custom alias in ``/DR /Font`` — the alias
    + dictionary identity are the load-bearing pieces for the parity
    assertion.
    """
    cos = COSDictionary()
    cos.set_name(_TYPE, "Font")
    cos.set_name(_SUBTYPE, PDType1Font.SUB_TYPE)
    cos.set_name(_BASE_FONT, base_name)
    return cos


def _appearance_body(widget_cos: COSDictionary) -> bytes:
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    return n.create_input_stream().read()


def _appearance_resources(widget_cos: COSDictionary) -> COSDictionary:
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    stream = PDAppearanceStream(n)
    resources = stream.get_resources()
    assert resources is not None
    return resources.get_cos_object().get_dictionary_object(_FONT)


# ---------- AcroForm /DR /Font (tier 1) ----------


def test_resolve_font_picks_dr_font_for_custom_alias() -> None:
    """Custom alias declared in ``/DA`` resolves through AcroForm /DR/Font."""
    form = PDAcroForm()
    custom = _build_custom_font_dict("Times-Bold")
    dr = PDResources()
    dr.put(_FONT, COSName.get_pdf_name("Custom"), custom)
    form.set_default_resources(dr)

    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Custom 12 Tf 0 g")
    tf.set_value("hello")

    PDAppearanceGenerator().generate(tf)
    widget_cos = tf.get_widgets()[0].get_cos_object()
    fonts = _appearance_resources(widget_cos)
    assert isinstance(fonts, COSDictionary)
    # /Custom alias registered in the appearance /Resources/Font and points
    # at the exact COS object the form /DR carries (not a Standard 14 stub).
    custom_entry = fonts.get_dictionary_object(COSName.get_pdf_name("Custom"))
    assert custom_entry is custom


def test_resolve_font_emits_alias_in_tf_operator() -> None:
    """Generated content stream emits ``/<alias> <size> Tf`` not ``/F<n>``."""
    form = PDAcroForm()
    custom = _build_custom_font_dict("Times-Bold")
    dr = PDResources()
    dr.put(_FONT, COSName.get_pdf_name("MyFont"), custom)
    form.set_default_resources(dr)

    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/MyFont 11 Tf 0 g")
    tf.set_value("body")

    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf.get_widgets()[0].get_cos_object())
    assert b"/MyFont" in body
    assert b"Tf" in body
    # No auto-allocated F<n> slot took over the alias.
    assert b"/F0" not in body
    assert b"/F1" not in body


# ---------- Widget /AP /N /Resources /Font (tier 2) ----------


def test_resolve_font_picks_widget_ap_resources_when_dr_missing() -> None:
    """Custom alias missing from /DR — resolver walks widget /AP /N /Resources.

    Acrobat hoists per-widget fonts into the widget's appearance resources
    when a single field's widgets carry differing layouts. The lite-port
    must consult that bucket before falling back to Standard 14.
    """
    form = PDAcroForm()
    # AcroForm has /DR but no /Custom entry — forces the resolver to fall
    # through to the widget appearance bucket.
    form.set_default_resources(PDResources())

    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Custom 12 Tf 0 g")
    tf.set_value("widget-level")

    # Build the widget AP/N skeleton with a pre-existing /Resources/Font
    # carrying the custom font (mirrors what Acrobat would emit).
    widget_cos = tf.get_widgets()[0].get_cos_object()
    existing_n = COSStream()
    existing_n.set_item(_TYPE, COSName.get_pdf_name("XObject"))
    existing_n.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    existing_resources = COSDictionary()
    existing_font_dict = COSDictionary()
    custom = _build_custom_font_dict("Courier-Bold")
    existing_font_dict.set_item(COSName.get_pdf_name("Custom"), custom)
    existing_resources.set_item(_FONT, existing_font_dict)
    existing_n.set_item(_RESOURCES, existing_resources)
    existing_ap = COSDictionary()
    existing_ap.set_item(_N, existing_n)
    widget_cos.set_item(_AP, existing_ap)

    PDAppearanceGenerator().generate(tf)

    # After regeneration the widget AP/N is a *fresh* stream — but the
    # font dictionary registered under /Custom in the new appearance
    # /Resources must be the same COS object we seeded onto the widget.
    fonts = _appearance_resources(widget_cos)
    custom_entry = fonts.get_dictionary_object(COSName.get_pdf_name("Custom"))
    assert custom_entry is custom


# ---------- Page /Resources /Font (tier 3) ----------


def test_resolve_font_picks_page_resources_when_widget_ap_missing() -> None:
    """Custom alias resolves through the widget's parent page /Resources."""
    form = PDAcroForm()
    form.set_default_resources(PDResources())

    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/PageFont 12 Tf 0 g")
    tf.set_value("page-level")

    # Build a synthetic page dict with /Resources/Font/PageFont.
    page_cos = COSDictionary()
    page_cos.set_name(_TYPE, "Page")
    page_resources = COSDictionary()
    page_font_dict = COSDictionary()
    custom = _build_custom_font_dict("Helvetica-Bold")
    page_font_dict.set_item(COSName.get_pdf_name("PageFont"), custom)
    page_resources.set_item(_FONT, page_font_dict)
    page_cos.set_item(_RESOURCES, page_resources)

    # Wire the widget's /P back-pointer to the page.
    widget = tf.get_widgets()[0]
    widget.get_cos_object().set_item(COSName.get_pdf_name("P"), page_cos)

    PDAppearanceGenerator().generate(tf)

    fonts = _appearance_resources(widget.get_cos_object())
    page_entry = fonts.get_dictionary_object(COSName.get_pdf_name("PageFont"))
    assert page_entry is custom


# ---------- Lookup precedence (DR > widget > page) ----------


def test_resolve_font_dr_beats_widget_and_page() -> None:
    """When all three tiers carry the alias, the AcroForm /DR /Font wins."""
    form = PDAcroForm()
    dr_font = _build_custom_font_dict("Times-Bold")
    dr = PDResources()
    dr.put(_FONT, COSName.get_pdf_name("Shared"), dr_font)
    form.set_default_resources(dr)

    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Shared 12 Tf 0 g")
    tf.set_value("precedence")

    widget = tf.get_widgets()[0]
    widget_cos = widget.get_cos_object()

    # Seed widget /AP /N /Resources /Font /Shared with a *different* font.
    widget_font = _build_custom_font_dict("Courier-Bold")
    existing_n = COSStream()
    existing_n.set_item(_TYPE, COSName.get_pdf_name("XObject"))
    existing_n.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    existing_resources = COSDictionary()
    existing_font_dict = COSDictionary()
    existing_font_dict.set_item(COSName.get_pdf_name("Shared"), widget_font)
    existing_resources.set_item(_FONT, existing_font_dict)
    existing_n.set_item(_RESOURCES, existing_resources)
    existing_ap = COSDictionary()
    existing_ap.set_item(_N, existing_n)
    widget_cos.set_item(_AP, existing_ap)

    # Seed page /Resources /Font /Shared with a third font.
    page_font = _build_custom_font_dict("Helvetica-Bold")
    page_cos = COSDictionary()
    page_cos.set_name(_TYPE, "Page")
    page_resources = COSDictionary()
    page_font_dict = COSDictionary()
    page_font_dict.set_item(COSName.get_pdf_name("Shared"), page_font)
    page_resources.set_item(_FONT, page_font_dict)
    page_cos.set_item(_RESOURCES, page_resources)
    widget_cos.set_item(COSName.get_pdf_name("P"), page_cos)

    PDAppearanceGenerator().generate(tf)

    fonts = _appearance_resources(widget_cos)
    entry = fonts.get_dictionary_object(COSName.get_pdf_name("Shared"))
    assert entry is dr_font  # /DR wins
    assert entry is not widget_font
    assert entry is not page_font


def test_resolve_font_widget_beats_page() -> None:
    """When /DR is empty but both widget and page carry the alias, widget wins."""
    form = PDAcroForm()
    form.set_default_resources(PDResources())

    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Shared 12 Tf 0 g")
    tf.set_value("widget-wins")

    widget = tf.get_widgets()[0]
    widget_cos = widget.get_cos_object()

    widget_font = _build_custom_font_dict("Courier-Bold")
    existing_n = COSStream()
    existing_n.set_item(_TYPE, COSName.get_pdf_name("XObject"))
    existing_n.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    existing_resources = COSDictionary()
    existing_font_dict = COSDictionary()
    existing_font_dict.set_item(COSName.get_pdf_name("Shared"), widget_font)
    existing_resources.set_item(_FONT, existing_font_dict)
    existing_n.set_item(_RESOURCES, existing_resources)
    existing_ap = COSDictionary()
    existing_ap.set_item(_N, existing_n)
    widget_cos.set_item(_AP, existing_ap)

    page_font = _build_custom_font_dict("Helvetica-Bold")
    page_cos = COSDictionary()
    page_cos.set_name(_TYPE, "Page")
    page_resources = COSDictionary()
    page_font_dict = COSDictionary()
    page_font_dict.set_item(COSName.get_pdf_name("Shared"), page_font)
    page_resources.set_item(_FONT, page_font_dict)
    page_cos.set_item(_RESOURCES, page_resources)
    widget_cos.set_item(COSName.get_pdf_name("P"), page_cos)

    PDAppearanceGenerator().generate(tf)

    fonts = _appearance_resources(widget_cos)
    entry = fonts.get_dictionary_object(COSName.get_pdf_name("Shared"))
    assert entry is widget_font
    assert entry is not page_font


# ---------- Fallback (no /DR, no widget, no page) ----------


def test_resolve_font_falls_back_to_standard14_when_alias_unknown() -> None:
    """Alias resolves to Standard 14 face when none of the buckets carry it.

    With no /DR /Font entry, no widget /AP /N /Resources, and no page
    /Resources, the resolver collapses to ``_resolve_font(font_name)``,
    which maps unknown aliases to Helvetica (the safe fallback). The
    emitted alias is unchanged, but the registered font is a Standard
    14 face — the appearance is *renderable* even when the custom font
    is missing.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/UnknownFont 12 Tf 0 g")
    tf.set_value("fallback")

    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf.get_widgets()[0].get_cos_object())
    # Alias preserved in the emitted Tf operator (wave 1372).
    assert b"/UnknownFont" in body
    # Font registered under the alias is a Standard 14 face.
    fonts = _appearance_resources(tf.get_widgets()[0].get_cos_object())
    entry = fonts.get_dictionary_object(COSName.get_pdf_name("UnknownFont"))
    assert isinstance(entry, COSDictionary)
    # Standard 14 -> /BaseFont is one of the Helvetica family names.
    assert entry.get_name(_BASE_FONT) == Standard14Fonts.HELVETICA


def test_resolve_font_known_alias_uses_dr_not_alias_table() -> None:
    """``/Helv`` declared in /DR overrides the DA_FONT_ALIASES default.

    ``/Helv`` is in :attr:`PDAppearanceGenerator.DA_FONT_ALIASES` so the
    no-DR path would auto-create a Helvetica stub. When /DR carries an
    explicit ``/Helv`` entry pointing at a bold variant, the resolver
    honours that override — Acrobat does the same.
    """
    form = PDAcroForm()
    custom_helv = _build_custom_font_dict("Helvetica-Bold")
    dr = PDResources()
    dr.put(_FONT, COSName.get_pdf_name("Helv"), custom_helv)
    form.set_default_resources(dr)

    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 12 Tf 0 g")
    tf.set_value("override")

    PDAppearanceGenerator().generate(tf)
    fonts = _appearance_resources(tf.get_widgets()[0].get_cos_object())
    helv_entry = fonts.get_dictionary_object(COSName.get_pdf_name("Helv"))
    # /DR override wins — the appearance carries the bold variant we
    # registered, not the default Helvetica that DA_FONT_ALIASES maps to.
    assert helv_entry is custom_helv


# ---------- CID font (Type0 + descendant CIDFontType2) ----------


def test_resolve_font_picks_type0_cid_font_from_dr() -> None:
    """Custom-embedded Type0 (CID) font resolves through /DR.

    Type0 fonts carry their metrics on a descendant CIDFontType2 entry
    (``/DescendantFonts[0]``) and use a CMap to map character codes to
    CIDs. The lite-port resolver should accept any :class:`PDFont`
    subclass from /DR — including Type0 — and forward the COS object
    intact so the descendant font's ``/W`` widths and ``/CIDSystemInfo``
    travel along.
    """
    # Build a minimal Type0 font dict with a CIDFontType2 descendant.
    descendant_cos = COSDictionary()
    descendant_cos.set_name(_TYPE, "Font")
    descendant_cos.set_name(_SUBTYPE, "CIDFontType2")
    descendant_cos.set_name(_BASE_FONT, "EmbeddedCID")
    # /CIDSystemInfo — registry/ordering/supplement for Adobe-Japan1.
    cid_system_info = COSDictionary()
    cid_system_info.set_string(COSName.get_pdf_name("Registry"), "Adobe")
    cid_system_info.set_string(COSName.get_pdf_name("Ordering"), "Identity")
    cid_system_info.set_int(COSName.get_pdf_name("Supplement"), 0)
    descendant_cos.set_item(
        COSName.get_pdf_name("CIDSystemInfo"), cid_system_info
    )
    # Minimal /FontDescriptor (the embedder needs *some* descriptor for
    # downstream rendering, but the resolver itself only checks the dict
    # round-trips identically).
    descendant_cos.set_item(
        COSName.get_pdf_name("FontDescriptor"), COSDictionary()
    )
    # /W widths — character code 0x21 ('!') has width 500.
    widths_array = COSArray()
    widths_array.add(COSName.get_pdf_name("dummy"))  # not exercised here
    descendant_cos.set_item(COSName.get_pdf_name("W"), COSArray())

    type0_cos = COSDictionary()
    type0_cos.set_name(_TYPE, "Font")
    type0_cos.set_name(_SUBTYPE, PDType0Font.SUB_TYPE)
    type0_cos.set_name(_BASE_FONT, "EmbeddedCID")
    type0_cos.set_name(COSName.get_pdf_name("Encoding"), "Identity-H")
    descendants = COSArray()
    descendants.add(descendant_cos)
    type0_cos.set_item(COSName.get_pdf_name("DescendantFonts"), descendants)

    form = PDAcroForm()
    dr = PDResources()
    dr.put(_FONT, COSName.get_pdf_name("Embedded"), type0_cos)
    form.set_default_resources(dr)

    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Embedded 12 Tf 0 g")
    tf.set_value("cid-test")

    PDAppearanceGenerator().generate(tf)

    fonts = _appearance_resources(tf.get_widgets()[0].get_cos_object())
    embedded_entry = fonts.get_dictionary_object(
        COSName.get_pdf_name("Embedded")
    )
    # Same COS object — the Type0 font dict round-trips through /Resources
    # so the descendant CIDFontType2 (with its widths + CIDSystemInfo)
    # is still reachable from the appearance.
    assert embedded_entry is type0_cos
    # And the descendant chain is intact.
    descendants_after = embedded_entry.get_dictionary_object(
        COSName.get_pdf_name("DescendantFonts")
    )
    assert isinstance(descendants_after, COSArray)
    assert descendants_after.size() == 1
    assert descendants_after.get_object(0) is descendant_cos


# ---------- Direct unit tests of the lookup helpers ----------


def test_lookup_font_in_widget_appearance_returns_none_when_no_ap() -> None:
    """Helper returns ``None`` for widgets with no ``/AP`` entry."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    widget = tf.get_widgets()[0]
    result = PDAppearanceGenerator._lookup_font_in_widget_appearance(
        widget, COSName.get_pdf_name("Any")
    )
    assert result is None


def test_lookup_font_in_widget_appearance_walks_button_state_streams() -> None:
    """When ``/AP /N`` is a dict (button), the helper walks every state."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))

    widget = tf.get_widgets()[0]
    widget_cos = widget.get_cos_object()

    # Build /AP/N as a subdictionary with two state streams — the second
    # carries the custom font in its resources. The walker should find it.
    custom = _build_custom_font_dict("Times-Italic")
    state_a = COSStream()
    state_a.set_item(_TYPE, COSName.get_pdf_name("XObject"))
    state_a.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))

    state_b = COSStream()
    state_b.set_item(_TYPE, COSName.get_pdf_name("XObject"))
    state_b.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    resources_b = COSDictionary()
    font_b = COSDictionary()
    font_b.set_item(COSName.get_pdf_name("StateFont"), custom)
    resources_b.set_item(_FONT, font_b)
    state_b.set_item(_RESOURCES, resources_b)

    n_subdict = COSDictionary()
    n_subdict.set_item(COSName.get_pdf_name("Yes"), state_a)
    n_subdict.set_item(COSName.get_pdf_name("Off"), state_b)
    ap = COSDictionary()
    ap.set_item(_N, n_subdict)
    widget_cos.set_item(_AP, ap)

    result = PDAppearanceGenerator._lookup_font_in_widget_appearance(
        widget, COSName.get_pdf_name("StateFont")
    )
    assert isinstance(result, PDFont)
    assert result.get_cos_object() is custom


def test_lookup_font_in_widget_page_returns_none_without_page() -> None:
    """Helper returns ``None`` for widgets without ``/P``."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    widget = tf.get_widgets()[0]
    result = PDAppearanceGenerator._lookup_font_in_widget_page(
        widget, COSName.get_pdf_name("Any")
    )
    assert result is None


def test_lookup_font_in_widget_page_returns_none_without_page_resources() -> None:
    """Helper returns ``None`` for pages with no /Resources."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    widget = tf.get_widgets()[0]
    page_cos = COSDictionary()
    page_cos.set_name(_TYPE, "Page")
    widget.get_cos_object().set_item(COSName.get_pdf_name("P"), page_cos)
    result = PDAppearanceGenerator._lookup_font_in_widget_page(
        widget, COSName.get_pdf_name("Any")
    )
    assert result is None


# ---------- Smoke: choice (combo) path also picks DR font ----------


def test_combo_box_picks_dr_font_for_custom_alias() -> None:
    """The choice (combo) path also routes through the per-widget resolver."""
    from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox

    form = PDAcroForm()
    custom = _build_custom_font_dict("Times-Bold")
    dr = PDResources()
    dr.put(_FONT, COSName.get_pdf_name("ComboFont"), custom)
    form.set_default_resources(dr)

    combo = PDComboBox(form)
    combo.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    combo.get_cos_object().set_string(_DA, "/ComboFont 12 Tf 0 g")
    combo.set_value("selected")

    PDAppearanceGenerator().generate(combo)
    fonts = _appearance_resources(combo.get_widgets()[0].get_cos_object())
    entry = fonts.get_dictionary_object(COSName.get_pdf_name("ComboFont"))
    assert entry is custom


# ---------- Parametrised regression: every /DA-alias short key still resolves ----------


@pytest.mark.parametrize(
    "alias,canonical",
    [
        ("Helv", Standard14Fonts.HELVETICA),
        ("HeBo", Standard14Fonts.HELVETICA_BOLD),
        ("TiRo", "Times-Roman"),
        ("ZaDb", "ZapfDingbats"),
    ],
    ids=["helv", "hebo", "tiro", "zadb"],
)
def test_alias_no_dr_falls_back_to_standard14(
    alias: str, canonical: str
) -> None:
    """With no /DR entry, known short keys still map through DA_FONT_ALIASES."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, f"/{alias} 12 Tf 0 g")
    tf.set_value("alias-fallback")

    PDAppearanceGenerator().generate(tf)
    fonts = _appearance_resources(tf.get_widgets()[0].get_cos_object())
    entry = fonts.get_dictionary_object(COSName.get_pdf_name(alias))
    assert isinstance(entry, COSDictionary)
    assert entry.get_name(_BASE_FONT) == canonical
