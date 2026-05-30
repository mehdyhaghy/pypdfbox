"""Live PDFBox differential parity for inline-image PARAMETER-DICT parsing.

Targets the ``BI`` ... ``ID`` parameter-dictionary collection in
:class:`~pypdfbox.pdfparser.pdf_stream_parser.PDFStreamParser` — the facet of
inline-image (BI/ID/EI) parsing where the ``/Key value`` pairs between ``BI``
and ``ID`` are gathered into the operator's image-parameters dictionary using
the verbatim (abbreviated) key names from PDF 32000-1 §8.9.7 Table 91
(``/W /H /CS /BPC /F /IM /D /DP /I``), the abbreviated colour-space and filter
names being preserved (not expanded), and the raw ``ID`` ... ``EI`` payload
length captured on the same operator.

In PDFBox 3.0.x the parser absorbs the ``ID`` ... ``EI`` segment into the
``BI`` operator: there is no separate ``ID`` token in ``parse()``, and the
``BI`` operator carries BOTH ``get_image_parameters()`` and the raw
``get_image_data()``. This complements:

* ``test_inline_ei_scan_oracle`` — the binary EI-terminator scan (byte length /
  SHA of the payload).
* ``test_inline_cs_resolve_oracle`` — resolving ``/CS`` into a ``PDColorSpace``.

Here we assert the *parsed dictionary itself* — key set, key ORDER (insertion),
value types and values — matches Apache PDFBox's ``Operator.getImageParameters()``
exactly, via the ``InlineImageDictProbe`` Java oracle.

Canonical block grammar (must match ``oracle/probes/InlineImageDictProbe.java``)::

    BI keys=[K1=V1 K2=V2 ...] data=<rawImageDataLength>
    OPS:<n>

Value rendering: names ``/Name``; ints verbatim; reals ``COSFloat{<formatString>}``
(PDFBox preserves the source spelling); booleans ``true``/``false``; strings
``(<lower-hex-of-bytes>)``; arrays ``[..]``; dicts ``<<..>>``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _case_basic() -> bytes:
    return (
        b"q BI /W 4 /H 4 /BPC 8 /CS /RGB ID "
        + bytes([0, 1, 2, 3, 4, 5, 6, 7])
        + b"EI Q\n"
    )


def _case_stencil_mask() -> bytes:
    # /IM stencil mask, no /BPC, /D decode array of ints.
    return b"BI /IM true /W 8 /H 8 /D [1 0] ID " + bytes([0xFF, 0x00, 0xFF, 0x00]) + b"EI Q\n"


def _case_filter_array_ahx() -> bytes:
    # Abbreviated filter in an array; AHx payload terminated by '>'.
    return b"BI /W 2 /H 2 /CS /G /BPC 8 /F [/AHx] ID 00ff00ff>EI Q\n"


def _case_filter_scalar_fl() -> bytes:
    # Abbreviated scalar filter /Fl, with EI bytes embedded in the payload.
    return (
        b"BI /W 4 /H 4 /BPC 8 /CS /G /F /Fl ID "
        + bytes([0x45, 0x49, 0xFF, 0x01, 0x45, 0x49, 0x90])
        + b"EI Q\n"
    )


def _case_indexed_abbrev() -> bytes:
    # Abbreviated indexed colour space [/I base hival lookup], lookup as hex str.
    return (
        b"BI /W 4 /H 4 /BPC 8 /CS [/I /RGB 3 <000000ffffff80808000ff00>] ID "
        + bytes([0, 1, 2, 3])
        + b"EI Q\n"
    )


def _case_reals_and_extras() -> bytes:
    # Real-valued /Decode plus non-standard string / real keys exercising the
    # value-type renderers (COSFloat formatString preservation, COSString).
    return (
        b"BI /W 4 /H 4 /BPC 8 /CS /G /D [0.0 1.0 0.5] /Foo (hi) /Bar 3.14 ID "
        + bytes([1, 2, 3])
        + b"EI Q\n"
    )


def _case_long_form_keys() -> bytes:
    # Long-form keys are also legal and must be preserved verbatim (not
    # collapsed to the abbreviations).
    return (
        b"BI /Width 2 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8 "
        b"/Interpolate true ID " + bytes([9, 8, 7, 6]) + b"EI Q\n"
    )


def _case_decode_parms() -> bytes:
    # /DP DecodeParms dict alongside an abbreviated /F /CCF filter.
    return (
        b"BI /W 8 /H 8 /BPC 1 /IM true /F /CCF /DP <</K -1 /Columns 8 /Rows 8>> ID "
        + bytes([0x00, 0x10, 0x20, 0x30])
        + b"EI Q\n"
    )


def _case_no_params() -> bytes:
    # Degenerate: BI with an empty dict (straight to ID).
    return b"BI ID " + bytes([0xAA, 0xBB]) + b"EI Q\n"


_CASES = {
    "basic": _case_basic(),
    "stencil_mask": _case_stencil_mask(),
    "filter_array_ahx": _case_filter_array_ahx(),
    "filter_scalar_fl": _case_filter_scalar_fl(),
    "indexed_abbrev": _case_indexed_abbrev(),
    "reals_and_extras": _case_reals_and_extras(),
    "long_form_keys": _case_long_form_keys(),
    "decode_parms": _case_decode_parms(),
    "no_params": _case_no_params(),
}


def _describe(value: COSBase | None) -> str:
    if value is None:
        return "null"
    if isinstance(value, COSName):
        return "/" + value.get_name()
    if isinstance(value, COSInteger):
        return str(value.long_value())
    if isinstance(value, COSFloat):
        return "COSFloat{" + value.format_string() + "}"
    if isinstance(value, COSBoolean):
        return "true" if value.get_value() else "false"
    if isinstance(value, COSNull):
        return "null"
    if isinstance(value, COSString):
        return "(" + value.get_bytes().hex() + ")"
    if isinstance(value, COSArray):
        return "[" + " ".join(_describe(item) for item in value) + "]"
    if isinstance(value, COSDictionary):
        parts = [
            "/" + key.get_name() + "=" + _describe(value.get_item(key))
            for key in value.key_set()
        ]
        return "<<" + " ".join(parts) + ">>"
    return type(value).__name__


def _describe_dict(dictionary: COSDictionary) -> str:
    parts = [
        key.get_name() + "=" + _describe(dictionary.get_item(key))
        for key in dictionary.key_set()
    ]
    return "[" + " ".join(parts) + "]"


def _pypdfbox_blocks(data: bytes) -> str:
    tokens = PDFStreamParser.from_bytes(data).parse()
    out: list[str] = []
    for tok in tokens:
        if isinstance(tok, Operator) and tok.get_name() == "BI":
            params = tok.get_image_parameters()
            keys = "null" if params is None else _describe_dict(params)
            raw = tok.get_image_data()
            length = -1 if raw is None else len(raw)
            out.append(f"BI keys={keys} data={length}")
    out.append(f"OPS:{len(tokens)}")
    return "".join(line + "\n" for line in out)


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_inline_image_dict_matches_pdfbox(name: str) -> None:
    data = _CASES[name]
    with tempfile.NamedTemporaryFile(suffix=".cs", delete=False) as handle:
        handle.write(data)
        tmp_path = handle.name
    try:
        java = run_probe_text("InlineImageDictProbe", tmp_path)
        py = _pypdfbox_blocks(data)
        assert py == java
    finally:
        Path(tmp_path).unlink()
