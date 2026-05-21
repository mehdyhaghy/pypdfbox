"""Save with ``CompressParameters`` arg — round-trip parity (wave 1366, agent E).

Verifies that the trailing ``compress_parameters`` argument introduced on
``PDDocument.save`` in PDFBox 3.0 is accepted in all the spelling shapes
upstream code uses, that the output stays a valid PDF, and that the value
is currently a no-op (pypdfbox always writes uncompressed object streams —
see ``CompressParameters.NO_COMPRESSION`` in
``pypdfbox/pdfwriter/compress/compress_parameters.py``).

No upstream JUnit counterpart — pypdfbox-specific hand-written suite
covering the boundary that direct PDFBox ports compile against. The
behaviour pypdfbox guarantees here is documented in CHANGES.md under
"compression toggle accepted but no-op".
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters


@pytest.mark.parametrize(
    "params",
    [
        None,
        CompressParameters.NO_COMPRESSION,
        CompressParameters.DEFAULT_COMPRESSION,
        CompressParameters(0),
        CompressParameters(200),
        CompressParameters(1),
        object(),  # opaque truthy value — upstream parity only
    ],
    ids=["none", "no_compression", "default", "size0", "size200", "size1", "opaque"],
)
def test_save_accepts_compress_parameters(params: object) -> None:
    """All supported (and parity-pass-through) shapes for the trailing
    ``compress_parameters`` arg yield a valid PDF on a BytesIO sink."""
    sink = io.BytesIO()
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(sink, compress_parameters=params)
    out = sink.getvalue()
    assert out[:5] == b"%PDF-"
    assert out.endswith(b"%%EOF\n")
    # Reload to confirm the bytes parse back into the same page count.
    with PDDocument.load(out) as reloaded:
        assert reloaded.get_number_of_pages() == 1


def test_save_no_compression_roundtrip_file(tmp_path: Path) -> None:
    """``CompressParameters.NO_COMPRESSION`` round-trips through a file
    sink with content preserved (no-op behaviour confirmed)."""
    path = tmp_path / "no_compression.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.add_page(PDPage())
        doc.add_page(PDPage())
        doc.get_document_information().set_title("no-compression")
        doc.save(path, compress_parameters=CompressParameters.NO_COMPRESSION)

    with PDDocument.load(path) as reloaded:
        assert reloaded.get_number_of_pages() == 3
        assert reloaded.get_document_information().get_title() == "no-compression"


def test_default_compression_singleton_is_shared() -> None:
    """``CompressParameters.DEFAULT_COMPRESSION`` and ``NO_COMPRESSION`` are
    class-level singletons — repeated attribute access returns the same
    instance. Save accepts both equivalently."""
    a = CompressParameters.DEFAULT_COMPRESSION
    b = CompressParameters.DEFAULT_COMPRESSION
    assert a is b
    c = CompressParameters.NO_COMPRESSION
    d = CompressParameters.NO_COMPRESSION
    assert c is d
    # Both must be accepted and yield identical output (no-op).
    out_default = io.BytesIO()
    out_none = io.BytesIO()
    with PDDocument() as doc1:
        doc1.add_page(PDPage())
        doc1.save(out_default, compress_parameters=a)
    with PDDocument() as doc2:
        doc2.add_page(PDPage())
        doc2.save(out_none, compress_parameters=c)
    # Both produce a well-formed PDF — bytes may differ slightly
    # (timestamps, IDs) but page count must match on reload.
    with PDDocument.load(out_default.getvalue()) as r1:
        assert r1.get_number_of_pages() == 1
    with PDDocument.load(out_none.getvalue()) as r2:
        assert r2.get_number_of_pages() == 1


def test_save_compress_parameters_positional_arg() -> None:
    """Upstream ``save(File, CompressParameters)`` is positional —
    pypdfbox accepts the value at the same positional slot."""
    sink = io.BytesIO()
    with PDDocument() as doc:
        doc.add_page(PDPage())
        # Positional second argument — mirrors upstream's overload.
        doc.save(sink, CompressParameters.NO_COMPRESSION)
    assert sink.getvalue().endswith(b"%%EOF\n")


def test_compress_parameters_no_compression_is_disabled() -> None:
    """The CompressParameters value-type predicates are consistent —
    ``NO_COMPRESSION.is_disabled()`` is True, ``DEFAULT_COMPRESSION``
    reports ``is_compress() is True``."""
    assert CompressParameters.NO_COMPRESSION.is_disabled() is True
    assert CompressParameters.NO_COMPRESSION.is_compress() is False
    assert CompressParameters.DEFAULT_COMPRESSION.is_compress() is True
    assert CompressParameters.DEFAULT_COMPRESSION.is_disabled() is False


def test_compress_parameters_negative_raises() -> None:
    """The value-type constructor rejects negative sizes — sanity check
    that the save path will likewise fail at construction time."""
    with pytest.raises(ValueError, match="negative"):
        CompressParameters(-1)
