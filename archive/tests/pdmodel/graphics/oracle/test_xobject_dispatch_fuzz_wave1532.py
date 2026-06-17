"""PDXObject.createXObject /Subtype dispatch parity with PDFBox 3.0.7.

Covers the create-XObject factory's dispatch on ``/Subtype`` (Image / Form /
PS / unknown / absent), the Form→TransparencyGroup sub-dispatch on
``/Group /S /Transparency``, non-stream and indirect bases, and the
non-name ``/Subtype`` reads. The Java side is the live oracle
``XObjectDispatchFuzzProbe``; the Python side reproduces each case against
``PDXObject.create_x_object`` and projects the same result string.

Two facets are *unalignable* and pinned both-sides by normalisation, not by a
fixed expected literal:

* The ``Unexpected object type: <class>`` message embeds the Java
  fully-qualified class name (``org.apache.pdfbox.cos.COSDictionary``); Python
  has no such package-prefixed name, so the test strips the
  ``org.apache.pdfbox.cos.`` prefix from the Java side before comparing the
  simple class name both runtimes produce.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

CASE_IDS = (
    "img", "form", "ps",
    "unknown", "absent", "empty",
    "sub-str", "sub-int", "sub-null", "sub-arr", "sub-ind-name",
    "base-null", "base-dict", "base-name", "base-int", "base-array",
    "base-ind-stream",
    "form-grp-tr", "form-grp-other", "form-grp-no-s", "form-grp-nondict",
    "form-grp-null", "form-grp-ind", "form-grp-s-str",
    "img-no-res", "form-no-res",
    "ps-extra", "img-empty-stream",
)

_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]
_GROUP = COSName.get_pdf_name("Group")
_S = COSName.get_pdf_name("S")
_FOO = COSName.get_pdf_name("Foo")

# Cases whose base is a stream that should dispatch with resources == None,
# mirroring the Java probe's noResources(...) helper.
_NO_RESOURCES = {"img-no-res", "form-no-res", "base-null"}


def _stream(subtype: str | None) -> COSStream:
    stream = COSStream()
    if subtype is not None:
        stream.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    return stream


def _group(s_value: str | None, as_name: bool) -> COSDictionary:
    dictionary = COSDictionary()
    if s_value is not None:
        if as_name:
            dictionary.set_item(_S, COSName.get_pdf_name(s_value))
        else:
            dictionary.set_item(_S, COSString(s_value))
    return dictionary


def _base(case_id: str) -> COSBase | None:
    if case_id == "img":
        return _stream("Image")
    if case_id == "form":
        return _stream("Form")
    if case_id == "ps":
        return _stream("PS")
    if case_id == "unknown":
        return _stream("Bogus")
    if case_id == "absent":
        return _stream(None)
    if case_id == "empty":
        return COSStream()
    if case_id == "sub-str":
        stream = COSStream()
        stream.set_item(_SUBTYPE, COSString("Image"))
        return stream
    if case_id == "sub-int":
        stream = COSStream()
        stream.set_item(_SUBTYPE, COSInteger.get(7))
        return stream
    if case_id == "sub-null":
        stream = COSStream()
        stream.set_item(_SUBTYPE, COSNull.NULL)
        return stream
    if case_id == "sub-arr":
        stream = COSStream()
        array = COSArray()
        array.add(COSName.get_pdf_name("Form"))
        stream.set_item(_SUBTYPE, array)
        return stream
    if case_id == "sub-ind-name":
        stream = COSStream()
        stream.set_item(_SUBTYPE, COSObject(1, resolved=COSName.get_pdf_name("Form")))
        return stream
    if case_id == "base-null":
        return None
    if case_id == "base-dict":
        return COSDictionary()
    if case_id == "base-name":
        return COSName.get_pdf_name("Form")
    if case_id == "base-int":
        return COSInteger.get(3)
    if case_id == "base-array":
        return COSArray()
    if case_id == "base-ind-stream":
        return COSObject(1, resolved=_stream("Form"))
    if case_id == "form-grp-tr":
        stream = _stream("Form")
        stream.set_item(_GROUP, _group("Transparency", True))
        return stream
    if case_id == "form-grp-other":
        stream = _stream("Form")
        stream.set_item(_GROUP, _group("Other", True))
        return stream
    if case_id == "form-grp-no-s":
        stream = _stream("Form")
        stream.set_item(_GROUP, _group(None, True))
        return stream
    if case_id == "form-grp-nondict":
        stream = _stream("Form")
        stream.set_item(_GROUP, COSInteger.get(1))
        return stream
    if case_id == "form-grp-null":
        stream = _stream("Form")
        stream.set_item(_GROUP, COSNull.NULL)
        return stream
    if case_id == "form-grp-ind":
        stream = _stream("Form")
        stream.set_item(_GROUP, COSObject(1, resolved=_group("Transparency", True)))
        return stream
    if case_id == "form-grp-s-str":
        stream = _stream("Form")
        stream.set_item(_GROUP, _group("Transparency", False))
        return stream
    if case_id == "img-no-res":
        return _stream("Image")
    if case_id == "form-no-res":
        return _stream("Form")
    if case_id == "ps-extra":
        stream = _stream("PS")
        stream.set_item(_FOO, COSInteger.get(9))
        return stream
    if case_id == "img-empty-stream":
        return _stream("Image")
    raise AssertionError(case_id)


def _project(case_id: str) -> str:
    base = _base(case_id)
    resources = None if case_id in _NO_RESOURCES else PDResources()
    try:
        xobject = PDXObject.create_x_object(base, resources)
        result = "null" if xobject is None else type(xobject).__name__
    except Exception as exception:  # noqa: BLE001 — match Java's catch-all projection
        result = f"err:{exception}"
    return f"CASE {case_id} result={result}"


def _normalise(line: str) -> str:
    """Strip the Java COS package prefix so the unalignable FQN in the
    ``Unexpected object type`` message compares as the simple class name both
    runtimes emit."""
    return line.replace("org.apache.pdfbox.cos.", "")


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    return {
        line.split()[1]: _normalise(line)
        for line in run_probe_text("XObjectDispatchFuzzProbe").splitlines()
    }


@requires_oracle
@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_xobject_dispatch_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _project(case_id) == java_lines[case_id]
