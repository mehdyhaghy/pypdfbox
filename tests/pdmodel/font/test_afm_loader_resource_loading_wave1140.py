from __future__ import annotations

from tests.pdmodel.font.test_afm_loader_resource_loading import _MemoryAfmResource


def test_memory_afm_resource_stringifies_to_fake_path() -> None:
    resource = _MemoryAfmResource(b"")

    assert str(resource) == "/not/a/real/filesystem/Helvetica.afm"
