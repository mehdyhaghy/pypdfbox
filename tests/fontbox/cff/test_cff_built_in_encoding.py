"""Hand-written tests for :class:`CFFBuiltInEncoding` and :class:`Supplement`."""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_built_in_encoding import (
    CFFBuiltInEncoding,
    Supplement,
)


class _Probe(CFFBuiltInEncoding):
    """Concrete subclass used to drive the abstract base."""


def test_supplement_attributes() -> None:
    sup = Supplement(code=10, sid=99, name="myglyph")
    assert sup.code == 10
    assert sup.sid == 99
    assert sup.name == "myglyph"


def test_supplement_repr_matches_java_format() -> None:
    sup = Supplement(code=10, sid=99, name="myglyph")
    # Java: ClassName[code=N, sid=M] (Python ClassName has no qualifier)
    assert repr(sup) == "Supplement[code=10, sid=99]"


def test_supplement_is_immutable() -> None:
    import dataclasses

    sup = Supplement(code=1, sid=2, name="a")
    try:
        sup.code = 99  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Supplement should be frozen")


def test_default_supplement_list_is_empty() -> None:
    enc = _Probe()
    assert enc.supplement == ()


def test_supplement_setter_accepts_list_or_tuple() -> None:
    enc = _Probe()
    sups = [Supplement(1, 2, "a"), Supplement(3, 4, "b")]
    enc.supplement = sups
    assert enc.supplement == tuple(sups)


def test_add_supplement_populates_code_to_name() -> None:
    enc = _Probe()
    enc.add_supplement(Supplement(code=42, sid=1, name="space"))
    # add_supplement delegates to the 3-arg add, which uses the
    # explicit name (not the SID lookup), matching upstream.
    assert enc.get_name(42) == "space"
    assert enc.get_code("space") == 42


def test_inherits_cff_encoding_two_arg_add() -> None:
    enc = _Probe()
    enc.add(33, 2)  # SID 2 -> "exclam"
    assert enc.get_name(33) == "exclam"
