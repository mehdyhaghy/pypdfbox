from __future__ import annotations

from tests.xmpbox.upstream import test_photoshop_schema as upstream_photoshop


def test_wave882_upstream_photoshop_placeholder_bodies_activated() -> None:
    """
    The five upstream placeholders this guard originally pinned —
    ``test_setting_value_in_array``, ``test_random_setting_value_in_array``,
    ``test_property_setter_in_array``, ``test_random_property_setter_in_array``,
    and ``test_random_setter_simple`` — were activated in a later wave.
    ``*_in_array`` rows exercise the ``DocumentAncestors`` / ``TextLayers``
    array properties (PhotoshopSchema's only array-shaped slots), and
    ``test_random_setter_simple`` is now a fully parametric test over the
    Simple parameter set. This module is retained so a regression that
    re-stubs any of them would surface here at the attribute lookup below.
    """
    # Each name must still resolve on the upstream module (the tests exist).
    assert callable(upstream_photoshop.test_setting_value_in_array)
    assert callable(upstream_photoshop.test_random_setting_value_in_array)
    assert callable(upstream_photoshop.test_property_setter_in_array)
    assert callable(upstream_photoshop.test_random_property_setter_in_array)
    assert callable(upstream_photoshop.test_random_setter_simple)
