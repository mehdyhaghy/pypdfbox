"""Wave 268 round-out — fill in the cold appearance-handler surface on
:class:`PDAnnotationHighlight` (``set_custom_appearance_handler`` /
``get_custom_appearance_handler`` / ``construct_appearances``) so it
matches the parity surface upstream and the pattern already wired on
:class:`PDAnnotationFileAttachment`.
"""

from __future__ import annotations

from dataclasses import dataclass

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_highlight import (
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text_markup import (
    PDAnnotationTextMarkup,
)

# ---------- subtype + base wiring ----------


def test_subtype_constant_unchanged_wave268() -> None:
    """Adding the appearance-handler surface must not change the subtype."""
    assert PDAnnotationHighlight.SUB_TYPE == "Highlight"


def test_default_constructor_sets_subtype_wave268() -> None:
    ann = PDAnnotationHighlight()
    assert ann.get_subtype() == "Highlight"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_extends_text_markup_wave268() -> None:
    """Inheritance chain stays Markup → TextMarkup → Highlight."""
    ann = PDAnnotationHighlight()
    assert isinstance(ann, PDAnnotationTextMarkup)


def test_constructor_with_dict_preserves_subtype_wave268() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Highlight")  # type: ignore[attr-defined]
    ann = PDAnnotationHighlight(d)
    assert ann.get_subtype() == "Highlight"
    assert ann.get_cos_object() is d


# ---------- custom appearance handler ----------


@dataclass
class _RecordingAppearanceHandler:
    """Stand-in for a real ``PDAppearanceHandler`` — records call counts so
    tests can assert dispatch into the custom handler."""

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


def test_get_custom_appearance_handler_default_none_wave268() -> None:
    """Fresh annotation has no custom handler wired."""
    ann = PDAnnotationHighlight()
    assert ann.get_custom_appearance_handler() is None


def test_set_then_get_custom_appearance_handler_wave268() -> None:
    ann = PDAnnotationHighlight()
    handler = _RecordingAppearanceHandler()

    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    assert ann.get_custom_appearance_handler() is handler


def test_set_custom_appearance_handler_none_clears_wave268() -> None:
    ann = PDAnnotationHighlight()
    handler = _RecordingAppearanceHandler()
    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    ann.set_custom_appearance_handler(None)
    assert ann.get_custom_appearance_handler() is None


def test_custom_appearance_handler_is_used_wave268() -> None:
    ann = PDAnnotationHighlight()
    handler = _RecordingAppearanceHandler()

    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    ann.construct_appearances()

    assert handler.normal == 1
    assert handler.rollover == 1
    assert handler.down == 1


def test_custom_appearance_handler_called_with_document_argument_wave268() -> None:
    ann = PDAnnotationHighlight()
    handler = _RecordingAppearanceHandler()

    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    ann.construct_appearances(None)

    assert handler.normal == 1


def test_construct_appearances_default_path_is_noop_wave268() -> None:
    """Without a custom handler the dictionary is left untouched (the
    default ``PDHighlightAppearanceHandler`` is not ported yet, so the
    default path falls through to the base no-op)."""
    ann = PDAnnotationHighlight()
    before_keys = set(ann.get_cos_object().key_set())

    ann.construct_appearances()
    ann.construct_appearances(None)

    assert set(ann.get_cos_object().key_set()) == before_keys


def test_clear_custom_appearance_handler_restores_noop_path_wave268() -> None:
    ann = PDAnnotationHighlight()
    handler = _RecordingAppearanceHandler()
    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    ann.set_custom_appearance_handler(None)

    ann.construct_appearances()

    assert handler.normal == 0
    assert handler.rollover == 0
    assert handler.down == 0
