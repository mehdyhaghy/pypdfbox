"""
``pypdfbox decrypt -i in.pdf [-o out.pdf] [-password PWD]`` — strip
security from a PDF.

Mirrors upstream ``org.apache.pdfbox.tools.Decrypt``. Upstream loads the
PDF (optionally with a password / certificate keystore), checks owner
permission, sets ``allSecurityToBeRemoved=true``, then saves.

Exit codes follow upstream: 0 success, 1 wrong password / no permission,
4 IO error.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import PDInvalidPasswordException


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "decrypt",
        help="strip encryption from a PDF",
        description="Strip encryption from a PDF document. Loads the input "
        "with the supplied password (default empty), removes the /Encrypt "
        "entry, and writes the result to OUTFILE (or back to INFILE).",
    )
    p.add_argument(
        "-i", "--input", dest="input", required=True, metavar="INFILE",
        help="encrypted PDF to decrypt",
    )
    p.add_argument(
        "-o", "--output", dest="output", default=None, metavar="OUTFILE",
        help="output decrypted PDF (defaults to overwriting INFILE)",
    )
    p.add_argument(
        "-password", "--password", dest="password", default="", metavar="PASSWORD",
        help="password for the document (defaults to empty string)",
    )
    p.set_defaults(func=run)


def decrypt_pdf(
    input_path: str | Path,
    output_path: str | Path,
    password: str = "",
) -> None:
    """Load ``input_path``, decrypt with ``password``, save to
    ``output_path`` without ``/Encrypt``.

    Mirrors the body of upstream ``org.apache.pdfbox.tools.Decrypt#call``.
    Raises :class:`PDInvalidPasswordException` if the password is wrong.
    """
    doc = PDDocument.load(input_path, password=password)
    try:
        if doc.is_encrypted():
            # Loader auto-decrypted via the password; flag /Encrypt for
            # removal so the writer emits a plain (unencrypted) file.
            doc.set_all_security_to_be_removed(True)
        doc.save(output_path)
    finally:
        doc.close()


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"decrypt: {src}: not a file", flush=True)
        return 4
    out = Path(args.output) if args.output else src
    password = args.password if args.password is not None else ""

    # Save in-place via tempfile to avoid corrupting the source on a
    # mid-write failure (matches upstream's safe-replace behaviour).
    if out == src:
        with tempfile.NamedTemporaryFile(
            dir=src.parent,
            prefix=f".{src.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
        try:
            try:
                decrypt_pdf(src, tmp_path, password=password)
            except PDInvalidPasswordException as exc:
                print(f"decrypt: {exc}", flush=True)
                return 1
            tmp_path.replace(src)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        return 0

    try:
        decrypt_pdf(src, out, password=password)
    except PDInvalidPasswordException as exc:
        print(f"decrypt: {exc}", flush=True)
        return 1
    return 0
