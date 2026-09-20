"""Shared FDF/XFDF serialisation helpers.

Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFUtils`` (PDFBox 3.0 branch;
Java path ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFUtils.java``).

Upstream extracted the XML escaping that used to live as a private
``FDFField.escapeXML`` into this utility class (PDFBOX-5660) so that
``FDFDictionary.writeXML`` and ``FDFField.writeXML`` share a single
implementation, then hardened it to emit only characters that are legal in
XML 1.0 (PDFBOX-6242).
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

#: U+FFFD REPLACEMENT CHARACTER — substituted for code points that XML 1.0
#: forbids outright (upstream appends ``'�'``).
REPLACEMENT_CHARACTER: str = "�"


def _is_valid_xml10_char(cp: int) -> bool:
    """Mirrors upstream's private ``isValidXML10Char(int)``.

    XML 1.0 (§2.2 ``Char``) permits tab, LF, CR, and the ranges
    ``#x20-#xD7FF``, ``#xE000-#xFFFD`` and ``#x10000-#x10FFFF``. Everything
    else — the other C0 controls, the surrogate block and ``#xFFFE``/
    ``#xFFFF`` — is illegal even as a numeric character reference.
    """
    return (
        cp in (0x9, 0xA, 0xD)
        or 0x20 <= cp <= 0xD7FF
        or 0xE000 <= cp <= 0xFFFD
        or 0x10000 <= cp <= 0x10FFFF
    )


class FDFUtils:
    """Utility holder for the XFDF escaping helper. Mirrors upstream's
    non-instantiable ``FDFUtils``."""

    def __init__(self) -> None:  # pragma: no cover - utility class
        raise TypeError("FDFUtils is a utility class")

    @staticmethod
    def escape_xml10(input_: str) -> str:
        """Escape ``input_`` for use in XML 1.0.

        Mirrors upstream ``FDFUtils.escapeXML10(String)``. ``<``, ``>``,
        ``"``, ``&`` and ``'`` become the predefined entities; any other
        code point above ``0x7e`` becomes a decimal numeric character
        reference; characters that are not permitted in XML 1.0 at all are
        replaced with U+FFFD and the number of replacements is logged at
        INFO level.

        Upstream walks the Java string by code point (``codePointAt`` /
        ``charCount``) so that a supplementary character yields a single
        reference to its code point rather than two references to its
        surrogate halves; Python strings are already sequences of code
        points, so plain iteration is the faithful equivalent.
        """
        escaped_xml: list[str] = []
        invalid_count = 0
        for ch in input_:
            cp = ord(ch)

            if not _is_valid_xml10_char(cp):
                invalid_count += 1
                escaped_xml.append(REPLACEMENT_CHARACTER)
                continue

            if ch == "<":
                escaped_xml.append("&lt;")
            elif ch == ">":
                escaped_xml.append("&gt;")
            elif ch == '"':
                escaped_xml.append("&quot;")
            elif ch == "&":
                escaped_xml.append("&amp;")
            elif ch == "'":
                escaped_xml.append("&apos;")
            elif cp > 0x7E:
                escaped_xml.append(f"&#{cp};")
            else:
                escaped_xml.append(ch)

        if invalid_count > 0:
            _log.info(
                "Replaced %d character(s) invalid in XML 1.0 with U+FFFD",
                invalid_count,
            )

        return "".join(escaped_xml)


__all__ = ["FDFUtils"]
