"""Wave 1605 — PDFBOX-6236: seed incremental numbering from trailer /Size.

An incremental update may only *append*; every object number below the
origin document's ``/Size`` is already reserved by that document, even
when the loaded xref never mentions it (sparse subsections, a repaired
or truncated xref, a hybrid file whose classic table lists fewer keys
than the stream). Seeding the writer's counter purely from the highest
key we happened to load therefore hands out numbers the origin already
owns, and the appended revision silently redefines existing objects.

Upstream clamps the counter with ``number = max(trailerSize - 1, number)``
inside the incremental branch of ``COSWriter.write`` and logs a warning
when the highest loaded number is *above* the trailer entry (a sign the
origin's ``/Size`` is wrong). These tests pin both halves.
"""

import io
import logging
import re

from pypdfbox.cos import COSDictionary, COSName, COSObject
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter

_MARKER = COSName.get_pdf_name("Marker")
_EXTRA = COSName.get_pdf_name("Extra")


def _seed_pdf(trailer_size: int) -> bytes:
    """A two-object PDF (keys 1 and 2) whose trailer declares ``/Size``
    independently of the xref subsection — the sparse-xref shape
    PDFBOX-6236 is about."""
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [ ] /Count 0 >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n"
    out += f"0 {len(bodies) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n"
    out += f"<< /Size {trailer_size} /Root 1 0 R >>\n".encode("ascii")
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF\n"
    return bytes(out)


def _append_new_object(source: bytes, *, drop_size: bool = False,
                       size_override: int | None = None) -> bytes:
    """Load ``source``, attach one brand-new indirect dict to the catalog
    and save incrementally; return the full output bytes."""
    parsed = Loader.load_pdf(source)
    try:
        trailer = parsed.get_trailer()
        assert trailer is not None
        if drop_size:
            trailer.remove_item(COSName.SIZE)  # type: ignore[attr-defined]
        elif size_override is not None:
            trailer.set_int(COSName.SIZE, size_override)  # type: ignore[attr-defined]
        new_dict = COSDictionary()
        new_dict.set_int(_MARKER, 99)
        new_dict.set_needs_to_be_updated(True)
        catalog = parsed.get_catalog()
        assert catalog is not None
        catalog.set_item(_EXTRA, COSObject(0, 0, resolved=new_dict))
        catalog.set_needs_to_be_updated(True)
        sink = io.BytesIO()
        with COSWriter(sink, incremental=True) as writer:
            writer.write(parsed)
        return sink.getvalue()
    finally:
        parsed.close()


def _appended_object_numbers(source: bytes, output: bytes) -> set[int]:
    assert output.startswith(source)
    appended = output[len(source):]
    return {int(n) for n in re.findall(rb"(?m)^(\d+) \d+ obj\b", appended)}


def test_seed_pdf_keeps_declared_trailer_size() -> None:
    """Guard on the fixture: the loader must preserve the sparse ``/Size``
    (otherwise the tests below would not exercise the clamp at all)."""
    parsed = Loader.load_pdf(_seed_pdf(20))
    try:
        trailer = parsed.get_trailer()
        assert trailer is not None
        assert trailer.get_int(COSName.SIZE) == 20  # type: ignore[attr-defined]
        assert max(k.object_number for k in parsed.get_object_keys()) == 2
    finally:
        parsed.close()


def test_incremental_new_object_starts_at_trailer_size() -> None:
    """With ``/Size 20`` and only keys 1-2 loaded, the first minted number
    is 20 — numbers 3..19 stay reserved for the origin document."""
    source = _seed_pdf(20)
    output = _append_new_object(source)
    numbers = _appended_object_numbers(source, output)
    assert 20 in numbers, f"expected a fresh object 20, saw {sorted(numbers)}"
    reserved = {n for n in numbers if 3 <= n <= 19}
    assert not reserved, f"appended revision reused reserved numbers {sorted(reserved)}"


def test_incremental_appended_revision_round_trips() -> None:
    """The clamped numbering must still produce a loadable file whose new
    object and original objects both resolve."""
    source = _seed_pdf(20)
    output = _append_new_object(source)
    reparsed = Loader.load_pdf(output)
    try:
        catalog = reparsed.get_catalog()
        assert catalog is not None
        extra = catalog.get_dictionary_object(_EXTRA)
        assert isinstance(extra, COSDictionary)
        assert extra.get_int(_MARKER) == 99
        pages = catalog.get_dictionary_object(COSName.PAGES)  # type: ignore[attr-defined]
        assert isinstance(pages, COSDictionary)
        assert pages.get_int(COSName.COUNT) == 0  # type: ignore[attr-defined]
    finally:
        reparsed.close()


def test_incremental_numbering_unchanged_for_wellformed_size() -> None:
    """``/Size == highest + 1`` (a well-formed file): the clamp is a no-op,
    so the next number is still ``highest + 1``."""
    source = _seed_pdf(3)
    output = _append_new_object(source)
    numbers = _appended_object_numbers(source, output)
    assert 3 in numbers, f"expected a fresh object 3, saw {sorted(numbers)}"


def test_incremental_missing_trailer_size_does_not_lower_numbering() -> None:
    """A trailer without ``/Size`` yields ``-1`` (upstream ``getLong``
    default), so ``max(-2, highest)`` leaves the counter untouched."""
    source = _seed_pdf(3)
    output = _append_new_object(source, drop_size=True)
    numbers = _appended_object_numbers(source, output)
    assert 3 in numbers, f"expected a fresh object 3, saw {sorted(numbers)}"
    assert not {n for n in numbers if n < 0}


def test_warning_when_highest_number_exceeds_trailer_size(caplog) -> None:
    """A ``/Size`` below the highest loaded object number is a corrupt
    origin trailer — upstream warns and keeps the higher number."""
    source = _seed_pdf(3)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdfwriter.cos_writer"):
        output = _append_new_object(source, size_override=1)
    assert "The highest object number 2" in caplog.text
    assert "bigger than the trailer entry 1" in caplog.text
    numbers = _appended_object_numbers(source, output)
    assert 3 in numbers, f"expected a fresh object 3, saw {sorted(numbers)}"


def test_no_warning_for_wellformed_trailer_size(caplog) -> None:
    """The common case must stay silent."""
    source = _seed_pdf(3)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdfwriter.cos_writer"):
        _append_new_object(source)
    assert "bigger than the trailer entry" not in caplog.text
