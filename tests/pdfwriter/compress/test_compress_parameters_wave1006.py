from __future__ import annotations

from typing import NoReturn

import pytest

from tests.pdfwriter.compress import test_compress_parameters_wave289 as wave289


def test_always_equal_helper_equality_path() -> None:
    assert wave289._AlwaysEqual() == object()


def test_local_int_convertible_helper_int_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def constructor_that_converts(value: object) -> NoReturn:
        int(value)
        raise TypeError("must be an int")

    monkeypatch.setattr(
        wave289,
        "CompressParameters",
        constructor_that_converts,
    )

    wave289.test_constructor_rejects_object_with_only_int_conversion()
