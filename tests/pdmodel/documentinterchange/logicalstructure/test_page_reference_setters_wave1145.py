from __future__ import annotations

from pypdfbox.cos import COSArray
from tests.pdmodel.documentinterchange.logicalstructure.test_page_reference_setters_wave322 import (
    _NotPageWrapper,
)


def test_wave1145_not_page_wrapper_builds_array_cos_object() -> None:
    wrapper = _NotPageWrapper()

    assert isinstance(wrapper.get_cos_object(), COSArray)

