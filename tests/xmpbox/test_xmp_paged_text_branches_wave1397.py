"""Wave 1397 branch-coverage tests for ``XMPageTextSchema``.

Closes False-branch arrows:

* 133->139 — ``_coerce_boolean`` returns None when ``raw`` is neither bool nor str
* 217->220 — ``get_max_page_size_property`` dict-form with no ``w`` key
* 220->223 — dict-form with no ``h`` key
* 223->225 — dict-form with no ``unit`` key
"""

from __future__ import annotations

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type.dimensions_type import DimensionsType
from pypdfbox.xmpbox.xmp_paged_text_schema import XMPageTextSchema


def _pt() -> XMPageTextSchema:
    return XMPageTextSchema(XMPMetadata.create_xmp_metadata())


def test_coerce_boolean_returns_none_for_int_raw() -> None:
    """Closes 133->139: raw is not a str."""
    assert XMPageTextSchema._coerce_boolean(42) is None  # noqa: SLF001


def test_coerce_boolean_returns_none_for_list_raw() -> None:
    """Closes 133->139 (alternate non-str shape)."""
    assert XMPageTextSchema._coerce_boolean(["True"]) is None  # noqa: SLF001


def test_max_page_size_property_dict_without_w() -> None:
    """Closes 217->220: dict missing the ``w`` key."""
    schema = _pt()
    schema.set_max_page_size({"h": "792", "unit": "Pt"})
    dim = schema.get_max_page_size_property()
    assert isinstance(dim, DimensionsType)
    assert dim.get_w() is None
    assert dim.get_h() == 792.0
    assert dim.get_unit() == "Pt"


def test_max_page_size_property_dict_without_h() -> None:
    """Closes 220->223: dict missing the ``h`` key."""
    schema = _pt()
    schema.set_max_page_size({"w": "612", "unit": "Pt"})
    dim = schema.get_max_page_size_property()
    assert isinstance(dim, DimensionsType)
    assert dim.get_w() == 612.0
    assert dim.get_h() is None
    assert dim.get_unit() == "Pt"


def test_max_page_size_property_dict_without_unit() -> None:
    """Closes 223->225: dict missing the ``unit`` key."""
    schema = _pt()
    schema.set_max_page_size({"w": "612", "h": "792"})
    dim = schema.get_max_page_size_property()
    assert isinstance(dim, DimensionsType)
    assert dim.get_w() == 612.0
    assert dim.get_h() == 792.0
    assert dim.get_unit() is None
