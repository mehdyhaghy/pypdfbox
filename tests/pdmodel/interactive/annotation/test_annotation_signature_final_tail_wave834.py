from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import PDAnnotationInk
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
    PDAnnotationScreen,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_sound import (
    PDAnnotationSound,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationCircle,
)
from pypdfbox.pdmodel.interactive.digitalsignature.cos_filter_input_stream import (
    COSFilterInputStream,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_prop_build import PDPropBuild
from pypdfbox.pdmodel.interactive.digitalsignature.pd_prop_build_data_dict import (
    PDPropBuildDataDict,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_certificate import (
    PDSeedValueCertificate,
)

_INK_LIST = COSName.get_pdf_name("InkList")
_MK = COSName.get_pdf_name("MK")
_SOUND = COSName.get_pdf_name("Sound")


class _SoundWrapper:
    def __init__(self, cos: object) -> None:
        self._cos = cos

    def get_cos_object(self) -> object:
        return self._cos


class _ShortNonSeekable:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._offset
        start = self._offset
        self._offset = min(len(self._data), self._offset + size)
        return self._data[start : self._offset]

    def close(self) -> None:
        self._offset = len(self._data)


def test_sound_annotation_accepts_stream_wrapper_and_rejects_dict_wrapper() -> None:
    annotation = PDAnnotationSound()
    stream = COSStream()

    annotation.set_sound(_SoundWrapper(stream))  # type: ignore[arg-type]

    assert annotation.get_sound() is stream
    assert annotation.has_sound() is True

    with pytest.raises(TypeError, match="COSStream-backed"):
        annotation.set_sound(_SoundWrapper(COSDictionary()))  # type: ignore[arg-type]

    assert annotation.get_cos_object().get_dictionary_object(_SOUND) is stream


def test_screen_appearance_characteristics_accepts_raw_dictionary() -> None:
    annotation = PDAnnotationScreen()
    appearance = COSDictionary()

    annotation.set_appearance_characteristics(appearance)

    assert annotation.get_cos_object().get_dictionary_object(_MK) is appearance


def test_circle_constructor_and_malformed_ink_list_tails() -> None:
    with pytest.raises(TypeError, match="PDAnnotationCircle requires"):
        PDAnnotationCircle(COSString("not-a-dictionary"))  # type: ignore[arg-type]

    ink = PDAnnotationInk()
    ink.get_cos_object().set_item(_INK_LIST, COSString("not-an-array"))

    assert ink.has_ink_list() is True
    assert ink.is_empty() is True
    assert ink.get_ink_paths() == []


def test_seed_value_certificate_subject_dn_non_string_values_become_empty() -> None:
    certificate = PDSeedValueCertificate()
    subject_dn = COSDictionary()
    subject_dn.set_item("CN", COSInteger.get(834))
    subject_dns = COSArray([subject_dn])

    certificate.get_cos_object().set_item("SubjectDN", subject_dns)

    assert certificate.get_subject_dn() == [{"CN": ""}]


def test_prop_build_data_date_summary_and_parent_filter_summary() -> None:
    data = PDPropBuildDataDict()
    data.set_date("2026-05-09")
    build = PDPropBuild()

    build.set_pd_prop_build_filter(data)

    assert str(data) == "PDPropBuildDataDict(date=2026-05-09)"
    assert str(build) == "PDPropBuild(Filter)"


def test_cos_filter_non_seekable_skip_stops_when_source_ends_before_range() -> None:
    stream = COSFilterInputStream(_ShortNonSeekable(b"abc"), [10, 2])

    assert stream.read_all() == b""
