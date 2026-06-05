"""Port of the numeric helpers from ``org.apache.pdfbox.jbig2.util.Utils``.

Only the ``clamp`` / ``floor`` / ``ceil`` / ``round_`` helpers used by the image
resampling pipeline (:mod:`pypdfbox.jbig2.image.resizer`) are ported here. The
``Rectangle2D``-shaped helpers (``enlargeRectToGrid`` / ``dilateRect``) belong to
callers not yet ported and are left out.

Upstream's ``floor`` / ``round`` / ``ceil`` are *fast* approximations that are
only correct for the working range ``|x| < BIG_ENOUGH_INT`` (16384); the resize
pipeline always stays well inside that range. The constants and the exact
integer arithmetic are reproduced verbatim so the discrete sample indices match
the Java reference bit-for-bit.

Java's ``(int)`` truncates toward zero; Python's ``int()`` does the same for the
``float`` operands produced here, so the casts map directly.
"""

from __future__ import annotations

_BIG_ENOUGH_INT = 16 * 1024
_BIG_ENOUGH_FLOOR = float(_BIG_ENOUGH_INT)
_BIG_ENOUGH_ROUND = _BIG_ENOUGH_INT + 0.5


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Mirror ``Utils.clamp`` — ``min(max, max(value, min))``."""
    return min(maximum, max(value, minimum))


def floor(x: float) -> int:
    """Mirror ``Utils.floor`` — fast floor valid for ``|x| < 16384``."""
    return int(x + _BIG_ENOUGH_FLOOR) - _BIG_ENOUGH_INT


def round_(x: float) -> int:
    """Mirror ``Utils.round`` — fast round valid for ``|x| < 16384``."""
    return int(x + _BIG_ENOUGH_ROUND) - _BIG_ENOUGH_INT


def ceil(x: float) -> int:
    """Mirror ``Utils.ceil`` — fast ceil valid for ``|x| < 16384``."""
    return _BIG_ENOUGH_INT - int(_BIG_ENOUGH_FLOOR - x)
