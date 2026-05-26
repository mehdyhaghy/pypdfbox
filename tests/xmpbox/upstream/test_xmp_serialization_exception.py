"""Ported upstream tests for ``org.apache.xmpbox.xml.XmpSerializationException``.

Apache PDFBox does **not** ship a dedicated
``XmpSerializationExceptionTest.java``. The exception's behaviour is exercised
by two tests in
``xmpbox/src/test/java/org/apache/xmpbox/XMPMetaDataTest.java``:

    @Test void testTransformerExceptionMessage()
    {
        assertThrows(XmpSerializationException.class, () -> {
            throw new XmpSerializationException("TEST");
        });
    }

    @Test void testTransformerExceptionWithCause()
    {
        assertThrows(XmpSerializationException.class, () -> {
            throw new XmpSerializationException("TEST", new Throwable());
        });
    }

Those two were previously skipped in ``tests/xmpbox/upstream/test_xmp_meta_data.py``
because pypdfbox's serializer raised plain ``RuntimeError``. Now that the
upstream-named class exists they are translated here verbatim.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.xml import XmpSerializationException


def test_transformer_exception_message() -> None:
    """Translated from upstream ``testTransformerExceptionMessage``."""
    with pytest.raises(XmpSerializationException):
        raise XmpSerializationException("TEST")


def test_transformer_exception_with_cause() -> None:
    """Translated from upstream ``testTransformerExceptionWithCause``."""
    with pytest.raises(XmpSerializationException):
        raise XmpSerializationException("TEST", Exception())
