"""Parity tests for the nested-enum ``valueOf`` helpers.

Upstream PDFBox accepts a ``COSName`` (which may be ``null``) in
``BaseState.valueOf`` and ``PDOptionalContentGroup.RenderState.valueOf``.
These helpers verify the pypdfbox ports match the documented null-handling
contract: ``BaseState.value_of(None)`` returns :attr:`BaseState.ON`,
``RenderState.value_of(None)`` returns ``None``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    RenderState,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    BaseState,
)


def test_base_state_value_of_none_returns_on() -> None:
    # Upstream: BaseState.valueOf((COSName) null) returns BaseState.ON.
    assert BaseState.value_of(None) is BaseState.ON


def test_base_state_value_of_accepts_cos_name() -> None:
    assert BaseState.value_of(COSName.get_pdf_name("ON")) is BaseState.ON
    assert BaseState.value_of(COSName.get_pdf_name("OFF")) is BaseState.OFF
    assert (
        BaseState.value_of(COSName.get_pdf_name("Unchanged"))
        is BaseState.UNCHANGED
    )


def test_base_state_value_of_unknown_still_raises() -> None:
    with pytest.raises(ValueError):
        BaseState.value_of("Bogus")


def test_render_state_value_of_none_returns_none() -> None:
    # Upstream: RenderState.valueOf((COSName) null) returns null.
    assert RenderState.value_of(None) is None


def test_render_state_value_of_accepts_cos_name() -> None:
    assert RenderState.value_of(COSName.get_pdf_name("ON")) is RenderState.ON
    assert RenderState.value_of(COSName.get_pdf_name("OFF")) is RenderState.OFF


def test_render_state_value_of_unknown_still_raises() -> None:
    with pytest.raises(ValueError):
        RenderState.value_of("Bogus")
