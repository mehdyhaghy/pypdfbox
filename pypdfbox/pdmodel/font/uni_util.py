"""Unicode-fallback utility — generates ``"uniXXXX"`` glyph names.

Mirrors ``org.apache.pdfbox.pdmodel.font.UniUtil`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/UniUtil.java``
lines 25-47).

Adobe Glyph List Specification §6.4 says a glyph may be named
``"uniXXXX"`` where ``XXXX`` is an uppercase 4-digit-or-longer hex
representation of the Unicode code point. Both ``PDType0Font`` and
``PDCIDFontType2`` use this when synthesizing a fallback glyph name for
an otherwise unknown code point.

Upstream class is package-private and final; pypdfbox surfaces the
helper as a module-level function (``get_uni_name_of_code_point``) plus
an ``UniUtil`` namespace class for callers that prefer the Java-style
spelling.
"""

from __future__ import annotations


def get_uni_name_of_code_point(code_point: int) -> str:
    """Return ``"uniXXXX"`` glyph name for *code_point*.

    Mirrors upstream ``UniUtil.getUniNameOfCodePoint`` (Java line 32-46).
    Pads to 4 hex digits for code points < 0x1000, otherwise uses the
    natural hex width — matches upstream's ``switch`` ladder.
    """
    # Upstream uses ``Integer.toString(codePoint, 16).toUpperCase(Locale.US)``
    # then pads via a switch on string length. Python's format spec
    # produces the same result with ``{:X}``; pad to width 4 with zeros.
    hex_repr = format(code_point, "X")
    if len(hex_repr) < 4:
        # Pad to 4 hex chars — matches upstream cases length 1/2/3.
        return f"uni{hex_repr.zfill(4)}"
    # Length 4+ — emit verbatim (matches upstream ``default`` branch).
    return f"uni{hex_repr}"


class UniUtil:
    """Java-style namespace wrapper for :func:`get_uni_name_of_code_point`.

    Upstream class has a private constructor and a single static method;
    the wrapper exists so callers porting from Java can spell
    ``UniUtil.get_uni_name_of_code_point(cp)`` exactly as in
    ``UniUtil.getUniNameOfCodePoint(cp)``.
    """

    def __init__(self) -> None:
        # Upstream constructor is private — Python can't enforce that, but
        # we raise as a hint that instantiation is meaningless.
        raise TypeError("UniUtil is a static utility — do not instantiate")

    @staticmethod
    def get_uni_name_of_code_point(code_point: int) -> str:
        """See :func:`get_uni_name_of_code_point`."""
        return get_uni_name_of_code_point(code_point)


__all__ = ["UniUtil", "get_uni_name_of_code_point"]
