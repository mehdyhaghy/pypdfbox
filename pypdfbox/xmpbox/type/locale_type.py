from __future__ import annotations

from .text_type import TextType


class LocaleType(TextType):
    """
    XMP Locale simple property.

    Ported from ``org.apache.xmpbox.type.LocaleType``. Upstream simply
    extends ``TextType`` with no additional state or behavior; the type
    exists so that ``TypeMapping`` can distinguish locale-flavored text
    from plain text when reflecting property kinds back to callers.
    """
