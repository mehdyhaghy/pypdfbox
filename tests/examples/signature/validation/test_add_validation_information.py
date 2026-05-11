"""Tests for ``AddValidationInformation``."""

from __future__ import annotations

import pytest

from pypdfbox.examples.signature.validation.add_validation_information import (
    AddValidationInformation,
)


def test_construction():
    inst = AddValidationInformation()
    assert inst._cert_info is None


def test_missing_file_raises(tmp_path):
    inst = AddValidationInformation()
    with pytest.raises(FileNotFoundError):
        inst.validate_signature(tmp_path / "missing.pdf", tmp_path / "out.pdf")
