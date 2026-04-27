from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING, Any

from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class RationalType(TextType):
    """
    XMP rational simple property (``"<numerator>/<denominator>"`` text form).

    Ported from ``org.apache.xmpbox.type.RationalType``. Upstream is a thin
    ``TextType`` subclass that does no validation; the EXIF / TIFF specs that
    use it call out the ``"num/denom"`` shape, so we add that as an
    informational :meth:`as_fraction` accessor while keeping the wire form a
    plain :class:`str` for round-trip parity with upstream.
    """

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None,
        prefix: str | None,
        property_name: str,
        value: Any,
    ) -> None:
        super().__init__(metadata, namespace_uri, prefix, property_name, value)

    def as_fraction(self) -> Fraction | None:
        text = self.get_string_value()
        if "/" not in text:
            try:
                return Fraction(int(text))
            except ValueError:
                return None
        try:
            num_s, den_s = text.split("/", 1)
            return Fraction(int(num_s.strip()), int(den_s.strip()))
        except (ValueError, ZeroDivisionError):
            return None
