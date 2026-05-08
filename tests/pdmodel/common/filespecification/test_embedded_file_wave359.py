from __future__ import annotations

from pypdfbox.cos import COSInteger, COSName, COSObject, COSString
from pypdfbox.pdmodel.common.filespecification import PDEmbeddedFile


def test_wave359_embedded_file_subtype_reads_string_form() -> None:
    embedded = PDEmbeddedFile()
    embedded.get_cos_object().set_item(
        COSName.SUBTYPE,  # type: ignore[attr-defined]
        COSString("application/pdf"),
    )

    assert embedded.get_subtype() == "application/pdf"
    assert embedded.has_subtype() is True
    assert embedded.is_subtype("Application/PDF") is True


def test_wave359_embedded_file_subtype_reads_indirect_string_form() -> None:
    embedded = PDEmbeddedFile()
    embedded.get_cos_object().set_item(
        COSName.SUBTYPE,  # type: ignore[attr-defined]
        COSObject(359, 0, resolved=COSString("text/plain")),
    )

    assert embedded.get_subtype() == "text/plain"
    assert embedded.has_subtype() is True


def test_wave359_embedded_file_has_subtype_rejects_malformed_entry() -> None:
    embedded = PDEmbeddedFile()
    embedded.get_cos_object().set_item(
        COSName.SUBTYPE,  # type: ignore[attr-defined]
        COSInteger.get(1),
    )

    assert embedded.get_subtype() is None
    assert embedded.has_subtype() is False
