"""Abstract base for CFF encodings.

Mirrors upstream ``org.apache.fontbox.cff.CFFEncoding`` (PDFBox 3.0).
A CFF encoding is a Type 1-equivalent code -> glyph name mapping. This
class extends :class:`pypdfbox.fontbox.encoding.encoding.Encoding`, which
already provides ``add_character_encoding`` / ``get_name`` / ``get_code``
plus the dual code<->name dictionaries.

Subclasses populate the table at construction time via :meth:`add` (the
3-arg form takes a glyph ``name`` directly) or the 2-arg helper that
resolves the SID through the CFF Standard Strings table shipped with
fontTools (``fontTools.cffLib.cffStandardStrings``).
"""

from __future__ import annotations

from fontTools.cffLib import cffStandardStrings  # type: ignore[import-untyped]

from pypdfbox.fontbox.encoding.encoding import Encoding


class CFFEncoding(Encoding):
    """Abstract base mapping single-byte CFF codes to glyph names."""

    def __init__(self) -> None:
        super().__init__()

    # -- construction helpers --------------------------------------------

    def add(self, *args: object) -> None:  # type: ignore[override]
        """Add a (code, sid[, name]) entry to the encoding.

        Python lacks the static-method overloading the Java upstream
        relies on, so this single ``add`` dispatches by arity:

        - ``add(code, sid, name)`` — 3-arg form. Uses ``name`` directly,
          matching upstream ``add(int code, int sid, String name)``
          (``CFFEncoding.java:44``).
        - ``add(code, sid)`` — 2-arg form. Resolves the SID via the CFF
          Standard Strings table shipped with fontTools, matching
          upstream ``add(int code, int sid)``
          (``CFFEncoding.java:56``, ``protected``-for-subclasses in Java).

        Note: this deliberately does *not* fall through to the inherited
        ``Encoding.add(code, name)`` 2-arg signature; CFF encoding entries
        always carry a SID, even when discarded.
        """
        if len(args) == 2:
            code = _as_int(args[0], "code")
            sid = _as_int(args[1], "sid")
            name = _name_for_sid(sid)
        elif len(args) == 3:
            code = _as_int(args[0], "code")
            _ = _as_int(args[1], "sid")  # validated but unused (name explicit)
            raw_name = args[2]
            if not isinstance(raw_name, str):
                raise TypeError(
                    f"name must be str, got {type(raw_name).__name__}"
                )
            name = raw_name
        else:
            raise TypeError(
                f"CFFEncoding.add takes 2 or 3 positional arguments, got {len(args)}"
            )
        # Bypass any overridden add_character_encoding -> add chain by
        # poking the underlying maps directly. We replicate the
        # base-class add(code, name) "putIfAbsent" behavior on
        # name -> code so multi-name -> single-code is preserved.
        # pylint: disable=protected-access
        self._code_to_name[code] = name
        if name not in self._name_to_code:
            self._name_to_code[name] = code


def _as_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be int, got {type(value).__name__}")
    return value


def _name_for_sid(sid: int) -> str:
    """Return the glyph name for a CFF Standard String SID (0..390).

    Out-of-range SIDs degrade gracefully to ``".notdef"`` to match upstream
    ``CFFStandardString.getName(int)`` which throws on negative SIDs but
    we follow Python conventions here.
    """
    if 0 <= sid < len(cffStandardStrings):
        return cffStandardStrings[sid]
    return ".notdef"


__all__ = ["CFFEncoding"]
