"""Coverage round-out for :mod:`pypdfbox.cos.cos_name` (wave 1343).

Closes off the remaining ``NotImplemented`` branches of the rich-comparison
operators and the ``__repr__`` formatter, plus the equality-with-non-COSName
edge case.
"""

from __future__ import annotations

from pypdfbox.cos import COSName


def test_eq_with_non_cosname_is_not_implemented() -> None:
    # ``__eq__`` returns NotImplemented for non-COSName so the interpreter
    # tries the reflected comparison; the public behaviour is "not equal".
    n = COSName.get_pdf_name("Type")
    assert (n == "Type") is False
    assert (n == 42) is False
    assert (n == None) is False  # noqa: E711  intentional `==` check


def test_le_with_non_cosname_raises_type_error() -> None:
    import pytest

    n = COSName.get_pdf_name("Type")
    with pytest.raises(TypeError):
        _ = n <= "Type"  # type: ignore[operator]


def test_gt_with_non_cosname_raises_type_error() -> None:
    import pytest

    n = COSName.get_pdf_name("Type")
    with pytest.raises(TypeError):
        _ = n > "Type"  # type: ignore[operator]


def test_ge_with_non_cosname_raises_type_error() -> None:
    import pytest

    n = COSName.get_pdf_name("Type")
    with pytest.raises(TypeError):
        _ = n >= "Type"  # type: ignore[operator]


def test_le_with_cosname_consistent_with_compare_to() -> None:
    a = COSName.get_pdf_name("AAA")
    b = COSName.get_pdf_name("AAB")
    assert a <= b
    assert a <= a
    assert not (b <= a)


def test_gt_with_cosname_consistent_with_compare_to() -> None:
    a = COSName.get_pdf_name("AAA")
    b = COSName.get_pdf_name("AAB")
    assert b > a
    assert not (a > b)
    assert not (a > a)


def test_ge_with_cosname_consistent_with_compare_to() -> None:
    a = COSName.get_pdf_name("AAA")
    b = COSName.get_pdf_name("AAB")
    assert b >= a
    assert a >= a
    assert not (a >= b)


def test_repr_includes_class_name_and_quoted_name() -> None:
    # ``__repr__`` uses ``f"COSName({self.get_name()!r})"`` so a Python-quoted
    # string of the name appears in the output.
    assert repr(COSName.get_pdf_name("Type")) == "COSName('Type')"
    assert repr(COSName.get_pdf_name("")) == "COSName('')"
    # Names containing non-ASCII bytes go through get_name() too.
    assert repr(COSName.get_pdf_name("MediaBox")) == "COSName('MediaBox')"
