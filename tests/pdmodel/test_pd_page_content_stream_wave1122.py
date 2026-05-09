from __future__ import annotations

import sys
from types import ModuleType

import tests.pdmodel.test_pd_page_content_stream_wave1104 as wave1104
import tests.pdmodel.test_pd_page_content_stream_wave1113 as wave1113


def test_wave1122_wave1113_cleanup_handles_modules_missing_at_entry(tmp_path) -> None:
    saved: dict[str, ModuleType | None] = {
        name: sys.modules.get(name) for name in wave1104._FACTORY_MODULE_NAMES
    }
    try:
        for name in wave1104._FACTORY_MODULE_NAMES:
            sys.modules.pop(name, None)

        wave1113.test_wave1113_wave1104_cleanup_pops_modules_that_started_missing(
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
