"""Wave 1368 — COSName interning, byte encoding and ordering parity.

Round-out tests for paths not yet covered:

* Two-tier registry: predefined static constants survive
  ``clear_resources()``; dynamic names do not.
* ``get_pdf_name`` interning — identical text returns the same instance
  regardless of ``str`` vs ``bytes`` input.
* ``write_pdf`` encodes bytes outside the printable-name set using
  ``#XX`` escapes (e.g. ``/`` → ``#2F``, space → ``#20``).
* ``get_name`` falls back to Latin-1 when the bytes are not valid UTF-8
  (matches PDFBox's ``getName`` substitute behaviour).
* Lexicographic ordering via ``compare_to`` and the ``__lt__`` /
  ``__le__`` / ``__gt__`` / ``__ge__`` comparison operators.
* ``hash_code`` returns a signed 32-bit Java-style hash.
* ``equals`` is byte-array equality.
* ``to_string`` mirrors ``COSName{<text>}``.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSName

# ---------- interning ----------


def test_get_pdf_name_returns_interned_instance_for_str() -> None:
    a = COSName.get_pdf_name("MyName")
    b = COSName.get_pdf_name("MyName")
    assert a is b


def test_get_pdf_name_interns_across_str_and_bytes_input() -> None:
    a = COSName.get_pdf_name("Equal")
    b = COSName.get_pdf_name(b"Equal")
    assert a is b


def test_get_pdf_name_distinct_for_distinct_names() -> None:
    a = COSName.get_pdf_name("First")
    b = COSName.get_pdf_name("Second")
    assert a is not b


def test_static_constants_survive_clear_resources() -> None:
    # ``clear_resources`` wipes the dynamic intern table, which would
    # otherwise leak across tests — modules that captured a dynamic
    # ``COSName`` at import time (e.g. ``PDResources.FONT``) would lose
    # ``is``-equality with fresh lookups. Snapshot and restore the
    # registry around the assertions so unrelated tests stay green.
    snapshot = dict(COSName._name_map)  # noqa: SLF001 - intentional registry snapshot
    try:
        type_constant = COSName.TYPE
        dynamic = COSName.get_pdf_name("RegisteredForThisTest1368")
        assert dynamic is COSName.get_pdf_name("RegisteredForThisTest1368")
        COSName.clear_resources()
        # Static constant identity preserved.
        assert COSName.TYPE is type_constant
        # Dynamic name is no longer in the dynamic map → freshly interned.
        new_dynamic = COSName.get_pdf_name("RegisteredForThisTest1368")
        assert new_dynamic is not dynamic
    finally:
        COSName._name_map.clear()  # noqa: SLF001
        COSName._name_map.update(snapshot)  # noqa: SLF001


# ---------- name accessors ----------


def test_name_property_matches_get_name() -> None:
    n = COSName.get_pdf_name("Foo")
    assert n.name == n.get_name() == "Foo"


def test_get_name_falls_back_to_latin1_for_non_utf8_bytes() -> None:
    raw = bytes([0xC0, 0xC1])  # Invalid UTF-8 start bytes.
    n = COSName.get_pdf_name(raw)
    decoded = n.get_name()
    # Latin-1 maps 0xC0/0xC1 to the corresponding Unicode code points.
    assert decoded == "ÀÁ"


def test_is_empty_only_for_empty_name() -> None:
    assert COSName.get_pdf_name("").is_empty() is True
    assert COSName.get_pdf_name("X").is_empty() is False


def test_get_bytes_returns_copy_not_view() -> None:
    n = COSName.get_pdf_name("Hello")
    a = n.get_bytes()
    b = n.get_bytes()
    assert a == b
    # Mutating ``a`` (it's a bytes — immutable, so this is purely an API check)
    assert a == b"Hello"


# ---------- write_pdf escape handling ----------


def test_write_pdf_emits_simple_name_verbatim() -> None:
    out = io.BytesIO()
    COSName.get_pdf_name("Pages").write_pdf(out)
    assert out.getvalue() == b"/Pages"


def test_write_pdf_escapes_slash_byte() -> None:
    out = io.BytesIO()
    COSName.get_pdf_name("A/B").write_pdf(out)
    # ``/`` (0x2F) is not in the printable-name set.
    assert out.getvalue() == b"/A#2FB"


def test_write_pdf_escapes_space_byte() -> None:
    out = io.BytesIO()
    COSName.get_pdf_name("Foo Bar").write_pdf(out)
    assert out.getvalue() == b"/Foo#20Bar"


def test_write_pdf_escapes_hash_byte() -> None:
    out = io.BytesIO()
    COSName.get_pdf_name("#paren").write_pdf(out)
    # ``#`` (0x23) is not in the printable-name set → escaped to ``#23``.
    assert out.getvalue() == b"/#23paren"


def test_write_pdf_passes_through_allowed_punctuation() -> None:
    out = io.BytesIO()
    COSName.get_pdf_name("name-_.+").write_pdf(out)
    # ``-`` (0x2D), ``_`` (0x5F), ``.`` (0x2E), ``+`` (0x2B) are
    # all in the printable-name set and pass through verbatim.
    assert out.getvalue() == b"/name-_.+"


def test_write_pdf_escapes_high_bytes_as_uppercase_hex() -> None:
    out = io.BytesIO()
    COSName.get_pdf_name(bytes([0xC3, 0xA9])).write_pdf(out)
    # 0xC3 → #C3, 0xA9 → #A9. Both uppercase.
    assert out.getvalue() == b"/#C3#A9"


# ---------- ordering ----------


def test_compare_to_lexicographic_byte_order() -> None:
    a = COSName.get_pdf_name("aaa")
    b = COSName.get_pdf_name("aab")
    assert a.compare_to(b) < 0
    assert b.compare_to(a) > 0
    assert a.compare_to(a) == 0


def test_compare_to_handles_none() -> None:
    a = COSName.get_pdf_name("aaa")
    assert a.compare_to(None) == 1


def test_compare_to_handles_unsigned_byte_diff() -> None:
    a = COSName.get_pdf_name(bytes([0x7F]))
    b = COSName.get_pdf_name(bytes([0x80]))
    # 0x80 sorts after 0x7F when compared as unsigned bytes
    assert a.compare_to(b) < 0


def test_compare_to_handles_different_lengths() -> None:
    short = COSName.get_pdf_name("aa")
    long_name = COSName.get_pdf_name("aaa")
    # When a is a prefix of b, len(a) < len(b) returns negative.
    assert short.compare_to(long_name) < 0


def test_dunder_lt_le_gt_ge_via_comparators() -> None:
    a = COSName.get_pdf_name("alpha")
    b = COSName.get_pdf_name("beta")
    assert a < b
    assert a <= b
    assert b > a
    assert b >= a
    assert a <= COSName.get_pdf_name("alpha")
    assert a >= COSName.get_pdf_name("alpha")


def test_dunder_lt_with_non_name_is_notimplemented() -> None:
    n = COSName.get_pdf_name("x")
    # Python returns NotImplemented, which lets reflection happen; here
    # comparing to a str will raise TypeError.
    with pytest.raises(TypeError):
        _ = n < "anything"  # noqa: B015


def test_sorted_list_uses_unsigned_byte_order() -> None:
    names = [
        COSName.get_pdf_name(bytes([0x80])),
        COSName.get_pdf_name(bytes([0x40])),
        COSName.get_pdf_name(bytes([0xFF])),
        COSName.get_pdf_name(bytes([0x20])),
    ]
    sorted_names = sorted(names)
    sorted_byte_values = [n.get_bytes()[0] for n in sorted_names]
    assert sorted_byte_values == [0x20, 0x40, 0x80, 0xFF]


# ---------- equality / hashing ----------


def test_equals_byte_equality_only() -> None:
    a = COSName.get_pdf_name("hello")
    b = COSName.get_pdf_name("hello")
    assert a.equals(b) is True
    assert a.equals("hello") is False
    assert a.equals(42) is False
    assert a.equals(None) is False


def test_dunder_eq_with_non_name_returns_notimplemented() -> None:
    n = COSName.get_pdf_name("x")
    assert (n == "x") is False
    assert (n == None) is False  # noqa: E711 - explicit comparison


def test_hash_code_is_signed_int32() -> None:
    # Empty bytes → ``h = 1`` (Java's seed).
    empty = COSName.get_pdf_name("")
    assert empty.hash_code() == 1


def test_hash_code_for_single_ascii_byte() -> None:
    # ``"A"`` (0x41) → ``31 * 1 + 0x41 = 96``.
    n = COSName.get_pdf_name("A")
    assert n.hash_code() == 96


def test_hash_code_signed_for_high_byte() -> None:
    # ``bytes([0x80])`` → signed -128. ``31 * 1 + (-128) = -97``.
    n = COSName.get_pdf_name(bytes([0x80]))
    assert n.hash_code() == -97


def test_python_hash_matches_byte_hash() -> None:
    a = COSName.get_pdf_name("hash-me")
    assert hash(a) == hash(b"hash-me")


# ---------- str / repr ----------


def test_to_string_format() -> None:
    n = COSName.get_pdf_name("Hello")
    assert n.to_string() == "COSName{Hello}"


def test_str_prefixes_slash() -> None:
    n = COSName.get_pdf_name("Hello")
    assert str(n) == "/Hello"


def test_repr_contains_name() -> None:
    n = COSName.get_pdf_name("Hello")
    assert "Hello" in repr(n)
