from __future__ import annotations

from pypdfbox.cos import COSNull, COSObject, COSString
from pypdfbox.pdmodel.common.filespecification import (
    PDFileSpecification,
    PDSimpleFileSpecification,
)


def test_wave312_create_fs_treats_direct_cos_null_as_absent() -> None:
    assert PDFileSpecification.create_fs(COSNull.NULL) is None


def test_wave312_create_fs_treats_indirect_cos_null_as_absent() -> None:
    ref = COSObject(1, 0, resolved=COSNull.NULL)

    assert PDFileSpecification.create_fs(ref) is None


def test_wave312_create_fs_unwraps_nested_indirect_file_specification() -> None:
    inner = COSString("nested.pdf")
    first_ref = COSObject(2, 0, resolved=inner)
    second_ref = COSObject(3, 0, resolved=first_ref)

    spec = PDFileSpecification.create_fs(second_ref)

    assert isinstance(spec, PDSimpleFileSpecification)
    assert spec.get_file() == "nested.pdf"
