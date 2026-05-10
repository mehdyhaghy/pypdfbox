"""Wave 273 round-out tests for :class:`PDActionMovie`.

Covers the new gap surfaces added in Wave 273 — ``has_operation``,
``clear_*`` helpers, and the ``is_empty`` / ``is_valid`` sanity predicates.
PDF 32000-1 §12.6.4.10 Table 209 — Movie action."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_movie import PDActionMovie

_OPERATION: COSName = COSName.get_pdf_name("Operation")
_ANNOTATION: COSName = COSName.get_pdf_name("Annotation")
_T: COSName = COSName.get_pdf_name("T")


# ---------- has_operation ----------


def test_has_operation_false_when_absent_wave273() -> None:
    """Bare action has no ``/Operation``; ``has_operation`` is ``False``."""
    action = PDActionMovie()
    assert action.has_operation() is False


def test_has_operation_true_when_explicit_play_wave273() -> None:
    """An explicit ``/Operation /Play`` registers as present even though
    it equals the spec default — distinguishes ``has_operation`` from
    :meth:`is_play`."""
    action = PDActionMovie()
    action.set_operation(PDActionMovie.OPERATION_PLAY)
    assert action.has_operation() is True
    assert action.is_play() is True


def test_has_operation_true_for_each_constant_wave273() -> None:
    """Every Table 209 constant flips ``has_operation`` ``True``."""
    for value in (
        PDActionMovie.OPERATION_PLAY,
        PDActionMovie.OPERATION_STOP,
        PDActionMovie.OPERATION_PAUSE,
        PDActionMovie.OPERATION_RESUME,
    ):
        action = PDActionMovie()
        action.set_operation(value)
        assert action.has_operation() is True


# ---------- clear_annotation ----------


def test_clear_annotation_removes_entry_wave273() -> None:
    action = PDActionMovie()
    action.set_annotation(COSDictionary())
    assert action.has_annotation() is True

    action.clear_annotation()
    assert action.has_annotation() is False
    assert action.get_cos_object().get_dictionary_object(_ANNOTATION) is None


def test_clear_annotation_idempotent_wave273() -> None:
    """Calling ``clear_annotation`` on an action with no ``/Annotation``
    is a no-op — must not raise."""
    action = PDActionMovie()
    action.clear_annotation()
    action.clear_annotation()
    assert action.has_annotation() is False


# ---------- clear_title ----------


def test_clear_title_removes_entry_wave273() -> None:
    action = PDActionMovie()
    action.set_t("Trailer")
    assert action.has_title() is True

    action.clear_title()
    assert action.has_title() is False
    assert action.get_cos_object().get_dictionary_object(_T) is None


def test_clear_title_idempotent_wave273() -> None:
    action = PDActionMovie()
    action.clear_title()
    action.clear_title()
    assert action.has_title() is False


# ---------- clear_operation ----------


def test_clear_operation_removes_entry_and_re_engages_default_wave273() -> None:
    """Clearing ``/Operation`` removes the entry and brings back the
    spec default ``"Play"`` via :meth:`get_effective_operation`."""
    action = PDActionMovie()
    action.set_operation(PDActionMovie.OPERATION_STOP)
    assert action.has_operation() is True

    action.clear_operation()
    assert action.has_operation() is False
    assert action.get_operation() is None
    assert action.get_effective_operation() == PDActionMovie.OPERATION_PLAY
    assert action.get_cos_object().get_dictionary_object(_OPERATION) is None


def test_clear_operation_idempotent_wave273() -> None:
    action = PDActionMovie()
    action.clear_operation()
    action.clear_operation()
    assert action.has_operation() is False


# ---------- is_empty ----------


def test_is_empty_true_when_no_target_wave273() -> None:
    """Bare Movie action has no ``/Annotation`` and no ``/T`` — empty."""
    action = PDActionMovie()
    assert action.is_empty() is True


def test_is_empty_false_when_only_annotation_present_wave273() -> None:
    action = PDActionMovie()
    action.set_annotation(COSDictionary())
    assert action.is_empty() is False


def test_is_empty_false_when_only_title_present_wave273() -> None:
    action = PDActionMovie()
    action.set_t("Intro")
    assert action.is_empty() is False


def test_is_empty_false_when_both_present_wave273() -> None:
    """Pathological PDFs may set both entries — the action still has a
    target so :meth:`is_empty` returns ``False``."""
    action = PDActionMovie()
    action.set_annotation(COSDictionary())
    action.set_t("Trailer")
    assert action.is_empty() is False


def test_is_empty_unaffected_by_operation_only_wave273() -> None:
    """``/Operation`` alone does not constitute a target — emptiness is
    keyed on /Annotation or /T per Table 209."""
    action = PDActionMovie()
    action.set_operation(PDActionMovie.OPERATION_PAUSE)
    assert action.is_empty() is True


# ---------- is_valid ----------


def test_is_valid_true_for_default_constructor_wave273() -> None:
    """A freshly-constructed action sets ``/S /Movie`` — :meth:`is_valid`
    must report ``True``."""
    action = PDActionMovie()
    assert action.is_valid() is True
    assert action.get_sub_type() == "Movie"


def test_is_valid_false_when_subtype_overridden_wave273() -> None:
    """Hand-rolling a malformed dict whose ``/S`` is not ``"Movie"``
    flips :meth:`is_valid` to ``False``."""
    action = PDActionMovie()
    action.set_sub_type("URI")
    assert action.is_valid() is False


def test_is_valid_round_trip_via_pdaction_create_wave273() -> None:
    """Round-tripping a Movie dict through :meth:`PDAction.create`
    preserves the ``/S /Movie`` subtype."""
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

    src = PDActionMovie()
    src.set_t("Intro")
    rebuilt = PDAction.create(src.get_cos_object())
    assert isinstance(rebuilt, PDActionMovie)
    assert rebuilt.is_valid() is True
