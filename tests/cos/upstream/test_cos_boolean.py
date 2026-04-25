"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSBoolean.java

Upstream extends TestCOSBase. The two inherited tests covered here are
``testGetCOSObject`` (reduced to an ``isinstance`` check — pypdfbox doesn't
expose ``getCOSObject``) and ``testIsSetDirect``.

``testAccept`` upstream uses ``COSWriter`` to serialize the boolean; the
pdfwriter cluster has not been ported yet, so we replace it with a
recording visitor that confirms the visitor dispatch.
"""

from __future__ import annotations

from pypdfbox.cos import COSBoolean
from tests.cos.helpers import RecordingVisitor


def test_is_set_direct() -> None:
    test_cos_base = COSBoolean.TRUE
    test_cos_base.set_direct(True)
    assert test_cos_base.is_direct()
    test_cos_base.set_direct(False)
    assert not test_cos_base.is_direct()


def test_get_value() -> None:
    assert COSBoolean.TRUE.get_value() is True
    assert COSBoolean.FALSE.get_value() is False


def test_get_value_as_object() -> None:
    # Upstream ``getValueAsObject`` returns the boxed Boolean. The Python
    # ``get_value`` already returns the underlying ``bool``.
    assert isinstance(COSBoolean.TRUE.get_value(), bool)
    assert COSBoolean.TRUE.get_value() is True
    assert isinstance(COSBoolean.FALSE.get_value(), bool)
    assert COSBoolean.FALSE.get_value() is False


def test_get_boolean() -> None:
    assert COSBoolean.get(True) is COSBoolean.TRUE
    assert COSBoolean.get(False) is COSBoolean.FALSE


def test_equals() -> None:
    test1 = COSBoolean.TRUE
    test2 = COSBoolean.TRUE
    test3 = COSBoolean.TRUE
    # Reflexive, symmetric, transitive.
    assert test1 == test1
    assert test2 == test1
    assert test1 == test2
    assert test1 == test2
    assert test2 == test3
    assert test1 == test3

    assert COSBoolean.TRUE != COSBoolean.FALSE
    # Different type — Python ``True`` / ``False`` is not a ``COSBoolean``.
    assert COSBoolean.TRUE != True  # noqa: E712
    assert COSBoolean.FALSE != False  # noqa: E712


def test_accept() -> None:
    visitor = RecordingVisitor()
    COSBoolean.TRUE.accept(visitor)
    COSBoolean.FALSE.accept(visitor)
    assert visitor.calls == [
        ("boolean", COSBoolean.TRUE),
        ("boolean", COSBoolean.FALSE),
    ]
