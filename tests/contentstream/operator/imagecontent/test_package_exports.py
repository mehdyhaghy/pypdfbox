from __future__ import annotations

import pypdfbox.contentstream.operator.imagecontent as imagecontent_pkg


def test_all_lists_exactly_three_operator_classes() -> None:
    assert sorted(imagecontent_pkg.__all__) == [
        "BeginInlineImage",
        "BeginInlineImageData",
        "EndInlineImage",
    ]


def test_every_all_entry_is_resolvable_on_the_package() -> None:
    for name in imagecontent_pkg.__all__:
        assert hasattr(imagecontent_pkg, name), (
            f"package missing exported name {name!r}"
        )


def test_each_export_is_a_class() -> None:
    for name in imagecontent_pkg.__all__:
        attr = getattr(imagecontent_pkg, name)
        assert isinstance(attr, type), (
            f"{name!r} is not a class: {type(attr).__name__}"
        )
