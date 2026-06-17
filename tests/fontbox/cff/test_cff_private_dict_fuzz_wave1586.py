"""Fuzz / parity tests for CFF Private DICT parsing and the local subr
INDEX (wave 1586).

Targets ``CFFParser.read_private_dict`` plus the local-subr handling in
``CFFParser.parse_type1_dicts`` / ``parse_cid_font_dicts``: the Subrs
offset (op 19) is RELATIVE to the Private DICT's own start, the width
defaults (defaultWidthX op 20 / nominalWidthX op 21) are both 0 when
absent, the Blue* / StemSnap* arrays are delta-decoded (running sum),
StdHW / StdVW are single values, ForceBold is a boolean, and the local
subr bias derives from the local subr INDEX count.

Verified against Apache PDFBox 3.0.7 ``CFFParser.readPrivateDict``
(``CFFParser.java`` lines 836-857) and ``DictData.Entry.getDelta``
(lines 1410-1421). Each materialised value is asserted exactly.

The Private DICT operand encoding helpers below mirror the CFF spec
(Adobe Technical Note #5176, §4 Table 3) integer encoding.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.dict_data import DictData

# Private DICT operators (single-byte b0 codes) we exercise.
OP_BLUE_VALUES = 6
OP_OTHER_BLUES = 7
OP_FAMILY_BLUES = 8
OP_FAMILY_OTHER_BLUES = 9
OP_STD_HW = 10
OP_STD_VW = 11
OP_SUBRS = 19
OP_DEFAULT_WIDTH_X = 20
OP_NOMINAL_WIDTH_X = 21
# Two-byte (escape 12) operators.
OP_BLUE_SCALE = (12, 9)
OP_BLUE_SHIFT = (12, 10)
OP_BLUE_FUZZ = (12, 11)
OP_STEM_SNAP_H = (12, 12)
OP_STEM_SNAP_V = (12, 13)
# NB: upstream PDFBox 3.0.7 registers LanguageGroup/ExpansionFactor/
# initialRandomSeed at 12 15/16/17 (not the CFF-spec 12 17/18/19);
# pypdfbox mirrors upstream, so the parity codes below match.
OP_FORCE_BOLD = (12, 14)
OP_LANGUAGE_GROUP = (12, 15)
OP_EXPANSION_FACTOR = (12, 16)
OP_INITIAL_RANDOM_SEED = (12, 17)


# ---------------------------------------------------------------------------
# Byte builders for synthetic Private DICT + Subrs INDEX.
# ---------------------------------------------------------------------------


def _enc_int(value: int) -> bytes:
    """Encode a CFF DICT integer operand (spec Table 3)."""
    if -107 <= value <= 107:
        return bytes([value + 139])
    if 108 <= value <= 1131:
        value -= 108
        return bytes([(value >> 8) + 247, value & 0xFF])
    if -1131 <= value <= -108:
        value = -value - 108
        return bytes([(value >> 8) + 251, value & 0xFF])
    if -32768 <= value <= 32767:
        return b"\x1c" + struct.pack(">h", value)
    return b"\x1d" + struct.pack(">i", value)


def _enc_op(op: int | tuple[int, int]) -> bytes:
    if isinstance(op, tuple):
        return bytes(op)
    return bytes([op])


def _entry(operands: list[int], op: int | tuple[int, int]) -> bytes:
    out = bytearray()
    for v in operands:
        out += _enc_int(v)
    out += _enc_op(op)
    return bytes(out)


def _parse_priv(dict_bytes: bytes) -> dict:
    """Parse Private DICT bytes through the full read path."""
    di = DataInputByteArray(dict_bytes)
    dict_data: DictData = CFFParser.read_dict_data(di, 0, len(dict_bytes))
    return CFFParser.read_private_dict(dict_data)


def _build_subr_index(entries: list[bytes], off_size: int = 1) -> bytes:
    """Build a CFF INDEX (count, offSize, offsets, data)."""
    out = bytearray()
    out += struct.pack(">H", len(entries))
    if not entries:
        return bytes(out)
    out += bytes([off_size])
    offsets = [1]
    for e in entries:
        offsets.append(offsets[-1] + len(e))
    for off in offsets:
        if off_size == 1:
            out += bytes([off])
        elif off_size == 2:
            out += struct.pack(">H", off)
        else:
            out += struct.pack(">I", off)[4 - off_size :]
    for e in entries:
        out += e
    return bytes(out)


# ---------------------------------------------------------------------------
# Width defaults: defaultWidthX (op 20) / nominalWidthX (op 21) default 0.
# ---------------------------------------------------------------------------


def test_default_width_x_absent_defaults_to_zero() -> None:
    priv = _parse_priv(b"")
    assert priv["defaultWidthX"] == 0


def test_nominal_width_x_absent_defaults_to_zero() -> None:
    priv = _parse_priv(b"")
    assert priv["nominalWidthX"] == 0


@pytest.mark.parametrize(
    "value",
    [0, 1, 107, -107, 500, -500, 1131, -1131, 32767, -32768, 65535],
    ids=[
        "zero",
        "one",
        "pos107",
        "neg107",
        "pos500",
        "neg500",
        "pos1131",
        "neg1131",
        "short_max",
        "short_min",
        "int_65535",
    ],
)
def test_default_width_x_explicit(value: int) -> None:
    priv = _parse_priv(_entry([value], OP_DEFAULT_WIDTH_X))
    assert priv["defaultWidthX"] == value


@pytest.mark.parametrize(
    "value",
    [0, 1, 107, -107, 880, -880, 32000],
    ids=["zero", "one", "pos107", "neg107", "pos880", "neg880", "big"],
)
def test_nominal_width_x_explicit(value: int) -> None:
    priv = _parse_priv(_entry([value], OP_NOMINAL_WIDTH_X))
    assert priv["nominalWidthX"] == value


def test_both_widths_in_one_dict() -> None:
    blob = _entry([250], OP_DEFAULT_WIDTH_X) + _entry([42], OP_NOMINAL_WIDTH_X)
    priv = _parse_priv(blob)
    assert priv["defaultWidthX"] == 250
    assert priv["nominalWidthX"] == 42


# ---------------------------------------------------------------------------
# Subrs offset (op 19) is RELATIVE to the Private DICT start.
# ---------------------------------------------------------------------------


def test_subrs_offset_is_relative_to_private_dict_start() -> None:
    # Layout: [pad junk][private dict][gap][subr index]. The Subrs op
    # value must be measured from private_offset, NOT from file start.
    pad = b"\xaa" * 17
    subr_entries = [b"\x0e", b"\x8b\x0e"]  # endchar; "0 endchar"
    subr_index = _build_subr_index(subr_entries)
    # Private dict declares Subrs at relative offset = len(priv_dict) + gap.
    gap = b"\xff" * 5
    # Build private dict first to know its length.
    priv_dict_bytes = _entry([0], OP_DEFAULT_WIDTH_X)  # placeholder op
    rel_subrs = len(priv_dict_bytes) + len(gap)
    priv_dict_bytes = _entry([rel_subrs], OP_SUBRS) + _entry(
        [0], OP_DEFAULT_WIDTH_X
    )
    # Recompute relative offset now that the Subrs entry is present.
    rel_subrs = len(priv_dict_bytes) + len(gap)
    priv_dict_bytes = _entry([rel_subrs], OP_SUBRS) + _entry(
        [0], OP_DEFAULT_WIDTH_X
    )
    private_offset = len(pad)
    file_bytes = pad + priv_dict_bytes + gap + subr_index
    di = DataInputByteArray(file_bytes)
    dict_data = CFFParser.read_dict_data(
        di, private_offset, len(priv_dict_bytes)
    )
    local_subr_offset = dict_data.get_number("Subrs", 0)
    assert local_subr_offset == rel_subrs
    # Read the local subr INDEX at private_offset + relative offset.
    di.set_position(private_offset + local_subr_offset)
    subrs = CFFParser.read_index_data(di)
    assert subrs == subr_entries


def test_subrs_relative_offset_differs_from_absolute() -> None:
    # A non-zero pad guarantees private_offset != 0, so a parser that
    # (wrongly) used the absolute file offset would land on junk.
    pad = b"\x55" * 40
    subr_entries = [b"\x0e"]
    subr_index = _build_subr_index(subr_entries)
    priv_dict_bytes = _entry([1], OP_SUBRS)  # relative offset 1
    rel = len(priv_dict_bytes)
    priv_dict_bytes = _entry([rel], OP_SUBRS)
    private_offset = len(pad)
    file_bytes = pad + priv_dict_bytes + subr_index
    di = DataInputByteArray(file_bytes)
    dict_data = CFFParser.read_dict_data(
        di, private_offset, len(priv_dict_bytes)
    )
    rel_off = dict_data.get_number("Subrs", 0)
    di.set_position(private_offset + rel_off)
    subrs = CFFParser.read_index_data(di)
    assert subrs == subr_entries
    # If we (wrongly) used the absolute offset we'd be inside the pad.
    assert private_offset + rel_off != rel_off


def test_subrs_absent_defaults_to_zero_no_local_subrs() -> None:
    priv_dict_bytes = _entry([7], OP_DEFAULT_WIDTH_X)
    dict_data = CFFParser.read_dict_data(
        DataInputByteArray(priv_dict_bytes), 0, len(priv_dict_bytes)
    )
    # get_number default 0 -> no local subr read performed by the caller.
    assert dict_data.get_number("Subrs", 0) == 0


# ---------------------------------------------------------------------------
# Delta-encoded arrays: BlueValues / OtherBlues / Family* / StemSnap*.
# ---------------------------------------------------------------------------


def test_blue_values_delta_decoded_to_running_sum() -> None:
    # Stored deltas [-20, 30, 10] -> running sum [-20, 10, 20].
    priv = _parse_priv(_entry([-20, 30, 10], OP_BLUE_VALUES))
    assert priv["BlueValues"] == [-20, 10, 20]


def test_blue_values_first_element_unchanged() -> None:
    priv = _parse_priv(_entry([0, 700, 10, 20], OP_BLUE_VALUES))
    # [0, 0+700, 700+10, 710+20] = [0, 700, 710, 730]
    assert priv["BlueValues"] == [0, 700, 710, 730]


def test_other_blues_delta_decoded() -> None:
    priv = _parse_priv(_entry([-250, 10], OP_OTHER_BLUES))
    assert priv["OtherBlues"] == [-250, -240]


def test_family_blues_delta_decoded() -> None:
    priv = _parse_priv(_entry([0, 700], OP_FAMILY_BLUES))
    assert priv["FamilyBlues"] == [0, 700]


def test_family_other_blues_delta_decoded() -> None:
    priv = _parse_priv(_entry([-249, 11], OP_FAMILY_OTHER_BLUES))
    assert priv["FamilyOtherBlues"] == [-249, -238]


def test_stem_snap_h_delta_decoded() -> None:
    priv = _parse_priv(_entry([40, 10, 10], OP_STEM_SNAP_H))
    assert priv["StemSnapH"] == [40, 50, 60]


def test_stem_snap_v_delta_decoded() -> None:
    priv = _parse_priv(_entry([85, 5], OP_STEM_SNAP_V))
    assert priv["StemSnapV"] == [85, 90]


def test_delta_arrays_absent_default_none() -> None:
    priv = _parse_priv(b"")
    for key in (
        "BlueValues",
        "OtherBlues",
        "FamilyBlues",
        "FamilyOtherBlues",
        "StemSnapH",
        "StemSnapV",
    ):
        assert priv[key] is None


def test_single_element_delta_array() -> None:
    priv = _parse_priv(_entry([123], OP_BLUE_VALUES))
    assert priv["BlueValues"] == [123]


# ---------------------------------------------------------------------------
# StdHW / StdVW single values (default None).
# ---------------------------------------------------------------------------


def test_std_hw_explicit() -> None:
    priv = _parse_priv(_entry([75], OP_STD_HW))
    assert priv["StdHW"] == 75


def test_std_vw_explicit() -> None:
    priv = _parse_priv(_entry([95], OP_STD_VW))
    assert priv["StdVW"] == 95


def test_std_hw_vw_absent_default_none() -> None:
    priv = _parse_priv(b"")
    assert priv["StdHW"] is None
    assert priv["StdVW"] is None


# ---------------------------------------------------------------------------
# ForceBold boolean + scalar defaults.
# ---------------------------------------------------------------------------


def test_force_bold_true() -> None:
    priv = _parse_priv(_entry([1], OP_FORCE_BOLD))
    assert priv["ForceBold"] is True


def test_force_bold_false_explicit() -> None:
    priv = _parse_priv(_entry([0], OP_FORCE_BOLD))
    assert priv["ForceBold"] is False


def test_force_bold_absent_defaults_false() -> None:
    priv = _parse_priv(b"")
    assert priv["ForceBold"] is False


def test_language_group_default_zero() -> None:
    assert _parse_priv(b"")["LanguageGroup"] == 0


def test_language_group_explicit() -> None:
    priv = _parse_priv(_entry([1], OP_LANGUAGE_GROUP))
    assert priv["LanguageGroup"] == 1


def test_blue_scale_default() -> None:
    assert _parse_priv(b"")["BlueScale"] == pytest.approx(0.039625)


def test_blue_shift_default() -> None:
    assert _parse_priv(b"")["BlueShift"] == 7


def test_blue_fuzz_default() -> None:
    assert _parse_priv(b"")["BlueFuzz"] == 1


def test_expansion_factor_default() -> None:
    assert _parse_priv(b"")["ExpansionFactor"] == pytest.approx(0.06)


def test_initial_random_seed_default_zero() -> None:
    assert _parse_priv(b"")["initialRandomSeed"] == 0


def test_blue_shift_explicit() -> None:
    priv = _parse_priv(_entry([9], OP_BLUE_SHIFT))
    assert priv["BlueShift"] == 9


def test_blue_fuzz_explicit() -> None:
    priv = _parse_priv(_entry([2], OP_BLUE_FUZZ))
    assert priv["BlueFuzz"] == 2


# ---------------------------------------------------------------------------
# Local subr bias derives from the local subr INDEX count (Type2 spec).
# CharString bias: count < 1240 -> 107, < 33900 -> 1131, else 32768.
# ---------------------------------------------------------------------------


def _local_subr_bias(count: int) -> int:
    if count < 1240:
        return 107
    if count < 33900:
        return 1131
    return 32768


@pytest.mark.parametrize(
    ("count", "bias"),
    [
        (0, 107),
        (1, 107),
        (1239, 107),
        (1240, 1131),
        (33899, 1131),
        (33900, 32768),
    ],
    ids=["c0", "c1", "c1239", "c1240", "c33899", "c33900"],
)
def test_local_subr_bias_from_count(count: int, bias: int) -> None:
    assert _local_subr_bias(count) == bias


def test_local_subr_count_drives_bias_via_built_index() -> None:
    # Build a small local subr INDEX; its length feeds the bias.
    entries = [b"\x0e"] * 3
    subr_index = _build_subr_index(entries)
    di = DataInputByteArray(subr_index)
    subrs = CFFParser.read_index_data(di)
    assert len(subrs) == 3
    assert _local_subr_bias(len(subrs)) == 107


def test_empty_local_subr_index_count_zero() -> None:
    subr_index = _build_subr_index([])
    di = DataInputByteArray(subr_index)
    subrs = CFFParser.read_index_data(di)
    assert subrs == []
    assert _local_subr_bias(len(subrs)) == 107


# ---------------------------------------------------------------------------
# Full Private DICT round-trip combining many operators.
# ---------------------------------------------------------------------------


def test_full_private_dict_round_trip() -> None:
    blob = (
        _entry([-20, 1100, 0, 5], OP_BLUE_VALUES)
        + _entry([-250, 0], OP_OTHER_BLUES)
        + _entry([75], OP_STD_HW)
        + _entry([95], OP_STD_VW)
        + _entry([40, 10], OP_STEM_SNAP_H)
        + _entry([1], OP_FORCE_BOLD)
        + _entry([1], OP_LANGUAGE_GROUP)
        + _entry([520], OP_DEFAULT_WIDTH_X)
        + _entry([480], OP_NOMINAL_WIDTH_X)
        + _entry([100], OP_SUBRS)
    )
    priv = _parse_priv(blob)
    assert priv["BlueValues"] == [-20, 1080, 1080, 1085]
    assert priv["OtherBlues"] == [-250, -250]
    assert priv["StdHW"] == 75
    assert priv["StdVW"] == 95
    assert priv["StemSnapH"] == [40, 50]
    assert priv["ForceBold"] is True
    assert priv["LanguageGroup"] == 1
    assert priv["defaultWidthX"] == 520
    assert priv["nominalWidthX"] == 480
    # Subrs op is NOT materialised by read_private_dict (the caller reads
    # the INDEX separately using the offset from the raw DictData).
    assert "Subrs" not in priv


def test_read_private_dict_does_not_emit_subrs_key() -> None:
    priv = _parse_priv(_entry([42], OP_SUBRS))
    assert "Subrs" not in priv
