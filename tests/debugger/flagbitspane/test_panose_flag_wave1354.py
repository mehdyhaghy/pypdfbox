"""Wave 1354 tail-sweep: cover the static-helper raise in PanoseFlag.

``PanoseFlag.get_panose_bytes`` is reachable from both the constructor
(which guards against non-COSString /Panose at line 178) and from
external callers using it as a static utility. The constructor branch
short-circuits before line 276, so this test exercises the static
helper directly with a non-COSString entry.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.flagbitspane.panose_flag import PanoseFlag

_PANOSE = COSName.get_pdf_name("Panose")


def test_get_panose_bytes_raises_on_non_string() -> None:
    d = COSDictionary()
    d.set_item(_PANOSE, COSName.get_pdf_name("oops"))
    with pytest.raises(TypeError, match="COSString"):
        PanoseFlag.get_panose_bytes(d)
