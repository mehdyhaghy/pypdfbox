"""Hand-written tests for ``pypdfbox.xmpbox.xml.XmpSerializationException``.

Mirror of ``org.apache.xmpbox.xml.XmpSerializationException`` (extends
``Exception`` upstream; message-only and message-plus-cause constructors).
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XmpSerializationException
from pypdfbox.xmpbox.xml import XmpSerializationException as XmlPkgExport


def test_is_exception_subclass() -> None:
    assert issubclass(XmpSerializationException, Exception)


def test_message_only_constructor() -> None:
    exc = XmpSerializationException("boom")
    assert str(exc) == "boom"
    assert exc.__cause__ is None


def test_message_and_cause_constructor() -> None:
    cause = ValueError("root")
    exc = XmpSerializationException("boom", cause)
    assert str(exc) == "boom"
    assert exc.__cause__ is cause


def test_raisable_and_catchable() -> None:
    with pytest.raises(XmpSerializationException, match="failed"):
        raise XmpSerializationException("failed")


def test_re_export_from_top_level_matches_xml_package() -> None:
    assert XmpSerializationException is XmlPkgExport
