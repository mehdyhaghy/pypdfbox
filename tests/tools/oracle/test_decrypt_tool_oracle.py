"""Live Apache PDFBox parity for the ``Decrypt`` CLI tool.

pypdfbox encrypts a one-page fixture with a known owner/user password (both
AES-128 and AES-256 variants), then:

* drives Apache PDFBox 3.0.7's ``org.apache.pdfbox.tools.Decrypt`` CLI on the
  encrypted input via the ``DecryptToolProbe`` Java probe, which reloads the
  decrypted output and emits its structural shape as JSON
  (``exitCode``/``isEncrypted``/``pages``/``text``); and
* runs pypdfbox's own ``decrypt`` CLI (``pypdfbox.tools.cli``) on the *same*
  encrypted input.

The parity claim: both tools strip ``/Encrypt`` so the output reloads with no
password (``isEncrypted == False``), preserves the page count, and preserves
the extracted text. Each pypdfbox output is additionally run through
``qpdf --check`` to prove the produced file is structurally clean.

This is the end-to-end Decrypt-tool surface: encrypt -> upstream-Decrypt and
encrypt -> pypdfbox-Decrypt must converge on the same unencrypted document.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.tools import cli
from tests.oracle.harness import requires_oracle, run_probe_text

_OWNER_PASSWORD = "0wn3r-pass"
_USER_PASSWORD = "us3r-pass"

# Content stream whose extracted text is stable across both engines.
_CONTENT = b"BT /F1 12 Tf 50 700 Td (Decrypt tool parity sample) Tj ET"
_EXPECTED_TEXT = "Decrypt tool parity sample"


def _escape(value: str) -> str:
    """Mirror the Java probe's JSON string escaping for direct comparison."""
    out: list[str] = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def _build_encrypted_pdf(path: Path, key_length: int, prefer_aes: bool) -> Path:
    """Write an AES-encrypted one-page PDF to ``path``.

    ``key_length`` 128 + ``prefer_aes=True`` -> AES-128 (V4/R4);
    ``key_length`` 256 -> AES-256 (V5/R6).
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as out:
            out.write(_CONTENT)
        page.set_contents(stream)
        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PASSWORD,
            user_password=_USER_PASSWORD,
            permissions=AccessPermission(),
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        doc.protect(policy)
        doc.save(path)
    finally:
        doc.close()
    return path


def _qpdf_check(path: Path) -> None:
    """Assert ``qpdf --check`` reports a clean file (skip if qpdf absent)."""
    qpdf = shutil.which("qpdf")
    if qpdf is None:  # pragma: no cover - environment dependent
        pytest.skip("qpdf not installed")
    result = subprocess.run(
        [qpdf, "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    # qpdf returns 0 (clean) or 3 (warnings only); 2 = errors. Reject errors.
    assert result.returncode in (0, 3), (
        f"qpdf --check failed for {path}:\n{result.stdout}\n{result.stderr}"
    )


def _pypdfbox_summary(out_path: Path) -> tuple[str, dict[str, object]]:
    """Reload a pypdfbox-decrypted file and build the probe-shaped JSON line."""
    with PDDocument.load(out_path) as doc:
        is_encrypted = doc.is_encrypted()
        pages = doc.get_number_of_pages()
        text = PDFTextStripper().get_text(doc)
    payload = {
        "exitCode": 0,
        "isEncrypted": is_encrypted,
        "pages": pages,
        "text": text,
    }
    # Emit in the same key order / escaping the Java probe uses so the two
    # strings compare verbatim.
    return (
        '{"exitCode":0'
        f',"isEncrypted":{"true" if is_encrypted else "false"}'
        f',"pages":{pages}'
        f',"text":"{_escape(text)}"'
        "}"
    ), payload


@requires_oracle
@pytest.mark.parametrize(
    ("key_length", "prefer_aes"),
    [(128, True), (256, False)],
    ids=["aes128", "aes256"],
)
def test_decrypt_tool_matches_pdfbox(
    tmp_path: Path, key_length: int, prefer_aes: bool
) -> None:
    src = _build_encrypted_pdf(
        tmp_path / "encrypted.pdf", key_length, prefer_aes
    )

    # Upstream Decrypt CLI on the encrypted input.
    java_out = tmp_path / "java_decrypted.pdf"
    java_raw = run_probe_text(
        "DecryptToolProbe", str(src), str(java_out), _OWNER_PASSWORD
    )
    java = json.loads(java_raw)

    # Sanity: upstream succeeded and produced an unencrypted file.
    assert java["exitCode"] == 0, f"upstream Decrypt failed: {java_raw}"
    assert java["isEncrypted"] is False
    assert java["pages"] == 1
    assert _EXPECTED_TEXT in java["text"]

    # pypdfbox Decrypt CLI on the SAME encrypted input.
    py_out = tmp_path / "py_decrypted.pdf"
    rc = cli.run_cli(
        ["decrypt", "-i", str(src), "-o", str(py_out), "-password", _OWNER_PASSWORD]
    )
    assert rc == 0

    py_line, py = _pypdfbox_summary(py_out)

    # Structural parity against upstream's decrypted output.
    assert py["isEncrypted"] == java["isEncrypted"]
    assert py["pages"] == java["pages"]
    assert py["text"] == java["text"], (
        "Decrypt tool text divergence:\n"
        f"  java: {java['text']!r}\n"
        f"  py:   {py['text']!r}"
    )
    # Verbatim JSON line equality (proves identical escaping + ordering too).
    assert py_line == java_raw

    # pypdfbox's output must be structurally clean.
    _qpdf_check(py_out)


@requires_oracle
def test_decrypt_tool_output_reloads_without_password(tmp_path: Path) -> None:
    """Regression pin: the pypdfbox-decrypted file opens with NO password and
    carries no /Encrypt, matching upstream Decrypt's contract."""
    src = _build_encrypted_pdf(tmp_path / "enc.pdf", 256, False)
    py_out = tmp_path / "dec.pdf"
    rc = cli.run_cli(
        ["decrypt", "-i", str(src), "-o", str(py_out), "-password", _OWNER_PASSWORD]
    )
    assert rc == 0
    # Loading with no password must succeed and report unencrypted.
    with PDDocument.load(py_out) as doc:
        assert doc.is_encrypted() is False
        assert doc.get_number_of_pages() == 1
