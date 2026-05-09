from __future__ import annotations

import sys
from types import ModuleType

import tests.pdmodel.test_pd_page_content_stream as page_content_stream_tests

_FACTORY_MODULE_NAMES = (
    "pypdfbox.pdmodel.graphics.image.jpeg_factory",
    "pypdfbox.pdmodel.graphics.image.lossless_factory",
)


def test_wave1104_factory_stub_cleanup_pops_previously_missing_modules(tmp_path) -> None:
    saved: dict[str, ModuleType | None] = {
        name: sys.modules.get(name) for name in _FACTORY_MODULE_NAMES
    }
    try:
        for name in _FACTORY_MODULE_NAMES:
            sys.modules.pop(name, None)

        page_content_stream_tests.test_draw_image_path_without_factories_raises_not_implemented(
            tmp_path
        )

        for name in _FACTORY_MODULE_NAMES:
            assert name not in sys.modules
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
