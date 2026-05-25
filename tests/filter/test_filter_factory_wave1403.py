"""Wave 1403 branch round-out for ``FilterFactory.get_all_filters``.

Closes 110->109 — the ``if instance not in seen`` False arm (dedup): the
production registry currently maps every name to a *distinct* instance, so
the deduplication path never fires. Here we register an existing filter
singleton under a second name, then call ``get_all_filters`` so the same
instance is encountered twice and the dedup ``continue`` arm executes.

The registry is restored afterwards so the shared class-level state is not
polluted for other tests.
"""

from __future__ import annotations

from pypdfbox.filter.filter_factory import FilterFactory


def test_get_all_filters_dedups_duplicate_instance() -> None:
    """Closes 110->109: a single ``Filter`` instance registered under two
    names appears once in the deduplicated result."""
    saved = dict(FilterFactory._registry)  # noqa: SLF001
    try:
        any_name = next(iter(saved))
        instance = saved[any_name]
        # Alias the same singleton under a fresh second key.
        FilterFactory.register("__wave1403_alias__", instance)

        result = FilterFactory.get_all_filters()
        # The aliased instance must appear exactly once despite two keys.
        assert result.count(instance) == 1
    finally:
        FilterFactory._registry.clear()  # noqa: SLF001
        FilterFactory._registry.update(saved)  # noqa: SLF001
