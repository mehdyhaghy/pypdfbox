"""Wave 1395 — close ``CharStringCommand.get_value`` branches.

Targets lines 142-145 of ``pypdfbox/fontbox/cff/char_string_command.py``:

* ``get_value()`` returns ``_KEY_UNKNOWN`` (99) for the unknown
  singleton (no underlying ``Key``).
* ``get_value()`` returns ``key.hash_value`` when a Type 1 keyword is
  populated.
* ``get_value()`` returns ``key.hash_value`` when a Type 2 keyword is
  populated.

Mirrors upstream ``CharStringCommand.getValue()``
(``CharStringCommand.java:112``) which always returns the merged
operator hash (99 for ``UNKNOWN``).
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.char_string_command import (
    _COMMAND_UNKNOWN as COMMAND_UNKNOWN_SINGLETON,
)
from pypdfbox.fontbox.cff.char_string_command import (
    _KEY_UNKNOWN,
    CharStringCommand,
)
from pypdfbox.fontbox.cff.type1_keyword import Type1KeyWord
from pypdfbox.fontbox.cff.type2_keyword import Type2KeyWord


def test_get_value_returns_key_unknown_for_unknown_singleton() -> None:
    """Unknown command — get_value() returns 99 (the spec sentinel)."""
    assert COMMAND_UNKNOWN_SINGLETON.get_value() == _KEY_UNKNOWN
    assert COMMAND_UNKNOWN_SINGLETON.get_key() is None


def test_get_value_returns_type2_keyword_hash_when_present() -> None:
    """Common case — a Type 2 keyword's key.hash_value is returned.

    RMOVETO has b0 == 21 (single-byte op), present in both Type 1
    and Type 2 — get_value() should match the Type 2 hash."""
    cmd = CharStringCommand.get_instance(21)
    assert cmd.get_type2_key_word() is Type2KeyWord.RMOVETO
    assert cmd.get_value() == Type2KeyWord.RMOVETO.key.hash_value


def test_get_value_returns_type1_keyword_hash_for_type1_only_op() -> None:
    """Type-1-only operator (HSBW = b0 13) — get_value() returns the
    Type-1 keyword's key.hash_value via the get_key() fallthrough."""
    cmd = CharStringCommand.get_instance(13)
    # Sanity: HSBW has no Type-2 equivalent.
    assert cmd.get_type2_key_word() is None
    assert cmd.get_type1_key_word() is Type1KeyWord.HSBW
    assert cmd.get_value() == Type1KeyWord.HSBW.key.hash_value
