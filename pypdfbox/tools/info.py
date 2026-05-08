"""
``pypdfbox info FILE [-password PWD] [-metadata] [-output txt|json]``
— print metadata for a PDF.

There is no exact equivalent class in upstream PDFBox (the closest
stand-in is ``PDFDebugger``, which is GUI-driven). pypdfbox ships
``info`` as a small read-only inspection command suitable for CI logs
and quick checks.

Default output mirrors what most ``pdfinfo``-style utilities print:
header version, catalog override version (if any), page count,
encryption flag, and every populated entry of the document ``/Info``
dictionary (Title / Author / Subject / Keywords / Creator / Producer /
CreationDate / ModificationDate / Trapped, plus any custom keys).

Flags:

* ``-password`` — open password-protected files.
* ``-metadata`` — additionally dump the catalog ``/Metadata`` (XMP)
  stream as raw XML.
* ``-output txt|json`` — pick the output format. ``txt`` (default) is
  the human-readable form; ``json`` emits a single JSON object suitable
  for piping into ``jq``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import PDInvalidPasswordException


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "info",
        help="print PDF metadata (version, page count, /Info dict)",
        description="Print PDF version, page count, encryption status, and "
        "every populated entry of the document /Info dictionary. Optionally "
        "dump the XMP /Metadata stream and choose between text and JSON output.",
    )
    p.add_argument("input", help="path to the input PDF")
    p.add_argument(
        "-password", "--password", dest="password", default="",
        metavar="PASSWORD",
        help="password for the PDF (defaults to empty string)",
    )
    p.add_argument(
        "-metadata", "--metadata", dest="metadata", action="store_true",
        help="also dump the catalog /Metadata (XMP) stream",
    )
    p.add_argument(
        "-output", "--output", dest="output", default="txt",
        choices=("txt", "json"), metavar="FORMAT",
        help="output format: 'txt' (default) or 'json'",
    )
    p.set_defaults(func=run)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


_STANDARD_INFO_KEYS = (
    "Title", "Author", "Subject", "Keywords", "Creator", "Producer",
    "CreationDate", "ModDate", "Trapped",
)


def _collect_info(doc: PDDocument, src: Path) -> dict[str, object]:
    """Snapshot the bits of metadata ``info`` reports on, as a plain dict
    (so the txt and json branches can share the gather step)."""
    cos_doc = doc.get_document()
    header_version = cos_doc.get_version()
    try:
        catalog_version = doc.get_document_catalog().get_version()
    except Exception:  # noqa: BLE001 — defensive, malformed catalogs
        catalog_version = None

    info = doc.get_document_information()
    info_rows: dict[str, str] = {}
    for label, value in (
        ("Title", info.get_title()),
        ("Author", info.get_author()),
        ("Subject", info.get_subject()),
        ("Keywords", info.get_keywords()),
        ("Creator", info.get_creator()),
        ("Producer", info.get_producer()),
        ("CreationDate", info.get_property_string_value("CreationDate")),
        ("ModDate", info.get_property_string_value("ModDate")),
        ("Trapped", info.get_trapped()),
    ):
        if value:
            info_rows[label] = str(value)
    custom: dict[str, str] = {}
    for key in sorted(info.get_metadata_keys()):
        if key in _STANDARD_INFO_KEYS:
            continue
        value = info.get_custom_metadata_value(key)
        if value:
            custom[key] = value

    return {
        "file": str(src),
        "header_version": header_version,
        "catalog_version": catalog_version,
        "effective_version": doc.get_version(),
        "pages": doc.get_number_of_pages(),
        "encrypted": bool(doc.is_encrypted()),
        "info": info_rows,
        "custom": custom,
    }


def _read_xmp(doc: PDDocument) -> str | None:
    """Return the catalog ``/Metadata`` stream as decoded UTF-8 XML, or
    ``None`` if the document carries no XMP."""
    try:
        meta = doc.get_document_catalog().get_metadata()
    except Exception:  # noqa: BLE001 — defensive
        return None
    if meta is None:
        return None
    try:
        text = meta.get_metadata_as_string()
        if text is None:
            return None
        return text if isinstance(text, str) else str(text)
    except Exception:  # noqa: BLE001 — fall back to raw bytes
        try:
            with meta.create_input_stream() as stream:
                raw = stream.read()
            return bytes(raw).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return None


def _print_txt(snapshot: dict[str, object], xmp: str | None) -> None:
    print(f"File: {snapshot['file']}")
    header_version = snapshot["header_version"]
    if isinstance(header_version, (int, float)):
        print(f"PDF version (header): {float(header_version):.1f}")
    else:
        print(f"PDF version (header): {header_version}")
    catalog_version = snapshot["catalog_version"]
    if catalog_version is not None:
        print(f"PDF version (catalog override): {catalog_version}")
    effective = snapshot["effective_version"]
    if isinstance(effective, (int, float)):
        print(f"Effective version: {float(effective):.1f}")
    else:
        print(f"Effective version: {effective}")
    print(f"Pages: {snapshot['pages']}")
    print(f"Encrypted: {'yes' if snapshot['encrypted'] else 'no'}")

    info_rows = snapshot["info"]
    custom = snapshot["custom"]
    assert isinstance(info_rows, dict)
    assert isinstance(custom, dict)
    if info_rows or custom:
        print("Info:")
        for label, value in info_rows.items():
            print(f"  {label}: {value}")
        for key, value in custom.items():
            print(f"  {key}: {value}")
    if xmp is not None:
        print("Metadata (XMP):")
        print(xmp)


def _print_json(snapshot: dict[str, object], xmp: str | None) -> None:
    payload = dict(snapshot)
    if xmp is not None:
        payload["xmp"] = xmp
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"info: {src}: not a file", flush=True)
        return 4
    try:
        doc = PDDocument.load(src, password=getattr(args, "password", "") or "")
    except PDInvalidPasswordException as exc:
        print(f"info: {exc}", flush=True)
        return 1
    try:
        snapshot = _collect_info(doc, src)
        xmp = _read_xmp(doc) if getattr(args, "metadata", False) else None
        fmt = getattr(args, "output", "txt") or "txt"
        if fmt == "json":
            _print_json(snapshot, xmp)
        else:
            _print_txt(snapshot, xmp)
    finally:
        doc.close()
    return 0
