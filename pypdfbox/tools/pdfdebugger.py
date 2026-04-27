"""
``pypdfbox pdfdebugger FILE [-trailer | -page N | -object NUM[,GEN] | -xref |
-catalog | -tree] [--password PWD] [--depth N]``
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
* ``-object NUM [GEN]`` — pretty-print the resolved object at the given
  object number (generation defaults to ``0`` when omitted).
* ``-xref`` — dump the in-memory xref table (one ``num gen R`` per line).
* ``-catalog`` — pretty-print the document catalog tree (resolves the
  first level of indirect references inline; honours ``--depth``).
* ``-tree`` — full object-pool dump: every indirect object printed in
  ``num gen R`` order. Output can be very large for non-trivial PDFs.

Auxiliary flags:

* ``--password PWD`` — passphrase for an encrypted document, mirroring
  upstream ``-password`` on PDFDebugger / PDFBox CLI tools.
* ``--depth N`` — maximum nesting depth when pretty-printing dictionaries
  / arrays / streams (default ``24``). Lower values give a quick "shape"
  overview of large object graphs.

Output is plain text (UTF-8 stdout). Format is "human-readable", not a
machine-parseable contract — callers wanting structured data should reach
for ``qpdf --json`` instead.

Stream bodies are previewed *decoded* (filter chain applied) up to the
first ~64 bytes; if decoding fails the raw, undecoded bytes are shown
instead with a ``raw`` marker so the operator knows which form they're
looking at.

Exit codes: 0 success, 4 I/O / not-a-file / bad password. Bad ``-page`` /
``-object`` arguments come back as exit 2 via argparse.
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
        "a terse summary. Use -trailer / -page / -object / -xref / -catalog / "
        "-tree to dump specific subgraphs. The upstream Swing GUI is "
        "intentionally not ported — this is a CLI-only lite version.",
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
        "-object", "--object", nargs="+", type=int, metavar="NUM",
        default=None,
        help="dump the indirect object at NUM [GEN] (GEN defaults to 0)",
    )
    group.add_argument(
        "-xref", "--xref", action="store_true",
        help="dump the in-memory xref table (one entry per line)",
    )
    group.add_argument(
        "-catalog", "--catalog", action="store_true",
        help="dump the document catalog dictionary tree",
    )
    group.add_argument(
        "-tree", "--tree", action="store_true",
        help="dump every resolved indirect object in the COS pool",
    )
    # Auxiliary flags — combine freely with any mode above.
    p.add_argument(
        "-password", "--password", metavar="PWD", default=None,
        help="passphrase for encrypted documents (owner or user)",
    )
    p.add_argument(
        "--depth", type=int, metavar="N", default=_MAX_DEPTH,
        help=f"max nesting depth when pretty-printing (default {_MAX_DEPTH})",
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
    max_depth: int = _MAX_DEPTH,
) -> None:
    """Append a pretty-printed representation of ``node`` to ``out``.

    ``follow_refs=False`` (the default) prints indirect references as
    ``N G R`` and stops — the same convention upstream PDFDebugger uses
    for its tree view. ``follow_refs=True`` resolves and recurses, with
    cycle protection via ``visited`` (object ids) and ``depth``.

    ``max_depth`` caps recursion; when reached the node is replaced with
    a ``... (max depth)`` placeholder. Defaults to ``_MAX_DEPTH``."""
    pad = _INDENT * indent

    if node is None:
        out.append(f"{pad}<unresolved>")
        return

    simple = _fmt_simple(node)
    if simple is not None and not (follow_refs and isinstance(node, COSObject)):
        out.append(f"{pad}{simple}")
        return

    if depth >= max_depth:
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
                max_depth=max_depth,
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
                _format_entry(
                    k, v, indent + 1, out,
                    visited=visited, depth=depth + 1, follow_refs=follow_refs,
                    max_depth=max_depth,
                )
            out.append(f"{pad}>>")
            # Best-effort body preview — try the *decoded* bytes first
            # (filter chain applied), fall back to raw if decoding fails.
            sample, kind = _stream_preview(node)
            if sample:
                out.append(
                    f"{pad}stream-body[0:{len(sample)}, {kind}]: {sample!r}"
                )
            return

        if isinstance(node, COSDictionary):
            out.append(f"{pad}<<")
            for k, v in node.entry_set():
                _format_entry(
                    k, v, indent + 1, out,
                    visited=visited, depth=depth + 1, follow_refs=follow_refs,
                    max_depth=max_depth,
                )
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
                    max_depth=max_depth,
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
    max_depth: int = _MAX_DEPTH,
) -> None:
    pad = _INDENT * indent
    simple = _fmt_simple(value)
    # Indirect refs in follow_refs mode must descend into their target
    # rather than print as a single ``N G R`` line.
    if simple is not None and not (follow_refs and isinstance(value, COSObject)):
        out.append(f"{pad}/{key.name} {simple}")
        return
    out.append(f"{pad}/{key.name}")
    _format_node(
        value, indent + 1, out,
        visited=visited, depth=depth + 1, follow_refs=follow_refs,
        max_depth=max_depth,
    )


def _stream_preview(node: COSStream) -> tuple[bytes, str]:
    """Return ``(bytes, kind)`` where ``kind`` is ``"decoded"`` if the
    filter chain ran cleanly or ``"raw"`` if we had to fall back. Empty
    bytes means we couldn't get any sample at all (and the caller will
    suppress the preview line entirely)."""
    # Decoded path first — matches what most consumers actually see.
    try:
        with node.create_input_stream() as decoded:
            sample = decoded.read(_MAX_STREAM_PREVIEW)
        if sample:
            return sample, "decoded"
    except Exception:  # noqa: BLE001 — filter errors are diverse
        pass
    # Fall back to raw, undecoded bytes.
    try:
        with node.create_raw_input_stream() as raw:
            sample = raw.read(_MAX_STREAM_PREVIEW)
        return sample, "raw"
    except (OSError, AttributeError, NotImplementedError):
        return b"", "raw"


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


def _print_trailer(doc: PDDocument, max_depth: int = _MAX_DEPTH) -> None:
    cos_doc = doc.get_document()
    trailer = cos_doc.get_trailer()
    if trailer is None:
        print("<no trailer>")
        return
    out: list[str] = ["Trailer:"]
    _format_node(
        trailer, 0, out, visited=set(), follow_refs=False, max_depth=max_depth,
    )
    print("\n".join(out))


def _print_page(doc: PDDocument, one_based_index: int, max_depth: int = _MAX_DEPTH) -> int:
    n = doc.get_number_of_pages()
    if one_based_index < 1 or one_based_index > n:
        print(f"pdfdebugger: page {one_based_index} out of range (1..{n})", flush=True)
        return 4
    page = doc.get_page(one_based_index - 1)
    out: list[str] = [f"Page {one_based_index}:"]
    _format_node(
        page.get_cos_object(), 0, out,
        visited=set(), follow_refs=False, max_depth=max_depth,
    )
    print("\n".join(out))
    return 0


def _print_object(doc: PDDocument, num: int, gen: int, max_depth: int = _MAX_DEPTH) -> int:
    cos_doc = doc.get_document()
    key = COSObjectKey(num, gen)
    if not cos_doc.has_object(key):
        print(f"pdfdebugger: object {num} {gen} R not in pool", flush=True)
        return 4
    cos_obj = cos_doc.get_object_from_pool(key)
    resolved = cos_obj.get_object()
    out: list[str] = [f"Object {num} {gen} R:"]
    _format_node(
        resolved, 0, out, visited=set(), follow_refs=False, max_depth=max_depth,
    )
    print("\n".join(out))
    return 0


def _print_tree(doc: PDDocument, max_depth: int = _MAX_DEPTH) -> None:
    cos_doc: COSDocument = doc.get_document()
    keys = sorted(cos_doc.get_object_keys())
    print(f"Object pool ({len(keys)} entries):")
    for key in keys:
        cos_obj = cos_doc.get_object_from_pool(key)
        resolved = cos_obj.get_object()
        out: list[str] = [f"  {key.object_number} {key.generation_number} R:"]
        _format_node(
            resolved, 2, out, visited=set(), follow_refs=False, max_depth=max_depth,
        )
        print("\n".join(out))


def _print_xref(doc: PDDocument) -> None:
    """Dump the in-memory xref table — one ``num gen R`` line per entry,
    ordered by object number. PDFBox's GUI shows this as the ``Cross
    Reference Table`` node; the headless equivalent is just the keys."""
    cos_doc: COSDocument = doc.get_document()
    keys = sorted(cos_doc.get_object_keys())
    start_xref = cos_doc.get_start_xref()
    is_stream = cos_doc.is_xref_stream()
    print(f"Xref ({len(keys)} entries, startxref={start_xref}, "
          f"stream={'yes' if is_stream else 'no'}):")
    for key in keys:
        print(f"  {key.object_number} {key.generation_number} R")


def _print_catalog(doc: PDDocument, max_depth: int = _MAX_DEPTH) -> int:
    """Pretty-print the document catalog dictionary subtree, resolving
    indirect references inline (one level deep is the upstream default;
    deeper resolution is bounded by ``max_depth``). Returns 4 if the
    catalog is missing — corrupt-PDF case."""
    cos_doc: COSDocument = doc.get_document()
    catalog = cos_doc.get_catalog()
    if catalog is None:
        print("pdfdebugger: catalog missing from document", flush=True)
        return 4
    out: list[str] = ["Catalog:"]
    _format_node(
        catalog, 0, out,
        visited=set(), follow_refs=True, max_depth=max_depth,
    )
    print("\n".join(out))
    return 0


# ---------- CLI entry ----------


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"pdfdebugger: {src}: not a file", flush=True)
        return 4

    depth = args.depth if args.depth is not None and args.depth > 0 else _MAX_DEPTH
    password = args.password

    # ``PDDocument.load`` raises on bad/missing password — surface as exit 4
    # so shell callers can distinguish from argparse-rejected input (exit 2).
    try:
        ctx = PDDocument.load(src, password=password) if password is not None \
            else PDDocument.load(src)
    except Exception as exc:  # noqa: BLE001 — broad on purpose at the CLI seam
        print(f"pdfdebugger: cannot open {src}: {exc}", flush=True)
        return 4

    with ctx as doc:
        if args.trailer:
            _print_trailer(doc, max_depth=depth)
            return 0
        if args.page is not None:
            return _print_page(doc, args.page, max_depth=depth)
        if args.object is not None:
            nums = args.object
            if len(nums) == 1:
                num, gen = nums[0], 0
            elif len(nums) == 2:
                num, gen = nums[0], nums[1]
            else:
                print(
                    "pdfdebugger: -object expects NUM [GEN] (one or two ints)",
                    flush=True,
                )
                return 2
            return _print_object(doc, num, gen, max_depth=depth)
        if args.xref:
            _print_xref(doc)
            return 0
        if args.catalog:
            return _print_catalog(doc, max_depth=depth)
        if args.tree:
            _print_tree(doc, max_depth=depth)
            return 0
        _print_summary(doc, src)
        return 0


# Re-export for static analysis / consumers that import the symbol set.
__all__ = ["build_parser", "run"]


# Keep type checkers calm about COSBase being "used" — it gates _fmt_simple.
_ = COSBase
_ = Any
