"""Wave 384 coverage for pdfdebugger walker and mode edge branches."""
from __future__ import annotations

import builtins
import json
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.tools import pdfdebugger


class _FakeDoc:
    def __init__(self, cos_doc: COSDocument) -> None:
        self._cos_doc = cos_doc

    def get_document(self) -> COSDocument:
        return self._cos_doc


class _BrokenString(COSString):
    def get_string(self) -> str:
        raise ValueError("not text")


class _UnknownCOS(COSBase):
    def accept(self, visitor: Any) -> None:
        return None


class _FakePage:
    def get_contents(self) -> bytes:
        return b"not a content stream"


class _FakePageDoc:
    def get_number_of_pages(self) -> int:
        return 1

    def get_page(self, index: int) -> _FakePage:
        assert index == 0
        return _FakePage()


class _EncryptionFlagOnlyCosDoc:
    def is_encrypted(self) -> bool:
        return False


class _EncryptionFlagOnlyDoc:
    def get_document(self) -> _EncryptionFlagOnlyCosDoc:
        return _EncryptionFlagOnlyCosDoc()


def _build_walker_doc() -> tuple[COSDocument, COSStream]:
    cos_doc = COSDocument()
    trailer = COSDictionary()
    catalog = COSDictionary()
    catalog.set_item("Type", COSName.get_pdf_name("Catalog"))
    catalog.set_item("Kids", COSArray([COSInteger.get(1), COSString("two")]))

    stream = COSStream()
    stream.set_data(b"stream data")
    catalog.set_item("Stream", stream)

    key = COSObjectKey(7, 0)
    ref = cos_doc.get_object_from_pool(key)
    ref.set_object(catalog)
    trailer.set_item(COSName.ROOT, ref)
    cos_doc.set_trailer(trailer)
    return cos_doc, stream


def test_wave384_node_type_labels_and_navigation_helpers() -> None:
    stream = COSStream()
    try:
        ref = COSObject(3, 4, resolved=COSInteger.get(1))
        cycle = COSObject(9, 0)
        cycle.set_object(cycle)

        assert pdfdebugger._node_type_label(None) == "<unresolved>"
        assert pdfdebugger._node_type_label(stream) == "stream"
        assert pdfdebugger._node_type_label(COSDictionary()) == "dict"
        assert pdfdebugger._node_type_label(COSArray()) == "array"
        assert pdfdebugger._node_type_label(ref) == "ref=3 4 R"
        assert pdfdebugger._node_type_label(COSName.get_pdf_name("Name")) == "name=/Name"
        assert pdfdebugger._node_type_label(COSString("abc")) == "string=('abc')"
        assert pdfdebugger._node_type_label(_BrokenString(b"\xaa")) == "string=<aa>"
        assert pdfdebugger._node_type_label(COSBoolean.FALSE) == "bool=false"
        assert pdfdebugger._node_type_label(COSInteger.get(6)) == "int=6"
        assert pdfdebugger._node_type_label(COSFloat("2.5")) == "float=2.5"
        assert pdfdebugger._node_type_label(COSNull.NULL) == "null"
        assert pdfdebugger._node_type_label(_UnknownCOS()) == "_UnknownCOS"
        assert pdfdebugger._resolve_for_navigation(cycle) is cycle
    finally:
        stream.close()


def test_wave384_walker_list_children_supports_stream_dict_array_and_scalars() -> None:
    stream = COSStream()
    try:
        stream.set_item("Length", COSInteger.get(5))
        dictionary = COSDictionary()
        dictionary.set_item("Child", COSString("value"))
        array = COSArray([COSInteger.get(1), COSName.get_pdf_name("Two")])

        assert pdfdebugger._walker_list_children(stream) == [
            ("/Length", COSInteger.get(5))
        ]
        assert pdfdebugger._walker_list_children(dictionary) == [
            ("/Child", COSString("value"))
        ]
        assert pdfdebugger._walker_list_children(array) == [
            ("[0]", COSInteger.get(1)),
            ("[1]", COSName.get_pdf_name("Two")),
        ]
        assert pdfdebugger._walker_list_children(COSInteger.get(1)) == []
        assert pdfdebugger._walker_lookup_child(array, "not-int") is None
        assert pdfdebugger._walker_lookup_child(dictionary, "/Child") == COSString(
            "value"
        )
    finally:
        stream.close()


def test_wave384_interactive_walker_scripted_commands(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cos_doc, stream = _build_walker_doc()
    commands = iter(
        [
            "pwd",
            "ls",
            "raw",
            "decode",
            "hex",
            "cat nope",
            "cat 1",
            "find",
            "find Missing",
            "find Type",
            "cd Root",
            "pwd",
            "ls",
            "cd Kids",
            "ls",
            "cd 1",
            "ls",
            "pwd",
            "cd ..",
            "cd /",
            "ref",
            "ref nope",
            "ref -1",
            "ref 999",
            "ref 7 0",
            "cd 8 0",
            "cd 7 0",
            "cd Stream",
            "raw",
            "decode",
            "hex",
            "unknown",
            "q",
        ]
    )
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(commands))
    try:
        assert pdfdebugger._interactive_walker(_FakeDoc(cos_doc)) == 0  # type: ignore[arg-type]
    finally:
        stream.close()
        cos_doc.close()

    out = capsys.readouterr().out
    assert "pdfdebugger interactive walker" in out
    assert "trailer/Root/Kids/1" in out
    assert "cat: depth must be an integer" in out
    assert "find: usage: find <key>" in out
    assert "<no matches for /Missing>" in out
    assert "  /Root/Type" in out
    assert "ref: usage: ref <num> [gen]" in out
    assert "ref: num and gen must be integers" in out
    assert "ref: num and gen must be non-negative integers" in out
    assert "ref: object 999 0 R not in pool" in out
    assert "cd: object 8 0 R not in pool" in out
    assert "<not a stream>" in out
    assert "73 74 72 65 61 6d 20 64 61 74 61" in out
    assert "unknown command: 'unknown'" in out


def test_wave384_interactive_walker_missing_trailer_and_eof(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = COSDocument()
    try:
        assert pdfdebugger._interactive_walker(_FakeDoc(missing)) == 4  # type: ignore[arg-type]
        assert "trailer missing" in capsys.readouterr().out
    finally:
        missing.close()

    cos_doc, stream = _build_walker_doc()

    def raise_eof(_prompt: str) -> None:
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)
    try:
        assert pdfdebugger._interactive_walker(_FakeDoc(cos_doc)) == 0  # type: ignore[arg-type]
    finally:
        stream.close()
        cos_doc.close()
    assert "pdfdebugger interactive walker" in capsys.readouterr().out


def test_wave384_tree_xref_encryption_and_token_edges(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cos_doc = COSDocument()
    try:
        key = COSObjectKey(2, 0)
        cos_doc.get_object_from_pool(key).set_object(COSInteger.get(8))
        cos_doc.add_xref_table({key: 15})
        doc = _FakeDoc(cos_doc)

        pdfdebugger._print_tree(doc, output_format="json")  # type: ignore[arg-type]
        assert json.loads(capsys.readouterr().out) == {
            "objects": [
                {
                    "generation_number": 0,
                    "object_number": 2,
                    "value": 8,
                }
            ]
        }

        pdfdebugger._print_xref(doc, output_format="json")  # type: ignore[arg-type]
        payload = json.loads(capsys.readouterr().out)
        assert payload["entries"] == [
            {"generation_number": 0, "object_number": 2}
        ]

        pdfdebugger._print_list_objects(doc)  # type: ignore[arg-type]
        assert "used" in capsys.readouterr().out
    finally:
        cos_doc.close()

    assert pdfdebugger._print_encryption(
        _EncryptionFlagOnlyDoc(),  # type: ignore[arg-type]
        output_format="json",
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"encrypted": False}

    def raise_parse_error(_data: bytes) -> list[object]:
        raise ValueError("bad tokens")

    monkeypatch.setattr(pdfdebugger, "_tokenize_stream_bytes", raise_parse_error)
    assert pdfdebugger._print_page_tokens(_FakePageDoc(), 1) == 4  # type: ignore[arg-type]
    assert "tokenize page 1: bad tokens" in capsys.readouterr().out


def test_wave384_token_helpers_and_hex_prefix() -> None:
    opaque = object()

    assert pdfdebugger._tokenize_stream_bytes(b"") == []
    assert pdfdebugger._token_to_jsonable(opaque) == repr(opaque)
    assert pdfdebugger._hex_prefix(None) is None
    assert pdfdebugger._hex_prefix(b"") is None
    assert pdfdebugger._hex_prefix(b"abcdef") == "61626364"
