"""Port of upstream ``PDAcroFormFlattenTest`` (PDFBox 3.0.x).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/
PDAcroFormFlattenTest.java``.

The bulk of upstream's tests fetch sample PDFs from Apache JIRA URLs and
compare the rendered output to a checked-in reference PNG (via
``TestPDFToImage``). Those paths are intentionally **not** ported here:

* They require network access, which CI is not permitted to make.
* They depend on pixel-perfect rendering parity against PDFBox's renderer
  which is itself a separate parity target tracked elsewhere.

The local-fixture path — ``flattenSingleField`` against the bundled
``MultilineFields.pdf`` — is ported in full and asserts the upstream
post-condition: flattening one named field reduces ``/Fields`` by one and
that field can no longer be looked up by name.
"""

from __future__ import annotations

import pathlib

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form import PDTextField

_MULTILINE_FIXTURE = (
    pathlib.Path(__file__).resolve().parents[4]
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
    / "MultilineFields.pdf"
)


def test_flatten_single_field() -> None:
    """Flattening one named text field removes it from ``/Fields`` and
    leaves the rest of the form structurally intact (upstream
    ``flattenSingleField``)."""
    with PDDocument.load(_MULTILINE_FIXTURE) as document:
        acro_form = document.get_document_catalog().get_acro_form()
        num_fields_before = len(acro_form.get_fields())

        field = acro_form.get_field("AlignLeft-Filled")
        assert isinstance(field, PDTextField), (
            "fixture should expose 'AlignLeft-Filled' as a PDTextField"
        )
        acro_form.flatten([field], False)

        assert len(acro_form.get_fields()) == num_fields_before - 1, (
            "the number of form fields shall be reduced by one"
        )
        assert acro_form.get_field("AlignLeft-Filled") is None, (
            "the flattened field shall no longer exist"
        )


@pytest.mark.parametrize(
    "source_url, target_file_name",
    [
        (
            "https://issues.apache.org/jira/secure/attachment/12682897/FormI-9-English.pdf",
            "FormI-9-English.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/12689788/test.pdf",
            "test-2586.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/12792007/hidden_fields.pdf",
            "hidden_fields.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/12816014/Signed-Document-1.pdf",
            "Signed-Document-1.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/12816016/Signed-Document-2.pdf",
            "Signed-Document-2.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/12821307/Signed-Document-3.pdf",
            "Signed-Document-3.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/12821308/Signed-Document-4.pdf",
            "Signed-Document-4.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/12986337/"
            "stenotypeTest-3_rotate_no_flatten.pdf",
            "PDFBOX-4693-filled.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/12994791/flatten.pdf",
            "PDFBOX-4788.pdf",
        ),
        (
            "https://issues.apache.org/jira/secure/attachment/13011410/PDFBOX-4955.pdf",
            "PDFBOX-4955.pdf",
        ),
    ],
    ids=[
        "FormI-9-English",
        "test-2586",
        "hidden_fields",
        "Signed-Document-1",
        "Signed-Document-2",
        "Signed-Document-3",
        "Signed-Document-4",
        "PDFBOX-4693",
        "PDFBOX-4788",
        "PDFBOX-4955",
    ],
)
def test_flatten_network_render_compare(source_url: str, target_file_name: str) -> None:
    """Upstream ``testFlatten`` matrix — fetches each PDF from Apache JIRA
    and compares the rendered PNG to a generated reference. Skipped here:
    pypdfbox tests are forbidden from making network calls and renderer
    pixel parity is tracked outside the AcroForm flatten harness."""
    pytest.skip(
        f"network-dependent render-compare ({source_url} -> {target_file_name}); "
        "not portable to offline CI"
    )


def test_flatten_test_pdfbox_5254() -> None:
    """Upstream ``flattenTestPDFBOX5254`` — fetches f1040sb test.pdf via
    URL and renders. Skipped (network + render parity)."""
    pytest.skip(
        "network-dependent render-compare for PDFBOX-5254 (f1040sb test.pdf)"
    )


def test_flatten_test_pdfbox_5225() -> None:
    """Upstream ``flattenTestPDFBOX5225`` — fetches SourceFailure.pdf via
    URL, flattens ``VN_NAME`` only, asserts 76 field-tree entries remain
    and 59 annotations on page 0, then renders. Skipped (network + render
    parity)."""
    pytest.skip(
        "network-dependent render-compare for PDFBOX-5225 (SourceFailure.pdf)"
    )
