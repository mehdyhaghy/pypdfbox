"""Wave 1403 — branch round-out for :class:`FDArray`.

Closes the partial arc ``[180,182]`` — the ``isinstance(raw, dict)``
False branch in :meth:`FDArray.get_font_name`: when a Font DICT has no
``FontName`` attribute and its ``rawDict`` is not a mapping, the
rawDict-lookup is skipped and the empty-string fallback is returned.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.fd_array import FDArray


class _FontNoNameNonDictRaw:
    """Font DICT with no ``FontName`` and a non-dict ``rawDict``."""

    rawDict = None  # noqa: N815 — fontTools attribute name


def test_get_font_name_non_dict_raw_returns_empty() -> None:
    """A Font DICT whose ``rawDict`` is not a dict takes the
    ``isinstance(raw, dict)`` False arc ([180,182]); ``name`` stays
    ``None`` and the accessor returns the empty string."""
    arr = FDArray.from_fonttools([_FontNoNameNonDictRaw()])
    assert arr.get_font_name(0) == ""
