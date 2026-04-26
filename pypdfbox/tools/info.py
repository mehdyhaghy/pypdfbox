"""
``pypdfbox info FILE`` — print metadata for a PDF.

There is no equivalent class in upstream PDFBox (the closest stand-in is
``PDFDebugger``, which is GUI-driven). We add ``info`` here as a small,
read-only inspection command suitable for CI logs and quick checks.

Output mirrors what most ``pdfinfo``-style utilities print: header version,
catalog override version (if any), page count, encryption flag, and every
``/Info`` dictionary entry that is actually populated. The output format is
plain key/value lines — the contract is "human-readable", not machine-parsed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.pdmodel import PDDocument


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "info",
        help="print PDF metadata (version, page count, /Info dict)",
        description="Print PDF version, page count, encryption status, and every "
        "populated entry of the document /Info dictionary.",
    )
    p.add_argument("input", help="path to the input PDF")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"info: {src}: not a file", flush=True)
        return 4
    with PDDocument.load(src) as doc:
        cos_doc = doc.get_document()
        header_version = cos_doc.get_version()
        print(f"File: {src}")
        print(f"PDF version (header): {header_version:.1f}")
        try:
            catalog_version = doc.get_document_catalog().get_version()
        except Exception:  # noqa: BLE001 — defensive, malformed catalogs
            catalog_version = None
        if catalog_version is not None:
            print(f"PDF version (catalog override): {catalog_version}")
        print(f"Effective version: {doc.get_version():.1f}")
        print(f"Pages: {doc.get_number_of_pages()}")
        print(f"Encrypted: {'yes' if doc.is_encrypted() else 'no'}")

        info = doc.get_document_information()
        # Print only populated entries — empty lines from absent fields
        # are noise.
        rows: list[tuple[str, str]] = []
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
                rows.append((label, str(value)))
        # Tack on any custom (non-standard) keys after the standard set.
        standard = {
            "Title", "Author", "Subject", "Keywords", "Creator",
            "Producer", "CreationDate", "ModDate", "Trapped",
        }
        for key in sorted(info.get_metadata_keys()):
            if key in standard:
                continue
            value = info.get_custom_metadata_value(key)
            if value:
                rows.append((key, value))
        if rows:
            print("Info:")
            for label, value in rows:
                print(f"  {label}: {value}")
    return 0
