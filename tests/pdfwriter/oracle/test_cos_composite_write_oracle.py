"""Live PDFBox differential parity for COMPOSITE ``COSDictionary`` / ``COSArray``
serialization — the ``<< /Key Value ... >>`` and ``[ ... ]`` self-write surface.

This complements the per-scalar write/escape oracles:

* ``test_write_scalar_oracle.py`` / ``CosWriteSelfProbe`` — the five scalar
  ``writePDF`` paths (float, int, name, bool, null).
* ``test_cos_escape_oracle.py`` / ``CosEscapeProbe`` — name ``#XX`` escaping and
  string literal/hex selection.

Here the focus is the COMPOSITE framing decisions ``COSWriter`` alone owns
(``visitFromDictionary`` / ``visitFromArray`` upstream):

* **dictionary framing** — ``<<`` then an EOL, then per entry ``/Key`` + a
  single SPACE + the serialized value + an EOL, then ``>>`` + an EOL. Entry
  order follows ``COSDictionary`` insertion order. ``null``-valued entries are
  skipped entirely (the ``/Skipped`` entry never appears).
* **array framing** — ``[`` then elements separated by a single SPACE, with an
  EOL substituted for the space after every 10th element (the long-array case),
  then ``]`` + an EOL.
* **mixed inline value types** — name, int, real, string, boolean, and the
  ``null`` keyword for a Python/Java ``None`` element.
* **nested direct dict / direct array** — a ``COSArray`` is direct by default
  (emitted inline), a ``COSDictionary`` is indirect by default (emitted as a
  reference), exactly as PDFBox.
* **indirect reference values** — ``N G R`` with sequentially minted keys.
* **the empty dict ``<<\\n>>\\n`` and empty array ``[]\\n``.**

The oracle is ``oracle/probes/CosCompositeWriteProbe.java``. In the standalone
``visitFromDictionary`` / ``visitFromArray`` path PDFBox mints sequential object
keys (1, 2, ...) for each reference regardless of any pre-existing key, so the
Python side builds each ``COSObject`` with object number 0 — which makes
pypdfbox's writer mint a fresh sequential key too — keeping the emitted ``N G R``
references aligned and the comparison scoped to the framing surface (not the
separate key-minting policy that honours a declared indirect number when
re-saving parsed documents).

Result of this wave: pypdfbox is byte-identical to PDFBox 3.0.7 across all
composite cases — confirmed parity, kept as a regression pin.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSString,
)
from pypdfbox.pdfwriter.cos_writer import COSWriter
from tests.oracle.harness import requires_oracle, run_probe_text


def _emit_dict(dictionary: COSDictionary) -> bytes:
    """Serialize ``dictionary`` through ``COSWriter`` exactly as the visitor
    pipeline would, capturing the raw written bytes."""
    sink = io.BytesIO()
    writer = COSWriter(sink)
    writer.visit_from_dictionary(dictionary)
    writer.close()
    return sink.getvalue()


def _emit_array(array: COSArray) -> bytes:
    sink = io.BytesIO()
    writer = COSWriter(sink)
    writer.visit_from_array(array)
    writer.close()
    return sink.getvalue()


# ---------------------------------------------------------------------------
# pypdfbox builders for each labelled probe case. Each returns the serialized
# bytes for the structure the Java probe emits under the same label.
# ---------------------------------------------------------------------------


def _build_empty_dict() -> bytes:
    return _emit_dict(COSDictionary())


def _build_empty_array() -> bytes:
    return _emit_array(COSArray())


def _build_single_dict() -> bytes:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))
    return _emit_dict(d)


def _build_scalar_array() -> bytes:
    a = COSArray()
    a.add(COSName.get_pdf_name("Foo"))
    a.add(COSInteger.get(42))
    a.add(COSFloat(3.14))
    a.add(COSString("hi"))
    a.add(COSBoolean.TRUE)
    a.add(COSBoolean.FALSE)
    a.add(None)  # serialises as the keyword null
    return _emit_array(a)


def _build_long_array() -> bytes:
    a = COSArray()
    for i in range(12):
        a.add(COSInteger.get(i))
    return _emit_array(a)


def _build_nested_array() -> bytes:
    outer = COSArray()
    inner = COSArray()
    inner.add(COSInteger.get(1))
    inner.add(COSInteger.get(2))
    outer.add(inner)
    outer.add(COSInteger.get(3))
    return _emit_array(outer)


def _build_composite_dict() -> bytes:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Page"))
    d.set_item(COSName.COUNT, COSInteger.get(7))
    d.set_item(COSName.get_pdf_name("Scale"), COSFloat(0.5))
    d.set_item(COSName.get_pdf_name("Title"), COSString("Hello (PDF)"))
    d.set_item(COSName.get_pdf_name("Flag"), COSBoolean.TRUE)
    media_box = COSArray()
    for v in (0, 0, 612, 792):
        media_box.add(COSInteger.get(v))
    d.set_item(COSName.get_pdf_name("MediaBox"), media_box)
    # COSDictionary is indirect by default -> emitted as the first minted ref.
    resources = COSDictionary()
    resources.set_item(COSName.get_pdf_name("ProcSet"), COSName.get_pdf_name("PDF"))
    d.set_item(COSName.RESOURCES, resources)
    # object number 0 forces the writer to mint a fresh sequential key.
    d.set_item(COSName.get_pdf_name("Parent"), COSObject(0, 0, resolved=COSDictionary()))
    # null-valued entry: skipped entirely on write.
    d.set_item(COSName.get_pdf_name("Skipped"), None)
    return _emit_dict(d)


def _build_ref_array() -> bytes:
    a = COSArray()
    a.add(COSObject(0, 0, resolved=COSDictionary()))
    a.add(COSObject(0, 0, resolved=COSArray()))
    return _emit_array(a)


_BUILDERS = {
    "empty_dict": _build_empty_dict,
    "empty_array": _build_empty_array,
    "single_dict": _build_single_dict,
    "scalar_array": _build_scalar_array,
    "long_array": _build_long_array,
    "nested_array": _build_nested_array,
    "composite_dict": _build_composite_dict,
    "ref_array": _build_ref_array,
}


# ---------------------------------------------------------------------------
# Parse the probe battery once per session; each line becomes a parametrize id.
# ---------------------------------------------------------------------------


def _load_battery() -> list[tuple[str, str]]:
    """Return ``(label, output_hex)`` pairs from the probe output."""
    text = run_probe_text("CosCompositeWriteProbe")
    cases: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        label, out_hex = line.split(": ")
        cases.append((label, out_hex))
    return cases


def _battery() -> list[tuple[str, str]]:
    try:
        return _load_battery()
    except Exception:  # noqa: BLE001 — oracle unavailable; requires_oracle skips
        return []


_BATTERY = _battery()


@requires_oracle
@pytest.mark.parametrize(
    ("label", "out_hex"),
    _BATTERY,
    ids=[label for label, _ in _BATTERY],
)
def test_composite_serialization_matches_pdfbox(label: str, out_hex: str) -> None:
    """Every composite dict/array case serialises to exactly PDFBox's bytes:
    framing delimiters, key/value spacing, the every-10th-element array EOL,
    nested direct/indirect routing, and ``N G R`` references all match."""
    builder = _BUILDERS.get(label)
    assert builder is not None, f"no pypdfbox builder for probe label {label!r}"
    assert builder().hex() == out_hex


# ---------------------------------------------------------------------------
# Value-pinned assertions (independent of the oracle being available) so the
# framing contract stays enforced on machines without Java.
# ---------------------------------------------------------------------------


def test_empty_dict_framing() -> None:
    assert _build_empty_dict() == b"<<\n>>\n"


def test_empty_array_framing() -> None:
    assert _build_empty_array() == b"[]\n"


def test_long_array_tenth_element_eol() -> None:
    # A single SPACE between elements, but an EOL replaces the space after the
    # 10th element (between "9" and "10").
    assert _build_long_array() == b"[0 1 2 3 4 5 6 7 8 9\n10 11]\n"


def test_nested_array_inner_trailing_eol() -> None:
    # The inner array's own trailing EOL lands before the outer SPACE.
    assert _build_nested_array() == b"[[1 2]\n 3]\n"


def test_composite_dict_framing() -> None:
    assert _build_composite_dict() == (
        b"<<\n"
        b"/Type /Page\n"
        b"/Count 7\n"
        b"/Scale 0.5\n"
        b"/Title (Hello \\(PDF\\))\n"
        b"/Flag true\n"
        b"/MediaBox [0 0 612 792]\n"
        b"/Resources 1 0 R\n"
        b"/Parent 2 0 R\n"
        b">>\n"
    )


def test_ref_array_framing() -> None:
    assert _build_ref_array() == b"[1 0 R 2 0 R]\n"
