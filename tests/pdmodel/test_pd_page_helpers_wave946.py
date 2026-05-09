from __future__ import annotations

import pytest

from pypdfbox.cos import COSObject, COSStream
from pypdfbox.pdmodel import PDPage
from tests.pdmodel import test_pd_page as page_mod


def test_wave946_counting_cache_color_space_remover_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def purge_color_space(self: PDPage) -> None:
        self.get_resource_cache().remove_color_space(COSObject(44, resolved=COSStream()))

    monkeypatch.setattr(PDPage, "remove_page_resource_from_cache", purge_color_space)

    with pytest.raises(AssertionError):
        page_mod.test_remove_page_resource_from_cache_purges_indirect_objects()


def test_wave946_inherited_resource_cache_xobject_remover_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def purge_xobject(self: PDPage) -> None:
        self.get_resource_cache().remove_x_object(COSObject(45, resolved=COSStream()))

    monkeypatch.setattr(PDPage, "remove_page_resource_from_cache", purge_xobject)

    with pytest.raises(AssertionError):
        page_mod.test_remove_page_resource_from_cache_skips_inherited_resources()
