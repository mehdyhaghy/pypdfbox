"""Live PDFBox differential parity for tricky-but-valid COS scalar parsing.

Tokenizes raw content-stream byte snippets through both Apache PDFBox 3.0.7
(via the ``ParseEdgeTokenProbe`` Java oracle) and pypdfbox's
:class:`PDFStreamParser`, comparing the canonical fingerprint of every parsed
token. This exercises the shared ``BaseParser`` scalar-parse code that real
PDFs lean on:

  - numbers: double-negative ``--2``, leading dot ``.5``, trailing dot ``4.``,
    leading ``+3``, leading zeros ``007``, exponent-lookalikes ``1.0e3`` /
    ``1.5E2`` (the content-stream tokenizer stops the number at ``e``/``E`` and
    treats the rest as an operator), mid-string ``-`` recovery (``0.-262``),
    out-of-range integers (clamped to Long range), and ``-0`` / ``+.5`` / ``12.``;
  - literal strings: octal escapes (``\\101``), control escapes (``\\n`` / ``\\t``),
    escaped + bare parens, nested balanced parens, backslash-newline line
    continuation, and unknown escapes (backslash dropped);
  - hex strings: even and odd (implicit ``0`` pad) digit runs;
  - names: ``#``-hex escapes (``#42`` → ``B``, ``#20`` → space, ``#2F`` → ``/``);
  - dictionaries with duplicate keys (last value wins).

The token fingerprint grammar is identical on both sides (see
``ParseEdgeTokenProbe.java``). Floats are compared as their IEEE-754 float32
bit pattern (repr-independent); string bytes are compared as raw hex.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _float32_bits_hex(value: float) -> str:
    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"{bits:x}"


def _tag(token: object) -> str:
    """Canonical fingerprint mirroring ``ParseEdgeTokenProbe.tag`` exactly."""
    # Operator instances are the only non-COSBase tokens the parser yields.
    if type(token).__name__ == "Operator":
        return f"op({token.get_name()})"  # type: ignore[attr-defined]
    base = token  # a COSBase (or None) at this point
    if base is None or isinstance(base, COSNull):
        return "null"
    if isinstance(base, COSBoolean):
        return f"bool({'true' if base.get_value() else 'false'})"
    if isinstance(base, COSInteger):
        return f"int({base.long_value()})"
    if isinstance(base, COSFloat):
        return f"real({_float32_bits_hex(base.float_value())})"
    if isinstance(base, COSName):
        return f"name(/{base.get_name()})"
    if isinstance(base, COSString):
        return f"str({base.get_bytes().hex()})"
    if isinstance(base, COSArray):
        return "array[" + ",".join(_tag(base.get(i)) for i in range(base.size())) + "]"
    if isinstance(base, COSDictionary):
        keys = sorted(base.key_set(), key=lambda n: n.get_name())
        body = ",".join(f"/{k.get_name()}->{_tag(base.get_item(k))}" for k in keys)
        return "dict{" + body + "}"
    return f"unknown({type(base).__name__})"


def _pypdfbox_dump(data: bytes) -> str:
    """Tokenize ``data`` via :class:`PDFStreamParser`; emit the same canonical
    per-token fingerprint the Java probe does."""
    parser = PDFStreamParser.from_bytes(data)
    lines = [_tag(tok) for tok in parser.tokens()]
    return "".join(line + "\n" for line in lines)


# (name, raw operand/operator bytes). ``name`` doubles as the parametrize id.
_CASES: dict[str, bytes] = {
    "numbers_signs_dots": rb"--2 .5 4. +3 007 -.5 12.",
    "numbers_exponent_lookalike": rb"1.0e3 1.5E2 .e3",
    "numbers_mid_dash_recovery": rb"0.-262 --16.33",
    "numbers_range_and_zero": rb"100000000000000000000 -0 +.5 .0001",
    "string_octal_and_controls": b"(oct\\101) (a\\012b) (tab\\011x)",
    "string_parens_nested": b"(nested(p)q) (par(())) (\\0501\\051)",
    "string_escapes": b"(\\\\) (esc\\q) (line\\\ncont)",
    "hex_strings_even_odd": b"<48656C6C6F> <48656C6C6>",
    "names_hex_escapes": rb"/A#42C /Name#20Sp /#41#42 /A#2FB",
    "dict_duplicate_keys": rb"<< /A 1 /B 2 /A 3 >>",
}


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_scalar_parse_matches_pdfbox(name: str, tmp_path: Path) -> None:
    data = _CASES[name]
    snippet = tmp_path / f"{name}.bin"
    snippet.write_bytes(data)
    java = run_probe_text("ParseEdgeTokenProbe", str(snippet))
    py = _pypdfbox_dump(data)
    assert py == java
