from __future__ import annotations

from .text_type import TextType


class XPathType(TextType):
    """
    XMP XPath simple property.

    Ported from ``org.apache.xmpbox.type.XPathType``. Upstream simply
    extends ``TextType`` with no additional state or behavior; the type
    exists so that ``TypeMapping`` can distinguish XPath-flavored text
    from plain text when reflecting property kinds back to callers.
    """
