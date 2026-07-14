"""
``pypdfbox writedecodedstream -i in.pdf [-o out.pdf] [-password PWD]
[-skipImages]`` — load a PDF and write it back with every ``COSStream``
fully decoded (filter chain stripped, raw body replaced by the decoded
payload). Useful for debugging compressed PDFs.

Mirrors upstream ``org.apache.pdfbox.tools.WriteDecodedDoc``. Upstream's
processing loop iterates the cross-reference table, looks up each
``COSObject``, and for every ``COSStream`` it: reads the decoded bytes,
removes the ``/Filter`` (and ``/DecodeParms``) entries, then writes the
decoded bytes back as the new raw body. With ``-skipImages``, ``XObject``
streams of subtype ``/Image`` are left untouched (image filters often
carry irreversible parameters like JPEG DCT).

Output filename rule matches upstream: when ``-o`` is omitted, append
``_unc.pdf`` to the input (stripping ``.pdf`` first if present).

Exit codes follow upstream: ``0`` success, ``4`` IO error.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import InvalidPasswordException

# /DecodeParms must be cleared alongside /Filter — leaving it on a now-
# unfiltered stream is technically legal (a non-conformant reader may just
# ignore it) but PDFBox upstream removes it implicitly via
# ``COSStream.createOutputStream()`` semantics on writeback. We track the
# name explicitly so we don't depend on undocumented side effects.
_DECODE_PARMS = COSName.get_pdf_name("DecodeParms")
_FILTER = COSName.get_pdf_name("Filter")
_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_XOBJECT = COSName.get_pdf_name("XObject")
_IMAGE = COSName.get_pdf_name("Image")


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "writedecodedstream",
        help="rewrite a PDF with every stream decoded (filters stripped)",
        description="Load a PDF and write it back out with every COSStream "
        "fully decoded — the /Filter chain is removed and the raw body is "
        "replaced by the decoded bytes. Useful for inspecting compressed "
        "content streams, font programs, and metadata in a PDF debugger.",
    )
    p.add_argument(
        "-i", "--input", dest="input", required=True, metavar="INFILE",
        help="PDF whose streams should be decoded",
    )
    p.add_argument(
        "-o", "--output", dest="output", default=None, metavar="OUTFILE",
        help="destination PDF (default: INFILE with '.pdf' replaced by "
        "'_unc.pdf')",
    )
    p.add_argument(
        "-password", "--password", dest="password", default="", metavar="PASSWORD",
        help="password for an encrypted document (defaults to empty string)",
    )
    p.add_argument(
        "-skipImages", "--skip-images", dest="skip_images", action="store_true",
        help="leave image XObjects (Type=XObject, Subtype=Image) encoded",
    )
    p.set_defaults(func=run)


def calculate_output_filename(filename: str | Path) -> str:
    """Mirror upstream ``WriteDecodedDoc#calculateOutputFilename``:
    strip a trailing ``.pdf`` (case-insensitive) and append ``_unc.pdf``.
    """
    name = str(filename)
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    return name + "_unc.pdf"


def _process_stream(stream: COSStream, *, skip_images: bool) -> None:
    """Decode ``stream`` in place: strip ``/Filter`` + ``/DecodeParms`` and
    replace the raw body with the decoded bytes. Mirrors upstream's
    ``processObject`` body for a single stream."""
    if skip_images:
        type_item = stream.get_item(_TYPE)
        subtype_item = stream.get_item(_SUBTYPE)
        if type_item == _XOBJECT and subtype_item == _IMAGE:
            return
    if not stream.has_data():
        return
    try:
        # ``create_input_stream`` runs the full /Filter chain and (when a
        # security handler is attached) the decryption pass. Pull the
        # decoded payload eagerly so we can swap it in as the raw body.
        with stream.create_input_stream() as src:
            decoded = src.read()
    except Exception:  # noqa: BLE001 — upstream catches IOException and skips
        # PDFBox prints "skip <key> obj: <msg>" to stderr and moves on; we
        # mirror the swallow-and-continue behaviour so a single corrupt
        # stream doesn't sink the whole rewrite.
        return
    stream.remove_item(_FILTER)
    stream.remove_item(_DECODE_PARMS)
    # Raw write: bytes go in verbatim, so subsequent reads see the
    # already-decoded payload (no filter chain to undo).
    with stream.create_raw_output_stream() as out:
        out.write(decoded)


def write_decoded(
    input_path: str | Path,
    output_path: str | Path,
    password: str = "",
    *,
    skip_images: bool = False,
) -> None:
    """Load ``input_path``, decode every ``COSStream`` (subject to
    ``skip_images``), then save the result to ``output_path``.

    Mirrors the body of upstream ``WriteDecodedDoc#doIt``.
    """
    doc = PDDocument.load(input_path, password=password)
    try:
        # Drop encryption — once we rewrite the streams, the original
        # ciphertext-derived raw bytes no longer match the (now plaintext)
        # /Length, so the only safe thing is to emit unencrypted.
        if doc.is_encrypted():
            doc.set_all_security_to_be_removed(True)

        cos_doc = doc.get_document()
        for cos_obj in cos_doc.get_objects():
            base = cos_obj.get_object()
            if isinstance(base, COSStream):
                _process_stream(base, skip_images=skip_images)

        # Force a classic xref table (object streams are themselves
        # filtered streams; emitting an xref-stream after we've stripped
        # filters would re-encode them, defeating the point). Upstream
        # WriteDecodedDoc likewise saves with
        # ``CompressParameters.NO_COMPRESSION``.
        from pypdfbox.pdfwriter.compress import CompressParameters

        cos_doc.set_xref_stream(False)
        doc.save(output_path, CompressParameters.NO_COMPRESSION)
    finally:
        doc.close()


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"writedecodedstream: {src}: not a file", flush=True)
        return 4

    out = Path(args.output) if args.output else Path(calculate_output_filename(src))

    password = args.password if args.password is not None else ""
    skip_images = bool(args.skip_images)

    try:
        write_decoded(src, out, password=password, skip_images=skip_images)
    except InvalidPasswordException as exc:
        print(f"writedecodedstream: {exc}", flush=True)
        return 1
    except OSError:
        # Re-raise so the dispatcher's standard OSError → exit-4 handler
        # (in cli.run_cli) prints the message and returns the right code.
        raise
    return 0
