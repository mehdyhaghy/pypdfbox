from __future__ import annotations

from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo


def test_to_string_formats_three_arg_constructor() -> None:
    """Mirror upstream ``PDCIDSystemInfo.toString()`` —
    ``"<registry>-<ordering>-<supplement>"``."""
    info = PDCIDSystemInfo("Adobe", "Japan1", 6)
    assert info.to_string() == "Adobe-Japan1-6"


def test_to_string_matches_str() -> None:
    """``to_string`` and ``__str__`` stay in lock-step."""
    info = PDCIDSystemInfo("Adobe", "Identity", 0)
    assert info.to_string() == str(info)


def test_to_string_renders_missing_fields_as_null() -> None:
    """When ``/Registry`` / ``/Ordering`` are absent, the upstream Java
    ``String.valueOf(null)`` would render them as ``"null"``; pypdfbox
    matches that."""
    info = PDCIDSystemInfo()  # empty wrapper
    assert info.to_string() == "null-null-0"
