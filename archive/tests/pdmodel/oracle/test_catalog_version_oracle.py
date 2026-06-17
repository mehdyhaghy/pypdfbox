"""Live PDFBox differential parity for catalog ``/Version`` override resolution.

Per PDF 32000-1 §7.5.2 the document catalog may carry an optional ``/Version``
name entry that *overrides* the file-header ``%PDF-1.X`` declaration — but
*only* when the catalog version is later than the header. PDFBox 3.0.7's
``PDDocument.getVersion()`` resolves this with a literal
``max(catalogVersion, headerVersion)``; an *older* catalog ``/Version`` does
not roll the resolved version backwards.

This differential test exercises all three cases of that resolution against
the live PDFBox 3.0.7 oracle (``oracle/probes/CatalogVersionProbe.java``):

* ``catalog_overrides_header`` — header ``%PDF-1.4`` + catalog ``/Version /1.7``
  ⇒ resolved = 1.7 (catalog wins, the high-value case).
* ``header_wins_over_older_catalog`` — header ``%PDF-1.7`` +
  catalog ``/Version /1.4`` ⇒ resolved = 1.7 (header wins, never roll back).
* ``header_only`` — header ``%PDF-1.6`` with no catalog ``/Version`` ⇒
  resolved = 1.6 (header is all there is).

For each case we round-trip a one-page PDF written by pypdfbox (with the
COSDocument header and the catalog ``/Version`` independently controlled),
then assert pypdfbox's ``get_version()`` plus the raw header / catalog
components match PDFBox's view byte-for-byte.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_VERSION = COSName.get_pdf_name("Version")


def _build_fixture(
    path: Path, header_version: float, catalog_version: str | None
) -> None:
    """Author a one-page PDF whose header is exactly ``header_version`` and
    whose catalog ``/Version`` is exactly ``catalog_version`` (or absent when
    ``None``). Reaches under ``PDDocument`` to set the header / catalog
    versions independently — the public ``set_version`` clamps to a
    monotonic upgrade, which is the very behaviour we need to test
    *around*."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        # Pin the COSDocument's version: this is what the writer stamps
        # into the ``%PDF-x.y`` header line.
        doc._document.set_version(header_version)
        cat = doc.get_document_catalog()
        if catalog_version is None:
            # Strip the catalog ``/Version`` stamped by the no-arg
            # constructor (pypdfbox + upstream both stamp the default).
            cat.get_cos_object().remove_item(_VERSION)
        else:
            cat.set_version(catalog_version)
        doc.save(path)
    finally:
        doc.close()


def _py_version_dump(path: Path) -> str:
    """Reproduce the canonical CatalogVersionProbe output from pypdfbox."""
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        cat = doc.get_document_catalog()
        cos_doc = doc._document
        lines.append(f"resolved={doc.get_version():.1f}")
        lines.append(f"header={cos_doc.get_version():.1f}")
        catalog_v = cat.get_version()
        lines.append(f"catalog={'NULL' if catalog_v is None else catalog_v}")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


# (label, header version, catalog /Version name or None)
_CASES = [
    ("catalog_overrides_header", 1.4, "1.7"),
    ("header_wins_over_older_catalog", 1.7, "1.4"),
    ("header_only", 1.6, None),
]


@requires_oracle
@pytest.mark.parametrize(
    ("label", "header_version", "catalog_version"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_catalog_version_matches_pdfbox(
    tmp_path: Path,
    label: str,
    header_version: float,
    catalog_version: str | None,
) -> None:
    pdf = tmp_path / f"version_{label}.pdf"
    _build_fixture(pdf, header_version, catalog_version)
    java = run_probe_text("CatalogVersionProbe", str(pdf))
    py = _py_version_dump(pdf)
    assert py == java, (
        f"{label}: catalog/header version resolution diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
def test_catalog_overrides_header_resolves_to_catalog(tmp_path: Path) -> None:
    """Headline assertion — the high-value case in narrative form. A header
    ``%PDF-1.4`` carrying a catalog ``/Version /1.7`` must report 1.7, not
    1.4 (otherwise the catalog override is silently ignored)."""
    pdf = tmp_path / "catalog_override.pdf"
    _build_fixture(pdf, 1.4, "1.7")
    doc = PDDocument.load(pdf)
    try:
        assert doc.get_version() == pytest.approx(1.7)
        assert doc._document.get_version() == pytest.approx(1.4)
        assert doc.get_document_catalog().get_version() == "1.7"
    finally:
        doc.close()
    # And the live oracle agrees.
    java = run_probe_text("CatalogVersionProbe", str(pdf))
    assert "resolved=1.7" in java
    assert "header=1.4" in java
    assert "catalog=1.7" in java


@requires_oracle
def test_older_catalog_does_not_roll_back_header(tmp_path: Path) -> None:
    """A catalog ``/Version`` *older* than the header must not roll the
    resolved version backwards — that would be a real bug (downstream
    consumers would refuse PDF 1.7 features the header genuinely advertises).
    Mirrors PDFBox's ``max(catalog, header)`` semantics."""
    pdf = tmp_path / "older_catalog.pdf"
    _build_fixture(pdf, 1.7, "1.4")
    doc = PDDocument.load(pdf)
    try:
        assert doc.get_version() == pytest.approx(1.7)
        assert doc._document.get_version() == pytest.approx(1.7)
        assert doc.get_document_catalog().get_version() == "1.4"
    finally:
        doc.close()
    java = run_probe_text("CatalogVersionProbe", str(pdf))
    assert "resolved=1.7" in java
