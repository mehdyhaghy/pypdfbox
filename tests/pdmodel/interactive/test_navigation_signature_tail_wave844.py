from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.digitalsignature.cos_filter_input_stream import (
    COSFilterInputStream,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_prop_build_data_dict import (
    PDPropBuildDataDict,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_certificate import (
    PDSeedValueCertificate,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem
from pypdfbox.pdmodel.interactive.pagenavigation import PDThread
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition import PDTransition
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition_direction import (
    PDTransitionDirection,
)

_C = COSName.C  # type: ignore[attr-defined]
_DI = COSName.get_pdf_name("Di")


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


def test_wave844_navigation_destination_and_outline_tail_branches() -> None:
    with pytest.raises(NotImplementedError):
        PDDestination().get_cos_object()

    named = PDNamedDestination(b"chapter-844")
    assert named.is_string_form() is True
    assert named.get_named_destination() == "chapter-844"

    assert PDPageFitHeightDestination(COSArray()).is_left_unset() is True
    assert PDPageFitWidthDestination(COSArray()).is_top_unset() is True
    assert PDPageFitRectangleDestination(COSArray()).is_left_unset() is True

    item = PDOutlineItem()
    item.get_cos_object().set_item(
        _C,
        COSArray([COSFloat(0.0), COSName.get_pdf_name("Bad"), COSFloat(1.0)]),
    )
    assert item.get_text_color() is None


def test_wave844_page_navigation_tail_branches() -> None:
    thread = PDThread()

    assert thread.__eq__(thread) is True

    transition = PDTransition()
    transition.get_cos_object().set_item(_DI, COSString("bad-direction"))

    assert transition.get_direction() == PDTransitionDirection.LEFT_TO_RIGHT


def test_wave844_signature_tail_branches() -> None:
    stream = COSFilterInputStream(_ShortNonSeekable(b"abc"), [10, 2])
    assert stream.read_all() == b""

    data = PDPropBuildDataDict()
    data.set_date("2026-05-09")
    assert str(data) == "PDPropBuildDataDict(date=2026-05-09)"

    cert = PDSeedValueCertificate()
    subject_dn = COSDictionary()
    subject_dn.set_item("CN", COSInteger.get(844))
    cert.get_cos_object().set_item("SubjectDN", COSArray([subject_dn]))

    assert cert.get_subject_dn() == [{"CN": ""}]
