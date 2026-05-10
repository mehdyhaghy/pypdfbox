"""Wave 270 — pdmodel/interactive/annotation/PDAnnotationUnderline parity gaps.

Covers the custom appearance handler surface
(``set_custom_appearance_handler`` / ``get_custom_appearance_handler``)
and ``construct_appearances`` dispatch, mirroring the established
:class:`PDAnnotationHighlight` (Wave 268) and :class:`PDAnnotationStrikeout`
(Wave 269) patterns.
"""

from __future__ import annotations

from dataclasses import dataclass

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text_markup import (
    PDAnnotationTextMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_underline import (
    PDAnnotationUnderline,
)


@dataclass
class _RecordingAppearanceHandler:
    """Stand-in for a real ``PDAppearanceHandler`` — records call counts so
    tests can assert dispatch into the custom handler. Duck-typed (matches
    the same approach used by the highlight/strikeout wave tests)."""

    normal: int = 0
    rollover: int = 0
    down: int = 0

    def generate_normal_appearance(self) -> None:
        self.normal += 1

    def generate_rollover_appearance(self) -> None:
        self.rollover += 1

    def generate_down_appearance(self) -> None:
        self.down += 1

    def generate_appearance_streams(self) -> None:
        self.generate_normal_appearance()
        self.generate_rollover_appearance()
        self.generate_down_appearance()


# ---------- subtype + base wiring ----------


def test_subtype_constant_wave270() -> None:
    """Adding the appearance-handler surface must not change the subtype."""
    assert PDAnnotationUnderline.SUB_TYPE == "Underline"


def test_default_constructor_sets_subtype_wave270() -> None:
    annotation = PDAnnotationUnderline()
    assert annotation.get_subtype() == "Underline"
    assert annotation.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_extends_text_markup_wave270() -> None:
    """Inheritance chain stays Markup → TextMarkup → Underline."""
    annotation = PDAnnotationUnderline()
    assert isinstance(annotation, PDAnnotationTextMarkup)


def test_constructor_with_dict_preserves_subtype_wave270() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Underline")  # type: ignore[attr-defined]
    annotation = PDAnnotationUnderline(d)
    assert annotation.get_subtype() == "Underline"
    assert annotation.get_cos_object() is d


# ---------- custom appearance handler ----------


def test_default_custom_appearance_handler_is_none_wave270() -> None:
    annotation = PDAnnotationUnderline()
    assert annotation.get_custom_appearance_handler() is None


def test_set_custom_appearance_handler_round_trips_wave270() -> None:
    annotation = PDAnnotationUnderline()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    assert annotation.get_custom_appearance_handler() is handler


def test_set_custom_appearance_handler_none_clears_wave270() -> None:
    annotation = PDAnnotationUnderline()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.set_custom_appearance_handler(None)
    assert annotation.get_custom_appearance_handler() is None


def test_construct_appearances_with_custom_handler_invokes_it_wave270() -> None:
    annotation = PDAnnotationUnderline()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.construct_appearances()
    assert handler.normal == 1
    assert handler.rollover == 1
    assert handler.down == 1


def test_construct_appearances_with_document_arg_invokes_handler_wave270() -> None:
    """The single-arg ``constructAppearances(document)`` overload should
    dispatch through the custom handler the same way."""
    annotation = PDAnnotationUnderline()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.construct_appearances(None)
    assert handler.normal == 1


def test_construct_appearances_without_handler_is_noop_wave270() -> None:
    """The built-in ``PDUnderlineAppearanceHandler`` isn't ported yet, so
    the default path is the base no-op (returns ``None``, leaves the
    dictionary untouched)."""
    annotation = PDAnnotationUnderline()
    before_keys = set(annotation.get_cos_object().key_set())

    assert annotation.construct_appearances() is None
    assert annotation.construct_appearances(None) is None

    assert set(annotation.get_cos_object().key_set()) == before_keys


def test_clear_custom_appearance_handler_restores_noop_path_wave270() -> None:
    annotation = PDAnnotationUnderline()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.set_custom_appearance_handler(None)
    annotation.construct_appearances()
    assert handler.normal == 0
    assert handler.rollover == 0
    assert handler.down == 0


def test_handler_replacement_uses_latest_wave270() -> None:
    """Replacing a previously-wired handler should swap it: only the new
    handler must receive ``construct_appearances`` dispatch."""
    annotation = PDAnnotationUnderline()
    first = _RecordingAppearanceHandler()
    second = _RecordingAppearanceHandler()

    annotation.set_custom_appearance_handler(first)  # type: ignore[arg-type]
    annotation.set_custom_appearance_handler(second)  # type: ignore[arg-type]
    annotation.construct_appearances()

    assert first.normal == 0
    assert second.normal == 1


def test_construct_appearances_returns_none_with_handler_wave270() -> None:
    """Both the no-handler and the custom-handler branches return ``None``."""
    annotation = PDAnnotationUnderline()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    assert annotation.construct_appearances() is None
    assert annotation.construct_appearances(None) is None
