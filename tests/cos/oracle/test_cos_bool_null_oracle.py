"""Live PDFBox differential parity for COSBoolean and COSNull.

Drives Apache PDFBox 3.0.7's :class:`COSBoolean` / :class:`COSNull` leaf
classes directly (via the ``CosBoolNullProbe`` Java oracle) and asserts
pypdfbox matches on the full leaf surface:

  - ``COSBoolean.getBoolean(true/false)`` returns the ``TRUE`` / ``FALSE``
    singletons (reference identity — re-fetching always yields the same
    instance, and ``TRUE`` is never ``FALSE``);
  - ``getValue()`` / ``getValueAsObject()``;
  - ``writePDF`` emits the literal ``true`` / ``false`` / ``null`` bytes;
  - ``hashCode()`` (1231 / 1237 — the ``java.lang.Boolean`` recipe) and
    ``toString()`` (lowercase ``true`` / ``false``, ``COSNull{}``);
  - ``COSNull.NULL`` singleton + ``writePDF`` + ``toString``;
  - the content-stream tokenizer reading the literal ``true`` / ``false`` /
    ``null`` tokens back to the very same singletons.

The probe takes no args and emits a single JSON object; the Python side
reconstructs the identical record from the pypdfbox singletons and the
:class:`PDFStreamParser`, then asserts equality.
"""

from __future__ import annotations

import json

from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _write_pdf(obj: object) -> str:
    import io

    buf = io.BytesIO()
    obj.write_pdf(buf)  # type: ignore[attr-defined]
    return buf.getvalue().decode("latin-1")


def _parse_scalar(snippet: bytes) -> object:
    return PDFStreamParser.from_bytes(snippet).parse_next_token()


def _pypdfbox_record() -> dict[str, object]:
    t = COSBoolean.get_boolean(True)
    t2 = COSBoolean.get_boolean(True)
    f = COSBoolean.get_boolean(False)
    f2 = COSBoolean.get_boolean(False)
    return {
        "true_value": t.get_value(),
        "true_value_obj": t.get_value_as_object(),
        "false_value": f.get_value(),
        "false_value_obj": f.get_value_as_object(),
        "getbool_true_is_singleton": t is COSBoolean.TRUE and t2 is COSBoolean.TRUE,
        "getbool_false_is_singleton": f is COSBoolean.FALSE and f2 is COSBoolean.FALSE,
        "true_ne_false": t is not f,
        "true_write": _write_pdf(t),
        "false_write": _write_pdf(f),
        "null_write": _write_pdf(COSNull.NULL),
        "true_hash": t.hash_code(),
        "false_hash": f.hash_code(),
        "true_str": t.to_string(),
        "false_str": f.to_string(),
        "null_str": COSNull.NULL.to_string(),
        "parsed_true_is_singleton": _parse_scalar(b"true ") is COSBoolean.TRUE,
        "parsed_false_is_singleton": _parse_scalar(b"false ") is COSBoolean.FALSE,
        "parsed_null_is_singleton": _parse_scalar(b"null ") is COSNull.NULL,
    }


@requires_oracle
def test_cos_bool_null_matches_pdfbox() -> None:
    java = json.loads(run_probe_text("CosBoolNullProbe").strip())
    py = _pypdfbox_record()
    assert py == java
