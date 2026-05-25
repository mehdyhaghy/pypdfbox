"""Wave 1403 — branch round-out for :class:`CFFCIDFont`.

Closes the partial arc ``[285,292]`` — the ``isinstance(selector, str)``
False branch in :meth:`CFFCIDFont._coerce_to_cid`: a selector that is
neither an ``int`` nor a ``str`` falls straight through to the ``-1``
sentinel return.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont


def test_coerce_to_cid_non_int_non_str_returns_minus_one() -> None:
    """A float selector is neither int nor str → the
    ``isinstance(selector, str)`` False arc ([285,292]) returns -1."""
    assert CFFCIDFont._coerce_to_cid(3.5) == -1  # type: ignore[arg-type]


def test_coerce_to_cid_none_returns_minus_one() -> None:
    """``None`` selector also takes the non-str fall-through ([285,292])."""
    assert CFFCIDFont._coerce_to_cid(None) == -1  # type: ignore[arg-type]
