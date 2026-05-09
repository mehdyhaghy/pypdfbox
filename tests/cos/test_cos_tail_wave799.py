from __future__ import annotations

import pytest

from pypdfbox.cos import COSFloat


class _SliceContainsMinusOnly(str):
    def __getitem__(self, key: object) -> str:
        if isinstance(key, slice):
            return _AlwaysContainsMinus("tail")
        return super().__getitem__(key)

    def __contains__(self, item: object) -> bool:
        return False


class _AlwaysContainsMinus(str):
    def __contains__(self, item: object) -> bool:
        return item == "-"


class _PostStillContainsMinus(str):
    def count(self, sub: str, *args: object) -> int:
        if sub == "-":
            return 1
        return super().count(sub, *args)

    def split(self, sep: str | None = None, maxsplit: int = -1) -> list[str]:
        if sep == "-":
            return ["1", _AlwaysContainsMinus("2-3")]
        return super().split(sep, maxsplit)


def test_wave799_cos_float_returns_original_when_slice_reports_internal_minus() -> None:
    value = COSFloat(_SliceContainsMinusOnly("1.25"))

    assert value.float_value() == pytest.approx(1.25)
    assert value.get_original_form() == "1.25"


def test_wave799_cos_float_rejects_recombined_post_with_misplaced_minus() -> None:
    with pytest.raises(OSError, match="misplaced '-'"):
        COSFloat(_PostStillContainsMinus("1-2-3"))
