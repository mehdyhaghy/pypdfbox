"""Wave 1281: ICOSParser ABC port."""

from __future__ import annotations

import pytest

from pypdfbox.cos import ICOSParser


def test_abstract_methods_block_direct_instantiation() -> None:
    with pytest.raises(TypeError):
        ICOSParser()  # type: ignore[abstract]


def test_concrete_subclass_compiles() -> None:
    # Sanity: implementing both abstract methods produces an
    # instantiable subclass, mirroring upstream which is just an
    # interface declaration.
    class Stub(ICOSParser):
        def dereference_cos_object(self, obj):  # type: ignore[override]
            return None

        def create_random_access_read_view(self, start, length):  # type: ignore[override]
            return None

    stub = Stub()
    assert stub.dereference_cos_object(None) is None
    assert stub.create_random_access_read_view(0, 0) is None
