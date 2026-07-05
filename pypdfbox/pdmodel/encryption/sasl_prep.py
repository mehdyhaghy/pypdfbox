"""SASLPrep (RFC 4013) canonicalisation for /V 5 password strings.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.SaslPrep`` (PDFBox 3.x;
Java path ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/SaslPrep.java``).
Upstream is itself a port of Tom Bentley's RFC 4013 reference at
https://github.com/tombentley/saslprep — we reuse the same code-point
classification helpers and NFKC normalisation step (via Python's
:mod:`unicodedata` stdlib module).
"""

from __future__ import annotations

import unicodedata


class SaslPrep:
    """RFC 4013 SASLPrep — keep the upstream class shape for parity."""

    def __init__(self) -> None:
        # Java declares a private no-arg constructor; mirror that semantic.
        raise TypeError("SaslPrep is a utility class — use the classmethods")

    @staticmethod
    def sasl_prep_query(value: str) -> str:
        """Canonicalise ``value`` as a SASL query string.

        Mirrors ``SaslPrep.saslPrepQuery`` (Java line 48). Unassigned
        codepoints are permitted (per RFC 4013 §2.4 query semantics).
        """
        return _sasl_prep(value, allow_unassigned=True)

    @staticmethod
    def sasl_prep_stored(value: str) -> str:
        """Canonicalise ``value`` as a stored string.

        Mirrors ``SaslPrep.saslPrepStored`` (Java line 66). Unassigned
        codepoints are rejected.
        """
        return _sasl_prep(value, allow_unassigned=False)

    @staticmethod
    def prohibited(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.prohibited`` (Java line 146).

        Upstream calls ``nonAsciiSpace((char) character)`` and
        ``asciiControl((char) character)`` — a narrowing ``int`` → ``char``
        cast that keeps only the low 16 bits. Astral codepoints are therefore
        prohibited whenever their low 16 bits alias a non-ASCII space or an
        ASCII control (e.g. U+12000 CUNEIFORM SIGN A aliases U+2000, and
        U+10000 LINEAR B SYLLABLE B008 A aliases U+0000). Mirror the
        truncation exactly; the remaining predicates take the full codepoint
        upstream (``int`` parameters) and do so here as well.
        """
        return (
            _non_ascii_space(codepoint & 0xFFFF)
            or _ascii_control(codepoint & 0xFFFF)
            or _non_ascii_control(codepoint)
            or _private_use(codepoint)
            or _non_character_codepoint(codepoint)
            or _surrogate_codepoint(codepoint)
            or _inappropriate_for_plain_text(codepoint)
            or _inappropriate_for_canonical(codepoint)
            or _change_display_properties(codepoint)
            or _tagging(codepoint)
        )

    # --- Parity surface: expose the RFC 3454 codepoint predicates ---------
    # Upstream declares these as private statics, but the parity scanner
    # treats them as part of the class surface. Mirror each one as a
    # classmethod-style static helper delegating to the module-level helper.

    @staticmethod
    def tagging(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.tagging`` (Java line 166)."""
        return _tagging(codepoint)

    @staticmethod
    def change_display_properties(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.changeDisplayProperties`` (Java line 178)."""
        return _change_display_properties(codepoint)

    @staticmethod
    def inappropriate_for_canonical(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.inappropriateForCanonical`` (Java line 204)."""
        return _inappropriate_for_canonical(codepoint)

    @staticmethod
    def inappropriate_for_plain_text(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.inappropriateForPlainText`` (Java line 215)."""
        return _inappropriate_for_plain_text(codepoint)

    @staticmethod
    def surrogate_code_point(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.surrogateCodePoint`` (Java line 231)."""
        return _surrogate_codepoint(codepoint)

    @staticmethod
    def non_character_code_point(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.nonCharacterCodePoint`` (Java line 242)."""
        return _non_character_codepoint(codepoint)

    @staticmethod
    def private_use(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.privateUse`` (Java line 270)."""
        return _private_use(codepoint)

    @staticmethod
    def non_ascii_control(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.nonAsciiControl`` (Java line 282)."""
        return _non_ascii_control(codepoint)

    @staticmethod
    def ascii_control(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.asciiControl`` (Java line 307)."""
        return _ascii_control(codepoint)

    @staticmethod
    def non_ascii_space(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.nonAsciiSpace`` (Java line 317)."""
        return _non_ascii_space(codepoint)

    @staticmethod
    def mapped_to_nothing(codepoint: int) -> bool:
        """Mirror of ``SaslPrep.mappedToNothing`` (Java line 332)."""
        return _mapped_to_nothing(codepoint)


def _sasl_prep(value: str, *, allow_unassigned: bool) -> str:
    # 1. Map: non-ASCII space chars → ASCII space; drop "mapped to nothing".
    chars: list[str] = []
    for ch in value:
        cp = ord(ch)
        if _non_ascii_space(cp):
            chars.append(" ")
        elif _mapped_to_nothing(cp):
            continue
        else:
            chars.append(ch)

    # 2. Normalize (NFKC).
    normalized = unicodedata.normalize("NFKC", "".join(chars))

    # 3. Prohibit; 4. Check bidi.
    contains_randal_cat = False
    contains_l_cat = False
    initial_randal_cat = False
    for i, ch in enumerate(normalized):
        cp = ord(ch)
        if SaslPrep.prohibited(cp):
            raise ValueError(
                f"Prohibited character at position {i}: U+{cp:04X}"
            )
        directionality = unicodedata.bidirectional(ch)
        is_randal_cat = directionality in {"R", "AL"}
        contains_randal_cat |= is_randal_cat
        contains_l_cat |= directionality == "L"
        if i == 0 and is_randal_cat:
            initial_randal_cat = True
        if not allow_unassigned and unicodedata.category(ch) == "Cn":
            raise ValueError(f"Character at position {i} is unassigned")
        if initial_randal_cat and i == len(normalized) - 1 and not is_randal_cat:
            raise ValueError(
                "First character is RandALCat, but last character is not"
            )
    if contains_randal_cat and contains_l_cat:
        raise ValueError("Contains both RandALCat characters and LCat characters")
    return normalized


def _tagging(cp: int) -> bool:
    return cp == 0xE0001 or 0xE0020 <= cp <= 0xE007F


def _change_display_properties(cp: int) -> bool:
    return cp in {
        0x0340,
        0x0341,
        0x200E,
        0x200F,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x206A,
        0x206B,
        0x206C,
        0x206D,
        0x206E,
        0x206F,
    }


def _inappropriate_for_canonical(cp: int) -> bool:
    return 0x2FF0 <= cp <= 0x2FFB


def _inappropriate_for_plain_text(cp: int) -> bool:
    return cp in {0xFFF9, 0xFFFA, 0xFFFB, 0xFFFC, 0xFFFD}


def _surrogate_codepoint(cp: int) -> bool:
    return 0xD800 <= cp <= 0xDFFF


def _non_character_codepoint(cp: int) -> bool:
    if 0xFDD0 <= cp <= 0xFDEF:
        return True
    # Each Unicode plane's last two codepoints are non-characters.
    return cp & 0xFFFF in {0xFFFE, 0xFFFF}


def _private_use(cp: int) -> bool:
    return (
        0xE000 <= cp <= 0xF8FF
        or 0xF0000 <= cp <= 0xFFFFD
        or 0x100000 <= cp <= 0x10FFFD
    )


def _non_ascii_control(cp: int) -> bool:
    return (
        0x0080 <= cp <= 0x009F
        or cp in {
            0x06DD,
            0x070F,
            0x180E,
            0x200C,
            0x200D,
            0x2028,
            0x2029,
            0x2060,
            0x2061,
            0x2062,
            0x2063,
        }
        or 0x206A <= cp <= 0x206F
        or cp == 0xFEFF
        or 0xFFF9 <= cp <= 0xFFFC
        or 0x1D173 <= cp <= 0x1D17A
    )


def _ascii_control(cp: int) -> bool:
    return cp <= 0x1F or cp == 0x7F


def _non_ascii_space(cp: int) -> bool:
    return (
        cp == 0x00A0
        or cp == 0x1680
        or 0x2000 <= cp <= 0x200B
        or cp in {0x202F, 0x205F, 0x3000}
    )


def _mapped_to_nothing(cp: int) -> bool:
    return cp in {
        0x00AD,
        0x034F,
        0x1806,
        0x180B,
        0x180C,
        0x180D,
        0x200B,
        0x200C,
        0x200D,
        0x2060,
        0xFEFF,
    } or 0xFE00 <= cp <= 0xFE0F


__all__ = ["SaslPrep"]
