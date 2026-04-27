"""
``pypdfbox pdfdebugger FILE [-trailer | -page N | -object NUM GEN | -tree]``
— print a PDF object graph as text.

Upstream ``org.apache.pdfbox.tools.PDFDebugger`` is a heavy Swing GUI for
interactively browsing the COS object pool. We deliberately do **not**
replicate that — pypdfbox does not pull in any GUI subsystem (per the
project-wide divergence noted in ``CHANGES.md`` and ``CLAUDE.md``).

This is the *lite* CLI alternative — analogous in spirit to
``qpdf --json`` / ``mutool show``. It walks the same COS graph the GUI
would render and prints it as indented text on stdout.

Modes:

* default (no flag) — terse summary: header version, page count, catalog
  type, trailer key list (one line each).
* ``-trailer`` — pretty-print the document trailer dictionary.
* ``-page N`` — pretty-print the (1-based) page dictionary at index ``N``.
* ``-object NUM GEN`` — pretty-print the resolved object at the given
  ``(object_number, generation_number)`` pair.
* ``-tree`` — full object-pool dump: every indirect object printed in
  ``num gen R`` order. Output can be very large for non-trivial PDFs.

Output is plain text (UTF-8 stdout). Format is "human-readable", not a
machine-parseable contract — callers wanting structured data should reach
for ``qpdf --json`` instead.

Exit codes: 0 success, 4 I/O / not-a-file. Bad ``-page`` / ``-object``
arguments come back as exit 2 via argparse.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDDocument

_INDENT = "  "
_MAX_DEPTH = 24
_MAX_STREAM_PREVIEW = 64  # bytes shown for stream body previews


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "pdfdebugger",
        help="print a PDF object graph as text (lite CLI replacement for upstream's Swing PDFDebugger)",
        description="Print PDF object graph information. Without flags, prints "
        "a terse summary. Use -trailer / -page / -object / -tree to dump "
        "specific subgraphs. The upstream Swing GUI is intentionally not "
        "ported — this is a CLI-only lite version.",
    )
    p.add_argument("input", help="path to the input PDF")
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "-trailer", "--trailer", action="store_true",
        help="dump the document trailer dictionary",
    )
    group.add_argument(
        "-page", "--page", type=int, metavar="N", default=None,
        help="dump the (1-based) page dictionary at index N",
    )
    group.add_argument(
        "-object", "--object", nargs=2, type=int, metavar=("NUM", "GEN"),
        default=None,
        help="dump the indirect object at (NUM, GEN)",
    )
    group.add_argument(
        "-tree", "--tree", action="store_true",
        help="dump every resolved indirect object in the COS pool",
    )
    p.set_defaults(func=run)


# ---------- formatting helpers ----------


def _fmt_simple(node: COSBase) -> str | None:
    """Return a single-line representation for scalar / leaf COS values,
    or ``None`` when ``node`` is a container that needs multi-line output."""
    if isinstance(node, COSName):
        return f"/{node.name}"
    if isinstance(node, COSBoolean):
        return "true" if node.value else "false"
    if isinstance(node, COSInteger):
        return str(node.value)
    if isinstance(node, COSFloat):
        return repr(node.value)
    if isinstance(node, COSNull):
        return "null"
    if isinstance(node, COSString):
        # Prefer text decode; fall back to byte-hex preview.
        try:
            text = node.get_string()
        except (UnicodeDecodeError, ValueError):
            return f"<{node.get_bytes().hex()}>"
        return f"({text})"
    if isinstance(node, COSObject):
        return f"{node.object_number} {node.generation_number} R"
    return None


def _format_node(
    node: COSBase | None,
    indent: int,
    out: list[str],
    *,
    visited: set[int],
    depth: int = 0,
    follow_refs: bool = False,
) -> None:
    """Append a pretty-printed representation of ``node`` to ``out``.

    ``follow_refs=False`` (the default) prints indirect references as
    ``N G R`` and stops — the same convention upstream PDFDebugger uses
    for its tree view. ``follow_refs=True`` resolves and recurses, with
    cycle protection via ``visited`` (object ids) and ``depth``."""
    pad = _INDENT * indent

    if node is None:
        out.append(f"{pad}<unresolved>")
        return

    simple = _fmt_simple(node)
    if simple is not None and not (follow_refs and isinstance(node, COSObject)):
        out.append(f"{pad}{simple}")
        return

    if depth >= _MAX_DEPTH:
        out.append(f"{pad}... (max depth)")
        return

    node_id = id(node)
    if node_id in visited:
        out.append(f"{pad}... (cycle)")
        return
    visited.add(node_id)
    try:
        if isinstance(node, COSObject):
            # follow_refs path — resolve and recurse.
            ref = f"{node.object_number} {node.generation_number} R"
            target = node.get_object()
            if target is None:
                out.append(f"{pad}{ref} -> <unresolved>")
                return
            simple_target = _fmt_simple(target)
            if simple_target is not None:
                out.append(f"{pad}{ref} -> {simple_target}")
                return
            out.append(f"{pad}{ref} ->")
            _format_node(
                target, indent + 1, out,
                visited=visited, depth=depth + 1, follow_refs=follow_refs,
            )
            return

        if isinstance(node, COSStream):
            length = node.get_length()
            filt = node.get_dictionary_object(COSName.get_pdf_name("Filter"))
            filt_str = ""
            if filt is not None:
                filt_simple = _fmt_simple(filt)
                filt_str = f" filter={filt_simple}" if filt_simple else ""
            out.append(f"{pad}<<  (stream, length={length}{filt_str})")
            for k, v in node.entry_set():
                _format_entry(k, v, indent + 1, out, visited=visited, depth=depth + 1, follow_refs=follow_refs)
            out.append(f"{pad}>>")
            # Best-effort body preview (raw, undecoded).
            try:
                with node.create_raw_input_stream() as raw:
                    sample = raw.read(_MAX_STREAM_PREVIEW)
            except (OSError, AttributeError, NotImplementedError):
                sample = b""
            if sample:
                out.append(f"{pad}stream-body[0:{len(sample)}]: {sample!r}")
            return

        if isinstance(node, COSDictionary):
            out.append(f"{pad}<<")
            for k, v in node.entry_set():
                _format_entry(k, v, indent + 1, out, visited=visited, depth=depth + 1, follow_refs=follow_refs)
            out.append(f"{pad}>>")
            return

        if isinstance(node, COSArray):
            simple_items = [_fmt_simple(item) for item in node]
            if all(s is not None for s in simple_items) and len(node) <= 12:
                # Compact one-line array for short scalar sequences.
                out.append(f"{pad}[ {' '.join(simple_items)} ]")  # type: ignore[arg-type]
                return
            out.append(f"{pad}[")
            for item in node:
                _format_node(
                    item, indent + 1, out,
                    visited=visited, depth=depth + 1, follow_refs=follow_refs,
                )
            out.append(f"{pad}]")
            return

        # Fallback — anything we don't have a special case for.
        out.append(f"{pad}{node!r}")
    finally:
        visited.discard(node_id)


def _format_entry(
    key: COSName,
    value: COSBase,
    indent: int,
    out: list[str],
    *,
    visited: set[int],
    depth: int,
    follow_refs: bool,
) -> None:
    pad = _INDENT * indent
    simple = _fmt_simple(value)
    if simple is not None:
        out.append(f"{pad}/{key.name} {simple}")
        return
    out.append(f"{pad}/{key.name}")
    _format_node(
        value, indent + 1, out,
        visited=visited, depth=depth + 1, follow_refs=follow_refs,
    )


# ---------- mode handlers ----------


def _print_summary(doc: PDDocument, src: Path) -> None:
    cos_doc = doc.get_document()
    print(f"File: {src}")
    print(f"PDF version (header): {cos_doc.get_version():.1f}")
    print(f"Effective version: {doc.get_version():.1f}")
    print(f"Pages: {doc.get_number_of_pages()}")
    print(f"Encrypted: {'yes' if doc.is_encrypted() else 'no'}")

    trailer = cos_doc.get_trailer()
    if trailer is None:
        print("Trailer: <missing>")
    else:
        keys = sorted(k.name for k in trailer.key_set())
        print(f"Trailer keys: {' '.join('/' + k for k in keys) if keys else '<empty>'}")

    catalog = cos_doc.get_catalog()
    if catalog is not None:
        cat_type = catalog.get_dictionary_object(COSName.TYPE)
        cat_type_str = _fmt_simple(cat_type) if cat_type is not None else "<missing>"
        print(f"Catalog /Type: {cat_type_str}")
        pages = catalog.get_dictionary_object(COSName.get_pdf_name("Pages"))
        if pages is not None:
            simple = _fmt_simple(pages)
            print(f"Catalog /Pages: {simple if simple is not None else '<inline>'}")

    objects = cos_doc.get_objects()
    print(f"Indirect objects: {len(objects)}")


def _print_trailer(doc: PDDocument) -> None:
    cos_doc = doc.get_document()
    trailer = cos_doc.get_trailer()
    if trailer is None:
        print("<no trailer>")
        return
    out: list[str] = ["Trailer:"]
    _format_node(trailer, 0, out, visited=set(), follow_refs=False)
    print("\n".join(out))


def _print_page(doc: PDDocument, one_based_index: int) -> int:
    n = doc.get_number_of_pages()
    if one_based_index < 1 or one_based_index > n:
        print(f"pdfdebugger: page {one_based_index} out of range (1..{n})", flush=True)
        return 4
    page = doc.get_page(one_based_index - 1)
    out: list[str] = [f"Page {one_based_index}:"]
    _format_node(page.get_cos_object(), 0, out, visited=set(), follow_refs=False)
    print("\n".join(out))
    return 0


def _print_object(doc: PDDocument, num: int, gen: int) -> int:
    cos_doc = doc.get_document()
    key = COSObjectKey(num, gen)
    if not cos_doc.has_object(key):
        print(f"pdfdebugger: object {num} {gen} R not in pool", flush=True)
        return 4
    cos_obj = cos_doc.get_object_from_pool(key)
    resolved = cos_obj.get_object()
    out: list[str] = [f"Object {num} {gen} R:"]
    _format_node(resolved, 0, out, visited=set(), follow_refs=False)
    print("\n".join(out))
    return 0


def _print_tree(doc: PDDocument) -> None:
    cos_doc: COSDocument = doc.get_document()
    keys = sorted(cos_doc.get_object_keys())
    print(f"Object pool ({len(keys)} entries):")
    for key in keys:
        cos_obj = cos_doc.get_object_from_pool(key)
        resolved = cos_obj.get_object()
        out: list[str] = [f"  {key.object_number} {key.generation_number} R:"]
        _format_node(resolved, 2, out, visited=set(), follow_refs=False)
        print("\n".join(out))


# ---------- CLI entry ----------


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"pdfdebugger: {src}: not a file", flush=True)
        return 4
    with PDDocument.load(src) as doc:
        if args.trailer:
            _print_trailer(doc)
            return 0
        if args.page is not None:
            return _print_page(doc, args.page)
        if args.object is not None:
            num, gen = args.object
            return _print_object(doc, num, gen)
        if args.tree:
            _print_tree(doc)
            return 0
        _print_summary(doc, src)
        return 0


# Re-export for static analysis / consumers that import the symbol set.
__all__ = ["build_parser", "run"]


# Keep type checkers calm about COSBase being "used" — it gates _fmt_simple.
_ = COSBase
_ = Any
