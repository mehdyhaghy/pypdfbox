from enum import Enum


class CombinationOperator(Enum):
    """The available logical operators defined in the JBIG2 ISO standard.

    The enum member values mirror the operator codes used by the standard
    (OR=0, AND=1, XOR=2, XNOR=3, REPLACE=4), matching the Java enum ordinals.
    """

    OR = 0
    AND = 1
    XOR = 2
    XNOR = 3
    REPLACE = 4

    @staticmethod
    def translate_operator_code_to_enum(combination_operator_code: int) -> CombinationOperator:
        if combination_operator_code == 0:
            return CombinationOperator.OR
        if combination_operator_code == 1:
            return CombinationOperator.AND
        if combination_operator_code == 2:
            return CombinationOperator.XOR
        if combination_operator_code == 3:
            return CombinationOperator.XNOR
        return CombinationOperator.REPLACE
