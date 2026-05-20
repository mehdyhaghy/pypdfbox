"""Ported upstream tests for ``SymmetricKeyEncryption``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/encryption/TestSymmetricKeyEncryption.java``
(PDFBox 3.0.x).

Upstream's test exercises full PDF round-trips
(``StandardProtectionPolicy.protect`` → ``Loader.loadPDF`` → text-strip
parity) across RC4-40 / RC4-128 / AES-128 / AES-256 with sample
documents (PasswordSample-{40,128,256}bit.pdf, Acroform-PDFBOX-2333.pdf,
preEnc_20141025_105451.pdf) plus the network-downloaded PDFBOX-4308 /
4453 / 5639 / 5955 corpus. The structural slice that does not depend on
those fixtures lives in
``tests/pdmodel/encryption/upstream/test_security_handler.py`` and
``test_access_permission.py``; the fixture-driven scenarios below are
skipped with a one-line reason each.

PDFBOX-4453 is the one upstream test that constructs its own input
document in-line — we port that one here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# --------------------------------------------------------------------- #
# testPermissions — needs PasswordSample-*-bit.pdf fixtures.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="upstream needs PasswordSample-{40,128,256}bit.pdf fixtures "
    "(Adobe Acrobat–produced, NOT PDFBox-produced, kept upstream as the "
    "encrypted-document gold standard) and exercises the rendering "
    "pipeline via PDFRenderer.renderImage; both are out of scope for "
    "this parity-port pass."
)
def test_permissions() -> None: ...


# --------------------------------------------------------------------- #
# testProtection — needs Acroform-PDFBOX-2333.pdf + AES-256 wiring.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="upstream's testProtection iterates a 4-row matrix over "
    "{40,128,128+AES,256+AES} bits with a non-trivial AcroForm fixture; "
    "the per-revision protection round-trip is exercised by "
    "test_security_handler.py / test_standard_security_handler.py "
    "without the AcroForm dependency."
)
def test_protection() -> None: ...


# --------------------------------------------------------------------- #
# testPDFBox4308 — PDFBOX-4308: index colorspace + indirect-object encrypt.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="PDFBOX-4308: requires the upstream-only target/pdfs/PDFBOX-4308.pdf "
    "corpus document (a Maven-downloaded fixture exercising indexed "
    "color-space encryption); not bundled."
)
def test_pdf_box_4308() -> None: ...


# --------------------------------------------------------------------- #
# testPDFBox5955 — PDFBOX-5955: RC4-40 / RC4-48 unusual key lengths.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="PDFBOX-5955: requires target/pdfs/PDFBOX-5955-{40,48}bit.pdf "
    "corpus documents (unusual RC4 key lengths) and the text-extraction "
    "pipeline; not bundled."
)
def test_pdf_box_5955() -> None: ...


# --------------------------------------------------------------------- #
# testProtectionInnerAttachment — embedded-file encrypt + extract.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="upstream needs preEnc_20141025_105451.pdf fixture (an "
    "encrypted document with an embedded PDF, kept upstream as a "
    "round-trip regression target) and exercises the embedded-file "
    "extraction surface; not bundled."
)
def test_protection_inner_attachment() -> None: ...


# --------------------------------------------------------------------- #
# testPDFBox4453 — verify identical encrypted strings decrypt to different
# clear values. This is the one upstream test that builds its input in
# memory rather than loading a fixture; port it.
# --------------------------------------------------------------------- #


def test_pdf_box_4453_repeated_string_values_round_trip(tmp_path: Path) -> None:
    """PDFBOX-4453: many nested dictionaries with repeated COSString values
    must each round-trip to their clear-text after RC4-40 encrypt → save →
    ``Loader.load_pdf`` decrypt. Fixed in wave 1361 (see CHANGES.md):
    ``PDDocument.decrypt`` now runs a second pass over the object pool
    that calls ``handler.decrypt`` on every non-stream indirect, which in
    turn recurses through nested dictionaries decrypting each
    ``COSString`` slot with the right per-object key.

    Upstream parameterises ``TESTCOUNT`` at 1000 — we drop to 50 so the
    test stays well under the suite's per-test budget while still
    exercising the per-object-key derivation across many objects.
    """
    import io  # noqa: PLC0415

    from pypdfbox.cos.cos_dictionary import COSDictionary  # noqa: PLC0415
    from pypdfbox.cos.cos_name import COSName  # noqa: PLC0415
    from pypdfbox.loader import Loader  # noqa: PLC0415
    from pypdfbox.pdmodel.encryption.access_permission import (  # noqa: PLC0415
        AccessPermission,
    )
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (  # noqa: PLC0415
        StandardProtectionPolicy,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415
    from pypdfbox.pdmodel.pd_page import PDPage  # noqa: PLC0415

    testcount = 50  # upstream uses 1000

    doc = PDDocument()
    doc.add_page(PDPage())
    for i in range(testcount):
        nested = COSDictionary()
        doc.get_page(0).get_cos_object().set_item(
            COSName.get_pdf_name(f"_Test-{i}"), nested
        )
        # Two distinct string slots so the per-object key derivation has
        # to step the cipher state between them — single-string per dict
        # masks a class of cipher-state-reuse bugs.
        nested.set_string("key1", "3")
        nested.set_string("key2", "0")

    spp = StandardProtectionPolicy("12345", "", AccessPermission())
    spp.set_encryption_key_length(40)
    spp.set_prefer_aes(False)
    doc.protect(spp)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()

    reloaded_cos = Loader.load_pdf(buf.getvalue(), "12345")
    reloaded = PDDocument(reloaded_cos)
    try:
        assert reloaded.is_encrypted()
        for i in range(testcount):
            d = (
                reloaded.get_page(0)
                .get_cos_object()
                .get_cos_dictionary(COSName.get_pdf_name(f"_Test-{i}"))
            )
            assert d is not None
            assert d.get_string("key1") == "3"
            assert d.get_string("key2") == "0"
    finally:
        reloaded.close()


# --------------------------------------------------------------------- #
# testPDFBox5639 — AESV3 R=5 with excess bytes.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="PDFBOX-5639: requires target/pdfs/PDFBOX-5639.pdf corpus "
    "document (a Maven-downloaded AESV3 R=5 fixture); not bundled."
)
def test_pdf_box_5639() -> None: ...
