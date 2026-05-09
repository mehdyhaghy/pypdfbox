from __future__ import annotations

import pytest

from tests.pdmodel.font import test_pd_cid_font as cid_font_tests


def test_base_class_get_subtype_helper_raises_when_method_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cid_font_tests.PDCIDFont, "get_subtype", lambda self: "patched")

    with pytest.raises(
        AssertionError,
        match="PDCIDFont.get_subtype\\(\\) must raise NotImplementedError",
    ):
        cid_font_tests.test_cid_font_base_class_get_subtype_is_abstract()
