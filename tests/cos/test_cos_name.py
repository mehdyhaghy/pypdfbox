from __future__ import annotations

from pypdfbox.cos import COSName


def test_interning_returns_same_instance() -> None:
    a = COSName.get_pdf_name("Type")
    b = COSName.get_pdf_name("Type")
    assert a is b


def test_constructor_also_interns() -> None:
    assert COSName("Foo") is COSName("Foo")
    assert COSName("Foo") is COSName.get_pdf_name("Foo")


def test_distinct_names_are_distinct_instances() -> None:
    assert COSName.get_pdf_name("A") is not COSName.get_pdf_name("B")


def test_name_property_round_trips() -> None:
    n = COSName.get_pdf_name("MediaBox")
    assert n.name == "MediaBox"
    assert n.get_name() == "MediaBox"


def test_equality_and_hashing() -> None:
    a = COSName.get_pdf_name("Pages")
    b = COSName.get_pdf_name("Pages")
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_str_includes_leading_slash() -> None:
    assert str(COSName.get_pdf_name("Length")) == "/Length"


def test_predefined_constants_present() -> None:
    assert COSName.TYPE.name == "Type"  # type: ignore[attr-defined]
    assert COSName.PAGES.name == "Pages"  # type: ignore[attr-defined]
    assert COSName.STRUCT_TREE_ROOT.name == "StructTreeRoot"  # type: ignore[attr-defined]


def test_predefined_match_get_pdf_name() -> None:
    assert COSName.TYPE is COSName.get_pdf_name("Type")  # type: ignore[attr-defined]


def test_predefined_encoding_constants() -> None:
    # Upstream exposes interned ``COSName`` constants for the predefined
    # ``/Encoding`` names; mirror those for parity (referenced by the
    # encoding subclasses' ``getCOSObject`` overrides).
    assert COSName.STANDARD_ENCODING is COSName.get_pdf_name("StandardEncoding")  # type: ignore[attr-defined]
    assert COSName.MAC_EXPERT_ENCODING is COSName.get_pdf_name("MacExpertEncoding")  # type: ignore[attr-defined]
    assert COSName.MAC_ROMAN_ENCODING is COSName.get_pdf_name("MacRomanEncoding")  # type: ignore[attr-defined]
    assert COSName.WIN_ANSI_ENCODING is COSName.get_pdf_name("WinAnsiEncoding")  # type: ignore[attr-defined]


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    n = COSName.get_pdf_name("Foo")
    n.accept(v)
    assert v.calls == [("name", n)]


def test_is_empty_true_for_empty_string() -> None:
    assert COSName.get_pdf_name("").is_empty() is True


def test_is_empty_false_for_non_empty_string() -> None:
    assert COSName.get_pdf_name("Type").is_empty() is False


def test_is_empty_for_empty_bytes() -> None:
    assert COSName.get_pdf_name(b"").is_empty() is True


def test_compare_to_returns_zero_for_equal_names() -> None:
    a = COSName.get_pdf_name("Type")
    b = COSName.get_pdf_name("Type")
    assert a.compare_to(b) == 0


def test_compare_to_lexicographic_ordering() -> None:
    a = COSName.get_pdf_name("AAA")
    b = COSName.get_pdf_name("AAB")
    assert a.compare_to(b) < 0
    assert b.compare_to(a) > 0


def test_compare_to_shorter_name_sorts_first() -> None:
    a = COSName.get_pdf_name("A")
    b = COSName.get_pdf_name("AA")
    assert a.compare_to(b) < 0


def test_compare_to_uses_unsigned_byte_comparison() -> None:
    # 0x80 (high-bit set) must sort after 0x7F (ASCII), as in PDFBox's
    # unsigned comparison.
    high = COSName.get_pdf_name(b"\x80")
    low = COSName.get_pdf_name(b"\x7f")
    assert high.compare_to(low) > 0
    assert low.compare_to(high) < 0


def test_compare_to_with_none_returns_one() -> None:
    assert COSName.get_pdf_name("Type").compare_to(None) == 1


def test_ordering_with_lt_operator() -> None:
    names = [
        COSName.get_pdf_name("C"),
        COSName.get_pdf_name("A"),
        COSName.get_pdf_name("B"),
    ]
    sorted_names = sorted(names)
    assert [n.get_name() for n in sorted_names] == ["A", "B", "C"]


def test_ordering_operators_only_compare_cosnames() -> None:
    n = COSName.get_pdf_name("Type")
    # Comparing with non-COSName must raise TypeError, mirroring Java's
    # generic Comparable<COSName> bound.
    import pytest

    with pytest.raises(TypeError):
        _ = n < "Type"  # type: ignore[operator]


def test_clear_resources_drops_dynamic_names() -> None:
    # Dynamically interned names lose their slot after clear_resources().
    # Snapshot/restore the dynamic map so we don't break interning identity
    # for other tests that expect `COSName(x) is COSName(x)`.
    saved = dict(COSName._name_map)
    try:
        before = COSName.get_pdf_name("ClearResourcesProbe")
        COSName.clear_resources()
        after = COSName.get_pdf_name("ClearResourcesProbe")
        assert before is not after
        assert before == after
    finally:
        COSName._name_map.clear()
        COSName._name_map.update(saved)


def test_equals_byte_array_equality() -> None:
    a = COSName.get_pdf_name("Type")
    b = COSName.get_pdf_name("Type")
    c = COSName.get_pdf_name("Pages")
    assert a.equals(b) is True
    assert a.equals(c) is False


def test_equals_returns_false_for_non_cosname() -> None:
    n = COSName.get_pdf_name("Type")
    assert n.equals("Type") is False
    assert n.equals(None) is False
    assert n.equals(b"Type") is False


def test_hash_code_matches_java_arrays_hashcode_recipe() -> None:
    # Java's Arrays.hashCode(new byte[]{}) is 1.
    assert COSName.get_pdf_name(b"").hash_code() == 1
    # Java's Arrays.hashCode("A".getBytes(UTF_8)) ==
    #   31*1 + (int)'A' == 31 + 65 == 96
    assert COSName.get_pdf_name("A").hash_code() == 96
    # Java's Arrays.hashCode("AB".getBytes(UTF_8)) ==
    #   31*96 + (int)'B' == 2976 + 66 == 3042
    assert COSName.get_pdf_name("AB").hash_code() == 3042


def test_hash_code_signed_byte_widening_for_high_bit() -> None:
    # Java widens bytes as signed: 0x80 → -128. Arrays.hashCode({0x80}) ==
    #   31*1 + (-128) == -97
    assert COSName.get_pdf_name(b"\x80").hash_code() == -97


def test_hash_code_equal_names_have_equal_hash() -> None:
    assert COSName.get_pdf_name("Pages").hash_code() == COSName.get_pdf_name("Pages").hash_code()


def test_to_string_format() -> None:
    # COSName.toString() == "COSName{" + getName() + "}"
    assert COSName.get_pdf_name("Type").to_string() == "COSName{Type}"
    assert COSName.get_pdf_name("").to_string() == "COSName{}"


def test_to_string_distinct_from_str() -> None:
    # Java-style ``to_string()`` returns the COSName{...} form, while Python
    # ``__str__`` keeps the leading-slash convention used in repr/print.
    n = COSName.get_pdf_name("Length")
    assert n.to_string() == "COSName{Length}"
    assert str(n) == "/Length"


def test_clear_resources_preserves_predefined_constants() -> None:
    # Predefined static constants live in the common-name map and survive
    # clear_resources(), mirroring upstream PDFBox.
    saved = dict(COSName._name_map)
    try:
        type_before = COSName.TYPE  # type: ignore[attr-defined]
        COSName.clear_resources()
        assert COSName.get_pdf_name("Type") is type_before
        assert COSName.TYPE is type_before  # type: ignore[attr-defined]
    finally:
        COSName._name_map.clear()
        COSName._name_map.update(saved)
