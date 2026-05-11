"""``Encrypt`` class port — applies password / certificate encryption.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/Encrypt.java

Module is named ``encrypt_tool`` to avoid colliding with the existing
``pypdfbox/tools/encrypt.py`` argparse subcommand module.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.tools.encrypt import encrypt_pdf


class Encrypt:
    def __init__(self) -> None:
        self.owner_password: str | None = None
        self.user_password: str | None = None
        self.cert_files: list[Path] = []
        self.key_length: int = 256
        self.infile: Path | None = None
        self.outfile: Path | None = None
        # access-permission flags (mirrors upstream booleans)
        self.can_assemble: bool = True
        self.can_extract: bool = True
        self.can_extract_for_accessibility: bool = True
        self.can_fill_in_form: bool = True
        self.can_modify: bool = True
        self.can_modify_annotations: bool = True
        self.can_print: bool = True
        self.can_print_faithful: bool = True

    def _access_permission(self) -> AccessPermission:
        ap = AccessPermission()
        ap.set_can_assemble_document(self.can_assemble)
        ap.set_can_extract_content(self.can_extract)
        ap.set_can_extract_for_accessibility(self.can_extract_for_accessibility)
        ap.set_can_fill_in_form(self.can_fill_in_form)
        ap.set_can_modify(self.can_modify)
        ap.set_can_modify_annotations(self.can_modify_annotations)
        ap.set_can_print(self.can_print)
        ap.set_can_print_faithful(self.can_print_faithful)
        return ap

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        out = self.outfile if self.outfile is not None else self.infile
        try:
            encrypt_pdf(
                self.infile,
                out,
                owner_password=self.owner_password,
                user_password=self.user_password,
                permissions=self._access_permission(),
                cert_files=self.cert_files,
                key_length=self.key_length,
            )
        except OSError as ioe:
            sys.stderr.write(
                f"Error encrypting document [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="encrypt", description="Encrypts a PDF document",
        )
        parser.add_argument("-O", dest="ownerPassword", default=None)
        parser.add_argument("-U", dest="userPassword", default=None)
        parser.add_argument("-certFile", dest="certFile", action="append", default=[])
        parser.add_argument("-keyLength", dest="keyLength", type=int, default=256)
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", default=None)
        ns = parser.parse_args(args)
        runner = Encrypt()
        runner.owner_password = ns.ownerPassword
        runner.user_password = ns.userPassword
        runner.cert_files = [Path(p) for p in ns.certFile]
        runner.key_length = ns.keyLength
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile) if ns.outfile else None
        return runner.call()


if __name__ == "__main__":
    sys.exit(Encrypt.main(sys.argv[1:]))
