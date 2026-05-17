"""Wave 1332 — coverage boost for ``pdmodel.fixup.abstract_fixup``.

Covers the abstract ``apply`` raise-path so the module reaches >=95%.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.fixup.abstract_fixup import AbstractFixup
from pypdfbox.pdmodel.fixup.pd_document_fixup import PDDocumentFixup


def test_abstract_fixup_stores_document_reference() -> None:
    sentinel = object()
    fixup = AbstractFixup(sentinel)  # type: ignore[arg-type]
    assert fixup.document is sentinel


def test_abstract_fixup_is_pd_document_fixup_subclass() -> None:
    assert issubclass(AbstractFixup, PDDocumentFixup)


def test_abstract_fixup_apply_raises_not_implemented_error() -> None:
    fixup = AbstractFixup(object())  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        fixup.apply()


def test_abstract_fixup_subclass_overrides_apply() -> None:
    calls: list[object] = []

    class _Concrete(AbstractFixup):
        def apply(self) -> None:
            calls.append(self.document)

    document = object()
    _Concrete(document).apply()  # type: ignore[arg-type]
    assert calls == [document]
