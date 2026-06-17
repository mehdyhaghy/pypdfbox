"""Live PDFBox differential parity pinning the **appended tail of an
incremental save byte-for-byte** against Apache PDFBox 3.0.7
(``pypdfbox.pdmodel.PDDocument.save_incremental`` /
``pypdfbox.pdfwriter.cos_writer``).

The existing incremental-save oracles pin *structural* invariants — the
append-only prefix (``test_save_round_trip_oracle``), the ``/Prev`` chain and
the exact dirty-object set (``test_incremental_xref_delta_oracle``), the
appended xref-stream ``/W`` / ``/Index`` geometry
(``test_incremental_xref_stream_shape_oracle``). None of them asserts that the
*entire appended region* — new object bodies, the new xref section (table or
stream), the trailer dictionary, ``startxref``, and ``%%EOF`` — is **byte
identical** to what PDFBox writes for the same mutation.

This is the strongest possible pin for the non-signing incremental path: the
only non-deterministic byte in the tail is the regenerated ``/ID[1]`` octet
string (ISO 32000-1 §14.4 requires the changing identifier to be replaced),
and ``/ID[0]`` is preserved verbatim. We mask both ``/ID`` octet strings on
each side (same byte length on both engines) and assert the remaining bytes
are identical.

The mutation is identical on both engines: set ``/Info /Title`` to
``DeltaTitle``, flag the /Info dict dirty, ``save_incremental``. The Java
oracle ``IncrementalTailBytesProbe`` performs it through PDFBox and emits the
appended tail as hex; this module reproduces it through pypdfbox.

Fixtures deliberately cover both cross-reference encodings of the *source*
document — a classic ``xref`` table original (``SimpleForm2Fields.pdf``,
``page_labels_styles.pdf``) and an xref-*stream* original
(``unencrypted.pdf``, ``acroform.pdf``, ``attachment.pdf``,
``DemoType1Embedded.pdf``) — because the writer picks the appended xref
encoding from the source's kind (upstream ``COSWriter.doWriteXRefInc``), and
the xref-stream arm's dictionary key-insertion order is the byte-geometry the
wave-1503 fix converged.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

# (label, path, source-xref-kind) — both kinds exercised.
_FIXTURES_LIST = [
    ("table_simpleform", _FIXTURES / "pdfbox" / "pdfparser" / "SimpleForm2Fields.pdf"),
    ("table_pagelabels", _FIXTURES / "pdmodel" / "page_labels_styles.pdf"),
    ("stream_unencrypted", _FIXTURES / "pdfwriter" / "unencrypted.pdf"),
    ("stream_acroform", _FIXTURES / "pdfwriter" / "acroform.pdf"),
    ("stream_attachment", _FIXTURES / "pdfwriter" / "attachment.pdf"),
    ("stream_type1", _FIXTURES / "fontbox" / "type1" / "DemoType1Embedded.pdf"),
]

_ID_PATTERN = re.compile(rb"/ID\s*\[[^\]]*\]")
_HEX_STRING = re.compile(rb"<[0-9A-Fa-f]*>")


def _mask_id(tail: bytes) -> bytes:
    """Replace the hex contents of both ``/ID`` octet strings with ``X`` of
    the same length so the deterministic-elsewhere tail can be compared. The
    bracket positions and overall length are preserved (both engines emit
    16-byte ``/ID[0]`` and a 32-byte SHA-256 ``/ID[1]``)."""

    def _mask_array(m: re.Match[bytes]) -> bytes:
        return _HEX_STRING.sub(
            lambda mm: b"<" + b"X" * (len(mm.group(0)) - 2) + b">", m.group(0)
        )

    return _ID_PATTERN.sub(_mask_array, tail)


def _py_tail(src: bytes) -> bytes:
    doc = PDDocument.load(src)
    try:
        info = doc.get_document_information()
        info.set_title("DeltaTitle")
        info.get_cos_object().set_needs_to_be_updated(True)
        buf = io.BytesIO()
        doc.save_incremental(buf)
    finally:
        doc.close()
    out = buf.getvalue()
    return out[len(src) :]


def _java_tail(src_path: Path, tmp_path: Path) -> tuple[int, bytes]:
    out_path = tmp_path / "java_inc.pdf"
    text = run_probe_text(
        "IncrementalTailBytesProbe", str(src_path), str(out_path)
    )
    facts: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            facts[key] = value
    return int(facts["source_len"]), bytes.fromhex(facts["tail_hex"])


@requires_oracle
@pytest.mark.parametrize(
    "label,src_path",
    _FIXTURES_LIST,
    ids=[label for label, _ in _FIXTURES_LIST],
)
def test_incremental_appended_tail_byte_identical(
    label: str, src_path: Path, tmp_path: Path
) -> None:
    if not src_path.exists():  # pragma: no cover - fixture availability guard
        pytest.skip(f"fixture missing: {src_path}")
    src = src_path.read_bytes()

    java_src_len, java_tail = _java_tail(src_path, tmp_path)
    assert java_src_len == len(src)

    py_tail = _py_tail(src)

    # Same appended length on both engines (modulo nothing — /ID lengths match).
    assert len(py_tail) == len(java_tail), (
        f"{label}: tail length differs py={len(py_tail)} java={len(java_tail)}"
    )

    masked_py = _mask_id(py_tail)
    masked_java = _mask_id(java_tail)
    assert masked_py == masked_java, (
        f"{label}: appended tail diverges after /ID masking"
    )


@requires_oracle
def test_id_zero_preserved_id_one_regenerated(tmp_path: Path) -> None:
    """The only non-deterministic tail bytes are ``/ID[1]``: ``/ID[0]`` is
    preserved verbatim across engines, ``/ID[1]`` differs (fresh digest)."""
    src_path = _FIXTURES / "pdfwriter" / "unencrypted.pdf"
    src = src_path.read_bytes()

    _, java_tail = _java_tail(src_path, tmp_path)
    py_tail = _py_tail(src)

    def _ids(tail: bytes) -> list[bytes]:
        m = _ID_PATTERN.search(tail)
        assert m is not None
        return _HEX_STRING.findall(m.group(0))

    java_ids = _ids(java_tail)
    py_ids = _ids(py_tail)
    assert len(java_ids) == len(py_ids) == 2
    # /ID[0] identical across engines (permanent identifier, byte-stable).
    assert java_ids[0] == py_ids[0]
    # /ID[1] is a fresh digest — same length, content differs from /ID[0].
    assert len(py_ids[1]) == len(java_ids[1])
    assert py_ids[1] != py_ids[0]
