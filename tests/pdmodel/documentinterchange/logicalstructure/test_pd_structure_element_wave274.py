from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)

_P = COSName.get_pdf_name("P")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]


def _make_root_with_role_map(role_map: dict[str, str]) -> COSDictionary:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    mapped_roles = COSDictionary()
    for source, target in role_map.items():
        mapped_roles.set_name(source, target)
    root.set_item(_ROLE_MAP, mapped_roles)
    return root


def _attach_to_role_map(
    elem: PDStructureElement, role_map: dict[str, str]
) -> PDStructureElement:
    elem.get_cos_object().set_item(_P, _make_root_with_role_map(role_map))
    return elem


def _category_flags(elem: PDStructureElement) -> tuple[bool, bool, bool, bool]:
    return (
        elem.is_grouping_level(),
        elem.is_block_level(),
        elem.is_inline_level(),
        elem.is_illustration_level(),
    )


@pytest.mark.parametrize(
    ("structure_type", "expected_flags"),
    [
        ("Document", (True, False, False, False)),
        ("Div", (True, False, False, False)),
        ("P", (False, True, False, False)),
        ("H1", (False, True, False, False)),
        ("Table", (False, True, False, False)),
        ("Span", (False, False, True, False)),
        ("Link", (False, False, True, False)),
        ("Figure", (False, False, False, True)),
        ("Formula", (False, False, False, True)),
        ("MyCustomType", (False, False, False, False)),
    ],
)
def test_category_predicates_classify_direct_standard_types(
    structure_type: str, expected_flags: tuple[bool, bool, bool, bool]
) -> None:
    elem = PDStructureElement(structure_type=structure_type)

    assert _category_flags(elem) == expected_flags


def test_category_predicates_are_false_when_structure_type_absent() -> None:
    elem = PDStructureElement()

    assert _category_flags(elem) == (False, False, False, False)


@pytest.mark.parametrize(
    ("custom_type", "standard_type", "expected_flags"),
    [
        ("MyDoc", "Document", (True, False, False, False)),
        ("MyParagraph", "P", (False, True, False, False)),
        ("MyLink", "Link", (False, False, True, False)),
        ("MyFigure", "Figure", (False, False, False, True)),
    ],
)
def test_category_predicates_resolve_custom_types_through_role_map(
    custom_type: str,
    standard_type: str,
    expected_flags: tuple[bool, bool, bool, bool],
) -> None:
    elem = _attach_to_role_map(
        PDStructureElement(structure_type=custom_type),
        {custom_type: standard_type},
    )

    assert elem.get_standard_structure_type() == standard_type
    assert _category_flags(elem) == expected_flags


def test_category_predicates_use_single_hop_role_map_before_classifying() -> None:
    # Upstream getStandardStructureType() is a single hop: /S=MyBodyCopy maps
    # to ParagraphAlias and resolution stops there (it does NOT chase
    # ParagraphAlias -> P). ParagraphAlias is not a standard type, so no
    # category predicate fires. Verified against the live oracle.
    elem = _attach_to_role_map(
        PDStructureElement(structure_type="MyBodyCopy"),
        {"MyBodyCopy": "ParagraphAlias", "ParagraphAlias": "P"},
    )

    assert elem.get_standard_structure_type() == "ParagraphAlias"
    assert _category_flags(elem) == (False, False, False, False)


def test_category_predicates_do_not_classify_unresolved_custom_role() -> None:
    elem = _attach_to_role_map(
        PDStructureElement(structure_type="MyBodyCopy"),
        {"MyBodyCopy": "ParagraphAlias"},
    )

    assert elem.get_standard_structure_type() == "ParagraphAlias"
    assert _category_flags(elem) == (False, False, False, False)
