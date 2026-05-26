import pytest

from pypdfbox.jbig2.util.combination_operator import CombinationOperator


def test_members_exist():
    assert CombinationOperator.OR
    assert CombinationOperator.AND
    assert CombinationOperator.XOR
    assert CombinationOperator.XNOR
    assert CombinationOperator.REPLACE


def test_member_values_match_operator_codes():
    assert CombinationOperator.OR.value == 0
    assert CombinationOperator.AND.value == 1
    assert CombinationOperator.XOR.value == 2
    assert CombinationOperator.XNOR.value == 3
    assert CombinationOperator.REPLACE.value == 4


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0, CombinationOperator.OR),
        (1, CombinationOperator.AND),
        (2, CombinationOperator.XOR),
        (3, CombinationOperator.XNOR),
        (4, CombinationOperator.REPLACE),
    ],
)
def test_translate_operator_code_to_enum(code, expected):
    assert CombinationOperator.translate_operator_code_to_enum(code) == expected


def test_translate_unknown_code_defaults_to_replace():
    # the Java switch falls through to REPLACE for any code not in 0..3
    assert (
        CombinationOperator.translate_operator_code_to_enum(5)
        == CombinationOperator.REPLACE
    )
    assert (
        CombinationOperator.translate_operator_code_to_enum(99)
        == CombinationOperator.REPLACE
    )


def test_distinct_members():
    members = {
        CombinationOperator.OR,
        CombinationOperator.AND,
        CombinationOperator.XOR,
        CombinationOperator.XNOR,
        CombinationOperator.REPLACE,
    }
    assert len(members) == 5
