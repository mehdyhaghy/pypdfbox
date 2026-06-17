"""Live PDFBox differential parity for ``COSName.write_pdf`` write-escaping.

Surface: how a ``COSName`` is *serialized* (PDF 32000-1 §7.3.5) — the encode
direction. A name is written as ``/`` followed by its bytes, with any byte
outside the PDFBox printable allowlist replaced by ``#XX`` (two UPPERCASE hex
digits). The pass-through allowlist is ``A-Z a-z 0-9`` plus ``+ - _ @ * $ ; .``;
everything else (whitespace, the delimiters ``()<>[]{}/%``, the ``#`` escape
introducer itself, control chars 0x00-0x1F/0x7F, and every byte >= 0x80) is
hex-escaped.

Wave 1457 covered the ``#XX`` DECODE (parse) direction; this is the matching
WRITE/encode direction. The ``NameWriteEscapeProbe`` drives PDFBox's
``COSName.writePDF`` over every ASCII byte 0x00-0x7F (one codepoint each, so the
whole ASCII escape table is exercised byte-by-byte) plus a battery of multi-byte
UTF-8 codepoints and realistic composite names, emitting ``name <utf8-hex>:
<written-hex>`` per line. For each line we rebuild the matching pypdfbox COSName
from the raw name bytes and assert its own ``write_pdf`` is byte-identical.
"""

from __future__ import annotations

import io

from pypdfbox.cos.cos_name import COSName
from tests.oracle.harness import requires_oracle, run_probe_text


def _self_write(name_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    COSName.get_pdf_name(name_bytes).write_pdf(buf)
    return buf.getvalue()


def _probe_rows() -> list[tuple[bytes, str]]:
    """Run the probe once; return (name_bytes, java_written_hex) per line."""
    text = run_probe_text("NameWriteEscapeProbe")
    rows: list[tuple[bytes, str]] = []
    for raw in text.splitlines():
        if not raw:
            continue
        label, _, java_hex = raw.partition(": ")
        _kind, _, arg = label.partition(" ")
        name_bytes = bytes.fromhex(arg) if arg else b""
        rows.append((name_bytes, java_hex.strip()))
    return rows


@requires_oracle
def test_name_write_escaping_matches_pdfbox():
    rows = _probe_rows()
    # The probe iterates 0x00..0x7F (128 single-byte names) plus the extras;
    # guard against a silent empty/truncated run.
    assert len(rows) >= 128 + 20

    # Sanity: the full ASCII byte range 0x00..0x7F must be present exactly once.
    single_ascii = {nb[0] for nb, _ in rows if len(nb) == 1 and nb[0] <= 0x7F}
    assert single_ascii == set(range(0x80))

    mismatches: list[str] = []
    for name_bytes, java_hex in rows:
        py_hex = _self_write(name_bytes).hex()
        if py_hex != java_hex:
            mismatches.append(
                f"name={name_bytes.hex() or '<empty>'}: java={java_hex} py={py_hex}"
            )

    assert not mismatches, (
        "COSName write-escaping diverges from PDFBox:\n" + "\n".join(mismatches)
    )


@requires_oracle
def test_plain_name_round_trips_unescaped():
    """A name using only allowlisted bytes is written verbatim after ``/``."""
    rows = dict(_probe_rows())
    # "Type" -> /Type (no escapes); the all-pass-through composite stays raw.
    type_written = _self_write(b"Type")
    assert type_written == b"/Type"
    assert rows[b"Type"] == type_written.hex()

    composite = b"Plus+Minus-Under_At@Star*Dollar$Semi;Dot."
    assert _self_write(composite) == b"/" + composite


@requires_oracle
def test_delimiters_and_hash_are_escaped():
    """The escape-introducer ``#`` and the PDF delimiters are hex-escaped."""
    assert _self_write(b"A#B") == b"/A#23B"
    assert _self_write(b"A B") == b"/A#20B"
    assert _self_write(b"Name(1)") == b"/Name#281#29"
    assert _self_write(b"Slash/Sub") == b"/Slash#2FSub"
    assert _self_write(b"Pct%X") == b"/Pct#25X"
