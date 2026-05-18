"""Coverage-boost test (wave 1351) for ``WriteDecodedDoc.process_object``
skip-images branch (line 59 of ``write_decoded_doc.py``).

Wave-1323 covers the OSError arm, the COSObject unwrap, and the
attribute-fallback paths. The ``skip_images=True`` AND-of-three
condition (``isinstance(stream, COSStream)`` AND ``/Type == /XObject``
AND ``/Subtype == /Image``) was never exercised — the early ``return``
on line 59 stayed grey.
"""
from __future__ import annotations

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.tools.write_decoded_doc import WriteDecodedDoc


def test_process_object_skips_image_xobject_when_skip_images_true() -> None:
    """An ``/XObject`` ``/Image`` stream is left intact when
    ``skip_images=True``: the early return means the ``/Filter`` entry
    survives and the encoded payload is untouched."""
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.XOBJECT)
    stream.set_item(COSName.SUBTYPE, COSName.IMAGE)
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)
    # Use raw bytes that are NOT valid FlateDecode — confirms the early
    # return prevents the to_byte_array call (which would raise OSError).
    stream.set_raw_data(b"\xff\xff garbage that would fail to inflate")
    WriteDecodedDoc().process_object(stream, skip_images=True)
    # /Filter still present → the helper exited before reaching the
    # remove_item call on line 62.
    assert stream.get_item(COSName.FILTER) == COSName.FLATE_DECODE


def test_process_object_processes_non_image_xobject_even_with_skip_images() -> None:
    """A non-image XObject (e.g. ``/Subtype == /Form``) should NOT be
    skipped, even with ``skip_images=True`` — the AND short-circuits at
    the SUBTYPE check, dropping out of the early-return branch."""
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.XOBJECT)
    stream.set_item(COSName.SUBTYPE, COSName.FORM)
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)
    with stream.create_output_stream(COSName.FLATE_DECODE) as out:
        out.write(b"form data")
    WriteDecodedDoc().process_object(stream, skip_images=True)
    # Form stream was processed: /Filter is gone, raw data is the
    # decoded payload.
    assert stream.get_item(COSName.FILTER) is None
    assert stream.get_raw_data() == b"form data"


def test_process_object_processes_image_xobject_when_skip_images_false() -> None:
    """The same image stream IS rewritten when ``skip_images=False`` —
    confirms the gate is the flag itself, not the type/subtype."""
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.XOBJECT)
    stream.set_item(COSName.SUBTYPE, COSName.IMAGE)
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)
    with stream.create_output_stream(COSName.FLATE_DECODE) as out:
        out.write(b"image payload")
    WriteDecodedDoc().process_object(stream, skip_images=False)
    assert stream.get_item(COSName.FILTER) is None
    assert stream.get_raw_data() == b"image payload"
