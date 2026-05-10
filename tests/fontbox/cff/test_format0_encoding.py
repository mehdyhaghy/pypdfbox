"""Hand-written tests for :class:`Format0Encoding`."""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_built_in_encoding import Supplement
from pypdfbox.fontbox.cff.format0_encoding import Format0Encoding


def test_n_codes_is_stored() -> None:
    enc = Format0Encoding(7)
    assert enc.n_codes == 7


def test_n_codes_coerces_to_int() -> None:
    enc = Format0Encoding(True)  # noqa: FBT003 — verifying coercion only
    assert enc.n_codes == 1
    assert isinstance(enc.n_codes, int) and not isinstance(enc.n_codes, bool)


def test_inherits_built_in_encoding_methods() -> None:
    enc = Format0Encoding(2)
    enc.add(65, 34, "A")
    enc.add(66, 35, "B")
    assert enc.get_name(65) == "A"
    assert enc.get_name(66) == "B"


def test_repr_includes_n_codes_and_supplement() -> None:
    enc = Format0Encoding(3)
    enc.supplement = (Supplement(1, 2, "x"),)
    text = repr(enc)
    assert text.startswith("Format0Encoding[nCodes=3,")
    assert "supplement=" in text


def test_supplement_chaining_via_add_supplement() -> None:
    enc = Format0Encoding(0)
    enc.add_supplement(Supplement(code=200, sid=1, name="space"))
    assert enc.get_name(200) == "space"


def test_to_string_matches_upstream_format() -> None:
    # Upstream toString (CFFParser.java:1481-1485):
    # ``getClass().getName() + "[nCodes=" + nCodes
    #   + ", supplement=" + Arrays.toString(super.supplement) + "]"``.
    enc = Format0Encoding(3)
    rendered = enc.to_string()
    assert "Format0Encoding" in rendered
    assert "[nCodes=3," in rendered
    assert "supplement=[]" in rendered  # empty supplement renders as []


def test_to_string_includes_supplement_entries() -> None:
    enc = Format0Encoding(2)
    enc.supplement = (Supplement(1, 2, "x"),)
    rendered = enc.to_string()
    assert "[nCodes=2," in rendered
    assert "supplement=[" in rendered
    assert "]]" in rendered
