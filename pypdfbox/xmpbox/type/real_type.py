from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ...cos.cos_float import _float32_or_inf, float_to_string
from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata

# Java ``Float.parseFloat`` grammar (java.lang.Float javadoc): optional leading
# / trailing whitespace, optional sign, then either ``NaN`` / ``Infinity``
# (exact case; a sign is permitted before ``Infinity`` and ``NaN``), or a
# decimal / hexadecimal floating-point literal optionally followed by a single
# ``f`` / ``F`` / ``d`` / ``D`` type suffix. Notably it does NOT accept the
# lower-case ``inf`` / ``nan`` spellings (or ``infinity``) that Python's bare
# ``float()`` tolerates, nor digit-group underscores. We model the grammar with
# a regex so the acceptance set matches upstream exactly, then hand the matched
# numeric core to Python's ``float`` (after stripping the optional type suffix
# and normalising the ``Infinity`` / ``NaN`` words to Python spellings).
_DEC_SIG = r"(?:\d+\.?\d*|\.\d+)"
_DEC_FLOAT = rf"{_DEC_SIG}(?:[eE][+-]?\d+)?"
_HEX_SIG = r"(?:0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)[pP][+-]?\d+)"
_FLOAT_RE = re.compile(
    rf"^[+-]?(?:Infinity|NaN|(?:{_DEC_FLOAT}|{_HEX_SIG})[fFdD]?)$"
)


def _parse_java_float(text: str) -> float:
    """Parse ``text`` exactly like Java ``Float.parseFloat``.

    Raises :class:`ValueError` for any spelling Java's ``Float.parseFloat``
    would reject (lower-case ``inf`` / ``nan``, digit underscores, an empty
    string, etc.). On success the result is *not yet* narrowed to single
    precision — the caller does that with :func:`_float32_or_inf`.
    """
    stripped = text.strip()
    if not _FLOAT_RE.match(stripped):
        raise ValueError(f"not a Java float: {text!r}")
    sign = ""
    body = stripped
    if body[:1] in {"+", "-"}:
        sign, body = (body[0] if body[0] == "-" else ""), body[1:]
    if body == "Infinity":
        return float(f"{sign}inf")
    if body == "NaN":
        return float("nan")
    is_hex = body.lower().startswith("0x")
    # Drop the optional Java type suffix (f/F/d/D), which Python rejects. For a
    # hex literal a trailing ``d``/``D`` could be a hex digit, but the binary
    # exponent (``p``) is mandatory and ends the digit run, so any f/F/d/D after
    # it is unambiguously the type suffix.
    if not is_hex:
        if body[-1:] in {"f", "F", "d", "D"}:
            body = body[:-1]
        return float(f"{sign}{body}")
    if body[-1:] in {"f", "F", "d", "D"}:
        body = body[:-1]
    # Python's ``float.fromhex`` parses Java's hex-float grammar (``0x1.8p1``).
    return float.fromhex(f"{sign}{body}")


class RealType(AbstractSimpleProperty):
    """
    XMP Real (floating point) simple property.

    Ported from ``org.apache.xmpbox.type.RealType``. Accepts ``float`` /
    ``int`` (treated as float) or a numeric string. Upstream stores the value
    in a Java ``float`` field and parses strings with ``Float.parseFloat``, so
    the stored value is IEEE-754 *single* precision and the accepted string
    grammar is ``Float.parseFloat``'s — not Python's looser ``float()``. The
    port narrows every value to single precision (wave 1535) and renders
    :meth:`get_string_value` byte-for-byte like Java ``Float.toString`` via
    :func:`pypdfbox.cos.cos_float.float_to_string`.
    """

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None,
        prefix: str | None,
        property_name: str,
        value: Any,
    ) -> None:
        super().__init__(metadata, namespace_uri, prefix, property_name, value)

    def set_value(self, value: Any) -> None:
        if isinstance(value, bool):
            raise ValueError(f"Value given is not allowed for the Real type: {value!r}")
        if isinstance(value, (float, int)):
            self._real_value = _float32_or_inf(float(value))
        elif isinstance(value, str):
            try:
                parsed = _parse_java_float(value)
            except ValueError as exc:
                raise ValueError(
                    f"Value given is not allowed for the Real type: {value!r}"
                ) from exc
            self._real_value = _float32_or_inf(parsed)
        else:
            raise ValueError(f"Value given is not allowed for the Real type: {value!r}")

    def get_value(self) -> float:
        return self._real_value

    def get_string_value(self) -> str:
        # Mirror Java Float.toString used by upstream RealType.getStringValue.
        return float_to_string(self._real_value)
