"""Hand-written tests for :class:`CFFExpertEncoding`."""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_expert_encoding import CFFExpertEncoding


def test_get_instance_is_singleton() -> None:
    a = CFFExpertEncoding.get_instance()
    b = CFFExpertEncoding.get_instance()
    assert a is b


def test_known_mappings() -> None:
    enc = CFFExpertEncoding.get_instance()
    # Samples from upstream CFFEncodingTest.testCFFExpertEncoding().
    assert enc.get_name(0) == ".notdef"
    assert enc.get_name(32) == "space"
    assert enc.get_name(112) == "Psmall"
    assert enc.get_name(251) == "Ucircumflexsmall"


def test_reverse_lookup() -> None:
    enc = CFFExpertEncoding.get_instance()
    assert enc.get_code("space") == 32
    assert enc.get_code("Psmall") == 112
    assert enc.get_code("Ucircumflexsmall") == 251


def test_unmapped_slots_are_notdef() -> None:
    enc = CFFExpertEncoding.get_instance()
    # Per upstream CFFExpertEncoding.java, code 35 maps to SID 0 -> ".notdef".
    assert enc.get_name(35) == ".notdef"


def test_full_256_slot_coverage() -> None:
    enc = CFFExpertEncoding.get_instance()
    mapping = enc.get_code_to_name_map()
    # Expert Encoding fills all 256 slots, mostly with ".notdef".
    assert len(mapping) == 256
