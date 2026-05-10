"""Hand-written tests for
:class:`pypdfbox.fontbox.cff.cff_operator.CFFOperator`.

Mirrors upstream ``CFFOperator`` (``CFFOperator.java`` lines 26-131):
the static ``get_operator(b0)`` / ``get_operator(b0, b1)`` lookup, plus
the new :func:`get_operator_entry` accessor that returns the full
:class:`CFFOperator` record.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_operator import (
    CFFOperator,
    get_operator,
    get_operator_entry,
)

# -- Single-byte Top DICT operators -------------------------------------


def test_get_operator_single_byte_top_dict() -> None:
    # Picked from upstream static initialiser (CFFOperator.java line 76+)
    assert get_operator(0) == "version"
    assert get_operator(1) == "Notice"
    assert get_operator(2) == "FullName"
    assert get_operator(3) == "FamilyName"
    assert get_operator(4) == "Weight"
    assert get_operator(5) == "FontBBox"
    assert get_operator(13) == "UniqueID"
    assert get_operator(14) == "XUID"
    assert get_operator(15) == "charset"
    assert get_operator(16) == "Encoding"
    assert get_operator(17) == "CharStrings"
    assert get_operator(18) == "Private"


# -- Single-byte Private DICT operators ---------------------------------


def test_get_operator_single_byte_private_dict() -> None:
    assert get_operator(6) == "BlueValues"
    assert get_operator(7) == "OtherBlues"
    assert get_operator(8) == "FamilyBlues"
    assert get_operator(9) == "FamilyOtherBlues"
    assert get_operator(10) == "StdHW"
    assert get_operator(11) == "StdVW"
    assert get_operator(19) == "Subrs"
    assert get_operator(20) == "defaultWidthX"
    assert get_operator(21) == "nominalWidthX"


# -- Two-byte (escape 12) operators -------------------------------------


def test_get_operator_two_byte_top_dict() -> None:
    assert get_operator(12, 0) == "Copyright"
    assert get_operator(12, 1) == "isFixedPitch"
    assert get_operator(12, 2) == "ItalicAngle"
    assert get_operator(12, 7) == "FontMatrix"
    assert get_operator(12, 30) == "ROS"
    assert get_operator(12, 31) == "CIDFontVersion"
    assert get_operator(12, 36) == "FDArray"
    assert get_operator(12, 37) == "FDSelect"
    assert get_operator(12, 38) == "FontName"


def test_get_operator_two_byte_private_dict() -> None:
    assert get_operator(12, 9) == "BlueScale"
    assert get_operator(12, 10) == "BlueShift"
    assert get_operator(12, 11) == "BlueFuzz"
    assert get_operator(12, 12) == "StemSnapH"
    assert get_operator(12, 13) == "StemSnapV"
    assert get_operator(12, 14) == "ForceBold"
    assert get_operator(12, 17) == "initialRandomSeed"


# -- Unknown lookups ----------------------------------------------------


def test_unknown_single_byte_operator_returns_none() -> None:
    # Reserved / undefined CFF operators return ``None`` upstream
    # (HashMap.get on missing key) — we mirror that.
    assert get_operator(255) is None
    assert get_operator(22) is None  # 22 is reserved in the spec


def test_unknown_two_byte_operator_returns_none() -> None:
    assert get_operator(12, 99) is None
    assert get_operator(12, 50) is None


# -- get_operator_entry round-trip --------------------------------------


def test_get_operator_entry_returns_dataclass() -> None:
    entry = get_operator_entry(17)  # CharStrings
    assert isinstance(entry, CFFOperator)
    assert entry.b0 == 17
    assert entry.b1 == 0
    assert entry.name == "CharStrings"


def test_get_operator_entry_two_byte() -> None:
    entry = get_operator_entry(12, 30)  # ROS
    assert isinstance(entry, CFFOperator)
    assert entry.b0 == 12
    assert entry.b1 == 30
    assert entry.name == "ROS"


def test_get_operator_entry_unknown_returns_none() -> None:
    assert get_operator_entry(255) is None


def test_cff_operator_key_calculation() -> None:
    # Upstream ``calculateKey`` is ``(b1 << 8) + b0``; our ``key`` matches.
    assert CFFOperator(b0=0, b1=0, name="version").key == 0
    assert CFFOperator(b0=12, b1=30, name="ROS").key == (30 << 8) | 12
    assert CFFOperator(b0=18, b1=0, name="Private").key == 18


def test_cff_operator_default_b1_is_zero() -> None:
    # Single-byte operators round-trip with explicit b1=0.
    entry = get_operator_entry(0)
    assert entry is not None
    assert entry.b1 == 0


# -- Class-level mirrors of upstream's static methods -------------------


def test_class_calculate_key_matches_upstream() -> None:
    # Upstream ``calculateKey`` is ``(b1 << 8) + b0`` (CFFOperator.java:66).
    assert CFFOperator.calculate_key(0, 0) == 0
    assert CFFOperator.calculate_key(12, 30) == (30 << 8) + 12
    assert CFFOperator.calculate_key(18) == 18  # default b1=0


def test_class_get_operator_classmethod() -> None:
    # Mirrors upstream ``CFFOperator.getOperator`` static (lines 49-64).
    assert CFFOperator.get_operator(0) == "version"
    assert CFFOperator.get_operator(12, 30) == "ROS"
    assert CFFOperator.get_operator(255) is None


def test_class_register_adds_entry() -> None:
    # Mirrors upstream ``register(int, int, String)`` (lines 38-41).
    # Use a high (b0, b1) pair guaranteed not to collide with any real
    # operator so the global table is left clean for sibling tests.
    sentinel_b0, sentinel_b1 = 250, 250
    assert CFFOperator.get_operator(sentinel_b0, sentinel_b1) is None
    try:
        CFFOperator.register(sentinel_b0, sentinel_b1, "ParityProbe")
        assert CFFOperator.get_operator(sentinel_b0, sentinel_b1) == "ParityProbe"
    finally:
        # Clean up the synthetic entry so other tests don't observe it.
        from pypdfbox.fontbox.cff.cff_operator import _KEY_TO_OPERATOR

        _KEY_TO_OPERATOR.pop(
            CFFOperator.calculate_key(sentinel_b0, sentinel_b1), None
        )


def test_class_register_single_byte_overload() -> None:
    # Mirrors upstream ``register(int, String)`` (lines 33-36).
    sentinel = 251
    try:
        CFFOperator.register(sentinel, "SingleByteProbe")
        assert CFFOperator.get_operator(sentinel) == "SingleByteProbe"
    finally:
        from pypdfbox.fontbox.cff.cff_operator import _KEY_TO_OPERATOR

        _KEY_TO_OPERATOR.pop(CFFOperator.calculate_key(sentinel), None)
