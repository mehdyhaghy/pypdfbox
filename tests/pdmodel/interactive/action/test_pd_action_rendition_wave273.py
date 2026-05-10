"""Wave 273 round-out tests for :class:`PDActionRendition`.

Covers the new gap surfaces added in Wave 273:
``get_screen_annotation`` (typed ``/AN`` accessor),
``has_annotation`` / ``has_rendition`` presence helpers,
``clear_*`` helpers for ``/AN``, ``/OP``, ``/JS``, ``/R``, and the
``is_empty`` / ``is_valid`` sanity predicates.
PDF 32000-1 §12.6.4.13 Table 214 — Rendition action."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_rendition import (
    PDActionRendition,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
    PDAnnotationScreen,
)

_AN: COSName = COSName.get_pdf_name("AN")
_OP: COSName = COSName.get_pdf_name("OP")
_JS: COSName = COSName.get_pdf_name("JS")
_R: COSName = COSName.get_pdf_name("R")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_TYPE: COSName = COSName.get_pdf_name("Type")


# ---------- get_screen_annotation ----------


def test_get_screen_annotation_returns_none_when_absent_wave273() -> None:
    action = PDActionRendition()
    assert action.get_screen_annotation() is None


def test_get_screen_annotation_typed_wave273() -> None:
    """``/AN`` with ``/Subtype /Screen`` round-trips through the typed
    accessor as :class:`PDAnnotationScreen`."""
    action = PDActionRendition()
    screen = PDAnnotationScreen()
    action.set_annotation(screen)

    typed = action.get_screen_annotation()
    assert isinstance(typed, PDAnnotationScreen)
    # Same underlying dictionary identity preserved.
    assert typed.get_cos_object() is screen.get_cos_object()


def test_get_screen_annotation_returns_none_for_non_screen_subtype_wave273() -> None:
    """A non-Screen ``/AN`` (e.g. a Link annotation) must surface as
    ``None`` from the typed accessor — the untyped :meth:`get_annotation`
    is the right tool for malformed inputs."""
    action = PDActionRendition()
    annotation_dict = COSDictionary()
    annotation_dict.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    annotation_dict.set_item(_SUBTYPE, COSName.get_pdf_name("Link"))
    action.get_cos_object().set_item(_AN, annotation_dict)

    assert action.get_screen_annotation() is None
    # Untyped accessor still returns *something* (PDAnnotation subtype).
    assert action.get_annotation() is not None


# ---------- has_annotation ----------


def test_has_annotation_false_when_absent_wave273() -> None:
    action = PDActionRendition()
    assert action.has_annotation() is False


def test_has_annotation_true_when_dict_present_wave273() -> None:
    action = PDActionRendition()
    action.set_annotation(PDAnnotationScreen())
    assert action.has_annotation() is True


# ---------- has_rendition ----------


def test_has_rendition_false_when_absent_wave273() -> None:
    action = PDActionRendition()
    assert action.has_rendition() is False


def test_has_rendition_true_when_dict_present_wave273() -> None:
    action = PDActionRendition()
    rendition_dict = COSDictionary()
    rendition_dict.set_item(_TYPE, COSName.get_pdf_name("Rendition"))
    action.set_r(rendition_dict)
    assert action.has_rendition() is True


# ---------- clear_annotation ----------


def test_clear_annotation_removes_entry_wave273() -> None:
    action = PDActionRendition()
    action.set_annotation(PDAnnotationScreen())
    assert action.has_annotation() is True

    action.clear_annotation()
    assert action.has_annotation() is False
    assert action.get_cos_object().get_dictionary_object(_AN) is None


def test_clear_annotation_idempotent_wave273() -> None:
    action = PDActionRendition()
    action.clear_annotation()
    action.clear_annotation()
    assert action.has_annotation() is False


# ---------- clear_op ----------


def test_clear_op_removes_entry_wave273() -> None:
    action = PDActionRendition()
    action.set_op(PDActionRendition.OP_PAUSE)
    assert action.has_op() is True

    action.clear_op()
    assert action.has_op() is False
    assert action.get_operation() is None
    assert action.get_cos_object().get_dictionary_object(_OP) is None


def test_clear_op_idempotent_wave273() -> None:
    action = PDActionRendition()
    action.clear_op()
    action.clear_op()
    assert action.has_op() is False


# ---------- clear_js ----------


def test_clear_js_removes_entry_wave273() -> None:
    action = PDActionRendition()
    action.set_js("app.alert('hi')")
    assert action.has_js() is True

    action.clear_js()
    assert action.has_js() is False
    assert action.get_js() is None
    assert action.get_cos_object().get_dictionary_object(_JS) is None


def test_clear_js_idempotent_wave273() -> None:
    action = PDActionRendition()
    action.clear_js()
    action.clear_js()
    assert action.has_js() is False


# ---------- clear_rendition ----------


def test_clear_rendition_removes_entry_wave273() -> None:
    action = PDActionRendition()
    rendition_dict = COSDictionary()
    rendition_dict.set_item(_TYPE, COSName.get_pdf_name("Rendition"))
    action.set_r(rendition_dict)
    assert action.has_rendition() is True

    action.clear_rendition()
    assert action.has_rendition() is False
    assert action.get_cos_object().get_dictionary_object(_R) is None


def test_clear_rendition_idempotent_wave273() -> None:
    action = PDActionRendition()
    action.clear_rendition()
    action.clear_rendition()
    assert action.has_rendition() is False


# ---------- is_empty ----------


def test_is_empty_true_when_no_target_wave273() -> None:
    """Bare Rendition action has no ``/R`` and no ``/AN`` — empty."""
    action = PDActionRendition()
    assert action.is_empty() is True


def test_is_empty_false_when_only_rendition_present_wave273() -> None:
    action = PDActionRendition()
    rendition_dict = COSDictionary()
    rendition_dict.set_item(_TYPE, COSName.get_pdf_name("Rendition"))
    action.set_r(rendition_dict)
    assert action.is_empty() is False


def test_is_empty_false_when_only_annotation_present_wave273() -> None:
    action = PDActionRendition()
    action.set_annotation(PDAnnotationScreen())
    assert action.is_empty() is False


def test_is_empty_false_when_both_present_wave273() -> None:
    action = PDActionRendition()
    action.set_annotation(PDAnnotationScreen())
    rendition_dict = COSDictionary()
    rendition_dict.set_item(_TYPE, COSName.get_pdf_name("Rendition"))
    action.set_r(rendition_dict)
    assert action.is_empty() is False


def test_is_empty_unaffected_by_op_or_js_only_wave273() -> None:
    """``/OP`` and ``/JS`` are operation modifiers — they don't satisfy
    the action's target requirement so :meth:`is_empty` stays ``True``."""
    action = PDActionRendition()
    action.set_op(PDActionRendition.OP_PLAY)
    action.set_js("noop;")
    assert action.is_empty() is True


# ---------- is_valid ----------


def test_is_valid_true_for_default_constructor_wave273() -> None:
    """A freshly-constructed action sets ``/S /Rendition``."""
    action = PDActionRendition()
    assert action.is_valid() is True
    assert action.get_sub_type() == "Rendition"


def test_is_valid_false_when_subtype_overridden_wave273() -> None:
    action = PDActionRendition()
    action.set_sub_type("Movie")
    assert action.is_valid() is False


def test_is_valid_round_trip_via_pdaction_create_wave273() -> None:
    """Round-tripping a Rendition dict through :meth:`PDAction.create`
    preserves the ``/S /Rendition`` subtype."""
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

    src = PDActionRendition()
    src.set_op(PDActionRendition.OP_PLAY)
    rebuilt = PDAction.create(src.get_cos_object())
    assert isinstance(rebuilt, PDActionRendition)
    assert rebuilt.is_valid() is True
