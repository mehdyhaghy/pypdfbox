"""Pin the appended xref-STREAM dictionary key-insertion ORDER on an
incremental save (``COSWriter._do_write_xref_stream_increment``).

Wave 1503 converged the appended xref stream's dictionary key order to
PDFBox's exact insertion sequence so the appended tail of an incremental save
over an xref-stream source is byte-identical to Apache PDFBox 3.0.7. PDFBox's
``COSStream`` keySet is insertion-ordered, and the writer emits keys in that
order; the sequence (``PDFXRefStream.getStream`` + ``addTrailerInfo`` +
``COSStream`` constructor) is:

    /Length            (constructor seeds /Length 0)
    <trailer subset>   (addTrailerInfo: /Info /Root /Encrypt /ID /Prev,
                        copied IN TRAILER-ITERATION ORDER)
    /Type /Size /Index /W   (getStream, in that order)
    /Filter            (createOutputStream, appended last)

Before the fix pypdfbox emitted ``/Filter /Length /Type /XRef /Size /W /Index
/Root /Info /ID /Prev`` — valid but structurally divergent. This module is the
oracle-free guard for that geometry: it asserts the exact key order of the
appended xref stream's dictionary, that ``/Index`` precedes ``/W``, that
``/Filter`` is last, and that ``/Length`` is first.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from pypdfbox.pdmodel import PDDocument

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"
_XREF_STREAM_FIXTURE = _FIXTURES / "pdfwriter" / "unencrypted.pdf"

_KEY = re.compile(rb"/([A-Za-z][A-Za-z0-9]*)")


def _appended_xref_stream_keys(out: bytes, source_len: int) -> list[str]:
    """Parse the key names of the appended xref stream's dictionary, in the
    order they appear in the serialised bytes."""
    tail = out[source_len:]
    type_at = tail.find(b"/Type /XRef")
    assert type_at != -1, "no appended /Type /XRef object found in tail"
    # The dict opens at the ``obj`` keyword preceding /Type /XRef and closes
    # at the ``stream`` keyword that follows it.
    obj_at = tail.rfind(b"obj", 0, type_at)
    stream_at = tail.find(b"stream", type_at)
    assert obj_at != -1 and stream_at != -1
    body = tail[obj_at + len(b"obj") : stream_at]
    # Drop /XRef (the value of /Type) and inner array element names: only the
    # top-level keys matter. The xref-stream dict has no name-valued keys
    # except /Type /XRef and /Filter /FlateDecode, so strip those two values.
    keys: list[str] = []
    for km in _KEY.finditer(body):
        name = km.group(1).decode("ascii")
        keys.append(name)
    # Remove the value names (XRef after Type, FlateDecode after Filter).
    cleaned: list[str] = []
    skip_next = False
    for name in keys:
        if skip_next:
            skip_next = False
            continue
        cleaned.append(name)
        if name in ("Type", "Filter"):
            skip_next = True
    return cleaned


def _save_incremental(src: bytes) -> bytes:
    doc = PDDocument.load(src)
    try:
        info = doc.get_document_information()
        info.set_title("DeltaTitle")
        info.get_cos_object().set_needs_to_be_updated(True)
        buf = io.BytesIO()
        doc.save_incremental(buf)
    finally:
        doc.close()
    return buf.getvalue()


def test_appended_xref_stream_key_order_matches_pdfbox() -> None:
    src = _XREF_STREAM_FIXTURE.read_bytes()
    out = _save_incremental(src)
    keys = _appended_xref_stream_keys(out, len(src))

    # /Length first (constructor-seeded).
    assert keys[0] == "Length"
    # /Filter last (createOutputStream appends it after Type/Size/Index/W).
    assert keys[-1] == "Filter"
    # The four getStream keys appear in /Type /Size /Index /W order.
    assert keys.index("Type") < keys.index("Size") < keys.index("Index") < keys.index("W")
    # /Index immediately precedes /W (no key wedged between them).
    assert keys.index("W") == keys.index("Index") + 1
    # The trailer subset is inserted between /Length and /Type.
    for trailer_key in ("Root", "Info", "ID", "Prev"):
        assert keys.index(trailer_key) < keys.index("Type"), trailer_key


def test_trailer_subset_follows_source_trailer_iteration_order() -> None:
    """``addTrailerInfo`` copies the /Info /Root /Encrypt /ID /Prev subset in
    the source trailer's own iteration order. For this fixture that yields
    /ID /Info /Root /Prev (the source trailer's order)."""
    src = _XREF_STREAM_FIXTURE.read_bytes()
    doc = PDDocument.load(src)
    try:
        trailer = doc.get_document().get_trailer()
        subset = {"Info", "Root", "Encrypt", "ID", "Prev"}
        source_order = [
            str(k).lstrip("/")
            for k in trailer.key_set()
            if str(k).lstrip("/") in subset
        ]
    finally:
        doc.close()

    out = _save_incremental(src)
    keys = _appended_xref_stream_keys(out, len(src))
    emitted_subset = [k for k in keys if k in subset]
    assert emitted_subset == source_order
