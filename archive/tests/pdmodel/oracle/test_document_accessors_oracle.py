"""Live PDFBox differential parity for ``PDDocument`` top-level accessors.

The document-level accessors are the first surface any downstream consumer
touches — page count, page lookup, the security toggles, the current access
permission object, and the signature inventory. This differential test pins
each against the live Apache PDFBox 3.0.7 oracle
(``oracle/probes/DocumentAccessorsProbe.java``) so a regression in any of them
is caught against the reference implementation rather than a hand-translated
expectation.

The fixture is a three-page PDF authored by pypdfbox carrying a single
invisible signature field (a ``PDSignature`` wired in via
``PDDocument.add_signature`` — no real cryptography, just the ``/AcroForm``
``/FT /Sig`` field structure with a ``/V`` dictionary that PDFBox counts). It
is unencrypted, so:

* ``isEncrypted`` ⇒ ``false``;
* ``isAllSecurityToBeRemoved`` ⇒ ``false`` (never toggled);
* ``getCurrentAccessPermission`` ⇒ a non-null full-owner permission object
  (``canPrint`` / ``canModify`` / ``canExtractContent`` all ``true``);
* ``getSignatureFields().size()`` ⇒ 1, ``getSignatureDictionaries().size()``
  ⇒ 1 (the field's ``/V`` is set).

The out-of-range ``getPage`` probe confirms both sides *signal an error*
rather than silently returning a page for an index past the last page.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from tests.oracle.harness import requires_oracle, run_probe_text


def _build_fixture(path: Path) -> None:
    """Author a three-page, unencrypted PDF carrying one signed signature
    field (no real PKCS#7 — only the ``/AcroForm`` ``/FT /Sig`` field tree
    with a ``/V`` dictionary, which is what the count accessors walk)."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        doc.add_page(PDPage(PDRectangle.LETTER))
        doc.add_page(PDPage(PDRectangle.A4))
        sig = PDSignature()
        sig.set_name("oracle-doc-accessors")
        doc.add_signature(sig)
        doc.save(path)
    finally:
        doc.close()


def _py_accessor_dump(path: Path) -> str:
    """Reproduce the canonical DocumentAccessorsProbe output from pypdfbox."""

    def b(value: bool) -> str:
        return "true" if value else "false"

    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        n = doc.get_number_of_pages()
        lines.append(f"numberOfPages={n}")

        page0 = doc.get_page(0)
        lines.append(f"page0NotNull={b(page0 is not None)}")

        # Out-of-range page index: pypdfbox raises IndexError (Python's
        # IndexOutOfBoundsException analogue) — classify like the probe.
        try:
            doc.get_page(n)
            oor = "RETURN"
        except (IndexError, KeyError):
            oor = "RAISE"
        lines.append(f"pageOutOfRange={oor}")

        lines.append(f"isEncrypted={b(doc.is_encrypted())}")
        lines.append(
            f"isAllSecurityToBeRemoved={b(doc.is_all_security_to_be_removed())}"
        )

        perm = doc.get_current_access_permission()
        lines.append(f"accessPermNotNull={b(perm is not None)}")
        lines.append(f"canPrint={b(perm.can_print())}")
        lines.append(f"canModify={b(perm.can_modify())}")
        lines.append(f"canExtractContent={b(perm.can_extract_content())}")

        lines.append(f"signatureFields={len(doc.get_signature_fields())}")
        lines.append(
            f"signatureDictionaries={len(doc.get_signature_dictionaries())}"
        )
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
def test_document_accessors_match_pdfbox(tmp_path: Path) -> None:
    pdf = tmp_path / "doc_accessors.pdf"
    _build_fixture(pdf)
    java = run_probe_text("DocumentAccessorsProbe", str(pdf))
    py = _py_accessor_dump(pdf)
    assert py == java, (
        "PDDocument top-level accessors diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
def test_signature_inventory_counts_match_pdfbox(tmp_path: Path) -> None:
    """Headline assertion — the signed signature field must be counted by
    both ``getSignatureFields`` (structural) and ``getSignatureDictionaries``
    (only fields whose ``/V`` is set), and the live oracle must agree."""
    pdf = tmp_path / "doc_accessors_sig.pdf"
    _build_fixture(pdf)
    doc = PDDocument.load(pdf)
    try:
        assert len(doc.get_signature_fields()) == 1
        assert len(doc.get_signature_dictionaries()) == 1
    finally:
        doc.close()
    java = run_probe_text("DocumentAccessorsProbe", str(pdf))
    assert "signatureFields=1" in java
    assert "signatureDictionaries=1" in java


@requires_oracle
def test_out_of_range_page_signals_error_like_pdfbox(tmp_path: Path) -> None:
    """``getPage(index)`` past the last page must signal an error on both
    sides rather than silently handing back a page."""
    pdf = tmp_path / "doc_accessors_oor.pdf"
    _build_fixture(pdf)
    doc = PDDocument.load(pdf)
    try:
        n = doc.get_number_of_pages()
        with pytest.raises((IndexError, KeyError)):
            doc.get_page(n)
    finally:
        doc.close()
    java = run_probe_text("DocumentAccessorsProbe", str(pdf))
    assert "pageOutOfRange=RAISE" in java
