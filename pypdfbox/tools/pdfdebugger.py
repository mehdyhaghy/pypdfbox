"""
``pypdfbox pdfdebugger FILE [-trailer | -page N | -object NUM[,GEN] | -xref |
-catalog | -tree | --list-objects | --show-trailer | --show-catalog |
--show-tree | --dump-tree | --dump-stream NUM[.GEN] | --show-object NUM[.GEN] |
--show-page-tokens N | --show-encryption | -i / --interactive]
[--password PWD] [--depth N] [--format text|json]``
— print a PDF object graph as text, or open an interactive walker.

Upstream ``org.apache.pdfbox.tools.PDFDebugger`` is a heavy Swing GUI for
interactively browsing the COS object pool. We deliberately do **not**
replicate that — pypdfbox does not pull in any GUI subsystem (per the
project-wide divergence noted in ``CHANGES.md`` and ``CLAUDE.md``).

This is the *lite* CLI alternative — analogous in spirit to
``qpdf --json`` / ``mutool show`` (non-interactive) or ``pdb`` (interactive).
It walks the same COS graph the GUI would render and prints it as indented
text on stdout, or — under ``-i`` / ``--interactive`` — drops the operator
into a textual REPL with ``ls / cd / pwd / cat / hex / ref / find / raw /
decode / q`` commands modelled on POSIX shell + a debugger.

Modes (mutually exclusive):

* default (no flag) — terse summary: header version, page count, catalog
  type, trailer key list (one line each).
* ``-trailer`` / ``--trailer`` / ``--show-trailer`` — pretty-print the
  document trailer.
* ``-page N`` — pretty-print the (1-based) page dictionary at index ``N``.
* ``-object NUM [GEN]`` / ``--show-object NUM[.GEN]`` — pretty-print the
  resolved object at the given object number.
* ``-xref`` / ``--xref`` — dump the in-memory xref table (one ``num gen R``
  per line).
* ``--list-objects`` — like ``-xref`` but shows offset / in_objstm / free
  state for each entry, mirroring ``qpdf --show-xref`` output.
* ``-catalog`` / ``--show-catalog`` — pretty-print the document catalog.
* ``-tree`` / ``--show-tree`` / ``--dump-tree`` — full object-pool dump.
* ``--dump-stream NUM[.GEN]`` — hex + decoded body dump for the given
  stream object (errors with exit 4 if the object isn't a stream).
* ``--show-page-tokens N`` — tokenize and dump the content-stream of
  page ``N`` (1-based).
* ``--show-encryption`` — print encryption parameters (V/R/Length/Filter
  /SubFilter/permissions). For security, only the first 8 hex characters
  of /U and /O are shown (never the full hash).
* ``-i`` / ``--interactive`` — open the textual COS walker (REPL). See
  in-process ``help`` for the command list.

Auxiliary flags:

* ``--password PWD`` — passphrase for an encrypted document.
* ``--depth N`` — maximum nesting depth when pretty-printing dictionaries
  / arrays / streams (default ``24``).
* ``--format text|json`` — output format. JSON is a deterministic single
  object suitable for scripting; text is the default human-readable form.

Stream bodies are previewed *decoded* (filter chain applied) up to the
first ~64 bytes; if decoding fails the raw, undecoded bytes are shown
instead with a ``raw`` marker so the operator knows which form they're
looking at.

Interactive walker commands (``-i`` / ``--interactive``):

* ``ls`` — list children of the current node (key/index → short type).
* ``cd <key|index>`` — descend into a child (``cd ..`` ascends; ``cd /``
  jumps to the trailer; ``cd <num> <gen>`` follows an indirect ref by
  object key).
* ``pwd`` — print the path from trailer to the current node.
* ``cat`` — pretty-print the current node (default depth 6).
* ``hex`` — hex dump of the current node when it is a stream (raw bytes).
* ``ref <num> [gen]`` — jump straight to ``num gen R`` in the object pool.
* ``find <key>`` — list paths in the visited subtree where dict-key matches.
* ``raw`` — show the *raw* (encoded) stream bytes (preview).
* ``decode`` — show the *decoded* (filter-chain-applied) stream bytes
  (preview).
* ``q`` / ``quit`` / ``exit`` — leave the walker.
* ``help`` — print this list inside the walker.

Exit codes: 0 success, 4 I/O / not-a-file / bad password / bad object id.
Bad ``-page`` / ``-object`` arguments come back as exit 2 via argparse.
"""
from __future__ import annotations

import argparse
import json
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
_HEX_PREFIX_BYTES = 4  # 4 bytes -> 8 hex chars for /U /O preview
_FORMAT_TEXT = "text"
_FORMAT_JSON = "json"


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "pdfdebugger",
        help="print a PDF object graph as text (lite CLI replacement for upstream's Swing PDFDebugger)",
        description="Print PDF object graph information. Without flags, prints "
        "a terse summary. Use -trailer / -page / -object / -xref / -catalog / "
        "-tree / --list-objects / --show-page-tokens / --show-encryption to "
        "dump specific subgraphs. The upstream Swing GUI is intentionally not "
        "ported — this is a CLI-only lite version.",
    )
    p.add_argument("input", help="path to the input PDF")
    group = p.add_mutually_exclusive_group()
    # Existing short-form flags — kept for back-compat.
    group.add_argument(
        "-trailer", "--trailer", "--show-trailer",
        action="store_true", dest="trailer",
        help="dump the document trailer dictionary",
    )
    group.add_argument(
        "-page", "--page", type=int, metavar="N", default=None,
        help="dump the (1-based) page dictionary at index N",
    )
    group.add_argument(
        "-object", "--object", nargs="+", metavar="NUM",
        default=None,
        help="dump the indirect object at NUM [GEN] (GEN defaults to 0)",
    )
    group.add_argument(
        "--show-object", metavar="NUM[.GEN]", default=None, dest="show_object",
        help="dump the indirect object at NUM[.GEN] (GEN defaults to 0)",
    )
    group.add_argument(
        "-xref", "--xref", action="store_true", dest="xref",
        help="dump the in-memory xref table (one entry per line)",
    )
    group.add_argument(
        "--list-objects", action="store_true", dest="list_objects",
        help="dump the xref table with offset/in_objstm/free state per entry",
    )
    group.add_argument(
        "-catalog", "--catalog", "--show-catalog",
        action="store_true", dest="catalog",
        help="dump the document catalog dictionary tree",
    )
    group.add_argument(
        "-tree", "--tree", "--show-tree", "--dump-tree",
        action="store_true", dest="tree",
        help="dump every resolved indirect object in the COS pool",
    )
    group.add_argument(
        "--dump-stream", metavar="NUM[.GEN]", default=None, dest="dump_stream",
        help="hex + decoded body dump of the stream object at NUM[.GEN]",
    )
    group.add_argument(
        "--show-page-tokens", type=int, metavar="N", default=None,
        dest="show_page_tokens",
        help="tokenize and dump the content stream of (1-based) page N",
    )
    group.add_argument(
        "--show-encryption", action="store_true", dest="show_encryption",
        help="print encryption parameters; /U and /O shown as hex prefix only",
    )
    group.add_argument(
        "-i", "--interactive", action="store_true", dest="interactive",
        help="open the textual COS walker REPL (ls/cd/pwd/cat/hex/ref/find/"
        "raw/decode/q)",
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
    p.add_argument(
        "--format", choices=(_FORMAT_TEXT, _FORMAT_JSON), default=_FORMAT_TEXT,
        dest="output_format",
        help="output format (default text)",
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


def _node_to_jsonable(
    node: COSBase | None,
    *,
    visited: set[int],
    depth: int,
    follow_refs: bool,
    max_depth: int,
) -> Any:
    """Convert a COS node to a JSON-friendly structure. Same recursion
    discipline as :func:`_format_node` but emits dicts/lists instead of
    pretty-printed lines."""
    if node is None:
        return None
    if isinstance(node, COSName):
        return f"/{node.name}"
    if isinstance(node, COSBoolean):
        return bool(node.value)
    if isinstance(node, COSInteger):
        return int(node.value)
    if isinstance(node, COSFloat):
        return float(node.value)
    if isinstance(node, COSNull):
        return None
    if isinstance(node, COSString):
        try:
            return node.get_string()
        except (UnicodeDecodeError, ValueError):
            return {"hex": node.get_bytes().hex()}
    if isinstance(node, COSObject) and not follow_refs:
        return {
            "ref": f"{node.object_number} {node.generation_number} R",
            "object_number": node.object_number,
            "generation_number": node.generation_number,
        }
    if depth >= max_depth:
        return {"truncated": "max depth"}
    nid = id(node)
    if nid in visited:
        return {"truncated": "cycle"}
    visited.add(nid)
    try:
        if isinstance(node, COSObject):  # follow_refs branch
            target = node.get_object()
            return {
                "ref": f"{node.object_number} {node.generation_number} R",
                "value": _node_to_jsonable(
                    target, visited=visited, depth=depth + 1,
                    follow_refs=follow_refs, max_depth=max_depth,
                ),
            }
        if isinstance(node, COSStream):
            entries = {
                k.name: _node_to_jsonable(
                    v, visited=visited, depth=depth + 1,
                    follow_refs=follow_refs, max_depth=max_depth,
                )
                for k, v in node.entry_set()
            }
            sample, kind = _stream_preview(node)
            return {
                "type": "stream",
                "length": node.get_length(),
                "dict": entries,
                "preview_kind": kind,
                "preview_hex": sample.hex() if sample else "",
            }
        if isinstance(node, COSDictionary):
            return {
                k.name: _node_to_jsonable(
                    v, visited=visited, depth=depth + 1,
                    follow_refs=follow_refs, max_depth=max_depth,
                )
                for k, v in node.entry_set()
            }
        if isinstance(node, COSArray):
            return [
                _node_to_jsonable(
                    item, visited=visited, depth=depth + 1,
                    follow_refs=follow_refs, max_depth=max_depth,
                )
                for item in node
            ]
        return repr(node)
    finally:
        visited.discard(nid)


def _emit(payload: Any, lines: list[str], *, output_format: str) -> None:
    """Emit either the pretty-printed text lines or a JSON-encoded
    payload, depending on ``output_format``."""
    if output_format == _FORMAT_JSON:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("\n".join(lines))


# ---------- mode handlers ----------


def _print_summary(
    doc: PDDocument, src: Path, *, output_format: str = _FORMAT_TEXT,
) -> None:
    cos_doc = doc.get_document()
    trailer = cos_doc.get_trailer()
    trailer_keys = sorted(k.name for k in trailer.key_set()) if trailer is not None else []
    catalog = cos_doc.get_catalog()
    cat_type_str: str | None = None
    pages_simple: str | None = None
    if catalog is not None:
        cat_type = catalog.get_dictionary_object(COSName.TYPE)
        cat_type_str = _fmt_simple(cat_type) if cat_type is not None else None
        pages = catalog.get_dictionary_object(COSName.get_pdf_name("Pages"))
        if pages is not None:
            pages_simple = _fmt_simple(pages)

    if output_format == _FORMAT_JSON:
        payload: dict[str, Any] = {
            "file": str(src),
            "header_version": cos_doc.get_version(),
            "effective_version": doc.get_version(),
            "pages": doc.get_number_of_pages(),
            "encrypted": doc.is_encrypted(),
            "trailer_keys": [f"/{k}" for k in trailer_keys],
            "catalog_type": cat_type_str,
            "catalog_pages": pages_simple,
            "indirect_object_count": len(cos_doc.get_objects()),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    lines = [
        f"File: {src}",
        f"PDF version (header): {cos_doc.get_version():.1f}",
        f"Effective version: {doc.get_version():.1f}",
        f"Pages: {doc.get_number_of_pages()}",
        f"Encrypted: {'yes' if doc.is_encrypted() else 'no'}",
    ]
    if trailer is None:
        lines.append("Trailer: <missing>")
    else:
        joined = " ".join("/" + k for k in trailer_keys) if trailer_keys else "<empty>"
        lines.append(f"Trailer keys: {joined}")
    if catalog is not None:
        lines.append(f"Catalog /Type: {cat_type_str if cat_type_str else '<missing>'}")
        if pages_simple is not None:
            lines.append(f"Catalog /Pages: {pages_simple}")
        elif catalog.get_dictionary_object(COSName.get_pdf_name("Pages")) is not None:
            lines.append("Catalog /Pages: <inline>")
    lines.append(f"Indirect objects: {len(cos_doc.get_objects())}")
    print("\n".join(lines))


def _print_trailer(
    doc: PDDocument, *,
    max_depth: int = _MAX_DEPTH, output_format: str = _FORMAT_TEXT,
) -> None:
    cos_doc = doc.get_document()
    trailer = cos_doc.get_trailer()
    if trailer is None:
        if output_format == _FORMAT_JSON:
            print(json.dumps({"trailer": None}, indent=2, sort_keys=True))
        else:
            print("<no trailer>")
        return
    if output_format == _FORMAT_JSON:
        payload = {
            "trailer": _node_to_jsonable(
                trailer, visited=set(), depth=0,
                follow_refs=False, max_depth=max_depth,
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    out: list[str] = ["Trailer:"]
    _format_node(
        trailer, 0, out, visited=set(), follow_refs=False, max_depth=max_depth,
    )
    print("\n".join(out))


def _print_page(
    doc: PDDocument, one_based_index: int, *,
    max_depth: int = _MAX_DEPTH, output_format: str = _FORMAT_TEXT,
) -> int:
    n = doc.get_number_of_pages()
    if one_based_index < 1 or one_based_index > n:
        print(f"pdfdebugger: page {one_based_index} out of range (1..{n})", flush=True)
        return 4
    page = doc.get_page(one_based_index - 1)
    if output_format == _FORMAT_JSON:
        payload = {
            "page": one_based_index,
            "dict": _node_to_jsonable(
                page.get_cos_object(), visited=set(), depth=0,
                follow_refs=False, max_depth=max_depth,
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    out: list[str] = [f"Page {one_based_index}:"]
    _format_node(
        page.get_cos_object(), 0, out,
        visited=set(), follow_refs=False, max_depth=max_depth,
    )
    print("\n".join(out))
    return 0


def _print_object(
    doc: PDDocument, num: int, gen: int, *,
    max_depth: int = _MAX_DEPTH, output_format: str = _FORMAT_TEXT,
) -> int:
    cos_doc = doc.get_document()
    key = COSObjectKey(num, gen)
    if not cos_doc.has_object(key):
        print(f"pdfdebugger: object {num} {gen} R not in pool", flush=True)
        return 4
    cos_obj = cos_doc.get_object_from_pool(key)
    resolved = cos_obj.get_object()
    if output_format == _FORMAT_JSON:
        payload = {
            "object_number": num,
            "generation_number": gen,
            "value": _node_to_jsonable(
                resolved, visited=set(), depth=0,
                follow_refs=False, max_depth=max_depth,
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    out: list[str] = [f"Object {num} {gen} R:"]
    _format_node(
        resolved, 0, out, visited=set(), follow_refs=False, max_depth=max_depth,
    )
    print("\n".join(out))
    return 0


def _hex_dump(data: bytes, *, width: int = 16, max_lines: int = 64) -> str:
    """Return a ``hexdump -C``-style block: ``offset  hex  |ascii|``.

    Truncated after ``max_lines`` rows with a trailing ``...`` marker so a
    large stream doesn't flood the terminal. ``width`` is the number of
    bytes per row."""
    if not data:
        return "<empty>"
    rows: list[str] = []
    total = len(data)
    cap = min(total, max_lines * width)
    for offset in range(0, cap, width):
        chunk = data[offset:offset + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        # Pad hex column so the ascii column is aligned across short rows.
        hex_part = hex_part.ljust(width * 3 - 1)
        ascii_part = "".join(
            chr(b) if 32 <= b < 127 else "." for b in chunk
        )
        rows.append(f"{offset:08x}  {hex_part}  |{ascii_part}|")
    if cap < total:
        rows.append(f"... ({total - cap} more bytes)")
    return "\n".join(rows)


def _dump_stream(
    doc: PDDocument, num: int, gen: int, *,
    output_format: str = _FORMAT_TEXT,
) -> int:
    """Dump the stream object at ``num gen R`` as raw + decoded bytes.

    Mirrors ``qpdf --show-object=NUM --raw-stream-data`` in spirit. The
    raw block is the on-disk bytes; the decoded block is the result of
    running the ``/Filter`` chain. We always show *both* because they
    answer different debugging questions ("is the predictor right?" vs
    "what does the consumer see?").

    Exit codes: 0 success, 4 if the object isn't in the pool, 4 if it's
    not a stream."""
    cos_doc = doc.get_document()
    key = COSObjectKey(num, gen)
    if not cos_doc.has_object(key):
        print(f"pdfdebugger: object {num} {gen} R not in pool", flush=True)
        return 4
    resolved = cos_doc.get_object_from_pool(key).get_object()
    if not isinstance(resolved, COSStream):
        print(
            f"pdfdebugger: object {num} {gen} R is not a stream",
            flush=True,
        )
        return 4

    # Pull both forms — raw is always available; decoded may fail when a
    # filter is unsupported (we surface that as an error string rather
    # than crashing the dump).
    try:
        with resolved.create_raw_input_stream() as src:
            raw_bytes = src.read()
    except (OSError, AttributeError) as exc:
        raw_bytes = b""
        raw_err: str | None = str(exc)
    else:
        raw_err = None
    try:
        decoded_bytes = resolved.to_byte_array()
        decoded_err: str | None = None
    except Exception as exc:  # noqa: BLE001 — filters surface diverse errors
        decoded_bytes = b""
        decoded_err = str(exc)

    filt = resolved.get_dictionary_object(COSName.get_pdf_name("Filter"))
    filt_repr = _fmt_simple(filt) if filt is not None else None

    if output_format == _FORMAT_JSON:
        payload = {
            "object_number": num,
            "generation_number": gen,
            "filter": filt_repr,
            "length": resolved.get_length(),
            "raw_length": len(raw_bytes),
            "raw_hex": raw_bytes.hex(),
            "raw_error": raw_err,
            "decoded_length": len(decoded_bytes),
            "decoded_hex": decoded_bytes.hex(),
            "decoded_error": decoded_err,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(f"Stream {num} {gen} R:")
    print(f"  /Length : {resolved.get_length()}")
    print(f"  /Filter : {filt_repr if filt_repr else '<none>'}")
    print(f"  raw bytes ({len(raw_bytes)} bytes):")
    if raw_err is not None:
        print(f"    <error: {raw_err}>")
    else:
        for line in _hex_dump(raw_bytes).splitlines():
            print(f"    {line}")
    print(f"  decoded bytes ({len(decoded_bytes)} bytes):")
    if decoded_err is not None:
        print(f"    <error: {decoded_err}>")
    else:
        for line in _hex_dump(decoded_bytes).splitlines():
            print(f"    {line}")
    return 0


def _print_tree(
    doc: PDDocument, *,
    max_depth: int = _MAX_DEPTH, output_format: str = _FORMAT_TEXT,
) -> None:
    cos_doc: COSDocument = doc.get_document()
    keys = sorted(cos_doc.get_object_keys())
    if output_format == _FORMAT_JSON:
        entries = []
        for key in keys:
            cos_obj = cos_doc.get_object_from_pool(key)
            resolved = cos_obj.get_object()
            entries.append(
                {
                    "object_number": key.object_number,
                    "generation_number": key.generation_number,
                    "value": _node_to_jsonable(
                        resolved, visited=set(), depth=0,
                        follow_refs=False, max_depth=max_depth,
                    ),
                }
            )
        print(json.dumps({"objects": entries}, indent=2, sort_keys=True))
        return
    print(f"Object pool ({len(keys)} entries):")
    for key in keys:
        cos_obj = cos_doc.get_object_from_pool(key)
        resolved = cos_obj.get_object()
        out: list[str] = [f"  {key.object_number} {key.generation_number} R:"]
        _format_node(
            resolved, 2, out, visited=set(), follow_refs=False, max_depth=max_depth,
        )
        print("\n".join(out))


def _xref_state_for(
    cos_doc: COSDocument, key: COSObjectKey,
) -> tuple[str, int | None, int | None]:
    """Return ``(state, offset, in_objstm)`` for the given xref entry.

    The xref-table values follow PDFBox's encoding:

    * positive int — absolute byte offset in the source file (state="used")
    * negative int — ``-objstm_object_number`` (state="in_objstm")
    * missing key — synthetic / writer-allocated object (state="synthetic")

    Free entries are not stored in the in-memory ``_xref_table`` (the parser
    drops them); they're inferred for object number ``0 0 R`` which the
    spec defines as the head of the free list.
    """
    table = cos_doc.get_xref_table()
    if key.object_number == 0 and key.generation_number == 65535:
        return "free", 0, None
    offset = table.get(key)
    if offset is None:
        return "synthetic", None, None
    if offset < 0:
        return "in_objstm", None, -offset
    return "used", offset, None


def _print_xref(doc: PDDocument, *, output_format: str = _FORMAT_TEXT) -> None:
    """Dump the in-memory xref table — one ``num gen R`` line per entry,
    ordered by object number. PDFBox's GUI shows this as the ``Cross
    Reference Table`` node; the headless equivalent is just the keys."""
    cos_doc: COSDocument = doc.get_document()
    keys = sorted(cos_doc.get_object_keys())
    start_xref = cos_doc.get_start_xref()
    is_stream = cos_doc.is_xref_stream()
    if output_format == _FORMAT_JSON:
        payload = {
            "startxref": start_xref,
            "is_xref_stream": is_stream,
            "entries": [
                {
                    "object_number": k.object_number,
                    "generation_number": k.generation_number,
                }
                for k in keys
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"Xref ({len(keys)} entries, startxref={start_xref}, "
          f"stream={'yes' if is_stream else 'no'}):")
    for key in keys:
        print(f"  {key.object_number} {key.generation_number} R")


def _print_list_objects(
    doc: PDDocument, *, output_format: str = _FORMAT_TEXT,
) -> None:
    """Dump the xref table with state (used/in_objstm/free/synthetic) and
    offset / objstm-id columns. Mirrors ``qpdf --show-xref`` output."""
    cos_doc: COSDocument = doc.get_document()
    keys = sorted(cos_doc.get_object_keys())
    start_xref = cos_doc.get_start_xref()
    is_stream = cos_doc.is_xref_stream()
    rows = []
    for key in keys:
        state, offset, in_objstm = _xref_state_for(cos_doc, key)
        rows.append({
            "object_number": key.object_number,
            "generation_number": key.generation_number,
            "state": state,
            "offset": offset,
            "in_objstm": in_objstm,
        })
    if output_format == _FORMAT_JSON:
        payload = {
            "startxref": start_xref,
            "is_xref_stream": is_stream,
            "entries": rows,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"Xref ({len(keys)} entries, startxref={start_xref}, "
          f"stream={'yes' if is_stream else 'no'}):")
    print(f"  {'num':>6} {'gen':>5} {'state':<10} {'offset':>10} {'objstm':>8}")
    for row in rows:
        offset_str = "-" if row["offset"] is None else str(row["offset"])
        objstm_str = "-" if row["in_objstm"] is None else str(row["in_objstm"])
        print(
            f"  {row['object_number']:>6} {row['generation_number']:>5} "
            f"{row['state']:<10} {offset_str:>10} {objstm_str:>8}"
        )


def _print_catalog(
    doc: PDDocument, *,
    max_depth: int = _MAX_DEPTH, output_format: str = _FORMAT_TEXT,
) -> int:
    """Pretty-print the document catalog dictionary subtree, resolving
    indirect references inline (one level deep is the upstream default;
    deeper resolution is bounded by ``max_depth``). Returns 4 if the
    catalog is missing — corrupt-PDF case."""
    cos_doc: COSDocument = doc.get_document()
    catalog = cos_doc.get_catalog()
    if catalog is None:
        print("pdfdebugger: catalog missing from document", flush=True)
        return 4
    if output_format == _FORMAT_JSON:
        payload = {
            "catalog": _node_to_jsonable(
                catalog, visited=set(), depth=0,
                follow_refs=True, max_depth=max_depth,
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    out: list[str] = ["Catalog:"]
    _format_node(
        catalog, 0, out,
        visited=set(), follow_refs=True, max_depth=max_depth,
    )
    print("\n".join(out))
    return 0


def _tokenize_stream_bytes(data: bytes) -> list[Any]:
    """Tokenize ``data`` as a PDF content stream and return the token
    list. Lazily imports ``PDFStreamParser`` to keep the module import
    cheap for non-token paths."""
    if not data:
        return []
    from pypdfbox.io import RandomAccessReadBuffer
    from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser

    src = RandomAccessReadBuffer.from_bytes(data)
    try:
        parser = PDFStreamParser(src)
        try:
            return parser.get_tokens()
        finally:
            close = getattr(parser, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001 — best-effort close
                    pass
    finally:
        src.close()
    # Reference for type-checker — the parser tokens may include Operator.
    _ = Operator


def _format_token(tok: Any) -> str:
    """Render a single token from :class:`PDFStreamParser` as plain text."""
    from pypdfbox.pdfparser.pdf_stream_parser import Operator

    if isinstance(tok, Operator):
        return tok.get_name()
    if isinstance(tok, COSBase):
        simple = _fmt_simple(tok)
        if simple is not None:
            return simple
        if isinstance(tok, COSArray):
            inner = " ".join(_format_token(x) for x in tok)
            return f"[ {inner} ]"
        if isinstance(tok, COSDictionary):
            parts = [f"/{k.name} {_format_token(v)}" for k, v in tok.entry_set()]
            return "<< " + " ".join(parts) + " >>"
    return repr(tok)


def _token_to_jsonable(tok: Any) -> Any:
    from pypdfbox.pdfparser.pdf_stream_parser import Operator

    if isinstance(tok, Operator):
        return {"op": tok.get_name()}
    if isinstance(tok, COSBase):
        return _node_to_jsonable(
            tok, visited=set(), depth=0, follow_refs=False, max_depth=_MAX_DEPTH,
        )
    return repr(tok)


def _print_page_tokens(
    doc: PDDocument, one_based_index: int, *,
    output_format: str = _FORMAT_TEXT,
) -> int:
    """Tokenize the content stream of page ``one_based_index`` and print
    one operand-or-operator per line (text format) or a JSON list."""
    n = doc.get_number_of_pages()
    if one_based_index < 1 or one_based_index > n:
        print(
            f"pdfdebugger: page {one_based_index} out of range (1..{n})",
            flush=True,
        )
        return 4
    page = doc.get_page(one_based_index - 1)
    data = page.get_contents()
    try:
        tokens = _tokenize_stream_bytes(data)
    except Exception as exc:  # noqa: BLE001 — parser errors surface to CLI
        print(f"pdfdebugger: tokenize page {one_based_index}: {exc}", flush=True)
        return 4
    if output_format == _FORMAT_JSON:
        payload = {
            "page": one_based_index,
            "tokens": [_token_to_jsonable(t) for t in tokens],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"Page {one_based_index} content stream ({len(tokens)} tokens):")
    for tok in tokens:
        print(f"  {_format_token(tok)}")
    return 0


def _hex_prefix(b: bytes | None) -> str | None:
    """Return the first ``_HEX_PREFIX_BYTES`` bytes of ``b`` as a hex
    string, or ``None`` if ``b`` is empty / missing. We deliberately
    truncate /U and /O hashes to avoid leaking material that would help
    an offline cracker."""
    if not b:
        return None
    return b[:_HEX_PREFIX_BYTES].hex()


def _print_encryption(doc: PDDocument, *, output_format: str = _FORMAT_TEXT) -> int:
    """Print the document's encryption parameters. /U and /O are shown
    as a short hex prefix only — never the full hash — to limit what
    a debug-log capture leaks."""
    cos_doc = doc.get_document()
    if not cos_doc.is_encrypted():
        if output_format == _FORMAT_JSON:
            print(json.dumps({"encrypted": False}, indent=2, sort_keys=True))
        else:
            print("Encryption: <not encrypted>")
        return 0
    enc = doc.get_encryption()
    if enc is None:
        # Encrypted flag in trailer but no /Encrypt dict — corrupt file.
        if output_format == _FORMAT_JSON:
            print(json.dumps({"encrypted": True, "encryption": None},
                              indent=2, sort_keys=True))
        else:
            print("Encryption: <encrypted but /Encrypt dict missing>")
        return 0
    payload: dict[str, Any] = {
        "encrypted": True,
        "filter": enc.get_filter(),
        "sub_filter": enc.get_sub_filter(),
        "v": enc.get_v(),
        "r": enc.get_revision(),
        "length": enc.get_length(),
        "p": enc.get_p(),
        "encrypt_metadata": enc.is_encrypt_meta_data(),
        "u_hex_prefix": _hex_prefix(enc.get_u()),
        "o_hex_prefix": _hex_prefix(enc.get_o()),
    }
    if output_format == _FORMAT_JSON:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print("Encryption:")
    print(f"  /Filter      : {payload['filter']}")
    print(f"  /SubFilter   : {payload['sub_filter']}")
    print(f"  /V           : {payload['v']}")
    print(f"  /R           : {payload['r']}")
    print(f"  /Length      : {payload['length']}")
    print(f"  /P           : {payload['p']}")
    print(f"  /EncryptMeta : {payload['encrypt_metadata']}")
    # Truncated to first 8 hex chars (4 bytes) — never the full hash.
    u_prefix = payload["u_hex_prefix"] or "<none>"
    o_prefix = payload["o_hex_prefix"] or "<none>"
    print(f"  /U (prefix)  : {u_prefix}... (truncated for security)")
    print(f"  /O (prefix)  : {o_prefix}... (truncated for security)")
    return 0


# ---------- interactive walker ----------


_WALKER_HELP = """\
Commands:
  ls                   list children of the current node
  cd <key|index>       descend into the named child (cd .. to ascend,
                       cd / to jump back to the trailer)
  cd <num> <gen>       follow an indirect ref by object key
  pwd                  print path from root to current node
  cat                  pretty-print the current node (depth 6)
  hex                  hex dump of the current node (streams only)
  ref <num> [gen]      jump to indirect object num gen R
  find <key>           list paths in the visited subtree where dict-key matches
  raw                  preview the raw (encoded) stream bytes
  decode               preview the decoded (filter-applied) stream bytes
  q | quit | exit      leave the walker
  help                 show this list
"""

_WALKER_HEX_MAX_BYTES = 1024  # cap for ``hex`` output so large streams stay sane
_WALKER_DEFAULT_DEPTH = 6


def _node_type_label(node: COSBase | None) -> str:
    """Return a short type tag for ``ls`` output (``dict``, ``array``,
    ``stream``, ``ref``, ``name`` etc)."""
    if node is None:
        return "<unresolved>"
    if isinstance(node, COSStream):
        return "stream"
    if isinstance(node, COSDictionary):
        return "dict"
    if isinstance(node, COSArray):
        return "array"
    if isinstance(node, COSObject):
        return f"ref={node.object_number} {node.generation_number} R"
    if isinstance(node, COSName):
        return f"name=/{node.name}"
    if isinstance(node, COSString):
        try:
            return f"string=({node.get_string()!r})"
        except (UnicodeDecodeError, ValueError):
            return f"string=<{node.get_bytes().hex()}>"
    if isinstance(node, COSBoolean):
        return f"bool={'true' if node.value else 'false'}"
    if isinstance(node, COSInteger):
        return f"int={node.value}"
    if isinstance(node, COSFloat):
        return f"float={node.value!r}"
    if isinstance(node, COSNull):
        return "null"
    return type(node).__name__


def _resolve_for_navigation(node: COSBase | None) -> COSBase | None:
    """Follow ``COSObject`` indirect refs until we hit a concrete value.

    The walker treats refs as transparent for ``ls``/``cd`` so users can
    descend without an explicit ``ref`` jump every level."""
    seen: set[int] = set()
    cur: COSBase | None = node
    while isinstance(cur, COSObject):
        if id(cur) in seen:
            return cur  # cycle; stop here so we don't infinite-loop
        seen.add(id(cur))
        cur = cur.get_object()
    return cur


def _walker_list_children(node: COSBase | None) -> list[tuple[str, COSBase]]:
    """Return a list of ``(label, child)`` tuples for the ls/cd surface.

    Dictionary children are labelled with ``/Key`` and array children with
    ``[index]``. Streams expose their dict entries (the body itself is
    accessed via ``raw`` / ``decode`` / ``hex``). Scalars have no
    children."""
    target = _resolve_for_navigation(node)
    children: list[tuple[str, COSBase]] = []
    if isinstance(target, COSStream):
        for k, v in target.entry_set():
            children.append((f"/{k.name}", v))
        return children
    if isinstance(target, COSDictionary):
        for k, v in target.entry_set():
            children.append((f"/{k.name}", v))
        return children
    if isinstance(target, COSArray):
        for idx, item in enumerate(target):
            children.append((f"[{idx}]", item))
        return children
    return children


def _walker_lookup_child(
    node: COSBase | None, token: str,
) -> COSBase | None:
    """Resolve a single ``cd`` token (``/Foo``, ``Foo``, or ``[n]``) against
    ``node``'s children. Returns the child node or ``None`` if unmatched."""
    target = _resolve_for_navigation(node)
    if target is None:
        return None
    # Array index — accept both bare ``5`` and bracketed ``[5]``.
    if isinstance(target, COSArray):
        spec = token.strip()
        if spec.startswith("[") and spec.endswith("]"):
            spec = spec[1:-1]
        try:
            idx = int(spec)
        except ValueError:
            return None
        if 0 <= idx < len(target):
            return target[idx]
        return None
    if isinstance(target, (COSDictionary, COSStream)):
        # ``cd /Foo`` and ``cd Foo`` both work — strip a single leading slash.
        key = token[1:] if token.startswith("/") else token
        return target.get_dictionary_object(COSName.get_pdf_name(key))
    return None


def _walker_print_node(node: COSBase | None, *, depth: int) -> None:
    """Pretty-print ``node`` to stdout for the ``cat`` command. Depth is
    bounded so a top-level ``cat`` on the trailer doesn't dump the whole
    document."""
    out: list[str] = []
    _format_node(
        node, 0, out, visited=set(),
        follow_refs=False, max_depth=depth,
    )
    print("\n".join(out))


def _walker_find_in_subtree(
    node: COSBase | None, key: str, *, max_results: int = 64,
) -> list[str]:
    """Walk the subtree rooted at ``node`` and return the paths of every
    dict whose key set contains ``key`` (case-sensitive, slash optional).

    Cycles are guarded by an id-set; recursion is bounded by
    ``_MAX_DEPTH`` to mirror the pretty-printer."""
    target = key[1:] if key.startswith("/") else key
    matches: list[str] = []
    visited: set[int] = set()

    def walk(n: COSBase | None, path: str, depth: int) -> None:
        if len(matches) >= max_results or depth >= _MAX_DEPTH:
            return
        n = _resolve_for_navigation(n)
        if n is None or id(n) in visited:
            return
        visited.add(id(n))
        try:
            if isinstance(n, (COSStream, COSDictionary)):
                for k, v in n.entry_set():
                    if k.name == target:
                        matches.append(f"{path}/{k.name}")
                    walk(v, f"{path}/{k.name}", depth + 1)
            elif isinstance(n, COSArray):
                for idx, item in enumerate(n):
                    walk(item, f"{path}[{idx}]", depth + 1)
        finally:
            visited.discard(id(n))

    walk(node, "", 0)
    return matches


def _walker_stream_preview(
    node: COSBase | None, *, mode: str, limit: int = _MAX_STREAM_PREVIEW * 4,
) -> str:
    """Return a hex-dump preview of a stream body. ``mode`` is ``"raw"``
    or ``"decoded"``. Returns a human-readable error string when the
    target isn't a stream or the requested form is unavailable."""
    target = _resolve_for_navigation(node)
    if not isinstance(target, COSStream):
        return "<not a stream>"
    try:
        if mode == "raw":
            with target.create_raw_input_stream() as src:
                data = src.read(limit)
        else:
            with target.create_input_stream() as src:
                data = src.read(limit)
    except Exception as exc:  # noqa: BLE001 — surface filter errors verbatim
        return f"<error: {exc}>"
    return _hex_dump(data)


def _interactive_walker(doc: PDDocument) -> int:
    """Drop into a textual REPL rooted at the document trailer.

    Returns 0 on a clean ``q`` / EOF, ``4`` when the trailer isn't
    available (corrupt file). The dispatch is a flat if/elif so each
    command can short-circuit cleanly without nested state machines."""
    cos_doc = doc.get_document()
    trailer = cos_doc.get_trailer()
    if trailer is None:
        print("pdfdebugger: trailer missing; cannot start walker", flush=True)
        return 4

    # ``stack`` is the (label, node) breadcrumb from trailer to current.
    # Root is labelled ``trailer`` so ``pwd`` reads naturally.
    stack: list[tuple[str, COSBase]] = [("trailer", trailer)]

    def current() -> COSBase:
        return stack[-1][1]

    def path_str() -> str:
        if len(stack) == 1:
            return "trailer"
        head, *tail = stack
        return head[0] + "".join(t[0] for t in tail)

    print(
        "pdfdebugger interactive walker — type 'help' for commands, "
        "'q' to quit."
    )
    print(f"At: {path_str()}  ({_node_type_label(current())})")

    while True:
        try:
            raw_line = input("(pdfdebugger) ")
        except EOFError:
            print()
            return 0
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("q", "quit", "exit"):
            return 0
        if cmd == "help":
            print(_WALKER_HELP, end="")
            continue
        if cmd == "pwd":
            print(path_str())
            continue
        if cmd == "ls":
            children = _walker_list_children(current())
            if not children:
                print("<no children>")
                continue
            for label, child in children:
                print(f"  {label:<24} {_node_type_label(child)}")
            continue
        if cmd == "cat":
            depth = _WALKER_DEFAULT_DEPTH
            if args:
                try:
                    depth = max(1, int(args[0]))
                except ValueError:
                    print("cat: depth must be an integer")
                    continue
            _walker_print_node(current(), depth=depth)
            continue
        if cmd == "hex":
            data_block = _walker_stream_preview(
                current(), mode="raw", limit=_WALKER_HEX_MAX_BYTES,
            )
            print(data_block)
            continue
        if cmd == "raw":
            print(_walker_stream_preview(current(), mode="raw"))
            continue
        if cmd == "decode":
            print(_walker_stream_preview(current(), mode="decoded"))
            continue
        if cmd == "find":
            if not args:
                print("find: usage: find <key>")
                continue
            hits = _walker_find_in_subtree(current(), args[0])
            if not hits:
                print(f"<no matches for /{args[0].lstrip('/')}>")
                continue
            for hit in hits:
                print(f"  {hit}")
            continue
        if cmd == "ref":
            if not args:
                print("ref: usage: ref <num> [gen]")
                continue
            try:
                num = int(args[0])
                gen = int(args[1]) if len(args) > 1 else 0
            except ValueError:
                print("ref: num and gen must be integers")
                continue
            key = COSObjectKey(num, gen)
            if not cos_doc.has_object(key):
                print(f"ref: object {num} {gen} R not in pool")
                continue
            target = cos_doc.get_object_from_pool(key).get_object()
            stack = [
                ("trailer", trailer),
                (f"#{num} {gen} R", target),
            ]
            print(f"At: {path_str()}  ({_node_type_label(target)})")
            continue
        if cmd == "cd":
            if not args:
                print(
                    "cd: usage: cd <key|index> | cd .. | cd / | cd <num> <gen>"
                )
                continue
            # ``cd ..`` ascends one level.
            if args[0] == "..":
                if len(stack) > 1:
                    stack.pop()
                print(f"At: {path_str()}  ({_node_type_label(current())})")
                continue
            # ``cd /`` resets to trailer.
            if args[0] == "/":
                stack = [("trailer", trailer)]
                print(f"At: {path_str()}  ({_node_type_label(current())})")
                continue
            # ``cd <num> <gen>`` shorthand for ``ref``.
            if len(args) == 2 and all(a.lstrip("-").isdigit() for a in args):
                num = int(args[0])
                gen = int(args[1])
                key = COSObjectKey(num, gen)
                if not cos_doc.has_object(key):
                    print(f"cd: object {num} {gen} R not in pool")
                    continue
                target = cos_doc.get_object_from_pool(key).get_object()
                stack = [
                    ("trailer", trailer),
                    (f"#{num} {gen} R", target),
                ]
                print(f"At: {path_str()}  ({_node_type_label(target)})")
                continue
            child = _walker_lookup_child(current(), args[0])
            if child is None:
                print(f"cd: no child '{args[0]}'")
                continue
            label = args[0] if args[0].startswith(("/", "[")) else f"/{args[0]}"
            stack.append((label, child))
            print(f"At: {path_str()}  ({_node_type_label(current())})")
            continue
        print(f"unknown command: {cmd!r} (type 'help' for the list)")


# ---------- CLI entry ----------


def _parse_show_object(spec: str) -> tuple[int, int] | None:
    """Parse ``"NUM"`` or ``"NUM.GEN"`` from --show-object.

    Returns ``(num, gen)`` on success, ``None`` on a malformed spec."""
    text = spec.strip()
    if not text:
        return None
    if "." in text:
        head, _, tail = text.partition(".")
        try:
            return int(head), int(tail)
        except ValueError:
            return None
    try:
        return int(text), 0
    except ValueError:
        return None


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"pdfdebugger: {src}: not a file", flush=True)
        return 4

    depth = args.depth if args.depth is not None and args.depth > 0 else _MAX_DEPTH
    password = args.password
    output_format = getattr(args, "output_format", _FORMAT_TEXT)

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
            _print_trailer(doc, max_depth=depth, output_format=output_format)
            return 0
        if args.page is not None:
            return _print_page(
                doc, args.page, max_depth=depth, output_format=output_format,
            )
        if args.object is not None:
            nums = args.object
            try:
                int_nums = [int(n) for n in nums]
            except ValueError:
                print(
                    "pdfdebugger: -object expects integer NUM [GEN]",
                    flush=True,
                )
                return 2
            if len(int_nums) == 1:
                num, gen = int_nums[0], 0
            elif len(int_nums) == 2:
                num, gen = int_nums[0], int_nums[1]
            else:
                print(
                    "pdfdebugger: -object expects NUM [GEN] (one or two ints)",
                    flush=True,
                )
                return 2
            return _print_object(
                doc, num, gen, max_depth=depth, output_format=output_format,
            )
        if args.show_object is not None:
            parsed = _parse_show_object(args.show_object)
            if parsed is None:
                print(
                    "pdfdebugger: --show-object expects NUM[.GEN] (e.g. 12 or 12.0)",
                    flush=True,
                )
                return 2
            num, gen = parsed
            return _print_object(
                doc, num, gen, max_depth=depth, output_format=output_format,
            )
        if args.xref:
            _print_xref(doc, output_format=output_format)
            return 0
        if args.list_objects:
            _print_list_objects(doc, output_format=output_format)
            return 0
        if args.catalog:
            return _print_catalog(
                doc, max_depth=depth, output_format=output_format,
            )
        if args.tree:
            _print_tree(doc, max_depth=depth, output_format=output_format)
            return 0
        if args.dump_stream is not None:
            parsed = _parse_show_object(args.dump_stream)
            if parsed is None:
                print(
                    "pdfdebugger: --dump-stream expects NUM[.GEN] (e.g. 12 or 12.0)",
                    flush=True,
                )
                return 2
            num, gen = parsed
            return _dump_stream(doc, num, gen, output_format=output_format)
        if args.show_page_tokens is not None:
            return _print_page_tokens(
                doc, args.show_page_tokens, output_format=output_format,
            )
        if args.show_encryption:
            return _print_encryption(doc, output_format=output_format)
        if args.interactive:
            return _interactive_walker(doc)
        _print_summary(doc, src, output_format=output_format)
        return 0


# Re-export for static analysis / consumers that import the symbol set.
__all__ = ["build_parser", "run"]


# Keep type checkers calm about COSBase being "used" — it gates _fmt_simple.
_ = COSBase
_ = Any
