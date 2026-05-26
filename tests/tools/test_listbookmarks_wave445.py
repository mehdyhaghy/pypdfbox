"""Wave 445 coverage for ``pypdfbox.tools.listbookmarks`` edge branches."""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption import InvalidPasswordException
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.tools import listbookmarks


class _FallbackPage:
    def __init__(self, cos_object: object) -> None:
        self._cos_object = cos_object

    def get_cos_object(self) -> object:
        return self._cos_object


class _FallbackItem:
    def __init__(self, target_page: object | None) -> None:
        self._target_page = target_page

    def get_destination(self) -> None:
        return None

    def get_action(self) -> None:
        return None

    def find_destination_page(self, document: object) -> object | None:
        return self._target_page


class _FallbackDocument:
    def __init__(self, *pages: _FallbackPage) -> None:
        self._pages = pages

    def get_pages(self) -> tuple[_FallbackPage, ...]:
        return self._pages


class _OtherDestination(PDDestination):
    def get_cos_object(self) -> object:
        return object()


def test_describe_item_reports_unresolved_destination_and_non_goto_action() -> None:
    item = type(
        "Item",
        (),
        {
            "get_destination": lambda self: _OtherDestination(),
            "get_action": lambda self: PDActionURI(),
            "find_destination_page": lambda self, document: None,
        },
    )()

    page_number, info = listbookmarks._describe_item(object(), item)

    assert page_number is None
    assert info == ["Destination class: _OtherDestination", "Action class: PDActionURI"]


def test_describe_item_falls_back_to_outline_item_destination_page() -> None:
    first = object()
    second = object()
    document = _FallbackDocument(_FallbackPage(first), _FallbackPage(second))
    item = _FallbackItem(target_page=second)

    page_number, info = listbookmarks._describe_item(document, item)

    assert page_number == 2
    assert info == []


def test_describe_item_ignores_fallback_page_not_in_document() -> None:
    document = _FallbackDocument(_FallbackPage(object()))
    item = _FallbackItem(target_page=object())

    page_number, info = listbookmarks._describe_item(document, item)

    assert page_number is None
    assert info == []


def test_run_returns_one_for_invalid_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "locked.pdf"
    src.write_bytes(b"%PDF-1.7\n")

    def raise_bad_password(path: Path, *, password: str = "") -> PDDocument:
        assert path == src
        assert password == "secret"
        raise InvalidPasswordException("bad password")

    monkeypatch.setattr(listbookmarks.PDDocument, "load", raise_bad_password)
    args = argparse.Namespace(input=str(src), password="secret", format="tree")

    assert listbookmarks.run(args) == 1
    assert "bad password" in capsys.readouterr().out


def test_run_closes_loaded_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "plain.pdf"
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.save(src)
    doc.close()

    loaded = PDDocument.load(src)
    closed = {"value": False}
    original_close = loaded.close

    def close_and_note() -> None:
        closed["value"] = True
        original_close()

    monkeypatch.setattr(listbookmarks.PDDocument, "load", lambda *args, **kwargs: loaded)
    monkeypatch.setattr(loaded, "close", close_and_note)
    monkeypatch.setattr(listbookmarks, "list_bookmarks", lambda document, output, *, format: None)

    args = argparse.Namespace(input=str(src), password="", format="flat")

    assert listbookmarks.run(args) == 0
    assert closed["value"] is True


def test_list_bookmarks_unknown_format_uses_tree(
    tmp_path: Path,
) -> None:
    src = tmp_path / "plain.pdf"
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.save(src)
    doc.close()

    with PDDocument.load(src) as loaded:
        out = io.StringIO()
        listbookmarks.list_bookmarks(loaded, out, format="not-flat")

    assert out.getvalue() == "This document does not contain any bookmarks\n"
