from __future__ import annotations

import pytest

from pypdfbox.pdfwriter.compress import CompressParameters


class _AlwaysEqual:
    def __eq__(self, other: object) -> bool:
        return True


def test_with_object_stream_size_validates_before_equality() -> None:
    params = CompressParameters(200)

    with pytest.raises(TypeError, match="must be an int"):
        params.with_object_stream_size(_AlwaysEqual())  # type: ignore[arg-type]


def test_with_object_stream_size_preserves_self_for_matching_int_subclass() -> None:
    class IntLike(int):
        pass

    params = CompressParameters(200)

    assert params.with_object_stream_size(IntLike(200)) is params


def test_constructor_rejects_object_with_only_int_conversion() -> None:
    class IntConvertible:
        def __int__(self) -> int:
            return 200

    with pytest.raises(TypeError, match="must be an int"):
        CompressParameters(IntConvertible())  # type: ignore[arg-type]


def test_equality_returns_not_implemented_for_foreign_equal_object() -> None:
    params = CompressParameters(200)

    assert params.__eq__(_AlwaysEqual()) is NotImplemented
