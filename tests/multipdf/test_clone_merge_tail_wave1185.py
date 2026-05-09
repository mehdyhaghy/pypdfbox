from __future__ import annotations

from pypdfbox.cos import COSArray
from tests.multipdf.test_clone_merge_tail_wave787 import _Wrap


def test_wave1185_wrap_get_cos_object_returns_base() -> None:
    base = COSArray()

    assert _Wrap(base).get_cos_object() is base
