from __future__ import annotations

import types

import pytest

from pypdfbox.cos import COSArray, COSBoolean, COSInteger, COSNull

from . import test_content_stream_writer as writer_tests


def _local_class(function: object, name: str) -> type:
    code = function.__code__  # type: ignore[attr-defined]
    for const in code.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == name:
            namespace: dict[str, object] = {}
            exec(const, {"__name__": writer_tests.__name__}, namespace)
            return type(
                name,
                (),
                {
                    k: v
                    for k, v in namespace.items()
                    if k == "__init__" or not k.startswith("__")
                },
            )
    raise AssertionError(f"{name} not found")


def test_wave867_tokens_equal_covers_array_size_boolean_and_null_paths() -> None:
    one = COSArray([COSInteger.get(1)])
    empty = COSArray()

    assert writer_tests._tokens_equal(one, empty) is False
    assert writer_tests._tokens_equal(COSBoolean.TRUE, COSBoolean.TRUE) is True
    assert writer_tests._tokens_equal(COSBoolean.TRUE, COSBoolean.FALSE) is False
    assert writer_tests._tokens_equal(COSNull.NULL, COSNull.NULL) is True
    assert writer_tests._tokens_equal(object(), object()) is False


def test_wave867_random_access_raw_write_length_slice_branch_runs() -> None:
    raw_write_cls = _local_class(
        writer_tests.test_random_access_write_only_sink_works_end_to_end,
        "_RawWrite",
    )
    sink = raw_write_cls()

    sink.write_bytes(b"abcdef", 2, 3)

    assert bytes(sink.buf) == b"cde"


def test_wave867_inline_image_raw_write_length_slice_branch_runs() -> None:
    raw_write_cls = _local_class(
        writer_tests.test_random_access_write_inline_image_data,
        "_RawWrite",
    )
    sink = raw_write_cls()

    sink.write_bytes(memoryview(b"012345"), 1, 4)

    assert bytes(sink.buf) == b"1234"


def test_wave867_local_class_lookup_reports_missing_helper() -> None:
    with pytest.raises(AssertionError, match="_Missing"):
        _local_class(writer_tests.test_random_access_write_inline_image_data, "_Missing")
