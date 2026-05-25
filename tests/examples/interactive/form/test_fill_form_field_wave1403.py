"""Wave 1403 branch round-out for ``fill_form_field``.

Closes ``46->55``: when the document has no /AcroForm, the
``if acro_form is not None`` guard takes its False arc and ``fill`` proceeds
straight to the save without touching any fields.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.fill_form_field import FillFormField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def test_fill_skips_field_work_when_no_acro_form(tmp_path: Path) -> None:
    src = tmp_path / "plain.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(src))

    dst = tmp_path / "out.pdf"
    FillFormField.fill(str(src), str(dst))
    assert dst.exists()
    # Still no AcroForm in the saved file.
    with PDDocument.load(str(dst)) as out:
        assert out.get_document_catalog().get_acro_form() is None
