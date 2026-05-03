"""Wave 269 — pdmodel/interactive/annotation/PDAnnotationStrikeout parity gaps.

Covers the custom appearance handler surface
(``set_custom_appearance_handler`` / ``get_custom_appearance_handler``)
and ``construct_appearances`` dispatch, mirroring the established
:class:`PDAnnotationHighlight` pattern.
"""

from __future__ import annotations

from dataclasses import dataclass

from pypdfbox.pdmodel.interactive.annotation.pd_annotation_strikeout import (
    PDAnnotationStrikeout,
)


@dataclass
class _RecordingAppearanceHandler:
    """Stand-in for a real ``PDAppearanceHandler`` — records call counts so
    tests can assert dispatch into the custom handler. Duck-typed (matches
    the same approach used by the highlight wave268 tests)."""

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


def test_default_custom_appearance_handler_is_none_wave269() -> None:
    annotation = PDAnnotationStrikeout()
    assert annotation.get_custom_appearance_handler() is None


def test_set_custom_appearance_handler_round_trips_wave269() -> None:
    annotation = PDAnnotationStrikeout()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    assert annotation.get_custom_appearance_handler() is handler


def test_set_custom_appearance_handler_none_clears_wave269() -> None:
    annotation = PDAnnotationStrikeout()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.set_custom_appearance_handler(None)
    assert annotation.get_custom_appearance_handler() is None


def test_construct_appearances_with_custom_handler_invokes_it_wave269() -> None:
    annotation = PDAnnotationStrikeout()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.construct_appearances()
    assert handler.normal == 1
    assert handler.rollover == 1
    assert handler.down == 1


def test_construct_appearances_with_document_arg_invokes_handler_wave269() -> None:
    """The single-arg ``constructAppearances(document)`` overload should
    dispatch through the custom handler the same way."""
    annotation = PDAnnotationStrikeout()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.construct_appearances(None)
    assert handler.normal == 1


def test_construct_appearances_without_handler_is_noop_wave269() -> None:
    """The built-in ``PDStrikeoutAppearanceHandler`` isn't ported yet, so
    the default path is the base no-op (returns ``None``, leaves the
    dictionary untouched)."""
    annotation = PDAnnotationStrikeout()
    before_keys = set(annotation.get_cos_object().key_set())

    assert annotation.construct_appearances() is None
    assert annotation.construct_appearances(None) is None

    assert set(annotation.get_cos_object().key_set()) == before_keys


def test_clear_custom_appearance_handler_restores_noop_path_wave269() -> None:
    annotation = PDAnnotationStrikeout()
    handler = _RecordingAppearanceHandler()
    annotation.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    annotation.set_custom_appearance_handler(None)
    annotation.construct_appearances()
    assert handler.normal == 0


def test_strikeout_subtype_constant_wave269() -> None:
    """Sanity-check the spec capitalization: ``StrikeOut`` (not ``Strikeout``)."""
    assert PDAnnotationStrikeout.SUB_TYPE == "StrikeOut"
    annotation = PDAnnotationStrikeout()
    assert annotation.get_subtype() == "StrikeOut"
