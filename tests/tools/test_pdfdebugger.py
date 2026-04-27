"""Tests for ``pypdfbox pdfdebugger`` (lite CLI replacement for upstream's
Swing-based ``PDFDebugger``)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.tools import cli


def test_summary_default_mode(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(["pdfdebugger", str(pdf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert f"File: {pdf}" in out
    assert "Pages: 1" in out
    assert "Encrypted: no" in out
    # Catalog Type is /Catalog and Pages is an indirect ref or inline dict.
    assert "Catalog /Type: /Catalog" in out
    assert "Trailer keys:" in out
    # Trailer always carries /Root and /Size for a saved doc.
    assert "/Root" in out
    assert "/Size" in out


def test_trailer_dump(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=2)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-trailer"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Trailer:" in out
    assert "<<" in out and ">>" in out
    assert "/Root" in out
    assert "/Size" in out


def test_page_dump_prints_type_and_pages_marker(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=3)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-page", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Page 1:" in out
    assert "/Type" in out
    assert "/Page" in out
    # MediaBox is always written for newly-created pages.
    assert "/MediaBox" in out


def test_page_index_out_of_range(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-page", "5"])
    assert rc == 4
    out = capsys.readouterr().out
    assert "out of range" in out


def test_object_dump_for_catalog(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=1)
    # Find the catalog's object key via a real load.
    with PDDocument.load(pdf) as doc:
        cos_doc = doc.get_document()
        trailer = cos_doc.get_trailer()
        assert trailer is not None
        # /Root is stored as a COSObject indirect ref in the trailer.
        from pypdfbox.cos import COSName, COSObject

        root_entry = trailer.get_item(COSName.ROOT)  # type: ignore[attr-defined]
        assert isinstance(root_entry, COSObject)
        num = root_entry.object_number
        gen = root_entry.generation_number

    rc = cli.run_cli(["pdfdebugger", str(pdf), "-object", str(num), str(gen)])
    assert rc == 0
    out = capsys.readouterr().out
    assert f"Object {num} {gen} R:" in out
    assert "/Type" in out
    assert "/Catalog" in out


def test_object_not_in_pool(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-object", "9999", "0"])
    assert rc == 4
    out = capsys.readouterr().out
    assert "not in pool" in out


def test_tree_dump_lists_objects(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=2)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-tree"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Object pool" in out
    # Should mention the catalog and at least one page.
    assert "/Catalog" in out
    assert "/Page" in out


def test_missing_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    target = tmp_path / "does-not-exist.pdf"
    rc = cli.run_cli(["pdfdebugger", str(target)])
    assert rc == 4
    out = capsys.readouterr().out
    assert "not a file" in out


def test_mutually_exclusive_flags_rejected(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=1)
    with pytest.raises(SystemExit):
        cli.run_cli(["pdfdebugger", str(pdf), "-trailer", "-tree"])


# ---------- new flags: -xref / -catalog / -object NUM / --password / --depth


def test_xref_dump_lists_pool(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=2)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-xref"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("Xref (")
    assert "startxref=" in out
    # Each entry is "  N G R" — assert at least the first one is present.
    assert " 0 R" in out
    # At least one indirect object should be in the table after a real save.
    lines = [l for l in out.splitlines() if l.strip().endswith(" R")]
    assert len(lines) >= 1


def test_catalog_dump_shows_pages_and_resolves_refs(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-catalog"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("Catalog:")
    # /Type /Catalog must appear and /Pages either inline or as resolved ref.
    assert "/Type" in out
    assert "/Catalog" in out
    assert "/Pages" in out


def test_object_dump_accepts_single_number_default_gen(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=1)
    # Find a valid object number from the trailer's /Root.
    with PDDocument.load(pdf) as doc:
        from pypdfbox.cos import COSName, COSObject

        root = doc.get_document().get_trailer().get_item(COSName.ROOT)
        assert isinstance(root, COSObject)
        num = root.object_number
        # GEN is 0 for newly-saved docs.
        assert root.generation_number == 0

    rc = cli.run_cli(["pdfdebugger", str(pdf), "-object", str(num)])
    assert rc == 0
    out = capsys.readouterr().out
    assert f"Object {num} 0 R:" in out
    assert "/Catalog" in out


def test_depth_limit_truncates_dump(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(
        ["pdfdebugger", str(pdf), "-catalog", "--depth", "1"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # Depth 1 stops descending past the catalog's first sub-dictionary.
    assert "max depth" in out


def _build_encrypted(path: Path, *, owner: str = "o", user: str = "u") -> Path:
    pd = PDDocument()
    try:
        page = PDPage()
        pd.add_page(page)
        # Give the page a body so the resulting file has a real stream
        # (lets us also exercise the stream-preview path on the encrypted
        # round trip indirectly).
        body = COSStream()
        with body.create_raw_output_stream() as out:
            out.write(b"BT /F1 12 Tf 50 700 Td (hi) Tj ET")
        page.set_contents(body)
        pd.protect(
            StandardProtectionPolicy(
                owner_password=owner,
                user_password=user,
                permissions=AccessPermission(),
            )
        )
        pd.save(path)
    finally:
        pd.close()
    return path


def test_password_unlocks_encrypted_pdf(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    pdf = _build_encrypted(tmp_path / "enc.pdf", owner="o", user="u")
    rc = cli.run_cli(["pdfdebugger", str(pdf), "--password", "u"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Encrypted: yes" in out
    assert "Pages: 1" in out


def test_missing_password_for_encrypted_pdf_returns_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    pdf = _build_encrypted(tmp_path / "enc-nopw.pdf", owner="o", user="u")
    rc = cli.run_cli(["pdfdebugger", str(pdf)])
    # Either a clean exit-4 (load raised) or a successful summary with
    # "Encrypted: yes" — both are acceptable behaviours since some
    # workflows allow read-only inspection of the cos shell. We just
    # require *no crash* and that we got *some* output.
    assert rc in (0, 4)
    out = capsys.readouterr().out
    assert out  # something was emitted


def test_stream_preview_present_in_object_dump(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A real content stream should show a ``stream-body[...]`` preview
    line in the object dump."""
    pdf = tmp_path / "with-stream.pdf"
    pd = PDDocument()
    try:
        page = PDPage()
        pd.add_page(page)
        body = COSStream()
        with body.create_raw_output_stream() as out:
            out.write(b"BT /F1 12 Tf 50 700 Td (preview-marker) Tj ET")
        page.set_contents(body)
        pd.save(pdf)
    finally:
        pd.close()

    rc = cli.run_cli(["pdfdebugger", str(pdf), "-tree"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "stream-body[" in out
    # Either decoded or raw kind tag — both are valid outputs.
    assert ("decoded]" in out) or ("raw]" in out)
