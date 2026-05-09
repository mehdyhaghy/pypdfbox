from __future__ import annotations

import sys

import pytest

import tests.pdmodel.test_pd_page_content_stream_wave1104 as wave1104
import tests.pdmodel.test_pd_page_content_stream_wave1172 as wave1172


def test_wave1182_wave1172_cleanup_pops_modules_missing_at_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    for name in wave1104._FACTORY_MODULE_NAMES:
        monkeypatch.delitem(sys.modules, name, raising=False)

    wave1172.test_wave1172_wave1162_cleanup_pops_modules_missing_at_entry(tmp_path)

    for name in wave1104._FACTORY_MODULE_NAMES:
        assert name not in sys.modules
