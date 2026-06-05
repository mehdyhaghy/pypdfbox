"""Wave 1395 — residual coverage stragglers across ``pdmodel``.

Bundles single-line / two-line uncovered branches from a wide spread of
files. Each test is a small behavioural assertion targeting a specific
missing line per the wave-1395 coverage audit. Files / lines covered:

* ``pdmodel/interactive/annotation/pd_annotation_printer_mark.py``
  lines 30, 40 — no-arg constructor sets /Subtype + set_mark_name
  writes /MN.
* ``pdmodel/interactive/annotation/pd_annotation_file_attachment.py``
  line 136 — ``set_attachement_name`` (typo'd) alias delegates.
* ``pdmodel/encryption/public_key_protection_policy.py`` line 62 —
  legacy ``get_recipients_number`` spelling.
* ``pdmodel/interactive/form/pd_button.py`` lines 178-179 —
  ``_check_value_if_known`` accepts a stringified valid index when
  ``/Opt`` (export values) is present.
* ``pdmodel/interactive/form/pd_choice.py`` line 302 —
  ``_selected_option_indices_for_values`` returns ``[]`` when the value
  isn't in the export list on an editable combo.
* ``pdmodel/graphics/color/pd_indexed.py`` line 94 — ``PDIndexed.create``
  raises when the base color space has no COS form.
* ``pdmodel/font/pd_simple_font.py`` lines 489-490 — ``is_font_symbolic``
  returns ``True`` for Standard14 Symbol / ZapfDingbats fonts (forced by
  stubbing ``get_symbolic_flag`` to ``None``).
* ``pdmodel/graphics/shading/pd_shading_type6.py`` line 259 —
  ``parse_patches`` returns ``[]`` when backing COS is not a stream.
* ``pdmodel/graphics/shading/pd_shading_type7.py`` line 257 —
  ``parse_patches`` returns ``[]`` when backing COS is not a stream.
* ``pdmodel/common/cos_array_list.py`` lines 222-223 —
  ``remove_all`` rejects filtered lists.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)

# ---------- PDAnnotationPrinterMark ----------


def test_printer_mark_no_arg_constructor_sets_subtype() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_printer_mark import (
        PDAnnotationPrinterMark,
    )

    ann = PDAnnotationPrinterMark()
    assert ann.get_subtype() == PDAnnotationPrinterMark.SUB_TYPE


def test_printer_mark_set_mark_name_writes_mn_entry() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_printer_mark import (
        PDAnnotationPrinterMark,
    )

    ann = PDAnnotationPrinterMark()
    ann.set_mark_name("RegistrationTarget")
    assert ann.get_mark_name() == "RegistrationTarget"


# ---------- PDAnnotationFileAttachment.set_attachement_name (typo'd) ----------


def test_file_attachment_misspelled_setter_delegates() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
        PDAnnotationFileAttachment,
    )

    ann = PDAnnotationFileAttachment()
    ann.set_attachement_name("Paperclip")
    assert ann.get_attachment_name() == "Paperclip"
    # And the canonical setter still works.
    ann.set_attachement_name(None)
    # After None the spec default kicks back in.
    assert ann.get_attachment_name() == PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN


# ---------- PublicKeyProtectionPolicy.get_recipients_number ----------


def test_public_key_protection_policy_legacy_get_recipients_number_alias() -> None:
    from pypdfbox.pdmodel.encryption import PublicKeyProtectionPolicy

    policy = PublicKeyProtectionPolicy()
    assert policy.get_recipients_number() == 0
    assert policy.get_recipients_number() == policy.get_number_of_recipients()


# ---------- PDButton._check_value_if_known with /Opt index ----------


def test_pd_button_accepts_string_index_when_export_values_present() -> None:
    """Index-form selection routes through ``set_value_by_index`` (upstream
    ``PDButton.setValue(int)``, which validates the range itself and writes
    ``str(index)`` as ``/V``); the strict ``check_value`` (wave 1487 —
    upstream ``checkValue``) rejects any name outside on-values/Off, with no
    index parsing of its own (the permissive ``_check_value_if_known``
    scaffold that short-circuited on a parsable index is gone)."""
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
    from pypdfbox.pdmodel.interactive.form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_button import PDButton

    _AP = COSName.get_pdf_name("AP")
    _N = COSName.get_pdf_name("N")
    _KIDS = COSName.get_pdf_name("Kids")
    _OPT = COSName.get_pdf_name("Opt")

    # Widget with on-state "Yes" so on_values is non-empty.
    normal = COSDictionary()
    normal.set_item(COSName.get_pdf_name("Yes"), COSDictionary())
    ap = COSDictionary()
    ap.set_item(_N, normal)
    widget = PDAnnotationWidget()
    widget.get_cos_object().set_item(_AP, ap)

    form = PDAcroForm()
    button = PDButton(form)
    kids = COSArray()
    kids.add(widget.get_cos_object())
    button.get_cos_object().set_item(_KIDS, kids)
    # /Opt with two export values
    opt = COSArray()
    opt.add(COSString("first"))
    opt.add(COSString("second"))
    button.get_cos_object().set_item(_OPT, opt)
    # Verify export_values populated.
    assert button.get_export_values() == ["first", "second"]

    # 1 is a valid index into export_values (size 2) — must not raise, and
    # writes the str(index) token as /V (upstream setValue(int) contract).
    button.set_value_by_index(1)
    assert button.get_value() == "second"

    # An out-of-range index is rejected by set_value_by_index itself.
    with pytest.raises(ValueError, match="not a valid index"):
        button.set_value_by_index(9)

    # A non-on-state, non-Off name is rejected by the strict check_value —
    # including a numeric string: checkValue does no index parsing.
    with pytest.raises(ValueError, match="not a valid option"):
        button.set_value("bogus")
    with pytest.raises(ValueError, match="not a valid option"):
        button.set_value("9")


# ---------- PDChoice editable-combo escape branch ----------


def test_pd_combo_box_edit_mode_returns_empty_indices_for_free_text() -> None:
    """Line 302 — ``_selected_option_indices_for_values`` short-circuits
    with ``[]`` when the value isn't in ``/Opt`` *and* the field is an
    editable combo (``PDComboBox`` with FLAG_EDIT). Mirrors upstream's
    "free-typed text bypasses index lookup" behaviour."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox

    form = PDAcroForm()
    field = PDComboBox(form)
    # Set /Opt with two export values.
    opt = COSArray()
    opt.add(COSString("alpha"))
    opt.add(COSString("beta"))
    field.get_cos_object().set_item(COSName.get_pdf_name("Opt"), opt)
    # Make it editable (combo flag is auto-set by PDComboBox constructor).
    field.set_edit(True)
    assert field.is_combo()
    assert field.is_edit()

    # Free-typed value not in /Opt — must return empty list, not raise.
    result = field._selected_option_indices_for_values(["gamma"])  # noqa: SLF001
    assert result == []


# ---------- PDIndexed.create with a base whose get_cos_object() is None ----------


def test_pd_indexed_create_rejects_base_with_no_cos() -> None:
    """Line 94 — ``PDIndexed.create`` raises ``ValueError`` when the
    base color space's ``get_cos_object()`` returns ``None``.

    Reaches the branch by patching ``PDDeviceGray.INSTANCE.get_cos_object``
    to temporarily return ``None`` (a synthetic in-flight color space)."""
    from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    base = PDDeviceGray.INSTANCE
    with (
        patch.object(base, "get_cos_object", return_value=None),
        pytest.raises(ValueError, match="base color space has no COS form"),
    ):
        PDIndexed.create(base, 0, b"\x00")


# ---------- PDSimpleFont.is_font_symbolic Standard14 Symbol arm ----------


def test_pd_simple_font_is_symbolic_for_standard14_symbol() -> None:
    """Lines 489-490 — the Standard14 Symbol / ZapfDingbats arm of
    ``is_font_symbolic``. Reached by stubbing ``get_symbolic_flag``
    to return ``None`` (the "no descriptor" tri-state) so the
    Standard14-name fallback fires."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    fd = COSDictionary()
    fd.set_name(COSName.get_pdf_name("BaseFont"), "Symbol")
    font = PDType1Font(fd)
    with patch.object(font, "get_symbolic_flag", return_value=None):
        assert font.is_font_symbolic() is True


def test_pd_simple_font_is_symbolic_for_standard14_zapfdingbats() -> None:
    """Same Standard14 dispatch for ZapfDingbats."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    fd = COSDictionary()
    fd.set_name(COSName.get_pdf_name("BaseFont"), "ZapfDingbats")
    font = PDType1Font(fd)
    with patch.object(font, "get_symbolic_flag", return_value=None):
        assert font.is_font_symbolic() is True


def test_pd_simple_font_is_symbolic_false_for_standard14_helvetica() -> None:
    """A Standard14 font that is NOT Symbol / ZapfDingbats — same arm
    returns ``False`` via the ``in (SYMBOL, ZAPF_DINGBATS)`` check."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    fd = COSDictionary()
    fd.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font = PDType1Font(fd)
    with patch.object(font, "get_symbolic_flag", return_value=None):
        assert font.is_font_symbolic() is False


# ---------- PDShadingType6 / PDShadingType7 non-stream COS guard ----------


def test_pd_shading_type6_parse_patches_returns_empty_for_non_stream() -> None:
    """Line 259 — ``parse_patches`` returns ``[]`` when the backing COS
    object is not a stream (e.g. a bare dictionary)."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type6 import PDShadingType6

    cos = COSDictionary()
    cos.set_int(COSName.get_pdf_name("ShadingType"), 6)
    shading = PDShadingType6(cos)
    assert shading.parse_patches() == []


def test_pd_shading_type7_parse_patches_returns_empty_for_non_stream() -> None:
    """Line 257 — same guard on PDShadingType7."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type7 import PDShadingType7

    cos = COSDictionary()
    cos.set_int(COSName.get_pdf_name("ShadingType"), 7)
    shading = PDShadingType7(cos)
    assert shading.parse_patches() == []


# ---------- COSArrayList.remove_all on a filtered backing array ----------


def test_cos_array_list_remove_all_rejects_filtered_view() -> None:
    """Lines 222-223 — ``remove_all`` raises ``NotImplementedError`` on a
    filtered (size-mismatched) list, mirroring upstream's
    ``COSArrayList`` filtered-list semantics."""
    from pypdfbox.pdmodel.common.cos_array_list import COSArrayList

    cos = COSArray()
    cos.add(COSInteger.get(1))
    cos.add(COSInteger.get(2))
    cos.add(COSInteger.get(3))

    # Filtered: actual_list size != cos_array size, so _is_filtered is
    # auto-set by the (actual_list, cos_array) overload.
    lst = COSArrayList([1, 2], cos)
    assert lst._is_filtered is True  # noqa: SLF001

    with pytest.raises(NotImplementedError, match="filtered List"):
        lst.remove_all([1])
