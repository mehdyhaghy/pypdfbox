"""
``pypdfbox decrypt -i in.pdf [-o out.pdf] [-password PWD] [-keyStore KS] [-alias A]``
— strip security from a PDF.

Mirrors upstream ``org.apache.pdfbox.tools.Decrypt``. Upstream loads the
PDF (optionally with a password / certificate keystore), checks owner
permission, sets ``allSecurityToBeRemoved=true``, then saves.

Upstream ``Decrypt#call`` returns:

* ``0`` — success.
* ``1`` — document is not encrypted, OR the password unlocked it but only
  with user-level permissions (owner password is required to strip the
  ``/Encrypt`` dictionary).
* ``4`` — IO error (printed as ``Error decrypting document [<class>]: <msg>``).

The ``-keyStore`` / ``-alias`` flags select a certificate-based recipient
in the same way upstream's ``Loader.loadPDF(file, password, keyStore,
alias)`` does. Java's ``KeyStore`` has no stdlib counterpart in Python; we
load PKCS#12 files via ``cryptography.hazmat.primitives.serialization.pkcs12``
and surface the matching certificate + private key as a
:class:`PublicKeyDecryptionMaterial`. The alias selection mirrors Java's
"if alias is None, take the first key entry" behaviour. The pypdfbox
``PDDocument.decrypt`` path that wires public-key materials end-to-end
isn't yet plumbed, so for now ``-keyStore`` returns exit code ``4`` with a
clear error — but the CLI flag surface matches upstream so scripts port
cleanly.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import PDInvalidPasswordException

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from pypdfbox.pdmodel.encryption import PublicKeyDecryptionMaterial


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "decrypt",
        help="strip encryption from a PDF",
        description="Strip encryption from a PDF document. Loads the input "
        "with the supplied password (default empty), removes the /Encrypt "
        "entry, and writes the result to OUTFILE (or back to INFILE). "
        "Owner-password authentication is required.",
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
        help="password for the document (or for the keystore entry)",
    )
    p.add_argument(
        "-keyStore", "--keyStore", dest="key_store", default=None,
        metavar="KEYSTORE",
        help="path to a PKCS#12 keystore containing the recipient certificate "
        "(only required for documents encrypted via public-key recipients)",
    )
    p.add_argument(
        "-alias", "--alias", dest="alias", default=None, metavar="ALIAS",
        help="alias for the keystore entry to use (first key entry if omitted)",
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


def _load_pkcs12_keystore(
    keystore_path: str | Path,
    alias: str | None,
    password: str,
) -> PublicKeyDecryptionMaterial:
    """Load a PKCS#12 keystore and return a :class:`PublicKeyDecryptionMaterial`.

    Mirrors how upstream's ``KeyStore.getInstance("PKCS12")`` loads the
    file, then ``keyStore.getCertificate(alias)`` /
    ``keyStore.getKey(alias, password)`` resolves the entry. When ``alias``
    is ``None`` we pick the keystore's first key entry, matching the
    convention upstream samples use when no alias is supplied.
    """
    # Lazy import: keystores are uncommon, keep the dep cost off the
    # hot password-only decrypt path.
    from cryptography.hazmat.primitives.serialization.pkcs12 import (  # noqa: PLC0415
        load_pkcs12,
    )

    from pypdfbox.pdmodel.encryption import PublicKeyDecryptionMaterial  # noqa: PLC0415

    data = Path(keystore_path).read_bytes()
    pwd_bytes = password.encode("utf-8") if password else None
    bundle = load_pkcs12(data, pwd_bytes)

    # PKCS#12 alias matching: upstream uses ``KeyStore.getCertificate(alias)``.
    # ``cryptography`` exposes one private-key entry plus optional certificate-
    # only entries; public-key decryption needs the private-key entry.
    if bundle.cert is None or bundle.key is None:
        raise OSError("keystore has no private-key certificate entry")
    if alias is not None:
        target = alias.encode("utf-8")
        if bundle.cert.friendly_name not in (target, None):
            raise OSError(f"keystore has no private-key entry matching alias {alias!r}")

    material = PublicKeyDecryptionMaterial(
        certificate=bundle.cert.certificate,
        private_key=bundle.key,
        password=pwd_bytes,
    )
    return material


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"decrypt: {src}: not a file", flush=True)
        return 4
    out = Path(args.output) if args.output else src
    password = args.password if args.password is not None else ""
    keystore = getattr(args, "key_store", None)
    alias = getattr(args, "alias", None)

    if keystore is not None:
        # Surface-level: validate the keystore loads (upstream surfaces
        # CertificateException / IOException as exit 4). The end-to-end
        # public-key decryption pipeline is not yet wired into
        # ``PDDocument.decrypt`` — emit the upstream-shaped error so
        # scripts get a parity-friendly message.
        try:
            _load_pkcs12_keystore(keystore, alias, password)
        except OSError as exc:
            print(
                f"decrypt: Error decrypting document [{type(exc).__name__}]: {exc}",
                flush=True,
            )
            return 4
        except Exception as exc:  # noqa: BLE001 — surface as upstream IOException
            print(
                f"decrypt: Error decrypting document [{type(exc).__name__}]: {exc}",
                flush=True,
            )
            return 4
        # Standard-handler path is not yet wired for public-key materials.
        print(
            "decrypt: Error decrypting document [NotImplementedError]: "
            "public-key keystore decryption is not yet wired into "
            "PDDocument.decrypt; supply -password instead.",
            flush=True,
        )
        return 4

    # Owner / not-encrypted gates require probing the document first —
    # mirrors upstream's call() flow exactly.
    try:
        with PDDocument.load(src, password=password) as probe:
            if not probe.is_encrypted():
                # Upstream: ``SYSERR.println("Error: Document is not encrypted.");
                # return 1;``
                print("decrypt: Error: Document is not encrypted.", flush=True)
                return 1
            ap = probe.get_current_access_permission()
            if not ap.is_owner_permission():
                print(
                    "decrypt: Error: You are only allowed to decrypt a "
                    "document with the owner password.",
                    flush=True,
                )
                return 1
    except PDInvalidPasswordException as exc:
        print(f"decrypt: {exc}", flush=True)
        return 1
    except OSError as exc:
        print(
            f"decrypt: Error decrypting document [{type(exc).__name__}]: {exc}",
            flush=True,
        )
        return 4

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
            except OSError as exc:
                print(
                    f"decrypt: Error decrypting document [{type(exc).__name__}]: {exc}",
                    flush=True,
                )
                return 4
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
    except OSError as exc:
        print(
            f"decrypt: Error decrypting document [{type(exc).__name__}]: {exc}",
            flush=True,
        )
        return 4
    return 0
