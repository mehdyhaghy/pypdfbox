from __future__ import annotations

import builtins

from tests.fontbox.cff import test_cff_helper_tail_wave856 as wave856_mod


def test_wave1216_fake_import_error_delegates_other_imports() -> None:
    fake_import = wave856_mod._fake_import_error(builtins.__import__)

    math_module = fake_import("math")

    assert math_module.sqrt(9) == 3.0
