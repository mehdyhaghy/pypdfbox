from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from tests.pdmodel import test_tail_sweep_wave841 as wave841


def test_wave1102_wave841_other_destination_cos_object_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolve_via_cos_object(
        self: PDActionEmbeddedGoTo,
        _document: PDDocument,
    ) -> None:
        destination = self.get_d()
        assert destination is not None
        cos_object = destination.get_cos_object()
        assert isinstance(cos_object, COSDictionary)
        return None

    monkeypatch.setattr(
        PDActionEmbeddedGoTo,
        "_resolve_final_destination",
        resolve_via_cos_object,
    )

    wave841.test_wave841_embedded_goto_non_page_non_named_destination_resolves_absent()
