from __future__ import annotations

import pytest

import tests.fontbox.ttf.test_kerning_subtable as target


def test_invalid_arity_test_helper_assertion_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def accepts_any_arity(_self: object, *_args: object) -> int:
        return 0

    monkeypatch.setattr(target.KerningSubtable, "get_kerning", accepts_any_arity)

    with pytest.raises(AssertionError, match="expected TypeError"):
        target.test_get_kerning_invalid_arity_raises()
