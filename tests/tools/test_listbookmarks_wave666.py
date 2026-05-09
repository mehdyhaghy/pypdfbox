from __future__ import annotations

import io

from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination import PDDestination
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.tools import listbookmarks


class _UnresolvedPageDestination(PDPageDestination):
    def retrieve_page_number(self, document: object | None = None) -> int:
        return -1


class _ResolvedPageDestination(PDPageDestination):
    def retrieve_page_number(self, document: object | None = None) -> int:
        return 2


class _OtherDestination(PDDestination):
    def get_cos_object(self) -> object:
        return object()


class _Catalog:
    def __init__(self, resolved: object) -> None:
        self.resolved = resolved

    def find_named_destination_page(self, dest: PDNamedDestination) -> object:
        return self.resolved


class _Document:
    def __init__(self, resolved_named_destination: object = object()) -> None:
        self.catalog = _Catalog(resolved_named_destination)

    def get_document_catalog(self) -> _Catalog:
        return self.catalog


class _GoTo(PDActionGoTo):
    def __init__(self, destination: object) -> None:
        self.destination = destination

    def get_destination(self) -> object:
        return self.destination


class _Item:
    def __init__(
        self,
        *,
        title: str = "Bookmark",
        action: object | None = None,
        destination: object | None = None,
    ) -> None:
        self.title = title
        self.action = action
        self.destination = destination

    def get_destination(self) -> object | None:
        return self.destination

    def get_action(self) -> object | None:
        return self.action

    def find_destination_page(self, document: object) -> None:
        return None

    def get_title(self) -> str:
        return self.title

    def get_first_child(self) -> None:
        return None

    def get_next_sibling(self) -> None:
        return None


class _BookmarkRoot:
    def __init__(self, item: _Item) -> None:
        self.item = item

    def get_first_child(self) -> _Item:
        return self.item


def test_wave666_resolve_page_number_returns_none_for_unresolved_page_dest() -> None:
    assert (
        listbookmarks._resolve_page_number(  # noqa: SLF001
            object(),
            _UnresolvedPageDestination(),
        )
        is None
    )


def test_wave666_resolve_page_number_returns_none_for_unresolved_named_dest() -> None:
    assert (
        listbookmarks._resolve_page_number(  # noqa: SLF001
            _Document(resolved_named_destination=object()),
            PDNamedDestination("chapter"),
        )
        is None
    )


def test_wave666_describe_item_reports_goto_page_destination() -> None:
    page_number, info = listbookmarks._describe_item(  # noqa: SLF001
        _Document(),
        _Item(action=_GoTo(_ResolvedPageDestination())),
    )

    assert page_number == 3
    assert info == ["Destination page: 3"]


def test_wave666_describe_item_keeps_dest_page_when_action_also_resolves() -> None:
    page_number, info = listbookmarks._describe_item(  # noqa: SLF001
        _Document(),
        _Item(
            destination=_ResolvedPageDestination(),
            action=_GoTo(_ResolvedPageDestination()),
        ),
    )

    assert page_number == 3
    assert info == ["Destination page: 3", "Destination page: 3"]


def test_wave666_describe_item_reports_goto_non_page_destination() -> None:
    page_number, info = listbookmarks._describe_item(  # noqa: SLF001
        _Document(),
        _Item(action=_GoTo(_OtherDestination())),
    )

    assert page_number is None
    assert info == ["Destination class: _OtherDestination"]


def test_wave666_print_flat_writes_title_without_page_for_unresolved_item() -> None:
    out = io.StringIO()

    listbookmarks._print_flat(  # noqa: SLF001
        _Document(),
        _BookmarkRoot(_Item(title="Untargeted")),
        out,
    )

    assert out.getvalue() == "Untargeted\n"
