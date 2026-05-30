"""Live Apache PDFBox parity for the ``Encrypt`` CLI tool round-trip.

pypdfbox's ``encrypt`` CLI applies the standard security handler to a one-page
fixture across the three key-length families — RC4-40 (V1/R2-3), RC4-128
(V2/R3) and AES-256 (V5/R6) — optionally toggling individual permission bits
via the ``-can*`` flags. Each produced file must:

* pass ``qpdf --check`` *with the password supplied* (rc 0 or 3 — clean /
  warnings only), and be rejected by qpdf with a wrong password (proving the
  /U / /O entries actually gate access, not a missing /Encrypt); and
* be openable by Apache PDFBox 3.0.7 with the same password, reporting the
  same page count, decrypted text, and AccessPermission bits pypdfbox encoded.

The earlier failure on this surface ("qpdf: invalid password") came from
passing the wrong password to ``qpdf --check`` — the standard handler's /U /O
/P /R /Length are written correctly. This test pins that with the password
threaded through both the qpdf check and PDFBox's ``Loader.loadPDF`` overload.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.tools import cli
from tests.oracle.harness import requires_oracle, run_probe_text

_OWNER_PASSWORD = "0wn3r-pass"
_USER_PASSWORD = "us3r-pass"

# Content stream whose extracted text is stable across both engines.
_CONTENT = b"BT /F1 12 Tf 50 700 Td (Encrypt tool parity sample) Tj ET"
_EXPECTED_TEXT = "Encrypt tool parity sample"


def _build_plain_pdf(path: Path) -> Path:
    """Write a one-page, unencrypted PDF for the Encrypt CLI to consume."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as out:
            out.write(_CONTENT)
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()
    return path


def _qpdf_check(path: Path, password: str) -> subprocess.CompletedProcess[str]:
    """Run ``qpdf --check`` with ``password`` (skip if qpdf absent)."""
    qpdf = shutil.which("qpdf")
    if qpdf is None:  # pragma: no cover - environment dependent
        pytest.skip("qpdf not installed")
    return subprocess.run(
        [qpdf, "--check", f"--password={password}", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


@requires_oracle
@pytest.mark.parametrize(
    ("key_length", "extra_flags", "expect_print", "expect_modify", "expect_extract"),
    [
        (40, [], True, True, True),
        (128, [], True, True, True),
        (256, [], True, True, True),
        (
            128,
            ["--no-canPrint", "--no-canModify", "--no-canExtractContent"],
            False,
            False,
            False,
        ),
    ],
    ids=["rc4-40", "rc4-128", "aes-256", "rc4-128-restricted"],
)
def test_encrypt_tool_roundtrips_through_pdfbox(
    tmp_path: Path,
    key_length: int,
    extra_flags: list[str],
    expect_print: bool,
    expect_modify: bool,
    expect_extract: bool,
) -> None:
    src = _build_plain_pdf(tmp_path / "plain.pdf")
    out = tmp_path / "enc.pdf"

    rc = cli.run_cli(
        [
            "encrypt",
            "-i",
            str(src),
            "-o",
            str(out),
            "-O",
            _OWNER_PASSWORD,
            "-U",
            _USER_PASSWORD,
            "-keyLength",
            str(key_length),
            *extra_flags,
        ]
    )
    assert rc == 0, "pypdfbox encrypt CLI returned non-zero"
    assert out.is_file()

    # qpdf accepts the file with the correct password (rc 0 clean, 3 warnings).
    good = _qpdf_check(out, _USER_PASSWORD)
    assert good.returncode in (0, 3), (
        f"qpdf --check rejected a correctly-encrypted file:\n"
        f"{good.stdout}\n{good.stderr}"
    )
    # ...and rejects a wrong password (rc 2). This proves /U / /O actually gate
    # access — a file with /Encrypt stripped would pass with ANY password.
    bad = _qpdf_check(out, "definitely-wrong-password")
    assert bad.returncode == 2, (
        "qpdf accepted a wrong password — encryption is not gating access:\n"
        f"{bad.stdout}\n{bad.stderr}"
    )

    # Apache PDFBox 3.0.7 opens the same file with the user password and
    # round-trips to identical content + permission bits.
    for password in (_USER_PASSWORD, _OWNER_PASSWORD):
        raw = run_probe_text("EncryptToolProbe", str(out), password)
        probe = json.loads(raw)
        assert probe.get("opened") is True, (
            f"PDFBox failed to open pypdfbox-encrypted file with {password!r}: {raw}"
        )
        assert probe["isEncrypted"] is True
        assert probe["pages"] == 1
        assert _EXPECTED_TEXT in probe["text"], (
            f"decrypted text divergence: {probe['text']!r}"
        )

    # Permission bits PDFBox reconstructs from /P must match the -can* flags.
    # The owner password unlocks every permission upstream (owner == full
    # access), so assert the user-password view for the restricted case.
    user_probe = json.loads(
        run_probe_text("EncryptToolProbe", str(out), _USER_PASSWORD)
    )
    assert user_probe["canPrint"] is expect_print
    assert user_probe["canModify"] is expect_modify
    assert user_probe["canExtract"] is expect_extract
