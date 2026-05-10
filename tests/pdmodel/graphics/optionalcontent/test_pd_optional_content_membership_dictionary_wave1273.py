"""Wave 1273 — alternate camelCase split aliases for /OCGs accessors.

Upstream ``getOCGs`` / ``setOCGs`` admit two reasonable snake-case
splits depending on whether the boundary is taken at every uppercase
character (``get_o_cgs``) or on word boundaries (``get_oc_gs``). Both
spellings exist in ported call sites; the dictionary keeps them
aliased to the canonical :meth:`get_o_cgs` / :meth:`set_o_cgs` so
either form resolves.
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.optionalcontent import PDOptionalContentGroup
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    PDOptionalContentMembershipDictionary,
)


def _group(name: str) -> PDOptionalContentGroup:
    return PDOptionalContentGroup(name)


def test_get_oc_gs_alias_returns_same_as_get_o_cgs() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a, b = _group("A"), _group("B")
    ocmd.set_o_cgs([a, b])

    via_alt = ocmd.get_oc_gs()
    via_canon = ocmd.get_o_cgs()
    assert [g.get_name() for g in via_alt] == [g.get_name() for g in via_canon]
    assert len(via_alt) == 2


def test_set_oc_gs_alias_writes_through_to_o_cgs() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = _group("A")
    ocmd.set_oc_gs([a])

    assert len(ocmd.get_o_cgs()) == 1
    assert ocmd.get_o_cgs()[0].get_name() == "A"
    # And the alt accessor sees the same value.
    assert len(ocmd.get_oc_gs()) == 1


def test_get_oc_gs_empty_when_no_ocgs_entry() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_oc_gs() == []
