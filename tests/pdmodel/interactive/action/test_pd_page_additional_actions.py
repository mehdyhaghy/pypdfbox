from __future__ import annotations

from pypdfbox.pdmodel.interactive.action import (
    PDActionNamed,
    PDActionURI,
    PDPageAdditionalActions,
)


def test_page_additional_actions_open_close_round_trip() -> None:
    actions = PDPageAdditionalActions()
    open_action = PDActionURI()
    open_action.set_uri("https://example.test/open")
    close_action = PDActionNamed()
    close_action.set_n("NextPage")

    actions.set_o(open_action)
    actions.set_c(close_action)

    resolved_open = actions.get_o()
    assert isinstance(resolved_open, PDActionURI)
    assert resolved_open.get_uri() == "https://example.test/open"

    resolved_close = actions.get_c()
    assert isinstance(resolved_close, PDActionNamed)
    assert resolved_close.get_n() == "NextPage"
