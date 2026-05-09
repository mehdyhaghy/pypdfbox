from __future__ import annotations

from pypdfbox.cos import COSDictionary
from tests.multipdf.test_pdf_merger_utility_wave489 import _Root


def test_wave1009_root_default_constructor_exposes_cos_dictionary() -> None:
    root = _Root()

    assert isinstance(root.get_cos_object(), COSDictionary)
