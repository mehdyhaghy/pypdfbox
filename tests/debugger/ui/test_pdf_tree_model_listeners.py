"""Hand-written tests for :class:`PDFTreeModel` listener registration."""

from pypdfbox.debugger.ui import PDFTreeModel


def test_add_listener_then_fire_invokes_once() -> None:
    model = PDFTreeModel()
    calls: list[PDFTreeModel] = []

    def listener(source: PDFTreeModel) -> None:
        calls.append(source)

    model.add_tree_model_listener(listener)
    model._fire_tree_changed()
    assert calls == [model]


def test_remove_listener_stops_notifications() -> None:
    model = PDFTreeModel()
    calls: list[PDFTreeModel] = []

    def listener(source: PDFTreeModel) -> None:
        calls.append(source)

    model.add_tree_model_listener(listener)
    model.remove_tree_model_listener(listener)
    model._fire_tree_changed()
    assert calls == []


def test_add_same_listener_twice_only_registers_once() -> None:
    model = PDFTreeModel()
    calls: list[PDFTreeModel] = []

    def listener(source: PDFTreeModel) -> None:
        calls.append(source)

    model.add_tree_model_listener(listener)
    model.add_tree_model_listener(listener)
    model._fire_tree_changed()
    assert len(calls) == 1


def test_remove_unknown_listener_is_silent() -> None:
    model = PDFTreeModel()

    def listener(source: PDFTreeModel) -> None:
        pass

    # Must not raise even though ``listener`` was never added.
    model.remove_tree_model_listener(listener)
