"""Wave 1397 branch-coverage tests for ``XMPSchema``.

Closes False-branch arrows:

* ``__init__`` 79->exit — subclass without NAMESPACE/PREFIX skips the
  ``_namespaces[prefix] = namespace`` self-registration
* ``set_unqualified_language_property_value`` 452->454 — value=None on
  an absent property: nothing to pop, just return
* ``internal_add_bag_value`` 900->903 — existing IS already a plain list:
  append in place without allocating
"""

from __future__ import annotations

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.xmp_schema import XMPSchema


class _BareSchema(XMPSchema):
    """No NAMESPACE / PREFERRED_PREFIX set — the constructor's
    ``if self._prefix and self._namespace`` guard falls through to
    skip the ``_namespaces`` self-registration."""

    NAMESPACE = ""
    PREFERRED_PREFIX = ""


def test_init_without_namespace_or_prefix_skips_namespace_registration() -> None:
    """Closes 79->exit: when the subclass exposes neither a namespace
    URI nor a preferred prefix, the ``_namespaces`` dict stays empty."""
    schema = _BareSchema(XMPMetadata.create_xmp_metadata())
    assert schema._namespaces == {}  # noqa: SLF001


def test_set_unqualified_language_property_value_none_on_absent() -> None:
    """Closes 452->454: clearing an absent LangAlt entry is a no-op
    (existing is not a dict because the property was never created)."""
    schema = _BareSchema(XMPMetadata.create_xmp_metadata())
    # Property is absent — set with value=None.
    schema.set_unqualified_language_property_value("title", "en", None)
    # Still no value; no exception.
    assert "title" not in schema._properties  # noqa: SLF001


def test_internal_add_bag_value_appends_to_existing_list() -> None:
    """Closes 900->903: ``internal_add_bag_value`` reuses the existing
    list when the property is already a plain list."""
    schema = _BareSchema(XMPMetadata.create_xmp_metadata())
    # Pre-populate the property with a list so the branch ``if not
    # isinstance(existing, list)`` evaluates False.
    schema._properties["tag"] = ["first"]  # noqa: SLF001
    schema.internal_add_bag_value("tag", "second")
    assert schema._properties["tag"] == ["first", "second"]  # noqa: SLF001
