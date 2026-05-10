"""Encrypt-on-write coverage for xref-stream output.

Step-1 audit (see ``COSWriter.__doc__``) confirms that the cluster #1
writer always emits a *traditional* ``xref`` table + ``trailer`` pair —
xref-stream output (``writeXrefStream`` upstream) is explicitly stubbed
and slated for pdfwriter cluster #3. Until that cluster lands there is
no xref-stream body to encrypt on write, so the integration test is
skipped with a marker. We *do* keep one regression check that asserts
encrypted documents currently round-trip through the traditional xref
path (catches the day xref-stream output sneaks in without wiring the
encryption pipeline through it).
"""

from __future__ import annotations

import io

import pytest

# Skip cleanly on checkouts where the security cluster isn't present.
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_security_handler")
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")

from pypdfbox import Loader, PDDocument  # noqa: E402
from pypdfbox.cos import COSStream  # noqa: E402
from pypdfbox.pdmodel import PDPage  # noqa: E402
from pypdfbox.pdmodel.encryption.access_permission import (  # noqa: E402
    AccessPermission,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (  # noqa: E402
    StandardProtectionPolicy,
)

_CONTENT_PAYLOAD = b"BT /F1 12 Tf 50 700 Td (Hello xref-stream) Tj ET"


def _build_protected_document() -> PDDocument:
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(_CONTENT_PAYLOAD)
    page.set_contents(stream)
    policy = StandardProtectionPolicy(
        owner_password="owner",
        user_password="user",
        permissions=AccessPermission(),
    )
    pd.protect(policy)
    return pd


def _save_to_bytes(pd: PDDocument) -> bytes:
    sink = io.BytesIO()
    pd.save(sink)
    return sink.getvalue()


# ---------------------------------------------------------------------------
# Step-1 finding: traditional xref only — no xref-stream emit path exists.
# ---------------------------------------------------------------------------


def test_encrypted_document_uses_traditional_xref_table() -> None:
    """Regression check: today's writer must emit a classic ``xref`` /
    ``trailer`` pair even when the document is encrypted. The day xref-
    stream output lands in ``COSWriter`` (pdfwriter cluster #3), this
    test will fail and remind us to wire ``encrypt_stream`` through the
    xref-stream body before declaring the cluster done."""
    pd = _build_protected_document()
    saved = _save_to_bytes(pd)

    # Traditional xref section header + trailer keyword must both be
    # present. ISO 32000-1 §7.5.4 / §7.5.5.
    assert b"\nxref\n" in saved or b"\rxref\r" in saved or b"\nxref\r" in saved, (
        "expected a traditional 'xref' section in the saved bytes"
    )
    assert b"trailer" in saved, "expected a 'trailer' keyword in the saved bytes"

    # The xref-stream type marker must NOT appear in the trailer's xref
    # object — its presence would mean the writer started emitting xref
    # streams without this test being updated.
    assert b"/Type /XRef" not in saved and b"/Type/XRef" not in saved, (
        "writer unexpectedly emitted an xref stream — wire the encryption "
        "pipeline through it (see pdfwriter cluster #3) and update this test"
    )

    # Sanity: the saved bytes still parse back as an encrypted document.
    with PDDocument.load(saved, password="user") as reloaded:
        assert reloaded.is_encrypted()
        assert reloaded.get_number_of_pages() == 1


def test_xref_stream_encrypt_on_write_round_trip() -> None:
    """Full round-trip: protect, save with xref-stream output, parse back,
    verify object table. Skipped until pdfwriter cluster #3 lands."""
    # Probe: does ``COSWriter`` expose any xref-stream output surface?
    from pypdfbox.pdfwriter.cos_writer import COSWriter

    has_xref_stream_path = (
        hasattr(COSWriter, "write_xref_stream")
        or hasattr(COSWriter, "_do_write_xref_stream")
        or hasattr(COSWriter, "_write_xref_stream")
    )
    if not has_xref_stream_path:
        pytest.skip("xref-stream output deferred — pdfwriter cluster #3")

    # Once the cluster lands, the body below should be replaced with a
    # real round-trip exercising the xref-stream path. Until then the
    # skip above keeps CI green.
    pd = _build_protected_document()
    saved = _save_to_bytes(pd)
    with PDDocument.load(saved, password="user") as reloaded:
        assert reloaded.is_encrypted()
        assert reloaded.get_number_of_pages() == 1
        # Verify the recovered content stream matches the seed.
        page = reloaded.get_pages()[0]
        contents = page.get_cos_object().get_dictionary_object("Contents")
        assert isinstance(contents, COSStream)
        with contents.create_input_stream() as src:
            assert src.read() == _CONTENT_PAYLOAD

    # Silence unused-import lints for the helper kept around for the
    # eventual real implementation.
    _ = Loader
