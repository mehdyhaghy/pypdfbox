from __future__ import annotations

from dataclasses import dataclass

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_sound import (
    PDAnnotationSound,
)
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream


def test_subtype_constant() -> None:
    assert PDAnnotationSound.SUB_TYPE == "Sound"


def test_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationSound()
    assert ann.get_subtype() == "Sound"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_extends_markup() -> None:
    ann = PDAnnotationSound()
    assert isinstance(ann, PDAnnotationMarkup)


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Sound")  # type: ignore[attr-defined]
    ann = PDAnnotationSound(d)
    assert ann.get_subtype() == "Sound"
    assert ann.get_cos_object() is d


def test_name_default_speaker() -> None:
    assert PDAnnotationSound().get_name() == "Speaker"


def test_name_round_trip() -> None:
    ann = PDAnnotationSound()
    ann.set_name(PDAnnotationSound.NAME_MIC)
    assert ann.get_name() == "Mic"


def test_name_constants() -> None:
    assert PDAnnotationSound.NAME_SPEAKER == "Speaker"
    assert PDAnnotationSound.NAME_MIC == "Mic"


def test_name_clear_falls_back_to_default() -> None:
    ann = PDAnnotationSound()
    ann.set_name("Mic")
    ann.set_name(None)
    assert ann.get_name() == "Speaker"


def test_sound_default_none() -> None:
    assert PDAnnotationSound().get_sound() is None


def test_sound_round_trip_with_cosstream() -> None:
    ann = PDAnnotationSound()
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("R"), 22050)
    ann.set_sound(stream)
    got = ann.get_sound()
    assert got is stream


def test_sound_round_trip_with_pd_sound_stream() -> None:
    ann = PDAnnotationSound()
    pds = PDSoundStream()
    pds.set_samples_per_second(44100)
    ann.set_sound(pds)
    got = ann.get_sound()
    assert isinstance(got, COSStream)
    assert got is pds.get_cos_object()


def test_sound_clear() -> None:
    ann = PDAnnotationSound()
    ann.set_sound(COSStream())
    ann.set_sound(None)
    assert ann.get_sound() is None


def test_set_sound_rejects_garbage() -> None:
    ann = PDAnnotationSound()
    with pytest.raises(TypeError):
        ann.set_sound("not a stream")  # type: ignore[arg-type]


def test_factory_routes_to_sound() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Sound")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationSound)


def test_markup_creation_date_inherited() -> None:
    ann = PDAnnotationSound()
    ann.set_creation_date("D:20260427120000Z")
    assert ann.get_creation_date() == "D:20260427120000Z"


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


def test_custom_appearance_handler_is_used() -> None:
    ann = PDAnnotationSound()
    handler = _RecordingAppearanceHandler()

    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    ann.construct_appearances()

    assert handler.normal == 1
    assert handler.rollover == 1
    assert handler.down == 1


def test_construct_appearances_default_path_is_noop() -> None:
    ann = PDAnnotationSound()
    before_keys = set(ann.get_cos_object().key_set())

    ann.construct_appearances()
    ann.construct_appearances(None)

    assert set(ann.get_cos_object().key_set()) == before_keys


def test_clear_custom_appearance_handler_restores_noop_path() -> None:
    ann = PDAnnotationSound()
    handler = _RecordingAppearanceHandler()
    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]
    ann.set_custom_appearance_handler(None)

    ann.construct_appearances()

    assert handler.normal == 0
    assert handler.rollover == 0
    assert handler.down == 0
