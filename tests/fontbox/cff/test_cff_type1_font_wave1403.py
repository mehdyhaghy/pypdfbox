"""Wave 1403 — branch round-out for :class:`CFFType1Font`.

Closes the partial arc ``[288,291]`` — the ExpertEncoding name-lookup
``for`` loop in :meth:`name_to_code` exhausting without a match, falling
through to the ``-1`` return.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font


def test_name_to_code_expert_encoding_unmatched_name_returns_minus_one() -> None:
    """An ExpertEncoding font whose ``name_to_code`` lookup never matches
    exhausts the ``for`` loop and returns -1 ([288,291] arc)."""
    font = CFFType1Font()
    font.set_encoding("ExpertEncoding")
    assert font.name_to_code("__definitely_not_in_expert_encoding__") == -1


def test_name_to_code_expert_encoding_matched_name_still_resolves() -> None:
    """Companion: a real ExpertEncoding glyph name resolves to its code,
    confirming the loop's matching arm is intact."""
    font = CFFType1Font()
    font.set_encoding("ExpertEncoding")
    # "asuperior" is a known ExpertEncoding name (Adobe Technote #5176).
    assert font.name_to_code("asuperior") >= 0
