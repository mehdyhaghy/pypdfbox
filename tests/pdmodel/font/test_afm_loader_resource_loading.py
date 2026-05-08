from __future__ import annotations

from importlib import resources
from io import BytesIO
from typing import Any

import pytest

from pypdfbox.pdmodel.font import afm_loader


class _MemoryAfmResource:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.opened_modes: list[str] = []

    def __str__(self) -> str:
        return "/not/a/real/filesystem/Helvetica.afm"

    def open(self, mode: str = "r", *args: Any, **kwargs: Any) -> BytesIO:
        self.opened_modes.append(mode)
        assert mode == "rb"
        return BytesIO(self._payload)


class _MemoryAfmPackage:
    def __init__(self, resource: _MemoryAfmResource) -> None:
        self._resource = resource

    def joinpath(self, child: str) -> _MemoryAfmResource:
        assert child == "Helvetica.afm"
        return self._resource


def test_load_standard14_opens_importlib_resource_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    afm_bytes = (
        resources.files("pypdfbox.pdmodel.font.afm")
        .joinpath("Helvetica.afm")
        .read_bytes()
    )
    resource = _MemoryAfmResource(afm_bytes)

    def fake_files(package: str) -> _MemoryAfmPackage:
        assert package == "pypdfbox.pdmodel.font.afm"
        return _MemoryAfmPackage(resource)

    monkeypatch.setattr(afm_loader, "_CACHE", {})
    monkeypatch.setattr(afm_loader.__dict__["resources"], "files", fake_files)

    afm = afm_loader.load_standard14("Helvetica")

    assert afm.get_font_name() == "Helvetica"
    assert afm.get_character_width("A") == 667.0
    assert resource.opened_modes == ["rb"]
