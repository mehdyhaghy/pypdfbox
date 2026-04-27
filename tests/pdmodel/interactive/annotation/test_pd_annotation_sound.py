from __future__ import annotations

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
