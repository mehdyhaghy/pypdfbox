from __future__ import annotations

import sys
from types import ModuleType

import tests.pdmodel.test_pd_page_content_stream_wave1104 as wave1104
import tests.pdmodel.test_pd_page_content_stream_wave1162 as wave1162


def test_wave1172_wave1162_cleanup_pops_modules_missing_at_entry(tmp_path) -> None:
    saved: dict[str, ModuleType | None] = {
        name: sys.modules.get(name) for name in wave1104._FACTORY_MODULE_NAMES
    }
    try:
        for name in wave1104._FACTORY_MODULE_NAMES:
            sys.modules.pop(name, None)

        wave1162.test_wave1162_wave1152_cleanup_pops_modules_missing_at_entry(
            tmp_path
        )

        for name in wave1104._FACTORY_MODULE_NAMES:
            assert name not in sys.modules
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
