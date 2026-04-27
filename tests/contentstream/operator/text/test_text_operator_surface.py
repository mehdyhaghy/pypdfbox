"""Round-out coverage for the ``text/__init__.py`` re-export surface.

Wave 37 cluster: every operator listed in PDF 32000-1 §9.4 should be
exposed via :mod:`pypdfbox.contentstream.operator.text`. This file
verifies the surface and the operator-name → class binding for each.
"""

from __future__ import annotations

from pypdfbox.contentstream.operator import OperatorProcessor
from pypdfbox.contentstream.operator.text import (
    BeginText,
    EndText,
    MoveText,
    MoveTextSetLeading,
    NextLine,
    SetCharSpacing,
    SetFontAndSize,
    SetHorizontalTextScaling,
    SetMatrix,
    SetTextLeading,
    SetTextRenderingMode,
    SetTextRise,
    SetWordSpacing,
    ShowText,
    ShowTextAdjusted,
    ShowTextLine,
    ShowTextLineAndSpace,
)

# Authoritative (operator-token, processor-class) table for the full
# text-operator surface in §9.4 of ISO 32000-1.
_TEXT_OPERATORS: list[tuple[str, type[OperatorProcessor]]] = [
    # text-object delimiters
    ("BT", BeginText),
    ("ET", EndText),
    # text state
    ("Tc", SetCharSpacing),
    ("Tw", SetWordSpacing),
    ("Tz", SetHorizontalTextScaling),
    ("TL", SetTextLeading),
    ("Tf", SetFontAndSize),
    ("Tr", SetTextRenderingMode),
    ("Ts", SetTextRise),
    # text positioning
    ("Td", MoveText),
    ("TD", MoveTextSetLeading),
    ("Tm", SetMatrix),
    ("T*", NextLine),
    # text showing
    ("Tj", ShowText),
    ("TJ", ShowTextAdjusted),
    ("'", ShowTextLine),
    ('"', ShowTextLineAndSpace),
]


def test_every_text_operator_class_is_an_operator_processor() -> None:
    for _name, cls in _TEXT_OPERATORS:
        assert issubclass(cls, OperatorProcessor), (
            f"{cls.__name__} is not an OperatorProcessor subclass"
        )


def test_every_text_operator_advertises_correct_token() -> None:
    for name, cls in _TEXT_OPERATORS:
        instance = cls()
        assert instance.get_name() == name, (
            f"{cls.__name__}.get_name() == {instance.get_name()!r}, "
            f"expected {name!r}"
        )


def test_text_operator_surface_covers_iso_32000_section_9_4() -> None:
    """The set of operator tokens exposed must equal the §9.4 surface."""
    expected = {
        "BT",
        "ET",
        "Tc",
        "Tw",
        "Tz",
        "TL",
        "Tf",
        "Tr",
        "Ts",
        "Td",
        "TD",
        "Tm",
        "T*",
        "Tj",
        "TJ",
        "'",
        '"',
    }
    actual = {name for name, _ in _TEXT_OPERATORS}
    assert actual == expected
