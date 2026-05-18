"""Wave 1354 tail-sweep for the streampane tooltip helpers.

Covers:

* ``ColorToolTip.extract_color_values`` empty-words branch (line 55 in
  ``color_tool_tip.py``).
* ``KToolTip.get_icc_color_space`` success branch where the profile is
  present (line 87 in ``k_tool_tip.py``).
"""

from __future__ import annotations

from pypdfbox.debugger.streampane.tooltip import ColorToolTip, KToolTip


def test_extract_color_values_empty_row_returns_none() -> None:
    # An empty (or whitespace-only) row produces no words at all — the
    # upstream ``words.isEmpty()`` guard returns null in that case.
    assert ColorToolTip.extract_color_values("") is None
    assert ColorToolTip.extract_color_values("   \t   ") is None


def test_get_icc_color_space_returns_profile_when_available(monkeypatch) -> None:
    tip = KToolTip("0 0 0 0 k")
    # Force the upstream "profile loaded" branch by stubbing get_icc_profile.
    sentinel = object()
    monkeypatch.setattr(tip, "get_icc_profile", lambda: sentinel)
    assert tip.get_icc_color_space() is sentinel
