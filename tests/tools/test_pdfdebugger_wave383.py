"""Wave 383 coverage for pdfdebugger formatting and JSON helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.tools import pdfdebugger


class _BrokenString(COSString):
    def get_string(self) -> str:
        raise UnicodeDecodeError("pdfdoc", b"\xff", 0, 1, "bad byte")


class _UnknownCOS(COSBase):
    def accept(self, visitor: object) -> Any:
        return None

    def __repr__(self) -> str:
        return "<unknown-cos>"


class _FakeSummaryDoc:
    def get_version(self) -> float:
        return 1.7

    def get_number_of_pages(self) -> int:
        return 0

    def is_encrypted(self) -> bool:
        return False

    def get_document(self) -> _FakeSummaryCosDoc:
        return _FakeSummaryCosDoc()


class _FakeSummaryCosDoc:
    def get_trailer(self) -> None:
        return None

    def get_catalog(self) -> None:
        return None

    def get_version(self) -> float:
        return 1.4

    def get_objects(self) -> list[object]:
        return []


class _BytesContext:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self) -> _BytesContext:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        if limit < 0:
            return self._data
        return self._data[:limit]


class _FallbackPreviewStream:
    def create_input_stream(self) -> _BytesContext:
        raise OSError("decode failed")

    def create_raw_input_stream(self) -> _BytesContext:
        return _BytesContext(b"raw-preview")


class _NoPreviewStream:
    def create_input_stream(self) -> _BytesContext:
        raise OSError("decode failed")

    def create_raw_input_stream(self) -> _BytesContext:
        raise OSError("raw failed")


def test_wave383_scalar_formatting_and_json_fallbacks() -> None:
    broken = _BrokenString(b"\xff")

    assert pdfdebugger._fmt_simple(COSBoolean.TRUE) == "true"
    assert pdfdebugger._fmt_simple(COSBoolean.FALSE) == "false"
    assert pdfdebugger._fmt_simple(COSFloat("1.25")) == "1.25"
    assert pdfdebugger._fmt_simple(COSNull.NULL) == "null"
    assert pdfdebugger._fmt_simple(broken) == "<ff>"

    assert pdfdebugger._node_to_jsonable(
        broken,
        visited=set(),
        depth=0,
        follow_refs=False,
        max_depth=4,
    ) == {"hex": "ff"}
    assert pdfdebugger._node_to_jsonable(
        _UnknownCOS(),
        visited=set(),
        depth=0,
        follow_refs=False,
        max_depth=4,
    ) == "<unknown-cos>"


def test_wave383_format_node_handles_unresolved_refs_arrays_and_fallback() -> None:
    out: list[str] = []
    pdfdebugger._format_node(None, 0, out, visited=set())
    assert out == ["<unresolved>"]

    out = []
    pdfdebugger._format_node(
        COSObject(12, 0),
        0,
        out,
        visited=set(),
        follow_refs=True,
    )
    assert out == ["12 0 R -> <unresolved>"]

    out = []
    pdfdebugger._format_node(
        COSObject(13, 0, resolved=COSInteger.get(9)),
        0,
        out,
        visited=set(),
        follow_refs=True,
    )
    assert out == ["13 0 R -> 9"]

    long_array = COSArray(COSInteger.get(i) for i in range(13))
    out = []
    pdfdebugger._format_node(long_array, 0, out, visited=set())
    assert out[0] == "["
    assert out[-1] == "]"
    assert "  12" in out

    out = []
    pdfdebugger._format_node(_UnknownCOS(), 0, out, visited=set())
    assert out == ["<unknown-cos>"]


def test_wave383_node_to_jsonable_follows_indirect_refs() -> None:
    dictionary = COSDictionary()
    dictionary.set_item("Name", COSName.get_pdf_name("Child"))
    ref = COSObject(4, 2, resolved=dictionary)

    assert pdfdebugger._node_to_jsonable(
        ref,
        visited=set(),
        depth=0,
        follow_refs=False,
        max_depth=4,
    ) == {
        "ref": "4 2 R",
        "object_number": 4,
        "generation_number": 2,
    }
    assert pdfdebugger._node_to_jsonable(
        ref,
        visited=set(),
        depth=0,
        follow_refs=True,
        max_depth=4,
    ) == {"ref": "4 2 R", "value": {"Name": "/Child"}}


def test_wave383_stream_preview_falls_back_to_raw_and_empty() -> None:
    assert pdfdebugger._stream_preview(_FallbackPreviewStream()) == (
        b"raw-preview",
        "raw",
    )
    assert pdfdebugger._stream_preview(_NoPreviewStream()) == (b"", "raw")


def test_wave383_summary_trailer_catalog_and_emit_edges(
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdfdebugger._print_summary(_FakeSummaryDoc(), Path("missing-trailer.pdf"))  # type: ignore[arg-type]
    out = capsys.readouterr().out
    assert "Trailer: <missing>" in out
    assert "Indirect objects: 0" in out

    pdfdebugger._print_trailer(
        _FakeSummaryDoc(),  # type: ignore[arg-type]
        output_format="json",
    )
    assert capsys.readouterr().out == '{\n  "trailer": null\n}\n'

    assert pdfdebugger._print_catalog(_FakeSummaryDoc()) == 4  # type: ignore[arg-type]
    assert "catalog missing" in capsys.readouterr().out

    pdfdebugger._emit({"b": 1}, ["ignored"], output_format="json")
    assert capsys.readouterr().out == '{\n  "b": 1\n}\n'

    pdfdebugger._emit({}, ["line 1", "line 2"], output_format="text")
    assert capsys.readouterr().out == "line 1\nline 2\n"


def test_wave383_parse_helpers_reject_extra_or_blank_input() -> None:
    assert pdfdebugger._parse_show_object("") is None
    assert pdfdebugger._parse_show_object("1.2.3") is None
    assert pdfdebugger._parse_object_args([]) is None
    assert pdfdebugger._parse_object_args(["1", "2", "3"]) is None
    assert pdfdebugger._valid_object_id_or_none(0, 0) == (0, 0)
