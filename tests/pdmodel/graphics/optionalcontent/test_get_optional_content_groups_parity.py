"""Upstream-spelling alias parity for
``PDOptionalContentProperties.get_optional_content_groups()``.

Apache PDFBox exposes both ``getGroup``/``getGroupNames`` and the
collection-shaped ``getOptionalContentGroups()`` returning every OCG. The
pypdfbox port already had ``get_groups()``; this verifies the
upstream-spelled alias resolves to the same list of wrappers.
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)


def test_get_optional_content_groups_empty() -> None:
    props = PDOptionalContentProperties()
    assert props.get_optional_content_groups() == []


def test_get_optional_content_groups_returns_each_added() -> None:
    props = PDOptionalContentProperties()
    g1 = PDOptionalContentGroup("Layer 1")
    g2 = PDOptionalContentGroup("Layer 2")
    props.add_group(g1)
    props.add_group(g2)

    out = props.get_optional_content_groups()
    assert [g.get_name() for g in out] == ["Layer 1", "Layer 2"]
    assert all(isinstance(g, PDOptionalContentGroup) for g in out)


def test_get_optional_content_groups_matches_get_groups() -> None:
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("A"))
    props.add_group(PDOptionalContentGroup("B"))

    canonical = [g.get_name() for g in props.get_groups()]
    upstream_alias = [
        g.get_name() for g in props.get_optional_content_groups()
    ]
    assert canonical == upstream_alias
