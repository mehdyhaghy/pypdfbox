#!/usr/bin/env python3
"""Differential validation of pypdfbox-generated PDFs via ``qpdf``.

PRD §12 calls for a release-time validation stack:
``qpdf --check``, ``qpdf --qdf``, veraPDF, PAC. This script is the
``qpdf`` portion — it builds representative PDFs through the pypdfbox
writer, then shells out to the system ``qpdf`` to confirm the bytes are
structurally valid and can be normalized round-trip.

``qpdf`` is a *system* tool (Homebrew on macOS, ``apt install qpdf`` on
Debian). It is intentionally **not** added to ``pyproject.toml`` — the
test harness skips when the binary is missing so CI can opt in by
installing the package.

Usage::

    python scripts/qpdf_check.py [--keep-tmp]

Exits non-zero if any built PDF fails ``qpdf --check`` or ``qpdf --qdf``.
When qpdf is not on ``PATH`` the script prints a one-line notice and
exits 0 (so it can be wired into pre-commit without becoming a hard
blocker on developer laptops without the tool installed).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

# Each flow returns the PDF bytes for a small synthetic document. The
# pytest module ``tests/integration/test_qpdf_validation.py`` defines
# matching flows; this script is the standalone CLI cousin.
FlowBuilder = Callable[[], bytes]


def _flows() -> dict[str, FlowBuilder]:
    """Lazy-import pypdfbox so ``--help`` works without the package."""
    import io

    from pypdfbox import PDDocument
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel import PDPage, PDRectangle
    from pypdfbox.pdmodel.font import PDType1Font
    from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

    def _helvetica() -> PDType1Font:
        font = PDType1Font()
        font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
        return font

    def _basic_save() -> bytes:
        doc = PDDocument()
        doc.add_page(PDPage(PDRectangle.LETTER))
        sink = io.BytesIO()
        doc.save(sink)
        return sink.getvalue()

    def _with_text() -> bytes:
        doc = PDDocument()
        page = PDPage(PDRectangle.LETTER)
        doc.add_page(page)
        font = _helvetica()
        with PDPageContentStream(doc, page) as cs:
            cs.begin_text()
            cs.set_font(font, 12)
            cs.new_line_at_offset(50.0, 700.0)
            cs.show_text("qpdf check")
            cs.end_text()
        sink = io.BytesIO()
        doc.save(sink)
        return sink.getvalue()

    return {"basic_save": _basic_save, "with_text": _with_text}


def _run_qpdf(args: list[str]) -> tuple[int, str]:
    """Invoke ``qpdf`` and return ``(returncode, combined stdout+stderr)``."""
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run qpdf validation on pypdfbox-generated PDFs."
    )
    parser.add_argument(
        "--keep-tmp", action="store_true", help="Do not delete the scratch dir on exit."
    )
    args = parser.parse_args()

    qpdf = shutil.which("qpdf")
    if qpdf is None:
        print(
            "qpdf not on PATH; install with `brew install qpdf` (macOS) "
            "or `apt install qpdf` (Debian)."
        )
        return 0

    flows = _flows()
    failures: list[str] = []

    scratch = Path(tempfile.mkdtemp(prefix="pypdfbox_qpdf_"))
    try:
        for name, build in flows.items():
            pdf_bytes = build()
            target = scratch / f"{name}.pdf"
            target.write_bytes(pdf_bytes)

            check_rc, check_out = _run_qpdf([qpdf, "--check", str(target)])
            if check_rc != 0:
                failures.append(f"{name}: qpdf --check rc={check_rc}\n{check_out}")
                continue

            qdf_target = scratch / f"{name}.qdf.pdf"
            qdf_rc, qdf_out = _run_qpdf(
                [qpdf, "--qdf", "--object-streams=disable", str(target), str(qdf_target)]
            )
            if qdf_rc != 0:
                failures.append(f"{name}: qpdf --qdf rc={qdf_rc}\n{qdf_out}")
                continue

            print(f"OK  {name}")
    finally:
        if not args.keep_tmp:
            shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print("\nFAILURES:")
        for entry in failures:
            print(entry)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
