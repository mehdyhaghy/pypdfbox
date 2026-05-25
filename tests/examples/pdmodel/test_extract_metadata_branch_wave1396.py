"""Wave 1396 branch-coverage tests for ``ExtractMetadata`` schema show
helpers.

Closes False-branch arrows for the ``isinstance(schema, X)`` guard in
each ``show_*`` method:

* 56->exit — ``show_xmp_basic_schema`` no-op when /XMPBasic absent
* 63->exit — ``show_adobe_pdf_schema`` no-op when /AdobePDF absent
* 72->exit — ``show_dublin_core_schema`` no-op when /DC absent
* 81->exit — ``show_document_information`` False arm via main path
"""

from __future__ import annotations

import pytest

from pypdfbox.examples.pdmodel.extract_metadata import ExtractMetadata
from pypdfbox.xmpbox import XMPMetadata


def test_show_xmp_basic_schema_no_basic_schema_is_noop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No /XMPBasic schema → method is a no-op.

    Closes False arm at line 63 (and exit at line 56 in main).
    """
    metadata = XMPMetadata.create_xmp_metadata()
    # No basic schema added.
    ExtractMetadata.show_xmp_basic_schema(metadata)
    out = capsys.readouterr().out
    # No output produced — the show body was skipped.
    assert "Create Date" not in out
    assert "Modify Date" not in out


def test_show_adobe_pdf_schema_no_pdf_schema_is_noop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No /AdobePDF schema → method is a no-op.

    Closes False arm at line 72.
    """
    metadata = XMPMetadata.create_xmp_metadata()
    ExtractMetadata.show_adobe_pdf_schema(metadata)
    out = capsys.readouterr().out
    assert "Keywords" not in out
    assert "PDF Version" not in out


def test_show_dublin_core_schema_no_dc_schema_is_noop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No /DC schema → method is a no-op.

    Closes False arm at line 81.
    """
    metadata = XMPMetadata.create_xmp_metadata()
    ExtractMetadata.show_dublin_core_schema(metadata)
    out = capsys.readouterr().out
    assert "Title" not in out
    assert "Description" not in out
