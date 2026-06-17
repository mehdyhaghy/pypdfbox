"""Live PDFBox differential parity for COS *per-type self-serialization*.

Surface: the ``write_pdf(...)`` methods the COS objects implement themselves —
the five COS scalar types that own a ``writePDF`` in Apache PDFBox (COSFloat,
COSInteger, COSName, COSBoolean, COSNull). COSString / COSArray / COSDictionary
/ COSStream have NO ``writePDF`` upstream — they are serialized by COSWriter —
so their bytes are covered by the COSWriter oracle, not here; this module
deliberately checks only the self-write paths.

One Java probe (``CosWriteSelfProbe``) drives each type's ``writePDF`` through
the exact paths COSWriter uses and emits ``label: <hex-of-written-bytes>`` lines.
For every line we reconstruct the matching pypdfbox object and assert its OWN
``write_pdf`` produces identical bytes — i.e. we do NOT route through
``cos_writer`` (that path was verified in wave 1415); this confirms the
per-type self-write.

The float battery is the focus: wave 1415 fixed ``COSWriter.format_float`` but
flagged that ``COSFloat.format_string`` carried a SEPARATE formatter (``repr`` +
``Decimal.normalize``) that leaked float32 representation noise (``0.1`` →
``0.10000000149011612``). That formatter is now unified onto the shared
``pypdfbox.cos.cos_float.format_float32``; this oracle is the regression guard.

Wave 1487 closed the former subnormal divergence: ``Float.MIN_VALUE`` (1.4e-45)
now serializes byte-for-byte with Java. ``format_float32`` derives from
``float_to_string`` (the raw ``Float.toString`` port, whose scientific branch
carries Java's two-significant-digit subnormal floor — ``1.4E-45``, not the
globally-shortest ``1E-45``) and then strips the ``E`` form to plain decimal the
way ``COSFloat.formatString`` does. So every float bit pattern the probe emits is
now asserted against Java with no exclusions.
"""

from __future__ import annotations

import struct

from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from tests.oracle.harness import requires_oracle, run_probe_text


def _self_write(obj: object) -> bytes:
    import io

    buf = io.BytesIO()
    obj.write_pdf(buf)  # type: ignore[attr-defined]
    return buf.getvalue()


def _hex(data: bytes) -> str:
    return data.hex()


def _probe_lines() -> list[tuple[str, str, str]]:
    """Run the probe once; return (kind, arg, java_hex) per emitted line.

    ``kind`` is the first whitespace token (float/floats/int/name/bool/null);
    ``arg`` is whatever sits between ``kind`` and the ``": "`` separator (may be
    empty, e.g. for ``null``); ``java_hex`` is the hex after ``": "``.
    """
    text = run_probe_text("CosWriteSelfProbe")
    rows: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        if not raw:
            continue
        label, _, java_hex = raw.partition(": ")
        kind, _, arg = label.partition(" ")
        rows.append((kind, arg, java_hex.strip()))
    return rows


@requires_oracle
def test_cos_scalar_self_write_matches_pdfbox():
    rows = _probe_lines()
    # Sanity: the probe must actually emit every type so a silent empty run
    # can't pass vacuously.
    kinds = {k for k, _, _ in rows}
    assert kinds == {"float", "floats", "int", "name", "bool", "null"}

    mismatches: list[str] = []
    asserted = 0
    for kind, arg, java_hex in rows:
        if kind == "float":
            bits = int(arg)
            value = struct.unpack(">f", struct.pack(">i", bits))[0]
            py = _self_write(COSFloat(value))
        elif kind == "floats":
            py = _self_write(COSFloat(arg))
        elif kind == "int":
            py = _self_write(COSInteger.get(int(arg)))
        elif kind == "name":
            name_bytes = bytes.fromhex(arg) if arg else b""
            py = _self_write(COSName.get_pdf_name(name_bytes))
        elif kind == "bool":
            py = _self_write(COSBoolean.get(arg == "true"))
        elif kind == "null":
            py = _self_write(COSNull.NULL)
        else:  # pragma: no cover - guarded by the kinds assertion above
            raise AssertionError(f"unexpected probe kind: {kind!r}")
        asserted += 1
        if _hex(py) != java_hex:
            mismatches.append(f"{kind} {arg!r}: java={java_hex} py={_hex(py)}")

    assert not mismatches, "per-type self-write diverges from PDFBox:\n" + "\n".join(
        mismatches
    )
    # Guard against a future probe edit that drops every case.
    assert asserted >= 50


@requires_oracle
def test_documented_subnormal_divergence_round_trips():
    """The documented MIN_VALUE divergence is a *non-significant* digit
    difference: pypdfbox's self-write still parses back to the identical
    float32, so it is a valid PDF number, just not byte-identical to Java's
    legacy FloatingDecimal output."""
    value = struct.unpack(">f", struct.pack(">i", 1))[0]  # Float.MIN_VALUE
    py = _self_write(COSFloat(value)).decode("ascii")
    # pypdfbox emits the truly-shortest form...
    assert py != "0.0"
    # ...and it round-trips to the same single-precision value.
    reparsed = struct.unpack(">f", struct.pack(">f", float(py)))[0]
    assert struct.pack(">f", reparsed) == struct.pack(">f", value)
    # The COSWriter path produces the same bytes (single shared formatter).
    from pypdfbox.pdfwriter.cos_writer import COSWriter

    assert COSWriter.format_float(value).decode("ascii") == py
