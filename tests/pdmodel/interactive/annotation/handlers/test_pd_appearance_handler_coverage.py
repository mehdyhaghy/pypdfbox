"""Coverage-boost tests for ``PDAppearanceHandler`` (the ABC strategy
interface at ``pypdfbox.pdmodel.interactive.annotation.handlers.pd_appearance_handler``).

The base file is tiny (an ABC with three abstract hooks and one default
helper). Existing handler-subclass tests don't exercise the default
:meth:`generate_appearance_streams` aggregator nor the abstractmethod
enforcement directly, leaving lines 31-33 uncovered. These tests close
those gaps with a concrete subclass that records every call.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.annotation.handlers.pd_appearance_handler import (
    PDAppearanceHandler,
)


class _RecordingHandler(PDAppearanceHandler):
    """Concrete subclass: records ordered call names so we can assert on
    the order the default :meth:`generate_appearance_streams` dispatches.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_normal_appearance(self) -> None:
        self.calls.append("normal")

    def generate_rollover_appearance(self) -> None:
        self.calls.append("rollover")

    def generate_down_appearance(self) -> None:
        self.calls.append("down")


def test_pd_appearance_handler_is_abstract_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        PDAppearanceHandler()  # type: ignore[abstract]


def test_partial_subclass_missing_abstract_method_still_raises() -> None:
    class _Partial(PDAppearanceHandler):
        def generate_normal_appearance(self) -> None:
            return None

        # Intentionally omits rollover + down.

    with pytest.raises(TypeError):
        _Partial()  # type: ignore[abstract]


def test_generate_appearance_streams_calls_all_three_in_order() -> None:
    handler = _RecordingHandler()
    handler.generate_appearance_streams()
    assert handler.calls == ["normal", "rollover", "down"]


def test_generate_appearance_streams_returns_none() -> None:
    handler = _RecordingHandler()
    assert handler.generate_appearance_streams() is None


def test_generate_appearance_streams_can_be_called_multiple_times() -> None:
    handler = _RecordingHandler()
    handler.generate_appearance_streams()
    handler.generate_appearance_streams()
    assert handler.calls == [
        "normal",
        "rollover",
        "down",
        "normal",
        "rollover",
        "down",
    ]


def test_subclass_overrides_aggregator_is_allowed() -> None:
    """Subclasses are free to override the default aggregator — verify
    that doing so is honoured (no implicit dispatch through the base)."""

    class _Override(_RecordingHandler):
        def generate_appearance_streams(self) -> None:
            self.calls.append("override")

    handler = _Override()
    handler.generate_appearance_streams()
    assert handler.calls == ["override"]


def test_all_export_lists_appearance_handler() -> None:
    from pypdfbox.pdmodel.interactive.annotation.handlers import (
        pd_appearance_handler as module,
    )

    assert "PDAppearanceHandler" in module.__all__
