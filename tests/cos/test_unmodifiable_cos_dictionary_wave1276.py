"""Wave 1276 — :class:`UnmodifiableCOSDictionary.set_need_to_be_updated`
parity.

Mirrors upstream ``UnmodifiableCOSDictionary.setNeedToBeUpdated``
(``UnmodifiableCOSDictionary.java`` L40-44) which unconditionally
throws ``UnsupportedOperationException``. We raise :class:`RuntimeError`
per the project Java→Python exception mapping.

The strict snake_case rendering of upstream's
``setNeedToBeUpdated`` is ``set_need_to_be_updated`` (singular "need");
the parent ``COSDictionary``'s preferred Python spelling is
``set_needs_to_be_updated`` (plural). Both should reject on the
read-only view.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.cos.unmodifiable_cos_dictionary import UnmodifiableCOSDictionary


def _readonly() -> UnmodifiableCOSDictionary:
    return UnmodifiableCOSDictionary(COSDictionary())


def test_set_need_to_be_updated_raises_runtime_error() -> None:
    unmodifiable = _readonly()
    with pytest.raises(RuntimeError, match="setNeedToBeUpdated"):
        unmodifiable.set_need_to_be_updated(True)


def test_set_need_to_be_updated_raises_with_false_too() -> None:
    # Upstream's UnsupportedOperationException ignores the flag value;
    # both True and False must raise.
    unmodifiable = _readonly()
    with pytest.raises(RuntimeError):
        unmodifiable.set_need_to_be_updated(False)


def test_module_exports_unmodifiable_cos_dictionary() -> None:
    from pypdfbox.cos.unmodifiable_cos_dictionary import (
        UnmodifiableCOSDictionary as Imported,
    )

    assert Imported is UnmodifiableCOSDictionary


def test_unmodifiable_extends_cos_dictionary() -> None:
    assert issubclass(UnmodifiableCOSDictionary, COSDictionary)


def test_plural_spelling_still_rejected() -> None:
    # The parent class's set_needs_to_be_updated (plural) also rejects;
    # this guards against a regression where the subclass shadow accidentally
    # un-rejected it.
    unmodifiable = _readonly()
    with pytest.raises(TypeError):
        unmodifiable.set_needs_to_be_updated(True)
