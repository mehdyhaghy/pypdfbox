"""Wave 1396 branch-coverage tests for ``Type2CharString.convert_type2_command``.

Closes False-branch arrows for the flex / curve operators that guard
their bodies with ``if len(numbers) >= N:``. Calling each with too few
operands exercises the False arm (line ARROW->418, the shared loop tail).

Arrows closed:
* 353->418 — ``hflex`` insufficient operands
* 365->418 — ``flex`` insufficient operands
* 370->418 — ``hflex1`` insufficient operands
* 389->418 — ``flex1`` insufficient operands
* 407->418 — ``rcurveline`` insufficient operands
* 411->418 — ``rlinecurve`` insufficient operands
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.type2_char_string import Type2CharString


@pytest.fixture
def cs() -> Type2CharString:
    return Type2CharString(
        font=None,
        font_name="Test",
        glyph_name="glyph",
        gid=0,
        sequence=[],
    )


@pytest.mark.parametrize(
    ("op", "args"),
    [
        ("hflex", []),
        ("hflex", [1.0, 2.0, 3.0]),  # needs 7
        ("flex", []),
        ("flex", [1.0] * 11),  # needs 12
        ("hflex1", []),
        ("hflex1", [1.0] * 8),  # needs 9
        ("flex1", []),
        ("flex1", [1.0] * 10),  # needs 11
        ("rcurveline", []),
        ("rcurveline", [1.0]),  # needs 2
        ("rlinecurve", []),
        ("rlinecurve", [1.0] * 5),  # needs 6
    ],
)
def test_convert_type2_command_insufficient_operands_skips_body(
    cs: Type2CharString,
    op: str,
    args: list,
) -> None:
    """Operator body is skipped when operand count is below the spec
    minimum; the method must still return an empty list.

    Closes the False arms at lines 353->418, 365->418, 370->418,
    389->418, 407->418, 411->418.
    """
    result = cs.convert_type2_command(list(args), op)
    # The dispatcher unconditionally returns ``[]`` after the operator
    # body (or skipped body) runs.
    assert result == []
