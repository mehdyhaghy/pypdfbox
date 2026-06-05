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

    # The embed ctor encodes the decoded payload through the /Filter chain
    # (upstream createOutputStream(filters)); the recorded body is the
    # encoded form, and create_input_stream() round-trips back.
    embedded = PDEmbeddedFile(None, b"decoded payload", filters)

    cos = embedded.get_cos_object()
    assert cos.get_raw_data() != b"decoded payload"
    assert embedded.create_input_stream().read() == b"decoded payload"
    recorded = cos.get_dictionary_object(COSName.get_pdf_name("Filter"))
    assert [n.name for n in recorded] == ["FlateDecode", "ASCII85Decode"]
