"""Wave 1273 — pdmodel/interactive/annotation/PDAnnotationFreeText parity gaps.

Covers the custom appearance handler surface
(``set_custom_appearance_handler`` / ``get_custom_appearance_handler``)
and ``construct_appearances`` dispatch, mirroring the established
:class:`PDAnnotationUnderline` (Wave 270) and :class:`PDAnnotationLink`
(Wave 1267) patterns.
"""

from __future__ import annotations

from dataclasses import dataclass

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)


@dataclass
class _RecordingAppearanceHandler:
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


def test_subtype_constant_wave1273() -> None:
    assert PDAnnotationFreeText.SUB_TYPE == "FreeText"


def test_default_constructor_sets_subtype_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    assert annotation.get_subtype() == "FreeText"
    assert annotation.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_extends_markup_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    assert isinstance(annotation, PDAnnotationMarkup)


def test_constructor_with_dict_preserves_subtype_wave1273() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "FreeText")  # type: ignore[attr-defined]
    annotation = PDAnnotationFreeText(d)
    assert annotation.get_subtype() == "FreeText"
    assert annotation.get_cos_object() is d


# ---------- custom appearance handler ----------


def test_default_custom_appearance_handler_is_none_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    assert annotation.get_custom_appearance_handler() is None


def test_set_custom_appearance_handler_round_trips_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    assert annotation.get_custom_appearance_handler() is handler


def test_set_custom_appearance_handler_none_clears_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.set_custom_appearance_handler(None)
    assert annotation.get_custom_appearance_handler() is None


def test_construct_appearances_with_custom_handler_invokes_it_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.construct_appearances()
    assert handler.normal == 1
    assert handler.rollover == 1
    assert handler.down == 1


def test_construct_appearances_with_document_arg_invokes_handler_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.construct_appearances(None)
    assert handler.normal == 1


def test_construct_appearances_without_handler_is_noop_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    before_keys = set(annotation.get_cos_object().key_set())

    assert annotation.construct_appearances() is None
    assert annotation.construct_appearances(None) is None

    assert set(annotation.get_cos_object().key_set()) == before_keys


def test_clear_custom_appearance_handler_restores_noop_path_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.set_custom_appearance_handler(None)
    annotation.construct_appearances()
    assert handler.normal == 0
    assert handler.rollover == 0
    assert handler.down == 0


def test_handler_replacement_uses_latest_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    first = _RecordingAppearanceHandler()
    second = _RecordingAppearanceHandler()

    annotation.set_custom_appearance_handler(first)  # type: ignore[arg-type]
    annotation.set_custom_appearance_handler(second)  # type: ignore[arg-type]
    annotation.construct_appearances()

    assert first.normal == 0
    assert second.normal == 1


def test_construct_appearances_returns_none_with_handler_wave1273() -> None:
    annotation = PDAnnotationFreeText()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    assert annotation.construct_appearances() is None
    assert annotation.construct_appearances(None) is None
