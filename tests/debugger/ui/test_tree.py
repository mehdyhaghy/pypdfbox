"""Hand-written tests for ``pypdfbox.debugger.ui.Tree``."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.debugger.ui import Tree
from pypdfbox.debugger.ui.map_entry import MapEntry


@pytest.fixture
def stream_with_flate() -> COSStream:
    stream = COSStream()
    # Write through the FlateDecode filter so the encoded body is valid
    # zlib output that ``create_input_stream`` can later decompress.
    with stream.create_output_stream(filters=COSName.FLATE_DECODE) as out:
        out.write(b"hello world")
    return stream


def test_constructor_does_not_require_init(tk_root: tk.Tk) -> None:
    tree = Tree(tk_root)
    assert tree is not None


def test_init_sets_row_height(tk_root: tk.Tk) -> None:
    tree = Tree(tk_root)
    tree.init(row_height=24)
    assert tree._row_height == 24


def test_register_node_round_trips(tk_root: tk.Tk) -> None:
    tree = Tree(tk_root)
    sentinel = object()
    tree.register_node("I001", sentinel)
    assert tree.get_node("I001") is sentinel
    assert tree.get_node("missing") is None


def test_build_menu_items_includes_copy_path() -> None:
    tree = Tree(None)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Foo"))
    items = tree.build_menu_items(entry, (entry,))
    labels = [label for label, _ in items]
    assert "Copy Tree Path" in labels


def test_build_menu_items_skips_save_for_non_stream() -> None:
    tree = Tree(None)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Foo"))
    items = tree.build_menu_items(entry, (entry,))
    # Only the copy entry should be present.
    assert len(items) == 1


def test_build_menu_items_adds_save_for_stream(
    tk_root: tk.Tk, stream_with_flate: COSStream
) -> None:
    tree = Tree(tk_root)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Plain"))
    entry.set_value(stream_with_flate)
    items = tree.build_menu_items(entry, (entry,))
    labels = [label for label, _ in items]
    assert any("Save Stream As" in lbl for lbl in labels)
    assert any("Save Raw Stream" in lbl for lbl in labels)


def test_copy_path_uses_tree_status() -> None:
    tree = Tree(None)

    class FakeStatus:
        def __init__(self) -> None:
            self.seen: list[tuple[Any, ...]] = []

        def get_string_for_path(self, path: tuple[Any, ...]) -> str:
            self.seen.append(path)
            return "/Root/Foo"

    fake = FakeStatus()
    tree.set_tree_status(fake)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Foo"))
    items = tree.build_menu_items(entry, (entry,))
    label, callback = items[0]
    assert label == "Copy Tree Path"
    callback()
    assert fake.seen == [(entry,)]


def test_save_action_invokes_save_dialog(
    tk_root: tk.Tk, stream_with_flate: COSStream
) -> None:
    tree = Tree(tk_root)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Plain"))
    entry.set_value(stream_with_flate)

    saved: list[tuple[bytes, str | None]] = []

    class FakeDialog:
        def save_file(self, data: bytes, ext: str | None) -> bool:
            saved.append((data, ext))
            return True

    items = tree.build_menu_items(entry, (entry,), save_dialog=FakeDialog())
    # Find the "Save Stream As..." callback and invoke it.
    callback = next(cb for label, cb in items if "Save Stream As" in label)
    callback()
    assert len(saved) == 1
    data, ext = saved[0]
    assert data == b"hello world"
    assert ext is None


def test_open_handler_only_appears_for_fontfile_streams(
    tk_root: tk.Tk, stream_with_flate: COSStream
) -> None:
    tree = Tree(tk_root)
    # Non-font key: no open entry.
    entry_plain = MapEntry()
    entry_plain.set_key(COSName.get_pdf_name("Plain"))
    entry_plain.set_value(stream_with_flate)
    items = tree.build_menu_items(
        entry_plain,
        (entry_plain,),
        open_handler=lambda path: None,
    )
    labels = [label for label, _ in items]
    assert not any("Open with Default" in lbl for lbl in labels)

    # FontFile2 key: open entry should appear.
    entry_font = MapEntry()
    entry_font.set_key(COSName.get_pdf_name("FontFile2"))
    entry_font.set_value(stream_with_flate)
    items = tree.build_menu_items(
        entry_font,
        (entry_font,),
        open_handler=lambda path: None,
    )
    labels = [label for label, _ in items]
    assert any("Open with Default" in lbl for lbl in labels)
