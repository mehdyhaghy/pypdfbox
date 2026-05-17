"""Wave 1345 coverage-boost tests for :class:`CharStringCommand`.

Targets the residual missing branches:

* lines 125-129 — :meth:`get_key` falling through to the type-1 keyword
  (only that one set) and finally returning ``None`` when neither
  keyword is populated.
* line 188 — the :attr:`name` property's type-1-only arm.

Constructing a command with neither key word filled is achieved via the
``KEY_UNKNOWN`` (b0=99) singleton that the module exposes as
``_COMMAND_UNKNOWN``. For the type-1-only case we look up a Type 1
operator that has no Type 2 counterpart (e.g. ``HSBW`` (b0=13), present
in Type1KeyWord only).
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.char_string_command import (
    _COMMAND_UNKNOWN as COMMAND_UNKNOWN_SINGLETON,
)
from pypdfbox.fontbox.cff.char_string_command import (
    CharStringCommand,
)
from pypdfbox.fontbox.cff.type1_keyword import Key, Type1KeyWord
from pypdfbox.fontbox.cff.type2_keyword import Type2KeyWord


def test_unknown_command_singleton_returns_none_for_get_key_and_name() -> None:
    """``CharStringCommand(_KEY_UNKNOWN, 0)`` has neither type-1 nor type-2
    keyword set — :meth:`get_key` and :attr:`name` both return ``None``."""
    cmd = COMMAND_UNKNOWN_SINGLETON
    assert cmd.get_type1_key_word() is None
    assert cmd.get_type2_key_word() is None
    assert cmd.get_key() is None
    assert cmd.name is None


def _type1_only_b0() -> int:
    """Return a single-byte b0 that resolves to a Type 1 operator without
    a Type 2 counterpart, so the constructed command has type1_key_word
    set but type2_key_word ``None``."""
    for b0 in range(0, 32):
        t1 = Type1KeyWord.value_of_key(b0)
        t2 = Type2KeyWord.value_of_key(b0)
        if t1 is not None and t2 is None:
            return b0
    msg = "no Type1-only single-byte operator found"
    raise AssertionError(msg)


def test_get_key_falls_through_to_type1_when_type2_is_none() -> None:
    """Type-1-only command — :meth:`get_key` returns the Type-1 keyword's
    ``key`` (line 128)."""
    b0 = _type1_only_b0()
    cmd = CharStringCommand(b0)
    assert cmd.get_type1_key_word() is not None
    assert cmd.get_type2_key_word() is None
    key = cmd.get_key()
    assert isinstance(key, Key)
    # Mirrors the type-1 keyword's own ``.key`` attribute.
    assert key is cmd.get_type1_key_word().key


def test_name_property_falls_through_to_type1_when_type2_is_none() -> None:
    """Type-1-only command — :attr:`name` returns the Type 1 keyword's
    mnemonic (line 188)."""
    b0 = _type1_only_b0()
    cmd = CharStringCommand(b0)
    assert cmd.get_type2_key_word() is None
    assert cmd.name == cmd.get_type1_key_word().name


def test_repr_round_trips_via_to_string() -> None:
    """``repr(cmd)`` wraps ``to_string()`` in ``CharStringCommand(...)``
    (line 151)."""
    cmd = CharStringCommand.COMMAND_RLINETO
    assert repr(cmd) == f"CharStringCommand({cmd.to_string()!r})"


def test_get_key_returns_type2_key_when_type2_keyword_populated() -> None:
    """When the Type 2 keyword is present, :meth:`get_key` returns its
    underlying :class:`Key` (line 126).

    COMMAND_RLINETO is a one-byte op present in BOTH Type 1 and Type 2
    keyword tables, so ``type2_key_word`` is populated and the Type 2
    arm wins per the upstream "Type 2 superset" semantics.
    """
    cmd = CharStringCommand.COMMAND_RLINETO
    assert cmd.get_type2_key_word() is not None
    assert cmd.get_key() is cmd.get_type2_key_word().key
