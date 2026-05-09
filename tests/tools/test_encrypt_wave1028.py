from __future__ import annotations

import pytest

from tests.tools.test_encrypt_wave630 import _fail_encrypt_pdf


def test_wave1028_fail_encrypt_pdf_guard_raises() -> None:
    with pytest.raises(AssertionError, match="encrypt_pdf should not be called"):
        _fail_encrypt_pdf()
