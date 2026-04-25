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


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    n = COSName.get_pdf_name("Foo")
    n.accept(v)
    assert v.calls == [("name", n)]
