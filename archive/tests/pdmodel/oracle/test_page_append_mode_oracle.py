"""Live PDFBox differential parity for the ``PDPageContentStream`` append-mode
constructor — appending / prepending / overwriting onto a page that already
carries content.

The sibling ``test_content_raw_bytes_oracle`` pins the *operator bytes* a fresh
OVERWRITE stream emits. This file pins the *structural* behaviour of the
``PDPageContentStream(doc, page, AppendMode, compress, resetContext)``
constructor: how it threads a second content stream into a page's existing
``/Contents``.

The Java probe (``oracle/probes/PageAppendModeProbe.java``) builds a page with
one content stream (a stroked red rect, ``1 0 0 RG``), then constructs a second
``PDPageContentStream`` in the named mode drawing a filled blue rect
(``0 0 1 rg``), and emits a canonical JSON description of the resulting
``/Contents`` entry:

  * ``contents_is_array`` — whether ``/Contents`` became a ``COSArray``;
  * ``array_length`` — number of streams in that array;
  * ``first_tokens`` — first token of each stream body in order (the
    ``resetContext`` q-guard prefix shows up as ``q``; the appended stream's
    leading ``Q`` restore shows up as ``Q``);
  * ``reset_guard`` — a leading ``q\n``-only prefix stream is present AND the
    appended stream begins with ``Q`` (the save/restore guard around the
    pre-existing content);
  * ``concat_has_original`` / ``concat_has_appended`` — both the original
    (``1 0 0 RG``) and the new (``0 0 1 rg``) content survive.

pypdfbox reproduces the identical construction and emits the same JSON shape;
the two dicts must be equal.

Selectors:
  * ``append`` — ``[original, new]``.
  * ``prepend`` — ``[new, original]``.
  * ``overwrite`` — ``/Contents`` replaced by the single new stream.
  * ``append_reset`` — ``resetContext=True`` wraps with a ``q\n`` prefix stream
    and the appended stream begins with ``Q`` → ``[q-prefix, original, new]``.
  * ``append_empty`` — the page starts with a present-but-empty content stream;
    ``hasContents()`` treats it as content (the stream dict is non-empty), so
    APPEND still promotes to a 2-element array.
"""

from __future__ import annotations

import json

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text

_CONTENTS = COSName.get_pdf_name("Contents")


def _first_token(body: bytes) -> str:
    text = body.decode("ascii", errors="replace").lstrip()
    out: list[str] = []
    for ch in text:
        if ch.isspace():
            break
        out.append(ch)
    return "".join(out)


def _describe(page: PDPage) -> dict:
    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    is_array = isinstance(contents, COSArray)
    bodies: list[bytes] = []
    if is_array:
        for entry in contents:
            resolved = entry.get_object() if hasattr(entry, "get_object") else entry
            bodies.append(bytes(resolved.get_raw_data()))
    elif isinstance(contents, COSStream):
        bodies.append(bytes(contents.get_raw_data()))

    concat = b"".join(bodies)
    first_tokens = [_first_token(b) for b in bodies]
    guard_prefix = bool(bodies) and bodies[0] == b"q\n"
    appended_has_restore = bool(bodies) and _first_token(bodies[-1]) == "Q"
    reset_guard = guard_prefix and appended_has_restore

    return {
        "contents_is_array": is_array,
        "array_length": len(bodies) if is_array else 0,
        "first_tokens": first_tokens,
        "reset_guard": reset_guard,
        "concat_has_original": b"1 0 0 RG" in concat,
        "concat_has_appended": b"0 0 1 rg" in concat,
    }


def _build(selector: str) -> dict:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0))
        doc.add_page(page)

        if selector == "append_empty":
            with PDPageContentStream(
                doc, page, AppendMode.OVERWRITE, False, False
            ):
                pass  # no operators — present-but-empty content stream
        else:
            with PDPageContentStream(
                doc, page, AppendMode.OVERWRITE, False, False
            ) as cs:
                cs.set_stroking_color(1.0, 0.0, 0.0)  # "1 0 0 RG"
                cs.add_rect(10, 10, 50, 50)
                cs.stroke()

        if selector in ("append", "append_empty"):
            mode, reset = AppendMode.APPEND, False
        elif selector == "append_reset":
            mode, reset = AppendMode.APPEND, True
        elif selector == "prepend":
            mode, reset = AppendMode.PREPEND, False
        elif selector == "overwrite":
            mode, reset = AppendMode.OVERWRITE, False
        else:
            raise ValueError(f"unknown selector: {selector}")

        with PDPageContentStream(
            doc, page, mode, False, reset
        ) as cs:
            cs.set_non_stroking_color(0.0, 0.0, 1.0)  # "0 0 1 rg"
            cs.add_rect(100, 100, 40, 40)
            cs.fill()

        return _describe(page)
    finally:
        doc.close()


_SELECTORS = ["append", "prepend", "overwrite", "append_reset", "append_empty"]


@requires_oracle
@pytest.mark.parametrize("selector", _SELECTORS)
def test_page_append_mode_matches_pdfbox(selector: str) -> None:
    java = json.loads(run_probe_text("PageAppendModeProbe", selector))
    py = _build(selector)
    assert py == java, (
        f"append-mode /Contents shape diverges from PDFBox for '{selector}'.\n"
        f"--- pypdfbox ---\n{json.dumps(py, sort_keys=True)}\n"
        f"--- java ---\n{json.dumps(java, sort_keys=True)}"
    )
