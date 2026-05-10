"""Hand-written tests for the pdmodel ``MacOSRomanEncoding`` wrapper.

MacOSRomanEncoding extends :class:`MacRomanEncoding` with 16 vendor-specific
glyph-name differences (high-bit math symbols, Apple logo, Euro sign).
Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.MacOSRomanEncoding``.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.encoding import (
    Encoding,
    MacOSRomanEncoding,
    MacRomanEncoding,
)
from pypdfbox.pdmodel.font.encoding.mac_os_roman_encoding import (
    _MAC_OS_ROMAN_DIFFERENCES,
)

# ---------- singleton + identity ----------


def test_singleton_identity() -> None:
    assert MacOSRomanEncoding.INSTANCE is MacOSRomanEncoding.INSTANCE
    assert isinstance(MacOSRomanEncoding.INSTANCE, MacOSRomanEncoding)


def test_distinct_singleton_from_mac_roman() -> None:
    """MacOSRomanEncoding.INSTANCE is *not* the same object as
    MacRomanEncoding.INSTANCE — they are different encodings even though
    one inherits from the other.
    """
    assert MacOSRomanEncoding.INSTANCE is not MacRomanEncoding.INSTANCE


def test_inherits_from_mac_roman_encoding() -> None:
    assert issubclass(MacOSRomanEncoding, MacRomanEncoding)


def test_inherits_from_encoding_via_mac_roman() -> None:
    assert issubclass(MacOSRomanEncoding, Encoding)


# ---------- COS surface ----------


def test_get_cos_object_returns_none() -> None:
    """Mac OS Roman has no PDF-spec ``/Encoding`` name — upstream returns
    ``null`` and pypdfbox returns ``None``. The serializable counterpart
    is :class:`MacRomanEncoding` (returns ``COSName /MacRomanEncoding``).
    """
    assert MacOSRomanEncoding.INSTANCE.get_cos_object() is None


def test_mac_roman_still_serializes_to_cos_name() -> None:
    """Sanity check: the parent class still has its own COS object even
    though MacOSRomanEncoding overrides ``get_cos_object`` to ``None``.
    """
    assert MacRomanEncoding.INSTANCE.get_cos_object() is not None


# ---------- difference table contents ----------


def test_difference_table_size_is_sixteen() -> None:
    """The vendor extension is exactly 16 entries (matches upstream
    ``MAC_OS_ROMAN_ENCODING_TABLE``)."""
    assert len(_MAC_OS_ROMAN_DIFFERENCES) == 16


def test_difference_table_codes_are_in_high_byte_range() -> None:
    """All Mac OS Roman differences live above 0x7F — they extend the
    high half of the 256-byte vector. Catches accidental low-ASCII
    overlap with ASCII letters/digits.
    """
    for code, _name in _MAC_OS_ROMAN_DIFFERENCES:
        assert 0x80 <= code <= 0xFF


def test_difference_table_codes_are_unique() -> None:
    codes = [code for code, _name in _MAC_OS_ROMAN_DIFFERENCES]
    assert len(set(codes)) == len(codes)


def test_difference_table_names_are_unique() -> None:
    """The 16 vendor differences each name a distinct glyph — no
    duplicates that would collapse two codes onto the same glyph name.
    """
    names = [name for _code, name in _MAC_OS_ROMAN_DIFFERENCES]
    assert len(set(names)) == len(names)


# ---------- vendor-specific entries are present ----------


def test_apple_logo_at_octal_360() -> None:
    """The Apple logo lives at octal 360 (decimal 240, 0xF0)."""
    enc = MacOSRomanEncoding.INSTANCE
    assert enc.get_name(0o360) == "apple"
    assert enc.get_code("apple") == 0o360


def test_euro_sign_at_octal_333() -> None:
    """Mac OS Roman places Euro at octal 333 (decimal 219, 0xDB)."""
    enc = MacOSRomanEncoding.INSTANCE
    assert enc.get_name(0o333) == "Euro"
    assert enc.get_code("Euro") == 0o333


def test_math_symbols_layered_on_top() -> None:
    enc = MacOSRomanEncoding.INSTANCE
    expected: dict[int, str] = {
        0o255: "notequal",
        0o260: "infinity",
        0o262: "lessequal",
        0o263: "greaterequal",
        0o266: "partialdiff",
        0o267: "summation",
        0o270: "product",
        0o271: "pi",
        0o272: "integral",
        0o275: "Omega",
        0o303: "radical",
        0o305: "approxequal",
        0o306: "Delta",
        0o327: "lozenge",
    }
    for code, name in expected.items():
        assert enc.get_name(code) == name
        assert enc.get_code(name) == code


# ---------- inherited MacRoman entries survive overlay ----------


def test_inherited_lowercase_letters() -> None:
    """ASCII letters live in the low half of the table and are inherited
    untouched from MacRomanEncoding."""
    enc = MacOSRomanEncoding.INSTANCE
    for ch in "abcdefghijklmnopqrstuvwxyz":
        assert enc.get_name(ord(ch)) == ch


def test_inherited_uppercase_letters() -> None:
    enc = MacOSRomanEncoding.INSTANCE
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert enc.get_name(ord(ch)) == ch


def test_inherited_digit_names() -> None:
    enc = MacOSRomanEncoding.INSTANCE
    digits = ["zero", "one", "two", "three", "four",
              "five", "six", "seven", "eight", "nine"]
    for i, name in enumerate(digits):
        assert enc.get_name(0x30 + i) == name


def test_inherited_high_byte_glyph_outside_differences() -> None:
    """A MacRoman high-byte code that is *not* in the differences table
    (e.g. 0x80 = Adieresis) survives the overlay unchanged.
    """
    enc = MacOSRomanEncoding.INSTANCE
    assert enc.get_name(0x80) == "Adieresis"


def test_inherited_copyright_at_a9() -> None:
    enc = MacOSRomanEncoding.INSTANCE
    assert enc.get_name(0xA9) == "copyright"


# ---------- glyph counts ----------


def test_total_glyph_count_at_least_mac_roman() -> None:
    """Mac OS Roman cannot have *fewer* codes than MacRoman — the
    differences table only ever adds or relabels entries.
    """
    assert len(MacOSRomanEncoding.INSTANCE) >= len(MacRomanEncoding.INSTANCE)


def test_size_method_matches_dunder_len() -> None:
    enc = MacOSRomanEncoding.INSTANCE
    assert enc.size() == len(enc)


# ---------- factory wiring ----------


def test_not_resolved_by_get_instance() -> None:
    """Mac OS Roman is *not* a PDF-spec ``/Encoding`` name — it should
    not be returned by :meth:`Encoding.get_instance` (otherwise a PDF
    serializer could mistakenly emit ``/MacOSRomanEncoding``, which is
    not legal). Mirrors upstream's omission from
    ``Encoding.getInstance``.
    """
    assert Encoding.get_instance("MacOSRomanEncoding") is None


def test_not_in_predefined_names() -> None:
    """Sanity check that the class itself doesn't try to register as a
    predefined name.
    """
    # Construct a fresh instance and confirm its (absent) encoding name
    # doesn't slip into the spec-name predicate.
    enc = MacOSRomanEncoding()
    # Inherited from MacRomanEncoding — would be "MacRomanEncoding"
    # since MacOSRomanEncoding doesn't override get_encoding_name.
    # Confirm at least it's not pretending to be a *new* spec name.
    assert enc.get_encoding_name() in ("MacRomanEncoding", None)


# ---------- predicates / containment ----------


def test_contains_apple_glyph() -> None:
    enc = MacOSRomanEncoding.INSTANCE
    assert enc.contains_name("apple")
    assert enc.contains("apple")
    assert "apple" in enc


def test_contains_octal_360() -> None:
    enc = MacOSRomanEncoding.INSTANCE
    assert enc.contains_code(0o360)
    assert 0o360 in enc


def test_unmapped_low_control_returns_notdef() -> None:
    assert MacOSRomanEncoding.INSTANCE.get_name(0x01) == ".notdef"


# ---------- difference vs. MacRoman ----------


def test_differences_relabel_some_macroman_codes() -> None:
    """At least one difference entry actually differs from the
    underlying MacRoman name — confirming the overlay is doing work
    rather than re-asserting identical mappings.
    """
    relabelled: list[tuple[int, str, str]] = []
    for code, new_name in _MAC_OS_ROMAN_DIFFERENCES:
        old = MacRomanEncoding.INSTANCE.get_name(code)
        if old != new_name:
            relabelled.append((code, old, new_name))
    # Most of the differences relabel previously-different codes
    # (e.g. 0o333 = "currency" in MacRoman, "Euro" in Mac OS Roman).
    assert len(relabelled) > 0


def test_overlay_does_not_clobber_letter_a() -> None:
    """Defensive: layering should never relabel ASCII 'A' (0x41)."""
    assert MacOSRomanEncoding.INSTANCE.get_name(0x41) == "A"


# ---------- direct constructor produces equivalent vector ----------


def test_fresh_instance_matches_singleton() -> None:
    """Building a second instance from scratch yields the same glyph
    table — no hidden state carried by the singleton.
    """
    fresh = MacOSRomanEncoding()
    canonical = MacOSRomanEncoding.INSTANCE
    assert fresh.get_code_to_name_map() == canonical.get_code_to_name_map()


def test_fresh_instance_get_cos_object_is_none() -> None:
    assert MacOSRomanEncoding().get_cos_object() is None
