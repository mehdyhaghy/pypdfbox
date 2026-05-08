from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pypdfbox.cos import COSBase

from .mac_roman_encoding import MacRomanEncoding

# 16 octal-coded ``(code, glyph_name)`` differences layered on top of
# :class:`MacRomanEncoding`. These are the entries Apple added to the
# vendor-specific "Mac OS Roman" extension over the original PostScript
# MacRoman encoding (high-bit math symbols, the Apple logo at 0o360,
# the Euro sign at 0o333, etc.). Mirrors the
# ``MAC_OS_ROMAN_ENCODING_TABLE`` constant in the upstream Java class.
_MAC_OS_ROMAN_DIFFERENCES: tuple[tuple[int, str], ...] = (
    (0o255, "notequal"),
    (0o260, "infinity"),
    (0o262, "lessequal"),
    (0o263, "greaterequal"),
    (0o266, "partialdiff"),
    (0o267, "summation"),
    (0o270, "product"),
    (0o271, "pi"),
    (0o272, "integral"),
    (0o275, "Omega"),
    (0o303, "radical"),
    (0o305, "approxequal"),
    (0o306, "Delta"),
    (0o327, "lozenge"),
    (0o333, "Euro"),
    (0o360, "apple"),
)


class MacOSRomanEncoding(MacRomanEncoding):
    """The Mac OS Roman encoding.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.MacOSRomanEncoding``.
    Layers 16 vendor-specific glyph-name differences on top of
    :class:`MacRomanEncoding` (notequal, infinity, lessequal, greaterequal,
    partialdiff, summation, product, pi, integral, Omega, radical,
    approxequal, Delta, lozenge, Euro, apple).

    Mac OS Roman has no PDF-spec ``/Encoding`` name — :meth:`get_cos_object`
    returns ``None`` (matches upstream). Use :class:`MacRomanEncoding` when
    you need a serializable ``/MacRomanEncoding`` entry.
    """

    INSTANCE: MacOSRomanEncoding

    #: Read-only ``{code: glyph_name}`` view of the 16 vendor-specific
    #: differences this encoding layers on top of :class:`MacRomanEncoding`.
    #: Exposed for downstream introspection (e.g. encoding-difference
    #: pretty-printers and parity tests) without leaking the private
    #: tuple-form definition. Wrapped in a :class:`MappingProxyType` so
    #: callers can read but never mutate.
    DIFFERENCES: Mapping[int, str] = MappingProxyType(
        dict(_MAC_OS_ROMAN_DIFFERENCES)
    )

    def __init__(self) -> None:
        # MacRomanEncoding's __init__ populates the base 256-glyph table;
        # we then layer the Mac OS Roman differences on top via :meth:`add`,
        # which preserves prior reverse-mappings (matching upstream's
        # ``Map.putIfAbsent`` semantics so the existing MacRoman name -> code
        # entries survive the overlay).
        super().__init__()
        for code, name in _MAC_OS_ROMAN_DIFFERENCES:
            self.add(code, name)

    def get_cos_object(self) -> COSBase | None:
        # Upstream returns ``null`` — Mac OS Roman is not a PDF-spec
        # ``/Encoding`` name, so it has no COS representation.
        return None


MacOSRomanEncoding.INSTANCE = MacOSRomanEncoding()


__all__ = ["MacOSRomanEncoding"]
