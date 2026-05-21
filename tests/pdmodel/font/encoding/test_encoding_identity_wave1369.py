"""Encoding equality / hash / COS-object identity.

Wave 1369 round-out — exercises the Python-natural identity contract that
sits where Java upstream uses ``Object.equals`` / ``Object.hashCode``
(both default identity-based on ``Encoding`` and subclasses). The
predefined singletons must be reference-identity stable so callers can
key dicts and sets on them.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.encoding import (
    BuiltInEncoding,
    DictionaryEncoding,
    Encoding,
    MacExpertEncoding,
    MacOSRomanEncoding,
    MacRomanEncoding,
    StandardEncoding,
    SymbolEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)

_PREDEFINED_SINGLETONS: list[tuple[str, Encoding]] = [
    ("StandardEncoding", StandardEncoding.INSTANCE),
    ("WinAnsiEncoding", WinAnsiEncoding.INSTANCE),
    ("MacRomanEncoding", MacRomanEncoding.INSTANCE),
    ("MacExpertEncoding", MacExpertEncoding.INSTANCE),
    ("SymbolEncoding", SymbolEncoding.INSTANCE),
    ("ZapfDingbatsEncoding", ZapfDingbatsEncoding.INSTANCE),
]


@pytest.mark.parametrize("name,inst", _PREDEFINED_SINGLETONS)
def test_predefined_singletons_have_stable_identity(
    name: str, inst: Encoding
) -> None:
    a = Encoding.get_instance(name)
    b = Encoding.get_instance(name)
    assert a is b is inst


@pytest.mark.parametrize("name,inst", _PREDEFINED_SINGLETONS)
def test_predefined_singletons_hashable_in_set(
    name: str, inst: Encoding
) -> None:
    bucket: set[Encoding] = {inst}
    # Identity-based hashing — re-inserting the same singleton must collapse.
    bucket.add(Encoding.get_instance(name))  # type: ignore[arg-type]
    assert len(bucket) == 1


def test_distinct_predefined_singletons_dont_collide() -> None:
    bucket: set[Encoding] = set()
    for _, inst in _PREDEFINED_SINGLETONS:
        bucket.add(inst)
    assert len(bucket) == len(_PREDEFINED_SINGLETONS)


def test_predefined_encoding_cos_object_is_name() -> None:
    # COS round-trip: predefined encodings serialize as a /Name.
    for spec_name, inst in _PREDEFINED_SINGLETONS:
        cos = inst.get_cos_object()
        assert isinstance(cos, COSName)
        assert cos.name == spec_name


def test_dictionary_encoding_cos_object_is_dict() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    cos = enc.get_cos_object()
    assert isinstance(cos, COSDictionary)
    # /Type entry distinguishes this from a bare /BaseEncoding name.
    assert cos.get_name(COSName.TYPE) == "Encoding"


def test_built_in_encoding_cos_object_raises() -> None:
    # Built-in encodings have no PDF representation.
    enc = BuiltInEncoding({0x41: "A"})
    with pytest.raises(NotImplementedError):
        enc.get_cos_object()


def test_mac_os_roman_extends_mac_roman() -> None:
    # MacOSRomanEncoding layers 16 vendor-specific glyph differences on top
    # of MacRoman. Both are distinct singletons; both inherit from Encoding.
    assert MacOSRomanEncoding.INSTANCE is not MacRomanEncoding.INSTANCE
    assert isinstance(MacOSRomanEncoding.INSTANCE, Encoding)
    # MacOSRoman maps every MacRoman code (no MacRoman entry is removed),
    # though a handful of slots get a different glyph name (e.g. 0o333 is
    # /currency in MacRoman and /Euro in MacOSRoman).
    mr = MacRomanEncoding.INSTANCE.get_code_to_name_map()
    mosr = MacOSRomanEncoding.INSTANCE.get_code_to_name_map()
    for code in mr:
        assert code in mosr
    # The MacOSRoman extension is strictly larger.
    assert len(mosr) > len(mr)
    # Per upstream's vendor-specific overlay 0o333 is /Euro in MacOSRoman.
    assert MacOSRomanEncoding.INSTANCE.get_name(0o333) == "Euro"
    # MacRoman has /currency at that slot.
    assert MacRomanEncoding.INSTANCE.get_name(0o333) == "currency"


def test_distinct_dictionary_encodings_dont_share_identity() -> None:
    a = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    b = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    # No structural equality override -> two distinct identities even though
    # the on-disk dictionaries would be equal.
    assert a is not b
    # The underlying COS dicts are also distinct.
    assert a.get_cos_object() is not b.get_cos_object()


def test_get_instance_none_input_returns_none() -> None:
    assert Encoding.get_instance(None) is None


def test_get_instance_unknown_name_returns_none() -> None:
    assert Encoding.get_instance("DoesNotExistEncoding") is None
    assert Encoding.get_instance(COSName.get_pdf_name("Nope")) is None


def test_predicate_predefined_vs_font_specific_disjoint() -> None:
    # Each encoding satisfies at most one classifier.
    for _, inst in _PREDEFINED_SINGLETONS:
        assert not (inst.is_predefined() and inst.is_font_specific())


def test_dictionary_encoding_predicates() -> None:
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding")
    )
    # DictionaryEncoding is neither predefined nor font-specific.
    assert enc.is_predefined() is False
    assert enc.is_font_specific() is False
