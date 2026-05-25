"""Wave 1397 branch-coverage tests for ``pypdfbox.tools.listbookmarks``.

Closes False-branch arrows in ``_resolve_page_number`` and
``_describe_item``:

* ``_resolve_page_number`` 99->103 — Page destination with ``retrieve_page_number`` < 0
* ``_describe_item`` 129->135 — ``/Dest`` resolves to None
* ``_describe_item`` 140->151 — GoTo action's destination resolves to None
* ``_describe_item`` 144->151 — GoTo action carries no destination at all
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.tools import listbookmarks


class _StubDestPage(PDPageDestination):
    def __init__(self, page: int) -> None:
        super().__init__()
        self._page = page

    def retrieve_page_number(self, doc: object) -> int:  # noqa: ARG002
        return self._page


class _StubGoToAction(PDActionGoTo):
    """GoTo action whose ``get_destination`` is hand-stubbed so we
    don't have to go through ``set_destination`` (which validates the
    backing array structure and refuses our test stubs)."""

    def __init__(self, dest: object | None) -> None:
        super().__init__()
        self._stub_dest = dest

    def get_destination(self) -> object | None:  # type: ignore[override]
        return self._stub_dest


class _StubItem:
    def __init__(self, destination: object | None, action: object | None) -> None:
        self._destination = destination
        self._action = action

    def get_destination(self) -> object | None:
        return self._destination

    def get_action(self) -> object | None:
        return self._action

    def find_destination_page(self, document: object) -> object | None:  # noqa: ARG002
        return None


def test_resolve_page_number_returns_none_for_unresolved_page_destination() -> None:
    """Closes the False arm of ``if isinstance(dest, PDPageDestination)``
    when retrieve_page_number returns -1."""
    dest = _StubDestPage(-1)
    assert listbookmarks._resolve_page_number(object(), dest) is None  # noqa: SLF001


def test_resolve_page_number_returns_none_for_non_page_non_named_destination() -> None:
    """Closes 99->103: ``dest`` is neither a PDPageDestination nor a
    PDNamedDestination — both isinstance guards fail and the function
    falls through to ``return None``."""

    class _OtherDest:
        """A bare object — neither PDPageDestination nor PDNamedDestination."""

    assert listbookmarks._resolve_page_number(object(), _OtherDest()) is None  # noqa: SLF001


def test_describe_item_skips_dest_when_resolved_is_none() -> None:
    """Closes 129->135: /Dest is a PDPageDestination but resolves to
    -1 (not in document) — no ``Destination page:`` line is appended."""
    dest = _StubDestPage(-1)
    item = _StubItem(destination=dest, action=None)
    page_num, info = listbookmarks._describe_item(object(), item)  # noqa: SLF001
    assert page_num is None
    # No "Destination page:" line — the resolve failed.
    assert all(not line.startswith("Destination page:") for line in info)


def test_describe_item_skips_goto_dest_when_resolved_is_none() -> None:
    """Closes 140->151: GoTo /A whose destination is a PDPageDestination
    but resolves to -1 — no ``Destination page:`` line."""
    action_dest = _StubDestPage(-1)
    action = _StubGoToAction(action_dest)
    item = _StubItem(destination=None, action=action)
    page_num, info = listbookmarks._describe_item(object(), item)  # noqa: SLF001
    assert page_num is None
    assert all(not line.startswith("Destination page:") for line in info)


def test_describe_item_goto_action_without_destination() -> None:
    """Closes 144->151: GoTo /A with no destination at all (the
    ``action_dest is not None`` arm short-circuits)."""
    action = _StubGoToAction(None)
    item = _StubItem(destination=None, action=action)
    page_num, info = listbookmarks._describe_item(object(), item)  # noqa: SLF001
    assert page_num is None
    # No Destination class line either — action_dest is None.
    assert all(not line.startswith("Destination class:") for line in info)
