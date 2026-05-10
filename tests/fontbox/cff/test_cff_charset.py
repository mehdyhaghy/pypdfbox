"""Hand-written tests for the abstract :class:`CFFCharset`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff import CFFCharset, CFFCharsetCID, CFFCharsetType1


def test_cff_charset_is_abstract() -> None:
    with pytest.raises(TypeError):
        CFFCharset()  # type: ignore[abstract]


def test_concrete_subclasses_register() -> None:
    assert issubclass(CFFCharsetCID, CFFCharset)
    assert issubclass(CFFCharsetType1, CFFCharset)


def test_required_methods_present() -> None:
    expected = {
        "is_cid_font",
        "add_sid",
        "add_cid",
        "get_sid_for_gid",
        "get_gid_for_sid",
        "get_gid_for_cid",
        "get_sid",
        "get_name_for_gid",
        "get_cid_for_gid",
    }
    assert expected.issubset(set(dir(CFFCharset)))
