"""Wave 1403 branch round-out for ``AcroFormDefaultsProcessor._ensure_font``.

Closes the False-branch arrow in
``pypdfbox/pdmodel/fixup/processor/acro_form_defaults_processor.py``:

* 118->120 — ``getattr(default_resources, "put", None)`` is None (the
  resources object exposes no ``put``), so the ``if put is not None`` arm
  is False and we skip the insert but still reach the
  ``set_need_to_be_updated`` propagation at line 120.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.fixup.processor.acro_form_defaults_processor import (
    AcroFormDefaultsProcessor,
)


class _CosObj:
    def __init__(self) -> None:
        self.needs_update: list[bool] = []

    def set_need_to_be_updated(self, flag: bool) -> None:
        self.needs_update.append(flag)


class _ResourcesWithoutPut:
    """Default-resources stub that intentionally lacks ``put`` but keeps a
    ``get_cos_object`` so the post-insert propagation still runs."""

    def __init__(self) -> None:
        self._cos = _CosObj()

    def get_cos_object(self) -> _CosObj:
        return self._cos


class _FontDictMissing:
    """Font dictionary stub: ``contains_key`` reports the key absent, so
    ``_ensure_font`` proceeds to build + insert the font."""

    def __init__(self) -> None:
        self.needs_update: list[bool] = []

    def contains_key(self, _name: object) -> bool:
        return False

    def set_need_to_be_updated(self, flag: bool) -> None:
        self.needs_update.append(flag)


class _StubDoc:
    def get_document_catalog(self) -> Any:
        return object()


def test_ensure_font_skips_insert_when_resources_have_no_put(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes 118->120: resources without ``put`` skip the insert step but
    still flag both COS objects as needing update.

    ``PDType1Font`` is stubbed because the real constructor expects a COS
    dictionary, not a base-font name string (the same approach the
    existing ``_ensure_font`` success-path test uses)."""
    import pypdfbox.pdmodel.font.pd_type1_font as pd_t1f

    class _FakeFont:
        def __init__(self, name: str) -> None:
            self.name = name

    monkeypatch.setattr(pd_t1f, "PDType1Font", _FakeFont, raising=True)

    proc = AcroFormDefaultsProcessor(_StubDoc())
    resources = _ResourcesWithoutPut()
    font_dict = _FontDictMissing()

    proc._ensure_font(  # noqa: SLF001
        resources,
        font_dict,
        COSName.get_pdf_name("Helv"),
        font_name="Helvetica",
    )

    # put was absent -> no insert, but the update propagation still ran.
    assert resources.get_cos_object().needs_update == [True]
    assert font_dict.needs_update == [True]
