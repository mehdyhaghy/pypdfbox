"""Headless-friendly debugger screenshot helper.

Launches the pypdfbox debugger, optionally loads a PDF, lets the Tk event
loop settle, screenshots the window via Pillow `ImageGrab`, and exits.

Usage::

    .venv/bin/python scripts/debugger_screenshot.py \
        --pdf gold.pdf \
        --out /tmp/debugger.png \
        --select 0 \
        --settle-ms 800

Notes:
    - macOS requires Screen Recording permission for the calling process
      (Terminal / iTerm / the Python binary). Tk windows show as their
      own toplevel rectangle.
    - The `--select` arg is a 0-indexed walk into the tree's children
      so we can prove the right-hand-side panel paints content.
"""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

from pypdfbox.debugger.pd_debugger import PDFDebugger


def _settle(root: tk.Tk, ms: int) -> None:
    """Pump the Tk event loop for ~``ms`` milliseconds.

    `update_idletasks` queues layout work; `update` actually paints.
    macOS Tk in particular often needs several update cycles before
    a freshly-mapped window is fully composited.
    """
    deadline = root.tk.call("after", "info")  # noqa: F841 - kept for diag
    end_marker = {"done": False}
    root.after(ms, lambda: end_marker.__setitem__("done", True))
    while not end_marker["done"]:
        root.update()


def _select_nth_tree_child(debugger: PDFDebugger, n: int) -> None:
    """Select the nth top-level item in the debugger's tree."""
    tree = debugger._tree  # noqa: SLF001 — debug helper
    children = tree.get_children()
    if n < 0 or n >= len(children):
        return
    target = children[n]
    tree.selection_set(target)
    tree.focus(target)
    tree.see(target)


def _select_first_page(debugger: PDFDebugger, page_index: int = 0) -> None:
    """Walk into the document root and select page ``page_index`` (0-based)."""
    tree = debugger._tree  # noqa: SLF001
    roots = tree.get_children()
    if not roots:
        return
    doc_root = roots[0]
    tree.item(doc_root, open=True)
    children = tree.get_children(doc_root)
    if not children:
        return
    if page_index < 0 or page_index >= len(children):
        page_index = 0
    target = children[page_index]
    tree.selection_set(target)
    tree.focus(target)
    tree.see(target)


def _grab_window(root: tk.Tk, out: Path) -> tuple[int, int, int, int]:
    """Grab the window region and return the (l, t, r, b) bbox used."""
    root.update_idletasks()
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    bbox = (x, y, x + w, y + h)
    img = ImageGrab.grab(bbox=bbox)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")
    return bbox


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Screenshot the pypdfbox debugger")
    parser.add_argument("--pdf", default=None, help="PDF to load")
    parser.add_argument(
        "--out",
        default="/tmp/pypdfbox_debugger.png",
        help="Output PNG path (default: /tmp/pypdfbox_debugger.png)",
    )
    parser.add_argument(
        "--select",
        type=int,
        default=-1,
        help="0-indexed top-level tree row to select before screenshot",
    )
    parser.add_argument(
        "--select-page",
        action="store_true",
        help="auto-select the first page node (drilling past doc root)",
    )
    parser.add_argument(
        "--page-index",
        type=int,
        default=0,
        help="0-based index of the page to select when --select-page is set",
    )
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=800,
        help="Milliseconds to pump the Tk event loop before screenshot",
    )
    parser.add_argument(
        "--geometry",
        default=None,
        help="Optional Tk geometry override (e.g. '1280x800+100+100')",
    )
    args = parser.parse_args(argv)

    root = tk.Tk()
    root.title(PDFDebugger.TITLE)

    debugger = PDFDebugger(root)
    # PDFDebugger.__init__ sets geometry from WindowPrefs.get_bounds; apply
    # override AFTER so it wins on initial paint.
    if args.geometry:
        root.geometry(args.geometry)

    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print(f"PDF not found: {pdf_path}", file=sys.stderr)
            return 2
        debugger.open_document(str(pdf_path), "")

    _settle(root, args.settle_ms)
    if args.select >= 0:
        _select_nth_tree_child(debugger, args.select)
        _settle(root, args.settle_ms)
    if args.select_page:
        _select_first_page(debugger, args.page_index)
        # Page rendering can be slow; double the settle window.
        _settle(root, args.settle_ms * 2)

    bbox = _grab_window(root, Path(args.out))
    root.destroy()
    print(f"saved {args.out}  bbox={bbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
