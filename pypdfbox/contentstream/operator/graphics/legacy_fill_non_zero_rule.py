from __future__ import annotations

from .. import OperatorName
from .fill_non_zero_rule import FillNonZeroRule


class LegacyFillNonZeroRule(FillNonZeroRule):
    """``F`` — Fill the path using the non-zero winding rule.
    Included only for compatibility with Acrobat. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.LegacyFillNonZeroRule``
    (upstream lines 28–40).

    Subclasses :class:`FillNonZeroRule` and only overrides the operator
    name so the registry sees the legacy ``F`` token.
    """

    OPERATOR_NAME = OperatorName.LEGACY_FILL_NON_ZERO

    def get_name(self) -> str:
        return OperatorName.LEGACY_FILL_NON_ZERO


__all__ = ["LegacyFillNonZeroRule"]
