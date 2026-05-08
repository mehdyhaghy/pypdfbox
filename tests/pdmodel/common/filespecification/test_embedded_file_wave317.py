from __future__ import annotations

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.common.filespecification import PDEmbeddedFile


def test_wave317_embedded_file_constructor_accepts_filter_array() -> None:
    filters = COSArray(
        [
            COSName.get_pdf_name("FlateDecode"),
            COSName.get_pdf_name("ASCII85Decode"),
        ]
    )

    embedded = PDEmbeddedFile(None, b"already-encoded", filters)

    cos = embedded.get_cos_object()
    assert cos.get_raw_data() == b"already-encoded"
    assert cos.get_dictionary_object(COSName.get_pdf_name("Filter")) is filters
