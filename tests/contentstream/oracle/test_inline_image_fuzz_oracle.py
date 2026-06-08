"""Live PDFBox differential parity for malformed/edge-case inline images.

Wave 1517 fuzz surface: the ``BI ... ID <bytes> EI`` operator sequence in a
content stream, driven through ``PDFStreamParser`` directly. This combines BOTH
facets the existing oracle tests split apart — the parsed parameter dictionary
(verbatim abbreviated keys ``/W /H /BPC /CS /F /DP /IM /D /I``) and the EI
binary-scan raw-data length/digest — so a divergence in either shows up here.

Cases target malformed/edge inputs not covered by ``test_inline_ei_scan_oracle``
or ``test_inline_image_dict_oracle``: ``ID`` with no / multiple trailing
whitespace, missing ``EI`` entirely (truncation), filter abbreviations
(AHx/A85/LZW/Fl/RL/CCF/DCT), abbreviated key forms, a non-``/Name`` token where
a key is expected, an empty parameter dict, nested ``BI`` (PDFBOX-6038), and
post-EI operator-stream resynchronisation.

Canonical block grammar (must match ``oracle/probes/InlineImageFuzzProbe.java``)::

    BI keys=[K1=V1 ...] dlen=<len> dsha=<sha1> dhead=<hex> dtail=<hex>
    OPS:<n>

or, on any throw out of ``parse()`` on either side, the single line ``THROW``
(exception class names differ across the port, so only throw-vs-not is
compared).
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdfparser.parse_error import PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# ---- case builders --------------------------------------------------------


def _c_id_no_ws_before_payload() -> bytes:
    # 'ID' immediately followed by a single space (the minimal legal form),
    # then a 1-byte payload then EI<sp>Q.
    return b"q BI /W 2 /H 2 /BPC 8 /CS /G ID \x41EI Q\n"


def _c_id_crlf_after() -> bytes:
    # 'ID' followed by CRLF: the linebreak is consumed, not part of payload.
    return b"BI /W 1 /H 1 ID\r\n\x00\x01\x02EI Q\n"


def _c_id_cr_only() -> bytes:
    return b"BI /W 1 /H 1 ID\r\x10\x11EI Q\n"


def _c_id_lf_only() -> bytes:
    return b"BI /W 1 /H 1 ID\n\x10\x11EI Q\n"


def _c_id_two_spaces() -> bytes:
    # Two spaces after ID: only one whitespace is consumed; the second is
    # part of the payload.
    return b"BI /W 1 /H 1 ID  \x10\x11EI Q\n"


def _c_missing_ei_truncated() -> bytes:
    # No EI at all — payload runs to EOF.
    return b"BI /W 4 /H 4 /BPC 8 ID \x00\x01\x02\x03\x04\x05\x06\x07"


def _c_empty_payload() -> bytes:
    # EI immediately after ID<sp> with zero payload bytes.
    return b"BI /W 1 /H 1 ID EI Q\n"


def _c_empty_params() -> bytes:
    # BI with no key/value pairs at all, then ID payload EI.
    return b"BI ID \x10\x20\x30EI Q\n"


def _c_filter_ahx() -> bytes:
    return b"BI /W 2 /H 2 /F /AHx ID 00FF>EI Q\n"


def _c_filter_a85() -> bytes:
    return b"BI /W 2 /H 2 /F /A85 ID z~>EI Q\n"


def _c_filter_fl() -> bytes:
    return b"BI /W 2 /H 2 /F /Fl ID \x78\x9c\x03\x00\x00\x00\x00\x01EI Q\n"


def _c_filter_lzw() -> bytes:
    return b"BI /W 2 /H 2 /F /LZW ID \x80\x0b\x60EI Q\n"


def _c_filter_rl() -> bytes:
    return b"BI /W 2 /H 2 /F /RL ID \x00\x41\x80EI Q\n"


def _c_filter_ccf_with_dp() -> bytes:
    return b"BI /W 8 /H 8 /BPC 1 /F /CCF /DP <</K -1>> ID \x00\x00\x00EI Q\n"


def _c_filter_dct() -> bytes:
    return b"BI /W 2 /H 2 /F /DCT ID \xff\xd8\xff\xd9EI Q\n"


def _c_filter_array() -> bytes:
    # /F as an array of abbreviated filter names.
    return b"BI /W 2 /H 2 /F [/AHx] ID 00FF>EI Q\n"


def _c_abbrev_keys_all() -> bytes:
    # Every abbreviated key: /W /H /BPC /CS /D /DP /F /IM /I (some bogus
    # values just to exercise verbatim collection).
    return (
        b"BI /W 4 /H 4 /BPC 8 /CS /RGB /D [0 1] /IM false /I true "
        b"ID \x01\x02\x03EI Q\n"
    )


def _c_decode_array() -> bytes:
    return b"BI /W 2 /H 2 /BPC 8 /D [1 0] ID \x05\x06EI Q\n"


def _c_imagemask_true() -> bytes:
    return b"BI /W 2 /H 2 /IM true ID \x01EI Q\n"


def _c_cs_named() -> bytes:
    return b"BI /W 2 /H 2 /CS /DeviceGray ID \x07\x08EI Q\n"


def _c_non_name_where_key() -> bytes:
    # A number appears where a /Key is expected: parser stops dict collection.
    return b"BI /W 2 123 /H 2 ID \x01\x02EI Q\n"


def _c_value_missing_at_eof() -> bytes:
    # /CS with no value, then EOF — malformed dict, no ID/EI.
    return b"BI /W 2 /CS"


def _c_nested_bi() -> bytes:
    # PDFBOX-6038: a second BI before the first ID/EI.
    return b"BI /W 2 BI /H 2 ID \x01EI Q\n"


def _c_real_ei_then_w_op() -> bytes:
    # Real terminator followed by a number+operator (PDFBOX-5957 acceptance).
    return b"BI /W 2 /H 2 ID \x40\x41\x42EI 5 w\n"


def _c_two_inline_images() -> bytes:
    # Two complete inline images back to back.
    return (
        b"BI /W 1 /H 1 ID \x10\x11EI Q "
        b"BI /W 2 /H 2 ID \x20\x21\x22EI S\n"
    )


def _c_payload_with_false_ei_then_dct() -> bytes:
    # Embedded EI followed by high byte (binary) must not terminate; the JPEG
    # SOI/EOI markers contain 0xFF bytes.
    payload = bytes([0x45, 0x49, 0xFF, 0x10, 0x00, 0x45, 0x49, 0x20, 0x01])
    return b"BI /W 2 /H 2 /F /DCT ID " + payload + b"EI Q\n"


def _c_id_no_space_tab() -> bytes:
    # 'ID' followed by a TAB (whitespace but not a linebreak): consumed as the
    # single whitespace separator.
    return b"BI /W 1 /H 1 ID\t\x10\x11EI Q\n"


def _c_bool_decode_parms_null() -> bytes:
    # /DP null is a valid COS value.
    return b"BI /W 2 /H 2 /F /Fl /DP null ID \x78\x9c\x03\x00\x00\x00\x00\x01EI Q\n"


def _c_ei_at_eof_no_sep() -> bytes:
    # Real EI at the very end, no trailing separator.
    return b"BI /W 2 /H 2 ID \x00\x11\x22\x33EI"


def _c_string_value() -> bytes:
    # A literal-string value in the dict (unusual but legal COS).
    return b"BI /W 2 /H 2 /CS (abc) ID \x01\x02EI Q\n"


def _c_id_no_ws_binary() -> bytes:
    # PDFBOX-1751 / wave 1517 regression: ``ID`` followed immediately by a
    # NON-whitespace binary byte (no separator). ``readOperator`` must stop
    # at exactly ``ID`` so the byte begins the payload rather than being
    # folded into a bogus ``ID<byte>`` keyword (which dropped the segment).
    return b"BI /W 1 /H 1 ID\x10\x11EI Q\n"


def _c_id_no_ws_high_byte() -> bytes:
    return b"BI /W 1 /H 1 ID\xff\x02EI Q\n"


def _c_idx_no_bi() -> bytes:
    # ``IDX...`` outside any BI: upstream still tokenizes ``ID`` + payload.
    return b"q IDX\x02EI Q\n"


_CASES = {
    "id_no_ws_before_payload": _c_id_no_ws_before_payload(),
    "id_crlf_after": _c_id_crlf_after(),
    "id_cr_only": _c_id_cr_only(),
    "id_lf_only": _c_id_lf_only(),
    "id_two_spaces": _c_id_two_spaces(),
    "missing_ei_truncated": _c_missing_ei_truncated(),
    "empty_payload": _c_empty_payload(),
    "empty_params": _c_empty_params(),
    "filter_ahx": _c_filter_ahx(),
    "filter_a85": _c_filter_a85(),
    "filter_fl": _c_filter_fl(),
    "filter_lzw": _c_filter_lzw(),
    "filter_rl": _c_filter_rl(),
    "filter_ccf_with_dp": _c_filter_ccf_with_dp(),
    "filter_dct": _c_filter_dct(),
    "filter_array": _c_filter_array(),
    "abbrev_keys_all": _c_abbrev_keys_all(),
    "decode_array": _c_decode_array(),
    "imagemask_true": _c_imagemask_true(),
    "cs_named": _c_cs_named(),
    "non_name_where_key": _c_non_name_where_key(),
    "value_missing_at_eof": _c_value_missing_at_eof(),
    "nested_bi": _c_nested_bi(),
    "real_ei_then_w_op": _c_real_ei_then_w_op(),
    "two_inline_images": _c_two_inline_images(),
    "payload_false_ei_dct": _c_payload_with_false_ei_then_dct(),
    "id_tab_sep": _c_id_no_space_tab(),
    "dp_null": _c_bool_decode_parms_null(),
    "ei_at_eof_no_sep": _c_ei_at_eof_no_sep(),
    "string_value": _c_string_value(),
    "id_no_ws_binary": _c_id_no_ws_binary(),
    "id_no_ws_high_byte": _c_id_no_ws_high_byte(),
    "idx_no_bi": _c_idx_no_bi(),
}


# ---- pypdfbox projection (mirrors the Java probe) --------------------------


def _describe(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, COSName):
        return "/" + v.get_name()
    if isinstance(v, COSBoolean):
        return "true" if v.get_value() else "false"
    if isinstance(v, COSNull):
        return "null"
    if isinstance(v, COSInteger):
        return str(v.long_value())
    if isinstance(v, COSFloat):
        return _cosfloat_str(v)
    if isinstance(v, COSString):
        return "(" + v.get_bytes().hex() + ")"
    if isinstance(v, COSArray):
        return "[" + " ".join(_describe(item) for item in v) + "]"
    if isinstance(v, COSDictionary):
        parts = [
            "/" + k.get_name() + "=" + _describe(v.get_item(k))
            for k in v.key_set()
        ]
        return "<<" + " ".join(parts) + ">>"
    return type(v).__name__


def _cosfloat_str(v: COSFloat) -> str:
    # Mirror PDFBox COSFloat.toString() (trailing-zero stripping). Not
    # exercised by the current cases (no real-valued dict entries), but kept
    # for fidelity with the Java describe().
    return str(v.float_value())


def _describe_dict(d: COSDictionary) -> str:
    parts = [
        k.get_name() + "=" + _describe(d.get_item(k)) for k in d.key_set()
    ]
    return "[" + " ".join(parts) + "]"


def _pypdfbox_blocks(data: bytes) -> str:
    parser = PDFStreamParser.from_bytes(data)
    try:
        tokens = parser.parse()
    except PDFParseError:
        return "THROW\n"
    out: list[str] = []
    for tok in tokens:
        if isinstance(tok, Operator) and tok.get_name() == "BI":
            params = tok.get_image_parameters()
            img = tok.get_image_data()
            keys = "null" if params is None else _describe_dict(params)
            if img is None:
                out.append(f"BI keys={keys} dlen=-1 dsha=- dhead=- dtail=-")
            else:
                sha = hashlib.sha1(img).hexdigest()  # noqa: S324 - parity hash
                out.append(
                    f"BI keys={keys} dlen={len(img)} dsha={sha} "
                    f"dhead={img[:16].hex()} dtail={img[-16:].hex()}"
                )
    out.append(f"OPS:{len(tokens)}")
    return "".join(line + "\n" for line in out)


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_inline_image_fuzz_matches_pdfbox(name: str) -> None:
    data = _CASES[name]
    with tempfile.NamedTemporaryFile(suffix=".cs", delete=False) as handle:
        handle.write(data)
        tmp_path = handle.name
    try:
        java = run_probe_text("InlineImageFuzzProbe", tmp_path)
        py = _pypdfbox_blocks(data)
        assert py == java
    finally:
        Path(tmp_path).unlink()
