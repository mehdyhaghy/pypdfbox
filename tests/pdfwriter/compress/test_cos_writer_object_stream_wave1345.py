"""Wave 1345: residual coverage for ``COSWriterObjectStream``.

Targets:
  - the ``_write_pdf`` missing-method raise (line 48) when a passed
    ``COSBase`` lacks ``write_pdf``;
  - the ``write_object`` dispatch arms for each concrete COS type
    (lines 141/143/147/151/153 — string/float/boolean/array/dictionary
    arrived via the top-level dispatch rather than the typed helper).
"""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfwriter.compress.cos_writer_object_stream import (
    COSWriterObjectStream,
    _write_pdf,
)


class _StubPool:
    def __init__(self) -> None:
        self._map: dict[int, COSObjectKey] = {}

    def add(self, obj: object, key: COSObjectKey) -> None:
        self._map[id(obj)] = key

    def contains(self, obj: object) -> bool:
        return id(obj) in self._map

    def get_key(self, obj: object) -> COSObjectKey | None:
        return self._map.get(id(obj))


def _new_writer() -> COSWriterObjectStream:
    return COSWriterObjectStream(_StubPool())


def test_write_pdf_raises_on_missing_method() -> None:
    """A ``COSBase`` subclass with no ``write_pdf`` attribute triggers the
    explicit ``OSError`` rather than an ``AttributeError`` (line 48)."""

    class _NoWritePdf(COSBase):
        def accept(self, visitor: object) -> object:
            return None

    obj = _NoWritePdf()
    with pytest.raises(OSError, match="No write_pdf"):
        _write_pdf(obj, BytesIO())


def test_write_object_dispatches_cos_string() -> None:
    """A bare ``COSString`` routed through ``write_object`` triggers the
    string-branch dispatch (line 141)."""
    writer = _new_writer()
    out = BytesIO()
    writer.write_object(out, COSString("hi"), top_level=False)
    assert out.getvalue().endswith(b" ")
    assert b"hi" in out.getvalue() or b"6869" in out.getvalue()


def test_write_object_dispatches_cos_float() -> None:
    """A bare ``COSFloat`` routed through ``write_object`` triggers the
    float-branch dispatch (line 143)."""
    writer = _new_writer()
    out = BytesIO()
    writer.write_object(out, COSFloat(2.5), top_level=False)
    assert b"2.5" in out.getvalue()


def test_write_object_dispatches_cos_boolean() -> None:
    """A bare ``COSBoolean`` routed through ``write_object`` triggers the
    boolean-branch dispatch (line 147)."""
    writer = _new_writer()
    out = BytesIO()
    writer.write_object(out, COSBoolean.FALSE, top_level=False)
    assert b"false" in out.getvalue()


def test_write_object_dispatches_cos_array() -> None:
    """A bare ``COSArray`` routed through ``write_object`` triggers the
    array-branch dispatch (line 151)."""
    writer = _new_writer()
    out = BytesIO()
    arr = COSArray()
    arr.add(COSInteger.get(4))
    writer.write_object(out, arr, top_level=False)
    payload = out.getvalue()
    assert payload.startswith(b"[")
    assert b"4" in payload
    assert b"]" in payload


def test_write_object_dispatches_cos_dictionary() -> None:
    """A bare ``COSDictionary`` routed through ``write_object`` triggers
    the dict-branch dispatch (line 153)."""
    writer = _new_writer()
    out = BytesIO()
    cos_dict = COSDictionary()
    cos_dict.set_item(COSName.get_pdf_name("K"), COSInteger.get(9))
    writer.write_object(out, cos_dict, top_level=False)
    payload = out.getvalue()
    assert payload.startswith(b"<<")
    assert b"/K" in payload
    assert b">>" in payload


def test_write_cos_dictionary_with_none_value_continues() -> None:
    """A dictionary entry whose value is ``None`` is silently skipped
    (line 216-217).

    The public ``set_item(name, None)`` deletes the entry rather than
    storing a sentinel, so we mutate ``_items`` directly to inject a
    ``None`` value and exercise the explicit-skip branch.
    """
    writer = _new_writer()
    out = BytesIO()
    cos_dict = COSDictionary()
    cos_dict._items[COSName.get_pdf_name("Drop")] = None  # type: ignore[assignment]
    cos_dict.set_item(COSName.get_pdf_name("Keep"), COSInteger.get(1))
    writer.write_cos_dictionary(out, cos_dict)
    payload = out.getvalue()
    assert b"/Drop" not in payload
    assert b"/Keep" in payload
    assert b"1" in payload
