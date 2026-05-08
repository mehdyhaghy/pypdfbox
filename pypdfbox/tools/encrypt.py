"""
``pypdfbox encrypt -i in.pdf [-o out.pdf] [-O OWNER] [-U USER] ...`` —
apply password (or certificate) encryption to a PDF.

Mirrors upstream ``org.apache.pdfbox.tools.Encrypt``. Upstream loads the
input, builds an :class:`AccessPermission` from the ``-can*`` flags,
constructs a :class:`StandardProtectionPolicy` (or
:class:`PublicKeyProtectionPolicy` when ``-certFile`` is supplied), calls
``document.protect(...)``, and saves.

Exit codes follow upstream: 0 success, 4 IO / certificate error.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import (
    AccessPermission,
    PublicKeyProtectionPolicy,
    PublicKeyRecipient,
    StandardProtectionPolicy,
)

if TYPE_CHECKING:  # pragma: no cover — annotation only
    from collections.abc import Iterable

    from cryptography.x509 import Certificate


# Upstream's default in PDFBox 3.0: ``private int keyLength = 256;``.
DEFAULT_KEY_LENGTH: int = 256


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "encrypt",
        help="encrypt a PDF document",
        description="Read an unencrypted PDF and encrypt it with a password "
        "(or X.509 certificate). Permissions can be tuned with the "
        "``-can*`` flags.",
    )
    p.add_argument(
        "-i", "--input", dest="input", required=True, metavar="INFILE",
        help="the PDF file to encrypt",
    )
    p.add_argument(
        "-o", "--output", dest="output", default=None, metavar="OUTFILE",
        help="the encrypted PDF file. If omitted the original is overwritten.",
    )
    p.add_argument(
        "-O", dest="owner_password", default=None, metavar="OWNER",
        help="set the owner password (ignored if -certFile is set)",
    )
    p.add_argument(
        "-U", dest="user_password", default=None, metavar="USER",
        help="set the user password (ignored if -certFile is set)",
    )
    p.add_argument(
        "-certFile", dest="cert_files", action="append", default=[],
        metavar="CERTFILE",
        help="path to X.509 certificate (repeat for multiple recipients)",
    )
    # Permission flags. Upstream defaults every permission to True; the
    # ``--no-*`` form turns one off without losing the others.
    _add_permission_flag(p, "-canAssemble", "can_assemble_document",
                         "assemble permission")
    _add_permission_flag(p, "-canExtractContent", "can_extract_content",
                         "extraction permission")
    _add_permission_flag(p, "-canExtractForAccessibility",
                         "can_extract_for_accessibility",
                         "extract-for-accessibility permission")
    _add_permission_flag(p, "-canFillInForm", "can_fill_in_form",
                         "form fill-in permission")
    _add_permission_flag(p, "-canModify", "can_modify", "modify permission")
    _add_permission_flag(p, "-canModifyAnnotations", "can_modify_annotations",
                         "modify-annotations permission")
    _add_permission_flag(p, "-canPrint", "can_print", "print permission")
    _add_permission_flag(p, "-canPrintFaithful", "can_print_faithful",
                         "print-faithful (high quality print) permission")

    p.add_argument(
        "-keyLength", dest="key_length", type=int,
        default=DEFAULT_KEY_LENGTH, metavar="BITS",
        help="key length in bits (valid: 40, 128 or 256). Default: %(default)s",
    )
    p.set_defaults(func=run)


def _add_permission_flag(
    parser: argparse.ArgumentParser, flag: str, dest: str, doc: str,
) -> None:
    """Register a tri-state-ish boolean flag.

    Upstream uses a simple ``boolean`` argument that PicoCLI flips to
    ``true`` when present; the default is already ``true``. We surface a
    matching ``-canX``/``--no-canX`` pair so users can disable individual
    permissions, while leaving every default at ``True``.
    """
    long_flag = flag.replace("-", "--", 1)
    no_flag = "--no-" + flag.lstrip("-")
    parser.add_argument(
        flag, long_flag, dest=dest, action="store_true", default=True,
        help=f"set the {doc} (default: True)",
    )
    parser.add_argument(
        no_flag, dest=dest, action="store_false",
        help=f"unset the {doc}",
    )


def _build_access_permission(args: argparse.Namespace) -> AccessPermission:
    ap = AccessPermission()
    ap.set_can_assemble_document(args.can_assemble_document)
    ap.set_can_extract_content(args.can_extract_content)
    ap.set_can_extract_for_accessibility(args.can_extract_for_accessibility)
    ap.set_can_fill_in_form(args.can_fill_in_form)
    ap.set_can_modify(args.can_modify)
    ap.set_can_modify_annotations(args.can_modify_annotations)
    ap.set_can_print(args.can_print)
    # Upstream's ``-canPrintFaithful`` maps directly to
    # ``AccessPermission.setCanPrintFaithful`` (the high-quality print bit).
    ap.set_can_print_faithful(args.can_print_faithful)
    return ap


def _load_certificates(cert_files: Iterable[str | Path]) -> list[Certificate]:
    """Load X.509 certificates from disk via ``cryptography``.

    The ``cryptography`` package is already a transitive dependency of the
    encryption cluster; importing it lazily keeps tools that never touch
    public-key encryption free of the import cost.
    """
    # Local import — keeps non-cert code paths free of the dependency.
    from cryptography import x509  # noqa: PLC0415 — lazy load

    certs = []
    for cert_path in cert_files:
        path = Path(cert_path)
        data = path.read_bytes()
        # Try DER first, fall back to PEM. Mirrors how Java's
        # CertificateFactory.generateCertificate sniffs both encodings.
        try:
            cert = x509.load_der_x509_certificate(data)
        except ValueError:
            cert = x509.load_pem_x509_certificate(data)
        certs.append(cert)
    return certs


def encrypt_pdf(
    input_path: str | Path,
    output_path: str | Path,
    *,
    owner_password: str | None = None,
    user_password: str | None = None,
    permissions: AccessPermission | None = None,
    cert_files: Iterable[str | Path] = (),
    key_length: int = DEFAULT_KEY_LENGTH,
) -> None:
    """Load ``input_path``, apply the chosen protection policy, save to
    ``output_path``.

    Mirrors the body of upstream ``org.apache.pdfbox.tools.Encrypt#call``.
    Skips encryption when the source is already encrypted (matches upstream's
    "Document is already encrypted" branch — caller decides whether that is
    an error).
    """
    ap = permissions if permissions is not None else AccessPermission()

    cert_list = list(cert_files)
    doc = PDDocument.load(input_path)
    try:
        if doc.is_encrypted():
            return  # Upstream prints to stderr and falls through to no save.

        if cert_list:
            ppp = PublicKeyProtectionPolicy()
            for cert in _load_certificates(cert_list):
                recip = PublicKeyRecipient()
                recip.set_permission(ap)
                recip.set_x509(cert)
                ppp.add_recipient(recip)
            ppp.set_encryption_key_length(key_length)
            doc.protect(ppp)
        else:
            spp = StandardProtectionPolicy(
                owner_password=owner_password,
                user_password=user_password,
                permissions=ap,
            )
            spp.set_encryption_key_length(key_length)
            doc.protect(spp)
        doc.save(output_path)
    finally:
        doc.close()


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"encrypt: {src}: not a file", flush=True)
        return 4
    out = Path(args.output) if args.output else src

    ap = _build_access_permission(args)

    # ``protect()`` rejects an already-encrypted source; warn (mirrors
    # upstream's "Error: Document is already encrypted." message) and exit
    # with the same code upstream would have returned (0 — upstream prints
    # the message and returns success).
    try:
        with PDDocument.load(src) as probe:
            if probe.is_encrypted():
                print("encrypt: Error: Document is already encrypted.", flush=True)
                return 0
            if probe.get_signature_dictionaries():
                print(
                    "encrypt: Warning: Document contains signatures which "
                    "will be invalidated by encryption.",
                    flush=True,
                )
    except OSError as exc:
        print(f"encrypt: Error encrypting PDF [{type(exc).__name__}]: {exc}",
              flush=True)
        return 4

    try:
        encrypt_pdf(
            src,
            out,
            owner_password=args.owner_password,
            user_password=args.user_password,
            permissions=ap,
            cert_files=args.cert_files,
            key_length=args.key_length,
        )
    except (OSError, ValueError, NotImplementedError) as exc:
        print(f"encrypt: Error encrypting PDF [{type(exc).__name__}]: {exc}",
              flush=True)
        return 4
    return 0
