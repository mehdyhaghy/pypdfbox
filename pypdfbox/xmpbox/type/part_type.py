from __future__ import annotations

from .text_type import TextType


class PartType(TextType):
    """
    XMP Part simple property.

    Ported from ``org.apache.xmpbox.type.PartType``. Upstream simply
    extends ``TextType`` with no additional state or behavior; the type
    exists so that ``TypeMapping`` can distinguish part-identifier text
    from plain text when reflecting property kinds back to callers.
    """
