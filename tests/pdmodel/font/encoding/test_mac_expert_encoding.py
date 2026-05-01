"""Hand-written tests for the pdmodel ``MacExpertEncoding`` wrapper.

Mac Expert is the typographic-extras encoding (small caps, ligatures,
old-style figures) — it does NOT cover the regular ASCII range.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import Encoding, MacExpertEncoding


def test_singleton_identity():
    assert MacExpertEncoding.INSTANCE is MacExpertEncoding.INSTANCE
    assert isinstance(MacExpertEncoding.INSTANCE, MacExpertEncoding)


def test_encoding_name():
    assert MacExpertEncoding.INSTANCE.get_encoding_name() == "MacExpertEncoding"


def test_get_cos_object():
    cos = MacExpertEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "MacExpertEncoding"


def test_get_cos_object_returns_interned_constant():
    # Upstream returns ``COSName.MAC_EXPERT_ENCODING`` directly — verify the
    # pypdfbox override yields the same interned ``COSName`` constant rather
    # than minting a fresh instance on every call.
    cos = MacExpertEncoding.INSTANCE.get_cos_object()
    assert cos is COSName.MAC_EXPERT_ENCODING  # type: ignore[attr-defined]


def test_space_is_mapped():
    # Space is one of the few common entries.
    assert MacExpertEncoding.INSTANCE.get_name(0x20) == "space"


def test_typographic_glyphs_are_present():
    # Mac Expert includes ligatures and small caps; verify the encoding has
    # at least some characteristic entries (exact codes vary by table).
    enc = MacExpertEncoding.INSTANCE
    name_to_code = enc.get_name_to_code_map()
    # Smallcaps "asuperior" is a classic Mac Expert glyph.
    assert "asuperior" in name_to_code or len(name_to_code) > 100


def test_factory_resolves_to_singleton():
    assert Encoding.get_instance("MacExpertEncoding") is MacExpertEncoding.INSTANCE
    assert Encoding.get_instance(COSName.get_pdf_name("MacExpertEncoding")) is MacExpertEncoding.INSTANCE


def test_uppercase_a_is_not_in_expert():
    # Mac Expert encoding does NOT contain regular "A" — it carries small caps
    # and ligatures, not the basic Latin alphabet.
    assert MacExpertEncoding.INSTANCE.contains_name("A") is False


def test_table_is_non_empty():
    enc = MacExpertEncoding.INSTANCE
    assert len(enc.get_code_to_name_map()) > 0
