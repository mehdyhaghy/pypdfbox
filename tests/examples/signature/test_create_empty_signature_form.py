"""Tests for ``CreateEmptySignatureForm``."""

from __future__ import annotations

import pytest

from pypdfbox.examples.signature.create_empty_signature_form import (
    CreateEmptySignatureForm,
)


def test_static_helper_cannot_be_instantiated():
    with pytest.raises(RuntimeError):
        CreateEmptySignatureForm()


def test_create_method_is_callable():
    assert callable(CreateEmptySignatureForm.create)
