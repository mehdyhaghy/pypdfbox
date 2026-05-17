"""Wave 1321 coverage-boost tests for
:mod:`pypdfbox.fontbox.cff.cff_parser`.

These tests target the still-uncovered branches after wave 1314: the
binary ``skip_header`` / ``create_tagged_cff_data_input`` mirrors of
upstream's pre-decompile dispatch, the negative path of
``read_string_index_data``, the BCD edge cases in ``read_real_number``
(stray ``D`` filler / repeated exponent markers / illegal nibble path /
end-marker hit mid-byte / empty-buffer fallback), the synthetic-font
rejection and empty-name-index branches in ``parse``, and the
``parse_cid_font_dicts`` / ``parse_type1_dicts`` per-font dispatchers
that the high-level ``parse`` shim sidesteps.

Each test name corresponds to the upstream branch being exercised so a
coverage regression bisect maps straight back to the source operation.
"""

from __future__ import annotations

import struct
from typing import Any
from unittest.mock import patch

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.cff_standard_encoding import CFFStandardEncoding
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.dict_data import DictData, Entry
from pypdfbox.fontbox.cff.embedded_charset import EmbeddedCharset
from pypdfbox.fontbox.cff.fd_select import Format0FDSelect
from pypdfbox.fontbox.cff.format1_encoding import Format1Encoding

# ---------------------------------------------------------------------
# parse_first_sub_font_ros — empty-font-list path (lines 184-186).
# ---------------------------------------------------------------------


class _StubHeaders:
    def __init__(self) -> None:
        self.error: str | None = None
        self.ros: tuple[str | None, str | None, int | None] | None = None

    def set_error(self, msg: str) -> None:
        self.error = msg

    def set_otf_ros(
        self,
        registry: str | None,
        ordering: str | None,
        supplement: int | None,
    ) -> None:
        self.ros = (registry, ordering, supplement)


def test_parse_first_sub_font_ros_reports_error_when_parse_returns_empty() -> None:
    """``parse_first_sub_font_ros`` must call ``set_error`` when the
    parsed font list comes back empty (mirrors upstream's
    ``fonts.isEmpty()`` guard at ``CFFParser.java`` line 130)."""
    parser = CFFParser()
    headers = _StubHeaders()
    with patch.object(parser, "parse", return_value=[]):
        parser.parse_first_sub_font_ros(b"any-bytes", headers)
    assert headers.error == "Name index missing in CFF font"


def test_parse_first_sub_font_ros_swallows_error_without_set_error() -> None:
    """When the OSError is raised but the headers stub has no
    ``set_error`` attribute, the parser must simply return (no raise)."""

    class _BareHeaders:
        pass

    parser = CFFParser()
    parser.parse_first_sub_font_ros(b"ttcf" + b"\x00" * 16, _BareHeaders())


def test_parse_first_sub_font_ros_skips_empty_branch_when_headers_lack_set_error() -> None:
    """Empty fonts + headers without ``set_error`` is a silent return."""

    class _BareHeaders:
        pass

    parser = CFFParser()
    with patch.object(parser, "parse", return_value=[]):
        parser.parse_first_sub_font_ros(b"x", _BareHeaders())


def test_parse_first_sub_font_ros_publishes_ros_for_cid_font() -> None:
    """When the first parsed font is a CFFCIDFont and headers expose
    ``set_otf_ros`` (covers line 190)."""
    parser = CFFParser()
    cid = CFFCIDFont()
    cid.set_registry("Adobe")
    cid.set_ordering("Identity")
    cid.set_supplement(0)
    headers = _StubHeaders()
    with patch.object(parser, "parse", return_value=[cid]):
        parser.parse_first_sub_font_ros(b"x", headers)
    assert headers.ros == ("Adobe", "Identity", 0)


# ---------------------------------------------------------------------
# parse() — synthetic-font + empty-name-index error branches (122-123,
# 133-134).
# ---------------------------------------------------------------------


def test_parse_rejects_synthetic_base_font() -> None:
    """Synthetic-base fonts surface upstream's
    ``"Synthetic Fonts are not supported"`` OSError
    (``CFFParser.java`` line 559)."""
    parser = CFFParser()

    class _StubFontSet:
        fontNames = ["Synthetic"]

        def decompile(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
            return None

        def __getitem__(self, name: str) -> Any:  # noqa: ARG002
            class _Top:
                rawDict = {"SyntheticBase": 1}

            return _Top()

    with patch(
        "fontTools.cffLib.CFFFontSet", return_value=_StubFontSet()
    ), pytest.raises(OSError, match="Synthetic Fonts are not supported"):
        parser.parse(b"\x00" * 4)


def test_parse_rejects_empty_name_index() -> None:
    """``fontNames`` empty maps to upstream's
    ``"Name index missing in CFF font"`` error (line 122)."""
    parser = CFFParser()

    class _StubFontSet:
        fontNames: list[str] = []

        def decompile(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
            return None

    with patch(
        "fontTools.cffLib.CFFFontSet", return_value=_StubFontSet()
    ), pytest.raises(OSError, match="Name index missing"):
        parser.parse(b"\x00" * 4)


# ---------------------------------------------------------------------
# skip_header — branches OTTO / ttcf / TTF / plain-CFF (lines 209-222).
# ---------------------------------------------------------------------


def _build_otf_with_cff(cff_payload: bytes) -> bytes:
    """Construct a minimal OTF byte stream wrapping ``cff_payload`` as
    the sole ``CFF `` table — used by ``skip_header`` /
    ``create_tagged_cff_data_input`` tests."""
    header = b"OTTO" + struct.pack(">HHHH", 1, 0, 0, 0)
    cff_offset = 12 + 16
    record = (
        b"CFF "
        + struct.pack(">I", 0)  # checksum (discarded)
        + struct.pack(">I", cff_offset)
        + struct.pack(">I", len(cff_payload))
    )
    return header + record + cff_payload


def test_skip_header_rewinds_plain_cff_then_reads_header() -> None:
    """Non-OTF / non-TTF magic must rewind to position 0 then consume
    the 4-byte CFF header (line 219-221). Use a payload that starts with
    valid header bytes (major=1, minor=0, hdrSize=4, offSize=2) followed
    by trailing bytes."""
    payload = b"\x01\x00\x04\x02trailingbytes"
    inp = DataInputByteArray(payload)
    parser = CFFParser()
    result = parser.skip_header(inp)
    # Returned the same input, now positioned past the header.
    assert result is inp
    assert inp.get_position() == 4


def test_skip_header_rejects_ttcf_collection() -> None:
    """``ttcf`` tag must raise OSError (line 212-214)."""
    inp = DataInputByteArray(b"ttcf" + b"\x00" * 12)
    parser = CFFParser()
    with pytest.raises(OSError, match="True Type Collection"):
        parser.skip_header(inp)


def test_skip_header_rejects_pure_truetype() -> None:
    """``\\x00\\x01\\x00\\x00`` tag must raise OSError (line 215-217)."""
    inp = DataInputByteArray(b"\x00\x01\x00\x00" + b"\x00" * 12)
    parser = CFFParser()
    with pytest.raises(OSError, match="containing a true type"):
        parser.skip_header(inp)


def test_skip_header_routes_otto_through_create_tagged_input() -> None:
    """OTTO magic must dispatch through ``create_tagged_cff_data_input``
    and return a fresh inner-CFF DataInput (line 211)."""
    inner_cff = b"\x01\x00\x04\x02morepayload"
    otf = _build_otf_with_cff(inner_cff)
    inp = DataInputByteArray(otf)
    parser = CFFParser()
    result = parser.skip_header(inp)
    # The returned input is a fresh DataInputByteArray over inner CFF
    # (positioned past the 4-byte CFF header).
    assert isinstance(result, DataInputByteArray)
    assert result.get_position() == 4
    assert result.length() == len(inner_cff)


# ---------------------------------------------------------------------
# create_tagged_cff_data_input — happy / missing-table paths (229-245).
# ---------------------------------------------------------------------


def test_create_tagged_cff_data_input_extracts_cff_table() -> None:
    """The OTF directory walk should hand back a DataInputByteArray
    pointing at the inner ``CFF `` payload bytes (lines 229-243)."""
    inner = b"INNER-CFF-PAYLOAD"
    otf = _build_otf_with_cff(inner)
    inp = DataInputByteArray(otf)
    # Position past the 4-byte ``OTTO`` magic the way ``skip_header``
    # would have done (upstream's read_tag_name advances by 4).
    inp.set_position(4)
    parser = CFFParser()
    result = parser.create_tagged_cff_data_input(inp)
    assert isinstance(result, DataInputByteArray)
    assert bytes(result.read_bytes(result.length())) == inner


def test_create_tagged_cff_data_input_raises_when_cff_missing() -> None:
    """A directory carrying only non-CFF tags must raise the upstream
    ``"CFF tag not found"`` error (line 244-245)."""
    # 1 table named "ABCD" with bogus offset/length.
    header = b"OTTO" + struct.pack(">HHHH", 1, 0, 0, 0)
    record = (
        b"ABCD"
        + struct.pack(">I", 0)
        + struct.pack(">I", 28)
        + struct.pack(">I", 0)
    )
    otf = header + record + b"\x00" * 32
    inp = DataInputByteArray(otf)
    inp.set_position(4)
    parser = CFFParser()
    with pytest.raises(OSError, match="CFF tag not found"):
        parser.create_tagged_cff_data_input(inp)


# ---------------------------------------------------------------------
# read_string_index_data — negative-length guard (lines 338-343).
# ---------------------------------------------------------------------


def test_read_string_index_data_rejects_negative_length() -> None:
    """When offsets[i+1] < offsets[i] the parser must raise OSError
    (mirrors upstream's ``IOException`` at ``CFFParser.java`` line 336)."""
    # count=2, off_size=1, offsets(5, 2, 6) — second jump is negative
    # (offsets[1]=2 < offsets[0]=5). Then 5 bytes of payload so the
    # initial offsets-past-EOF guard doesn't fire.
    payload = b"\x00\x02\x01\x05\x02\x06ABCDE"
    inp = DataInputByteArray(payload)
    with pytest.raises(OSError, match="Negative index data length"):
        CFFParser.read_string_index_data(inp)


# ---------------------------------------------------------------------
# read_entry — operand-byte branches (lines 385, 387).
# ---------------------------------------------------------------------


def test_read_entry_handles_short_operand_b0_28() -> None:
    """b0=28 (signed short operand) followed by operator (line 385)."""
    # 28, signed short -1 (0xFFFF), operator "version" (0)
    inp = DataInputByteArray(b"\x1c\xff\xff\x00")
    entry = CFFParser.read_entry(inp)
    assert entry.operator_name == "version"
    assert entry.get_number(0) == -1


def test_read_entry_handles_int_operand_b0_29() -> None:
    """b0=29 (signed int operand) followed by operator (line 385)."""
    # 29, signed int 0x12345678, operator "version" (0)
    inp = DataInputByteArray(b"\x1d\x12\x34\x56\x78\x00")
    entry = CFFParser.read_entry(inp)
    assert entry.get_number(0) == 0x12345678


def test_read_entry_handles_real_operand_b0_30() -> None:
    """b0=30 (BCD real operand) followed by operator (line 387)."""
    # 30, nibbles "1.5F" = bytes(0x1a, 0x5f), then operator 0 ("version")
    inp = DataInputByteArray(b"\x1e\x1a\x5f\x00")
    entry = CFFParser.read_entry(inp)
    assert entry.get_number(0) == 1.5


# ---------------------------------------------------------------------
# read_real_number — repeated-exponent / D-filler / EOF / empty paths
# (lines 447, 453, 458, 465-466, 470, 473-474).
# ---------------------------------------------------------------------


def test_read_real_number_skips_repeated_b_exponent_marker() -> None:
    """A second ``B`` nibble after the first must be ignored (continue
    branch at line 447), not appended a second time."""
    # Nibbles: 1, B, 2, B, F → upstream: "1E2" (the second B is dropped)
    # bytes: 0x1B 0x2B 0xF? – we need 0xF as terminator nibble.
    # Pack 1, B (=1B), 2, B (=2B), then F nibble. The end-marker can be
    # the high nibble of the next byte; lower nibble doesn't matter.
    inp = DataInputByteArray(b"\x1b\x2b\xf0")
    assert CFFParser.read_real_number(inp) == 100.0


def test_read_real_number_skips_repeated_c_exponent_marker() -> None:
    """A second ``C`` nibble after the first must be ignored (continue
    branch at line 453)."""
    # Nibbles: 1, C, 2, C, F → "1E-2" = 0.01
    inp = DataInputByteArray(b"\x1c\x2c\xf0")
    assert abs(CFFParser.read_real_number(inp) - 0.01) < 1e-9


def test_read_real_number_handles_d_filler_nibble() -> None:
    """Nibble 0xD is a no-op filler (line 458, ``pass`` branch)."""
    # Nibbles: 1, D, 0, F → "10" (D is silently dropped)
    inp = DataInputByteArray(b"\x1d\x0f")
    assert CFFParser.read_real_number(inp) == 10.0


def test_read_real_number_terminates_on_f_in_high_nibble() -> None:
    """End-marker nibble 0xF in the high half-byte must terminate the
    loop without consuming the low half (line 461-463)."""
    # First byte: 0xF? — high nibble 0xF terminates immediately. Buffer
    # has only this byte; if we tried to read another byte the buffer
    # would EOF, so this verifies the early-break.
    inp = DataInputByteArray(b"\xf0")
    # Empty BCD ⇒ 0.0 via the empty-list fallback (line 469-470).
    assert CFFParser.read_real_number(inp) == 0.0


def test_read_real_number_empty_returns_zero() -> None:
    """An immediate end-marker yields the empty-buffer fallback (line
    470)."""
    inp = DataInputByteArray(b"\xff")
    assert CFFParser.read_real_number(inp) == 0.0


def test_read_real_number_propagates_value_error_as_oserror() -> None:
    """``float("".join(sb))`` failure must be re-raised as OSError
    (lines 473-474). We force it by patching the built-in ``float`` so
    a non-empty BCD raises ValueError on conversion."""
    # Inject ``float`` into the module's globals (Python normally
    # resolves the builtin at call time, so the explicit binding
    # overrides it for the duration of the test).
    import pypdfbox.fontbox.cff.cff_parser as cff_parser_module

    def _boom(*args: Any, **kwargs: Any) -> float:  # noqa: ARG001
        msg = "boom"
        raise ValueError(msg)

    cff_parser_module.float = _boom  # type: ignore[attr-defined]
    try:
        # Nibbles: 1, F → "1", then patched ``float("1")`` raises.
        inp = DataInputByteArray(b"\x1f")
        with pytest.raises(OSError, match="boom"):
            CFFParser.read_real_number(inp)
    finally:
        del cff_parser_module.float  # type: ignore[attr-defined]


# ---------------------------------------------------------------------
# parse_font — empty-fonts fallback raise (lines 554-555).
# ---------------------------------------------------------------------


def test_parse_font_raises_when_parse_returns_empty() -> None:
    """Empty CFF (no fonts decompiled) must raise the upstream
    ``"Font %r not found"`` error (lines 554-555)."""
    parser = CFFParser()
    inp = DataInputByteArray(b"placeholder")
    with patch.object(parser, "parse", return_value=[]), pytest.raises(
        OSError, match="not found in CFF data"
    ):
        parser.parse_font(inp, "Missing", b"")


# ---------------------------------------------------------------------
# Format1Encoding with supplement bit set (line 620).
# ---------------------------------------------------------------------


def test_read_format1_encoding_consumes_supplement_when_high_bit_set() -> None:
    """Format byte with 0x80 set triggers the supplement read after
    Format1 ranges (line 619-620)."""
    parser = CFFParser()
    charset = EmbeddedCharset(is_cid_font=False)
    charset.add_sid(0, 0, ".notdef")
    charset.add_sid(1, 1, "space")
    # nRanges=1, range_first=0x41, nLeft=0 (1 glyph); then supplement:
    # nSups=1, code=0x80, sid=1 ("space")
    inp = DataInputByteArray(b"\x01\x41\x00\x01\x80\x00\x01")
    encoding = parser.read_format1_encoding(inp, charset, format_=0x81)
    assert isinstance(encoding, Format1Encoding)
    # Supplement was consumed → encoding.supplement is populated.
    assert len(encoding.supplement) == 1
    assert encoding.supplement[0].code == 0x80


# ---------------------------------------------------------------------
# parse_cid_font_dicts — the FDArray / private-dict / FDSelect walk
# (lines 807-866).
# ---------------------------------------------------------------------


def _enc_int(n: int) -> bytes:
    """Encode an integer per the CFF DICT operand encoding (CFF spec
    Table 3)."""
    if -107 <= n <= 107:
        return bytes([n + 139])
    if 108 <= n <= 1131:
        v = n - 108
        return bytes([(v >> 8) + 247, v & 0xFF])
    if -1131 <= n <= -108:
        v = -n - 108
        return bytes([(v >> 8) + 251, v & 0xFF])
    # Fallback to b0=29 + signed int.
    return bytes([29]) + n.to_bytes(4, "big", signed=True)


def _enc_dict_entry(op: int, *operands: int, two_byte: bool = False) -> bytes:
    """Encode a DICT entry: operands first, then operator."""
    body = b""
    for v in operands:
        body += _enc_int(v)
    if two_byte:
        body += bytes([12, op])
    else:
        body += bytes([op])
    return body


def _build_cid_payload() -> tuple[bytes, DictData, int]:
    """Hand-roll a CFF payload exercising ``parse_cid_font_dicts``.

    Returns ``(payload_bytes, top_dict, n_glyphs)``. The payload layout:

    - bytes[0..2)     : padding so offsets are non-trivial
    - bytes[3..]      : FDArray INDEX = 1 entry, font-dict containing a
      Private DICT pointer.
    - the Private DICT itself
    - the local Subrs INDEX (1 entry)
    - the FDSelect (format 0) with 2 glyphs.

    The returned ``top_dict`` references the FDArray / FDSelect offsets
    so callers can pass it straight to ``parse_cid_font_dicts``.
    """
    # ----- Layout planning -------------------------------------------
    # Build font-dict body first: 1 entry pointing at Private DICT.
    # Private DICT operator = 18 (one-byte, two-operand: size, offset).
    # FontType operator = 0x0C 0x22 (12, 34) — not strictly required.
    # Private DICT body: a single ``Subrs`` entry (op 19, 1 operand
    # relative to Private DICT start), plus a ``defaultWidthX`` (op 20).
    priv_subrs_op = 19
    priv_default_width_op = 20

    # Private DICT will hold: Subrs offset (relative to its start), and
    # defaultWidthX=500.
    # We choose Subrs offset = len(priv_body) so the Subrs INDEX starts
    # immediately after the Private DICT. The Subrs INDEX itself is:
    # count=1 off_size=1 offsets(1, 2) payload(0x0e) — total 5 bytes.

    # Subrs INDEX bytes.
    subrs_index = bytes([0x00, 0x01, 0x01, 0x01, 0x02, 0x0E])

    # Build a Private DICT placeholder to measure its size, then
    # patch the actual Subrs offset.
    def _build_priv(subrs_offset: int) -> bytes:
        return _enc_dict_entry(priv_subrs_op, subrs_offset) + _enc_dict_entry(
            priv_default_width_op, 500
        )

    # Iterate to a fixed point (size doesn't depend on the value much
    # for small ints, but be safe).
    priv_body = _build_priv(10)
    for _ in range(3):
        priv_body = _build_priv(len(priv_body))

    # Font-dict body: Private DICT entry = (size, offset) of Private.
    # The offset is absolute inside the CFF byte stream.
    # We'll patch the offset after we know where the Private DICT lands.
    font_dict_op_private = 18
    font_dict_op_font_type = 34  # two-byte 12 22 → "FontType"

    def _build_font_dict(priv_size: int, priv_offset: int) -> bytes:
        return _enc_dict_entry(
            font_dict_op_private, priv_size, priv_offset
        ) + _enc_dict_entry(font_dict_op_font_type, 2, two_byte=True)

    # First measurement of font-dict
    font_dict = _build_font_dict(len(priv_body), 100)
    fd_entry_len = len(font_dict)

    # FDArray INDEX header: count=1, off_size=1, offsets(1, fd_entry_len+1)
    fd_array_header = bytes([0x00, 0x01, 0x01, 0x01, fd_entry_len + 1])
    # FDSelect Format 0 body for 2 glyphs: format byte 0, then 2 FD
    # indices (both 0).
    fd_select_body = bytes([0x00, 0x00, 0x00])

    # ----- Assemble in order -----------------------------------------
    # We need: padding | FDArray | Private DICT | Subrs INDEX | FDSelect
    padding = b"\x00\x00\x00"
    fd_array_offset = len(padding)
    fd_array_full_pos_after = (
        fd_array_offset + len(fd_array_header) + fd_entry_len
    )
    priv_offset = fd_array_full_pos_after
    subrs_offset_in_priv = len(priv_body)
    abs_subrs_offset = priv_offset + subrs_offset_in_priv

    # Rebuild font_dict with the real Private offset.
    font_dict = _build_font_dict(len(priv_body), priv_offset)
    # Verify the recomputed font_dict length matches (it must, since the
    # operands are encoded with the same widths for small ints — we
    # iterate just in case).
    while len(font_dict) != fd_entry_len:
        fd_entry_len = len(font_dict)
        fd_array_header = bytes([0x00, 0x01, 0x01, 0x01, fd_entry_len + 1])
        fd_array_full_pos_after = (
            fd_array_offset + len(fd_array_header) + fd_entry_len
        )
        priv_offset = fd_array_full_pos_after
        abs_subrs_offset = priv_offset + subrs_offset_in_priv
        font_dict = _build_font_dict(len(priv_body), priv_offset)

    fd_select_offset = abs_subrs_offset + len(subrs_index)
    payload = (
        padding
        + fd_array_header
        + font_dict
        + priv_body
        + subrs_index
        + fd_select_body
    )

    # Top DICT mirrors what upstream would have parsed: just the
    # FDArray + FDSelect operators.
    top = DictData()
    fd_array_entry = Entry()
    fd_array_entry.operator_name = "FDArray"
    fd_array_entry.add_operand(fd_array_offset)
    top.add(fd_array_entry)

    fd_select_entry = Entry()
    fd_select_entry.operator_name = "FDSelect"
    fd_select_entry.add_operand(fd_select_offset)
    top.add(fd_select_entry)

    return payload, top, 2


def test_parse_cid_font_dicts_populates_font_priv_and_fd_select() -> None:
    """End-to-end happy path through ``parse_cid_font_dicts``: builds a
    valid FDArray + Private DICT + Subrs INDEX + FDSelect byte stream
    and verifies the resulting CFFCIDFont carries the expected dicts."""
    payload, top, n_glyphs = _build_cid_payload()
    parser = CFFParser()
    font = CFFCIDFont()
    inp = DataInputByteArray(payload)
    parser.parse_cid_font_dicts(inp, top, font, n_glyphs)
    # set_font_dict + set_priv_dict + set_fd_select were all called.
    assert len(font.get_font_dicts()) == 1
    assert len(font.get_priv_dicts()) == 1
    priv = font.get_priv_dicts()[0]
    # Default width carried into the materialised private dict.
    assert priv["defaultWidthX"] == 500
    # Subrs INDEX inlined.
    assert priv["Subrs"] == [b"\x0e"]
    assert isinstance(font.get_fd_select(), Format0FDSelect)


def test_parse_cid_font_dicts_rejects_missing_fd_array() -> None:
    """No FDArray ⇒ upstream's ``"FDArray is missing"`` error
    (line 809-810)."""
    parser = CFFParser()
    font = CFFCIDFont()
    inp = DataInputByteArray(b"\x00" * 16)
    with pytest.raises(OSError, match="FDArray is missing"):
        parser.parse_cid_font_dicts(inp, DictData(), font, 1)


def test_parse_cid_font_dicts_rejects_empty_fd_index() -> None:
    """When the FDArray INDEX has count=0 the parser must raise (line
    815-817)."""
    parser = CFFParser()
    font = CFFCIDFont()
    top = DictData()
    e = Entry()
    e.operator_name = "FDArray"
    e.add_operand(0)
    top.add(e)
    # Buffer with an empty INDEX (count=0) at offset 0, plus padding so
    # set_position(0) succeeds.
    inp = DataInputByteArray(b"\x00\x00\x00\x00")
    with pytest.raises(OSError, match="Font dict index is missing"):
        parser.parse_cid_font_dicts(inp, top, font, 1)


def test_parse_cid_font_dicts_rejects_missing_private_entry() -> None:
    """A font-dict without a ``Private`` entry must surface upstream's
    ``"Font DICT invalid without 'Private' entry"`` error (line 853-854)."""
    parser = CFFParser()
    font = CFFCIDFont()
    top = DictData()
    e = Entry()
    e.operator_name = "FDArray"
    e.add_operand(3)
    top.add(e)
    # FDArray INDEX with 1 entry containing only a FontType operator
    # (no Private DICT pointer).
    fd_entry = _enc_dict_entry(34, 2, two_byte=True)
    fd_array = bytes([0x00, 0x01, 0x01, 0x01, len(fd_entry) + 1]) + fd_entry
    payload = b"\x00\x00\x00" + fd_array + b"\x00" * 4
    inp = DataInputByteArray(payload)
    with pytest.raises(OSError, match="Font DICT invalid without"):
        parser.parse_cid_font_dicts(inp, top, font, 1)


def test_parse_cid_font_dicts_rejects_missing_fd_select() -> None:
    """When ``parse_cid_font_dicts`` finishes the Private-DICT walk but
    the Top DICT lacks ``FDSelect``, upstream raises (line 858-859)."""
    payload, top, n_glyphs = _build_cid_payload()
    # Strip FDSelect from the Top DICT to force the error path.
    del top.entries["FDSelect"]
    parser = CFFParser()
    font = CFFCIDFont()
    inp = DataInputByteArray(payload)
    with pytest.raises(OSError, match="FDSelect is missing"):
        parser.parse_cid_font_dicts(inp, top, font, n_glyphs)


# ---------------------------------------------------------------------
# parse_type1_dicts — encoding + private dict (lines 878-911).
# ---------------------------------------------------------------------


def _build_type1_payload() -> tuple[bytes, DictData, Any]:
    """Construct a CFF payload that ``parse_type1_dicts`` can walk
    cleanly. Returns ``(payload, top_dict, charset_stub)``."""
    # Private DICT: a single Subrs offset (op 19) + defaultWidthX (op 20).
    def _priv(subrs_offset: int) -> bytes:
        return _enc_dict_entry(19, subrs_offset) + _enc_dict_entry(20, 500)

    priv_body = _priv(10)
    for _ in range(3):
        priv_body = _priv(len(priv_body))

    subrs_index = bytes([0x00, 0x01, 0x01, 0x01, 0x02, 0x0E])
    padding = b"\x00\x00\x00"
    priv_offset = len(padding)
    payload = padding + priv_body + subrs_index

    # Top DICT: Private entry only — Encoding entry omitted so the
    # standard-encoding-default branch fires (encoding_id == 0).
    top = DictData()
    priv_entry = Entry()
    priv_entry.operator_name = "Private"
    priv_entry.add_operand(len(priv_body))  # size
    priv_entry.add_operand(priv_offset)     # offset
    top.add(priv_entry)

    return payload, top, None


def test_parse_type1_dicts_uses_standard_encoding_when_missing() -> None:
    """Missing Encoding entry must default to ``CFFStandardEncoding``
    (line 884-888)."""
    payload, top, charset = _build_type1_payload()
    parser = CFFParser()
    font = CFFType1Font()
    inp = DataInputByteArray(payload)
    parser.parse_type1_dicts(inp, top, font, charset)
    # Encoding was set; defaultWidthX bubbled through the private dict.
    assert font.get_encoding() is CFFStandardEncoding.get_instance()
    priv = font.get_private_dict()
    assert priv["defaultWidthX"] == 500
    assert priv["Subrs"] == [b"\x0e"]


def test_parse_type1_dicts_uses_expert_encoding_when_id_one() -> None:
    """encoding_id == 1 must select CFFExpertEncoding (line 889-890)."""
    from pypdfbox.fontbox.cff.cff_expert_encoding import CFFExpertEncoding

    payload, top, charset = _build_type1_payload()
    enc = Entry()
    enc.operator_name = "Encoding"
    enc.add_operand(1)
    top.add(enc)
    parser = CFFParser()
    font = CFFType1Font()
    inp = DataInputByteArray(payload)
    parser.parse_type1_dicts(inp, top, font, charset)
    assert font.get_encoding() is CFFExpertEncoding.get_instance()


def test_parse_type1_dicts_reads_embedded_encoding_for_nonzero_id() -> None:
    """For ``encoding_id > 1`` the parser must seek to that offset and
    decode an embedded encoding (lines 891-893)."""
    # Layout: 2 bytes padding | Format0 encoding (3 bytes) | Private
    # DICT. Encoding offset = 2 (must be >= 2 to skip the standard /
    # expert encoding short-circuits).
    encoding_bytes = bytes([0x00, 0x01, 0x41])  # format=0, n_codes=1, code
    priv_body = _enc_dict_entry(20, 500)
    padding = b"\x00\x00"
    encoding_offset = len(padding)
    priv_offset = encoding_offset + len(encoding_bytes)
    payload = padding + encoding_bytes + priv_body

    top = DictData()
    enc = Entry()
    enc.operator_name = "Encoding"
    enc.add_operand(encoding_offset)
    top.add(enc)
    priv_entry = Entry()
    priv_entry.operator_name = "Private"
    priv_entry.add_operand(len(priv_body))
    priv_entry.add_operand(priv_offset)
    top.add(priv_entry)

    parser = CFFParser()
    font = CFFType1Font()

    # Charset stub: parser only calls ``get_sid_for_gid`` on it.
    class _Charset:
        def get_sid_for_gid(self, gid: int) -> int:  # noqa: ARG002
            return 1  # "space"

    inp = DataInputByteArray(payload)
    parser.parse_type1_dicts(inp, top, font, _Charset())
    # Embedded Format0Encoding now installed (not standard / expert).
    assert font.get_encoding() is not CFFStandardEncoding.get_instance()


def test_parse_type1_dicts_rejects_missing_private_entry() -> None:
    """A Top DICT missing ``Private`` raises upstream's
    ``"Private dictionary entry missing"`` error (line 897-899)."""
    parser = CFFParser()
    font = CFFType1Font()
    font.set_name("X")
    top = DictData()
    # Encoding only (no Private) → triggers the missing-Private branch.
    enc = Entry()
    enc.operator_name = "Encoding"
    enc.add_operand(0)
    top.add(enc)
    inp = DataInputByteArray(b"\x00" * 16)
    with pytest.raises(OSError, match="Private dictionary entry missing"):
        parser.parse_type1_dicts(inp, top, font, None)


def test_parse_type1_dicts_handles_short_private_entry() -> None:
    """A Private entry with fewer than 2 operands must also raise (line
    897-899 — the ``size() < 2`` guard)."""
    parser = CFFParser()
    font = CFFType1Font()
    font.set_name("X")
    top = DictData()
    short_priv = Entry()
    short_priv.operator_name = "Private"
    short_priv.add_operand(0)
    top.add(short_priv)
    inp = DataInputByteArray(b"\x00" * 16)
    with pytest.raises(OSError, match="Private dictionary entry missing"):
        parser.parse_type1_dicts(inp, top, font, None)
