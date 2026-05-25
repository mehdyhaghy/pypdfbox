"""Wave 1396 branch-coverage tests for ``PDOutlineItem._resolve_named_destination``.

Closes the False-branch arrows clustered around lines 471–525 in
``pypdfbox/pdmodel/interactive/documentnavigation/outline/pd_outline_item.py``.
Each guard inside the named-destination lookup (``/Names/Dests`` tree
then legacy ``/Dests`` dict) has a missed False arm — these tests drive
each guard's missing arm via a fake-catalog scope so we can return
arbitrary objects without going through the typed setter wrappers.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


class _FakeCatalog:
    def __init__(self, names: Any = None, dests: Any = None) -> None:
        self._names = names
        self._dests = dests

    def get_names(self) -> Any:
        return self._names

    def get_dests(self) -> Any:
        return self._dests


class _FakeDocument:
    def __init__(self, catalog: _FakeCatalog) -> None:
        self._catalog = catalog

    def get_document_catalog(self) -> _FakeCatalog:
        return self._catalog


def _build_item_with_named_dest(name: str) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_destination(PDNamedDestination(name))
    return item


def test_resolve_named_destination_returns_none_when_get_named_not_callable() -> None:
    """Object missing ``get_named_destination`` returns None.

    Closes the False arm of the ``callable(get_named)`` guard.
    """
    fake = _FakeDocument(_FakeCatalog())

    class NotADestination:
        pass

    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, NotADestination(),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_returns_none_when_name_not_string() -> None:
    """``get_named_destination`` returning non-string short-circuits.

    Closes the False arm of the ``isinstance(name, str)`` guard.
    """
    fake = _FakeDocument(_FakeCatalog())

    class WeirdNamed:
        def get_named_destination(self) -> int:
            return 42

    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, WeirdNamed(),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_skips_names_when_dests_not_callable() -> None:
    """``/Names`` present but ``get_dests`` not callable falls through to /Dests.

    Closes the False arm of ``callable(get_dests_tree)`` (line 471->491).
    """
    class FakeNames:
        get_dests = None  # not callable

    fake = _FakeDocument(_FakeCatalog(names=FakeNames()))
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("missing"),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_skips_names_when_tree_is_none() -> None:
    """``get_dests`` returning None falls through to /Dests.

    Closes the False arm of ``tree is not None`` (line 473->491).
    """
    class FakeNames:
        def get_dests(self) -> None:
            return None

    fake = _FakeDocument(_FakeCatalog(names=FakeNames()))
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("missing"),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_skips_names_when_get_value_not_callable() -> None:
    """Names-tree without get_value falls through.

    Closes the False arm of ``callable(get_value)`` at line 475->491.
    """
    class FakeTree:
        get_value = "not-callable"

    class FakeNames:
        def get_dests(self) -> object:
            return FakeTree()

    fake = _FakeDocument(_FakeCatalog(names=FakeNames()))
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("missing"),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_skips_names_when_entry_missing() -> None:
    """Names-tree get_value returning None falls through.

    Closes the False arm of ``entry is not None`` at line 477->491.
    """
    class FakeTree:
        def get_value(self, name: str) -> None:
            return None

    class FakeNames:
        def get_dests(self) -> object:
            return FakeTree()

    fake = _FakeDocument(_FakeCatalog(names=FakeNames()))
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("missing"),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_skips_names_when_resolved_is_none() -> None:
    """Names-tree returns non-destination entry that can't be coerced.

    Closes the False arm of ``resolved is not None`` at line 487->491.
    """
    # Entry is a non-COSBase, non-PDDestination object — coercion returns None
    class FakeTree:
        def get_value(self, name: str) -> object:
            return object()

    class FakeNames:
        def get_dests(self) -> object:
            return FakeTree()

    fake = _FakeDocument(_FakeCatalog(names=FakeNames()))
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("missing"),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_returns_none_when_no_names_and_no_dests() -> None:
    """No /Names and no /Dests — returns None.

    Closes the False arm of ``dests is not None`` (line 492->513).
    """
    fake = _FakeDocument(_FakeCatalog())
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("ghost"),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_legacy_dests_no_get_value_uses_cos_path() -> None:
    """Legacy /Dests without get_value uses get_cos_object path.

    Closes the False arm of ``callable(get_value)`` at line 497->499.
    """
    with PDDocument() as document:
        document.add_page(PDPage())
        page_dict = document.get_pages()[0].get_cos_object()
        dest_array = COSArray()
        dest_array.add(page_dict)
        dest_array.add(COSName.get_pdf_name("Fit"))

        dests_dict = COSDictionary()
        dests_dict.set_item(COSName.get_pdf_name("ch1"), dest_array)

        class FakeDests:
            # No get_value attribute at all.
            def get_cos_object(self) -> COSDictionary:
                return dests_dict

        fake = _FakeDocument(_FakeCatalog(dests=FakeDests()))
        resolved = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
            fake, PDNamedDestination("ch1"),  # type: ignore[arg-type]
        )
        assert resolved is not None


def test_resolve_named_destination_legacy_dests_entry_none_falls_to_cos_lookup() -> None:
    """Legacy /Dests with get_value returning None tries get_cos_object.

    Closes 499->504 (the ``entry is None`` branch routes through to the
    cos lookup which also misses).
    """
    class FakeDests:
        def get_value(self, name: str) -> None:
            return None

        def get_cos_object(self) -> None:
            return None

    fake = _FakeDocument(_FakeCatalog(dests=FakeDests()))
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("missing"),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_legacy_dests_entry_remains_none() -> None:
    """Legacy /Dests where everything is None returns None.

    Closes 504->513 (entry stayed None, skips the resolution branch).
    """
    empty = COSDictionary()

    class FakeDests:
        def get_cos_object(self) -> COSDictionary:
            return empty

    fake = _FakeDocument(_FakeCatalog(dests=FakeDests()))
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("missing"),  # type: ignore[arg-type]
    )
    assert result is None


def test_resolve_named_destination_legacy_dests_entry_is_dict_without_inner_d() -> None:
    """Legacy /Dests entry is a dict without /D — coerces the dict itself.

    Closes the False arm of ``inner is not None`` at line 508->510.
    """
    wrapper = COSDictionary()
    wrapper.set_item(COSName.get_pdf_name("Other"), COSInteger(1))

    class FakeDests:
        def get_value(self, name: str) -> COSDictionary:
            return wrapper

    fake = _FakeDocument(_FakeCatalog(dests=FakeDests()))
    result = PDOutlineItem._resolve_named_destination(  # noqa: SLF001
        fake, PDNamedDestination("ch1"),  # type: ignore[arg-type]
    )
    # Coercion fails because there's no usable /D — but the False arm
    # of inner-is-None still ran (line 508->510 closed).
    assert result is None


def test_coerce_named_destination_entry_dict_without_inner_d() -> None:
    """``_coerce_named_destination_entry`` on a dict without /D coerces the dict.

    Closes the False arm of ``inner is not None`` at line 525->527.
    """
    # Build a /D-less dict — _coerce should attempt PDDestination.create
    # on the dict directly (the inner is None branch). The dict is not a
    # recognised destination so create() will raise OSError, returning None.
    bare = COSDictionary()
    bare.set_item(COSName.get_pdf_name("Other"), COSInteger(1))
    result = PDOutlineItem._coerce_named_destination_entry(bare)  # noqa: SLF001
    assert result is None
