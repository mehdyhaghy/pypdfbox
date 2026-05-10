"""Wave 1275 — PDField Java-named equality / hash / string helpers."""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField


def _make_field(name: str = "f") -> PDTextField:
    f = PDTextField(PDAcroForm())
    f.set_partial_name(name)
    return f


def test_equals_self_returns_true() -> None:
    f = _make_field()
    assert f.equals(f) is True


def test_equals_distinct_field_returns_false() -> None:
    a = _make_field("a")
    b = _make_field("b")
    assert a.equals(b) is False


def test_equals_non_field_returns_false() -> None:
    assert _make_field().equals("not-a-field") is False
    assert _make_field().equals(None) is False


def test_equals_same_dictionary_returns_true() -> None:
    # Two PDField wrappers around the same backing COSDictionary compare
    # equal — Java identity-via-COSDictionary semantics.
    form = PDAcroForm()
    a = PDTextField(form)
    a.set_partial_name("shared")
    b = PDTextField(form, a.get_cos_object())
    assert a.equals(b) is True


def test_hash_code_stable_per_instance() -> None:
    f = _make_field()
    assert f.hash_code() == f.hash_code()


def test_hash_code_equal_when_equals_true() -> None:
    form = PDAcroForm()
    a = PDTextField(form)
    a.set_partial_name("shared")
    b = PDTextField(form, a.get_cos_object())
    assert a.equals(b) is True
    assert a.hash_code() == b.hash_code()


def test_to_string_matches_str() -> None:
    f = _make_field("topfield")
    assert f.to_string() == str(f)


def test_to_string_includes_class_and_value() -> None:
    f = _make_field("hello")
    rendered = f.to_string()
    assert "PDTextField" in rendered
    assert "hello" in rendered
    assert "type:" in rendered
    assert "value:" in rendered
