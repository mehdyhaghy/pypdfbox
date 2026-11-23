"""Lazily loaded objects end up with the update-state links
``COSObject.get_object`` gives them.

The object-stream and file-offset loaders link the arrays and dictionaries
the parser's fast path builds to the loaded object's origin document state
themselves, ahead of ``get_object``'s ``dereference_child`` walk. The result
must be exactly what the walk alone produces: every container reachable from
the loaded body linked to the document state, none marked updated, and
nothing linked when the body is reached any other way.
"""

from __future__ import annotations

import io

import pytest

import pypdfbox.pdfparser.pdf_parser as pdf_parser_module
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdfwriter.compress import CompressParameters
from pypdfbox.pdmodel import PDDocument, PDPage


def _state(obj: object) -> tuple[bool, bool] | None:
    state = getattr(obj, "_update_state", None)
    if state is None:
        return None
    return (state._origin_document_state is not None, state._updated)


def _dump(obj: object, out: list) -> None:
    if isinstance(obj, COSObject):
        out.append(("ref", obj.get_object_number(), _state(obj)))
    elif isinstance(obj, COSDictionary):
        out.append(("dict", type(obj).__name__, obj.is_direct(), _state(obj)))
        for key, value in obj._items.items():
            out.append(key.get_name())
            _dump(value, out)
    elif isinstance(obj, COSArray):
        out.append(("array", obj.is_direct(), _state(obj)))
        for value in obj._items:
            _dump(value, out)
    else:
        out.append(repr(obj))


def _build(compress: bool) -> bytes:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        extra = COSDictionary()
        extra.set_item(
            COSName.get_pdf_name("Nums"),
            COSArray([COSInteger.get(1), COSFloat("2.5"), COSArray([])]),
        )
        nested = COSDictionary()
        nested.set_item(COSName.get_pdf_name("S"), COSString(b"\x00\xffhex"))
        nested.set_item(COSName.get_pdf_name("L"), COSString(b"lit"))
        extra.set_item(COSName.get_pdf_name("Inner"), nested)
        extra.set_item(COSName.get_pdf_name("Self"), page.get_cos_object())
        page.get_cos_object().set_item(COSName.get_pdf_name("Extra"), extra)
        buf = io.BytesIO()
        doc.save(
            buf,
            CompressParameters.DEFAULT_COMPRESSION
            if compress
            else CompressParameters.NO_COMPRESSION,
        )
        return buf.getvalue()
    finally:
        doc.close()


def _load_all(data: bytes) -> list:
    doc = PDDocument.load(data)
    try:
        out: list = []
        for cos_obj in doc.get_document().get_objects():
            body = cos_obj.get_object()
            out.append(("object", cos_obj.get_object_number()))
            _dump(body, out)
            if isinstance(body, COSStream):
                out.append(("stream", _state(body)))
        return out
    finally:
        doc.close()


@pytest.mark.parametrize("compress", [True, False], ids=["objstm", "classic"])
def test_loaded_objects_match_the_dereference_walk(
    compress: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _build(compress)
    actual = _load_all(data)

    # Reference: the loaders without the early linking, so only the walk in
    # ``COSObject.get_object`` links the parsed trees.
    def call(self, obj):  # type: ignore[no-untyped-def]
        entry = self._entry
        if entry.type is pdf_parser_module.XrefType.COMPRESSED:
            return self._parser._compressed_loader(
                entry.offset, entry.compressed_index, obj
            )
        return self._parser._offset_loader(entry.offset, obj)

    monkeypatch.setattr(pdf_parser_module._XrefEntryLoader, "__call__", call)
    expected = _load_all(data)
    assert actual == expected
    linked = [item for item in actual if isinstance(item, tuple) and len(item) == 4]
    assert linked
    assert all(item[3] == (True, False) for item in linked)


def test_direct_member_load_leaves_containers_unlinked() -> None:
    data = _build(True)
    doc = PDDocument.load(data)
    try:
        cos_doc = doc.get_document()
        loaders = [
            (cos_obj, cos_obj._loader)
            for cos_obj in cos_doc.get_objects()
            if cos_obj._loader is not None
            and cos_obj._loader._entry.type
            is pdf_parser_module.XrefType.COMPRESSED
        ]
        assert loaders
        for cos_obj, loader in loaders:
            parser = loader._parser
            entry = loader._entry
            body = parser._load_compressed_object(
                entry.offset, entry.compressed_index, cos_obj
            )
            if isinstance(body, (COSDictionary, COSArray)):
                assert body.get_update_state().get_origin_document_state() is None
                for value in (
                    body._items.values()
                    if isinstance(body, COSDictionary)
                    else body._items
                ):
                    if isinstance(value, (COSDictionary, COSArray)):
                        state = value.get_update_state()
                        assert state.get_origin_document_state() is None
    finally:
        doc.close()


@pytest.mark.parametrize("compress", [True, False], ids=["objstm", "classic"])
def test_loaders_link_fast_built_containers_themselves(
    compress: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pypdfbox.cos.cos_update_state import COSUpdateState

    data = _build(compress)
    monkeypatch.setattr(COSUpdateState, "dereference_child", lambda self, child: None)
    loaded = _load_all(data)
    roots = [
        item
        for item in loaded
        if isinstance(item, tuple) and item[:2] == ("dict", "COSDictionary")
    ]
    assert roots
    assert all(item[3] == (True, False) for item in roots)
