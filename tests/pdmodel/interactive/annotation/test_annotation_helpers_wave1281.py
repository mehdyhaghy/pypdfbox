"""Tests for ``AnnotationFilter`` and ``PDExternalDataDictionary``."""

from __future__ import annotations

from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.interactive.annotation.annotation_filter import AnnotationFilter
from pypdfbox.pdmodel.interactive.annotation.pd_external_data_dictionary import (
    PDExternalDataDictionary,
)


def test_annotation_filter_is_abstract() -> None:
    class AcceptAll(AnnotationFilter):
        def accept(self, annotation):  # noqa: ANN001
            return True

    flt = AcceptAll()
    assert flt.accept(object()) is True


def test_pd_external_data_dictionary_default_type() -> None:
    ext = PDExternalDataDictionary()
    assert ext.get_type() == "ExData"
    assert ext.get_cos_object().get_name_as_string(COSName.TYPE) == "ExData"


def test_pd_external_data_dictionary_subtype_round_trip() -> None:
    ext = PDExternalDataDictionary()
    ext.set_subtype("Markup3D")
    assert ext.get_subtype() == "Markup3D"
