from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_mapper import DefaultFontMapper


class _BrokenNameFont:
    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    def get_name(self) -> str:
        raise self._failure


class _BadDescriptor:
    def __init__(self, flags: Any) -> None:
        self._flags = flags

    def get_flags(self) -> Any:
        return self._flags


def test_cid_font_mapping_repr_falls_back_when_otf_name_raises_oserror() -> None:
    mapping = CIDFontMapping(_BrokenNameFont(OSError("broken")), None, False)

    assert repr(mapping) == (
        "CIDFontMapping(font='_BrokenNameFont', ttf=None, is_fallback=False)"
    )


def test_cid_font_mapping_repr_falls_back_when_ttf_name_missing() -> None:
    ttf = _BrokenNameFont(AttributeError("missing"))
    mapping = CIDFontMapping(None, ttf, True)  # type: ignore[arg-type]

    assert repr(mapping) == (
        "CIDFontMapping(font=None, ttf='_BrokenNameFont', is_fallback=True)"
    )


def test_default_mapper_bad_descriptor_flags_use_plain_helvetica() -> None:
    mapping = DefaultFontMapper().get_font_box_font(
        "DefinitelyNotStandard14",
        _BadDescriptor("not-an-int"),  # type: ignore[arg-type]
    )

    assert mapping is not None
    assert mapping.is_fallback() is True
    assert mapping.get_font().get_name() == "Helvetica"
