"""Wave 1272: parity coverage for ``Revisions.get_object`` and
``Revisions.to_string`` upstream-named accessors."""

from __future__ import annotations

from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import (
    Revisions,
)


def test_get_object_matches_get_object_at() -> None:
    revs: Revisions[str] = Revisions()
    revs.add_object("alpha", 1)
    revs.add_object("beta", 2)
    assert revs.get_object(0) == revs.get_object_at(0) == "alpha"
    assert revs.get_object(1) == revs.get_object_at(1) == "beta"


def test_to_string_matches_repr_format() -> None:
    revs: Revisions[str] = Revisions()
    revs.add_object("alpha", 1)
    revs.add_object("beta", 0)
    rendered = revs.to_string()
    assert rendered.startswith("{")
    assert rendered.endswith("}")
    assert "object=alpha" in rendered
    assert "revisionNumber=1" in rendered
    assert rendered == repr(revs)


def test_to_string_empty_revisions() -> None:
    assert Revisions[str]().to_string() == "{}"
