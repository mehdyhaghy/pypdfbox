"""
``pypdfbox decrypt -i in.pdf [-o out.pdf]`` — strip security from a PDF.

Mirrors upstream ``org.apache.pdfbox.tools.Decrypt``. Upstream loads the
PDF (optionally with a password / certificate keystore), checks owner
permission, sets ``allSecurityToBeRemoved=true``, then saves.

**Cluster #1 limitation.** Real decryption needs the security cluster
(pdmodel #10). Until that lands, this command:

  - succeeds silently when the input is not encrypted (just copies it
    through ``PDDocument.load`` then ``save`` — round-trips harmlessly);
  - exits non-zero with a clear error when the input *is* encrypted,
    pointing the user at the cluster that will land real decryption.

Exit codes follow upstream: 0 success, 1 not-encrypted-or-no-permission
(we collapse to 1 for both), 4 IO error.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from pypdfbox.pdmodel import PDDocument


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "decrypt",
        help="strip encryption from a PDF (cluster #1: pass-through only)",
        description="Strip encryption from a PDF document. Cluster #1 supports "
        "only the no-op-on-unencrypted case (input copied to output); real "
        "decryption requires the security cluster (pdmodel #10) and will "
        "be added then.",
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
        "-password", dest="password", default=None, metavar="PASSWORD",
        help="password (cluster #1: ignored — security cluster pending)",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"decrypt: {src}: not a file", flush=True)
        return 4
    out = Path(args.output) if args.output else src

    with PDDocument.load(src) as doc:
        if doc.is_encrypted():
            # Upstream returns 1 here when permissions are denied. We
            # generalise to 1 == "could not strip security in this build".
            print(
                "decrypt: input is encrypted; real decryption requires the "
                "security cluster (pdmodel #10) which is not yet ported.",
                flush=True,
            )
            return 1
        # Unencrypted -> mirror upstream's "set all security to be removed
        # then save" sequence even though there's nothing to remove. The
        # write happens through the same code path so callers get a
        # consistent file regardless.
        doc.set_all_security_to_be_removed(True)
        doc.save(out)
    return 0
