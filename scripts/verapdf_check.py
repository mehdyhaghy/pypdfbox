#!/usr/bin/env python3
"""PDF/A and PDF/UA validation of pypdfbox-generated PDFs via ``veraPDF``.

PRD §13 and the project ``CLAUDE.md`` "Hard Rules" carve PDF/A and
PDF/UA validation out of the in-tree code — Apache PDFBox 4.0 dropped
its ``preflight`` module, and we follow that decision. Validation is
delegated to the external `veraPDF <https://verapdf.org/>`_ CLI, which
is a Java tool installed alongside the system (Homebrew on macOS,
``apt install verapdf`` on recent Debian, or the upstream tarball
unpacked into ``$PATH``).

veraPDF is GPL-3 licensed. That is **forbidden as a Python dependency**
(see ``CLAUDE.md`` license matrix), but invoking it as an external
process via ``subprocess`` is fine — we are calling a binary, not
linking against it. No new Python deps are introduced by this script.

The CLI shape mirrors ``scripts/qpdf_check.py``:

    python scripts/verapdf_check.py [--keep-tmp] [--flavour 1b|2b|3b|...]

When ``verapdf`` is not on ``$PATH`` the script prints a one-line
notice and exits 0 so it can be wired into pre-commit / CI without
becoming a hard blocker on developer laptops without the tool.

Programmatic users should call :func:`run_verapdf` which returns a
``VeraPDFResult`` tuple ``(is_valid, conformance_level, errors)``.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

# ----------------------------------------------------------------- types


class VeraPDFResult(NamedTuple):
    """Outcome of a single ``verapdf`` invocation.

    Attributes:
        is_valid: ``True`` iff veraPDF reported zero validation errors
            against the requested profile. ``False`` when veraPDF ran
            but flagged at least one error.
        conformance_level: Free-form string describing the profile
            veraPDF actually validated against (e.g. ``"PDF/A-1B"``).
            Empty when veraPDF did not report a profile.
        errors: List of human-readable error messages extracted from
            veraPDF's JSON output. Empty on success.
    """

    is_valid: bool
    conformance_level: str
    errors: list[str]


#: Sentinel returned when ``verapdf`` is not installed. Tests should
#: skip rather than treat this as a failure.
NOT_INSTALLED = VeraPDFResult(
    is_valid=False, conformance_level="", errors=["verapdf binary not on PATH"]
)


# ----------------------------------------------------------------- core


def find_verapdf() -> str | None:
    """Return the ``verapdf`` binary path or ``None`` if missing."""
    return shutil.which("verapdf")


def _parse_verapdf_json(payload: str) -> VeraPDFResult:
    """Translate veraPDF's JSON report into a :class:`VeraPDFResult`.

    veraPDF's machine-readable layout changes between releases, so the
    parser is defensive: it looks for the common keys (``validationResult``,
    ``compliant``, ``profile``, ``ruleSummaries`` / ``testAssertions``)
    and falls back to a generic "no report" error when the document
    structure is unrecognised.
    """
    try:
        report = json.loads(payload)
    except json.JSONDecodeError as exc:
        return VeraPDFResult(False, "", [f"verapdf JSON parse error: {exc}"])

    # veraPDF 1.24+ wraps the report under "report" -> "jobs"[0] -> "validationResult".
    # Older releases put it at top-level. Try both.
    job: dict = {}
    jobs = (
        report.get("report", {}).get("jobs")
        or report.get("jobs")
        or []
    )
    if jobs:
        job = jobs[0]
    validation = (
        job.get("validationResult")
        or report.get("validationResult")
        or report.get("validationReports", [{}])[0]
        if report.get("validationReports")
        else {}
    )
    if not isinstance(validation, dict):
        validation = {}

    compliant = bool(
        validation.get("compliant")
        if "compliant" in validation
        else validation.get("isCompliant", False)
    )
    profile = (
        validation.get("profileName")
        or validation.get("profile")
        or validation.get("flavour")
        or ""
    )

    errors: list[str] = []
    # Newer schemas: details.ruleSummaries[].testAssertions[].message
    details = validation.get("details") or {}
    rule_summaries = details.get("ruleSummaries") or validation.get("ruleSummaries") or []
    for rule in rule_summaries:
        if not isinstance(rule, dict):
            continue
        rule_status = rule.get("ruleStatus") or rule.get("status")
        if rule_status and rule_status.upper() == "PASSED":
            continue
        # Some schemas inline the message at rule level
        message = rule.get("description") or rule.get("message")
        if message:
            errors.append(str(message))
        for assertion in rule.get("testAssertions") or rule.get("checks") or []:
            if not isinstance(assertion, dict):
                continue
            status = assertion.get("status") or assertion.get("result")
            if status and str(status).upper() in {"PASSED", "PASS"}:
                continue
            msg = assertion.get("message") or assertion.get("description")
            if msg:
                errors.append(str(msg))

    return VeraPDFResult(
        is_valid=compliant and not errors,
        conformance_level=str(profile),
        errors=errors,
    )


def run_verapdf(
    pdf_path: Path | str,
    *,
    flavour: str | None = None,
    binary: str | None = None,
    timeout: float = 60.0,
) -> VeraPDFResult:
    """Validate ``pdf_path`` and return a :class:`VeraPDFResult`.

    Args:
        pdf_path: Path to a PDF file on disk.
        flavour: Optional veraPDF flavour code (``"1b"``, ``"2b"``,
            ``"3b"``, ``"ua1"`` …). When ``None`` veraPDF auto-detects
            the declared conformance from the document's metadata.
        binary: Override the ``verapdf`` binary path (defaults to the
            one found on ``$PATH``).
        timeout: Subprocess timeout in seconds.

    Returns:
        :data:`NOT_INSTALLED` when the binary is missing; otherwise a
        populated :class:`VeraPDFResult`.
    """
    verapdf = binary or find_verapdf()
    if verapdf is None:
        return NOT_INSTALLED

    args = [verapdf, "--format", "json"]
    if flavour:
        args.extend(["--flavour", flavour])
    args.append(str(pdf_path))

    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return VeraPDFResult(False, "", [f"verapdf timed out after {timeout}s"])
    except OSError as exc:
        return VeraPDFResult(False, "", [f"verapdf invocation failed: {exc}"])

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if not stdout.strip():
        # Some veraPDF builds write JSON to stderr when stdout is consumed
        # by their banner; fall back gracefully.
        if stderr.strip().startswith("{"):
            stdout = stderr
        else:
            return VeraPDFResult(
                False,
                "",
                [
                    f"verapdf produced no JSON output (rc={proc.returncode}); "
                    f"stderr={stderr[:500]}"
                ],
            )

    return _parse_verapdf_json(stdout)


# ----------------------------------------------------------------- CLI helpers

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
            cs.show_text("verapdf check")
            cs.end_text()
        sink = io.BytesIO()
        doc.save(sink)
        return sink.getvalue()

    def _multi_page() -> bytes:
        doc = PDDocument()
        for _ in range(3):
            doc.add_page(PDPage(PDRectangle.LETTER))
        sink = io.BytesIO()
        doc.save(sink)
        return sink.getvalue()

    return {
        "basic_save": _basic_save,
        "with_text": _with_text,
        "multi_page": _multi_page,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run veraPDF validation on pypdfbox-generated PDFs."
    )
    parser.add_argument(
        "--keep-tmp",
        action="store_true",
        help="Do not delete the scratch dir on exit.",
    )
    parser.add_argument(
        "--flavour",
        default=None,
        help="veraPDF flavour code (1b, 2b, 3b, ua1, ...). Omit to auto-detect.",
    )
    args = parser.parse_args()

    if find_verapdf() is None:
        print(
            "verapdf not on PATH; install with `brew install --cask verapdf` "
            "(macOS) or download from https://verapdf.org/ and add to PATH."
        )
        return 0

    flows = _flows()
    failures: list[str] = []

    scratch = Path(tempfile.mkdtemp(prefix="pypdfbox_verapdf_"))
    try:
        for name, build in flows.items():
            pdf_bytes = build()
            target = scratch / f"{name}.pdf"
            target.write_bytes(pdf_bytes)

            result = run_verapdf(target, flavour=args.flavour)
            status = "OK " if result.is_valid else "BAD"
            profile = result.conformance_level or "(auto)"
            print(f"{status} {name:24s} profile={profile} errors={len(result.errors)}")
            # The pypdfbox writer does not currently emit PDF/A-conformant
            # output, so a non-empty error list here is expected. We only
            # bubble up failures when the *pipeline itself* breaks
            # (verapdf invocation failed, JSON parse failed, etc.).
            pipeline_broken = any(
                err.startswith(
                    (
                        "verapdf JSON parse error",
                        "verapdf timed out",
                        "verapdf invocation failed",
                        "verapdf produced no JSON",
                    )
                )
                for err in result.errors
            )
            if pipeline_broken:
                failures.append(f"{name}: {result.errors}")
    finally:
        if not args.keep_tmp:
            shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print("\nPIPELINE FAILURES:")
        for entry in failures:
            print(entry)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
