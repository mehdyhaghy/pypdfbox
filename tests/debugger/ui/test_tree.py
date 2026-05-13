"""Hand-written tests for ``pypdfbox.debugger.ui.Tree``."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.debugger.ui import Tree
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.tree import (
    _filter_for_extension,
    _read_stream,
    _read_stream_partial,
)
from pypdfbox.debugger.ui.xref_entry import XrefEntry


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


# ---- helper coverage -----------------------------------------------------


def test_unwrap_array_entry_returns_value() -> None:
    inner = COSStream()
    ae = ArrayEntry()
    ae.set_value(inner)
    assert Tree._unwrap(ae) is inner  # noqa: SLF001


def test_unwrap_xref_entry_returns_object() -> None:
    from pypdfbox.cos import COSObject, COSObjectKey

    inner = COSStream()
    cos_obj = COSObject(7, 0, resolved=inner)
    xe = XrefEntry(0, COSObjectKey(7, 0), 100, cos_obj)
    assert Tree._unwrap(xe) is inner  # noqa: SLF001


def test_unwrap_passthrough_for_other_types() -> None:
    sentinel = object()
    assert Tree._unwrap(sentinel) is sentinel  # noqa: SLF001


def test_get_file_extension_pfb_for_fontfile() -> None:
    stream = COSStream()
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("FontFile"))
    entry.set_value(stream)
    assert Tree._get_file_extension(stream, entry) == "pfb"  # noqa: SLF001


def test_get_file_extension_ttf_for_fontfile2() -> None:
    stream = COSStream()
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("FontFile2"))
    entry.set_value(stream)
    assert Tree._get_file_extension(stream, entry) == "ttf"  # noqa: SLF001


def test_get_file_extension_cff_for_fontfile3_default() -> None:
    stream = COSStream()
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("FontFile3"))
    entry.set_value(stream)
    assert Tree._get_file_extension(stream, entry) == "cff"  # noqa: SLF001


def test_get_file_extension_otf_for_fontfile3_opentype() -> None:
    stream = COSStream()
    stream.set_item("Subtype", COSName.get_pdf_name("OpenType"))
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("FontFile3"))
    entry.set_value(stream)
    assert Tree._get_file_extension(stream, entry) == "otf"  # noqa: SLF001


def test_get_file_extension_none_for_other_names() -> None:
    stream = COSStream()
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Other"))
    entry.set_value(stream)
    assert Tree._get_file_extension(stream, entry) is None  # noqa: SLF001


def test_get_file_extension_array_entry_uses_index() -> None:
    stream = COSStream()
    ae = ArrayEntry()
    ae.set_index(2)
    ae.set_value(stream)
    # Index "2" doesn't match any FontFile* name → None.
    assert Tree._get_file_extension(stream, ae) is None  # noqa: SLF001


def test_filter_for_extension_recognised() -> None:
    spec = _filter_for_extension("ttf")
    assert spec == [("TrueType Font (*.ttf)", "*.ttf")]


def test_filter_for_extension_unknown() -> None:
    assert _filter_for_extension(None) is None
    assert _filter_for_extension("xyz") is None


def test_get_filters_for_stream_single_name() -> None:
    stream = COSStream()
    stream.set_item("Filter", COSName.FLATE_DECODE)
    assert Tree._get_filters_for_stream(stream) == ["FlateDecode"]  # noqa: SLF001


def test_get_filters_for_stream_array() -> None:
    stream = COSStream()
    chain = COSArray()
    chain.add(COSName.get_pdf_name("ASCIIHexDecode"))
    chain.add(COSName.get_pdf_name("FlateDecode"))
    stream.set_item("Filter", chain)
    assert Tree._get_filters_for_stream(stream) == [  # noqa: SLF001
        "ASCIIHexDecode",
        "FlateDecode",
    ]


def test_get_filters_for_stream_no_filters() -> None:
    stream = COSStream()
    assert Tree._get_filters_for_stream(stream) == []  # noqa: SLF001


def test_build_menu_items_includes_partial_decode_for_two_filters(
    tk_root: tk.Tk,
) -> None:
    stream = COSStream()
    chain = COSArray()
    chain.add(COSName.get_pdf_name("ASCIIHexDecode"))
    chain.add(COSName.get_pdf_name("FlateDecode"))
    stream.set_item("Filter", chain)
    tree = Tree(tk_root)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Stream"))
    entry.set_value(stream)
    items = tree.build_menu_items(entry, (entry,))
    labels = [label for label, _ in items]
    # The partial-decode chain produces at least one "Keep ..." entry.
    assert any(lbl.startswith("Keep ") for lbl in labels)


def test_read_stream_returns_decoded_bytes(stream_with_flate: COSStream) -> None:
    data = _read_stream(stream_with_flate, raw=False)
    assert data == b"hello world"


def test_read_stream_handles_missing_creator() -> None:
    class _NoCreator:
        pass

    assert _read_stream(_NoCreator(), raw=False) == b""  # type: ignore[arg-type]
    assert _read_stream(_NoCreator(), raw=True) == b""  # type: ignore[arg-type]


def test_read_stream_partial_handles_missing_creator() -> None:
    class _NoCreator:
        pass

    assert _read_stream_partial(_NoCreator(), 0) == b""  # type: ignore[arg-type]


def test_read_stream_partial_with_filters(stream_with_flate: COSStream) -> None:
    # stop_index 0 falls through to the default creator call.
    data = _read_stream_partial(stream_with_flate, 0)
    assert isinstance(data, (bytes, bytearray))


def test_compute_tree_path_walks_parents(tk_root: tk.Tk) -> None:
    tree = Tree(tk_root)
    a = MapEntry()
    a.set_key(COSName.get_pdf_name("A"))
    b = MapEntry()
    b.set_key(COSName.get_pdf_name("B"))
    a_iid = tree.insert("", "end", text="A")
    b_iid = tree.insert(a_iid, "end", text="B")
    tree.register_node(a_iid, a)
    tree.register_node(b_iid, b)
    path = tree._compute_tree_path(b_iid)  # noqa: SLF001
    assert path == (a, b)


def test_save_dialog_default_constructs_when_none(
    tk_root: tk.Tk, stream_with_flate: COSStream
) -> None:
    """``_save_via_dialog`` with no caller-supplied dialog lazily builds one.

    We exercise the path that constructs the default
    ``FileOpenSaveDialog`` — the dialog itself is monkey-patched so we
    do not pop a real save sheet.
    """
    tree = Tree(tk_root)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("FontFile2"))
    entry.set_value(stream_with_flate)

    captured: list[tuple[bytes, str | None]] = []

    class _FakeDialog:
        def __init__(self, _master: Any, _file_filter: Any) -> None:
            pass

        def save_file(self, data: bytes, ext: str | None) -> bool:
            captured.append((data, ext))
            return True

    from pypdfbox.debugger.ui import file_open_save_dialog as fos

    original = fos.FileOpenSaveDialog
    fos.FileOpenSaveDialog = _FakeDialog  # type: ignore[misc]
    try:
        items = tree.build_menu_items(entry, (entry,))
        save_cb = next(cb for label, cb in items if "Save Stream As" in label)
        save_cb()
    finally:
        fos.FileOpenSaveDialog = original  # type: ignore[misc]
    assert captured
    assert captured[0][1] == "ttf"


def test_make_open_with_default_writes_temp_file(
    tk_root: tk.Tk, stream_with_flate: COSStream, tmp_path: Path
) -> None:
    tree = Tree(tk_root)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("FontFile2"))
    entry.set_value(stream_with_flate)

    seen: list[str] = []

    def _handler(path: str) -> None:
        seen.append(path)

    items = tree.build_menu_items(entry, (entry,), open_handler=_handler)
    open_cb = next(cb for label, cb in items if "Open with Default" in label)
    open_cb()
    assert len(seen) == 1
    written = Path(seen[0])
    assert written.exists()
    assert written.suffix == ".ttf"
    assert written.read_bytes() == b"hello world"


def test_make_partial_invokes_save_dialog(
    tk_root: tk.Tk,
) -> None:
    """Chain with two filters produces a partial-decode callback that
    delegates to the save dialog. The stream body itself does not need
    to round-trip — the callback swallows :class:`OSError` via the
    underlying ``_read_stream_partial`` returning an empty result; we
    only care that the wiring fires.
    """
    stream = COSStream()
    # Write through FlateDecode so the body is real zlib output that
    # ``create_input_stream`` can decode (one filter at a time).
    with stream.create_output_stream(
        filters=[
            COSName.get_pdf_name("ASCIIHexDecode"),
            COSName.FLATE_DECODE,
        ]
    ) as out:
        out.write(b"hi")
    tree = Tree(tk_root)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Stream"))
    entry.set_value(stream)

    captured: list[tuple[bytes, str | None]] = []

    class _FakeDialog:
        def save_file(self, data: bytes, ext: str | None) -> bool:
            captured.append((data, ext))
            return True

    items = tree.build_menu_items(entry, (entry,), save_dialog=_FakeDialog())
    partial_cb = next(cb for label, cb in items if label.startswith("Keep "))
    partial_cb()
    assert captured  # callback fired


def test_copy_path_silently_skips_without_tree_status() -> None:
    tree = Tree(None)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Foo"))
    items = tree.build_menu_items(entry, (entry,))
    label, cb = items[0]
    assert label == "Copy Tree Path"
    # No ``set_tree_status`` was called → callback returns immediately.
    cb()  # must not raise
