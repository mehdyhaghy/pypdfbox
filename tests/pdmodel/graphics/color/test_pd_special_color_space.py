"""Tests for the intermediate abstract base ``PDSpecialColorSpace``.

Upstream (``PDSpecialColorSpace.java``) is an empty abstract marker between
``PDColorSpace`` and the concrete special color spaces. These tests verify the
hierarchy is wired correctly: the concrete subtypes inherit from it, it inherits
from ``PDColorSpace``, and re-parenting did not change subclass behavior.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from pypdfbox.pdmodel.graphics.color.pd_special_color_space import PDSpecialColorSpace

_SPECIAL_SUBTYPES = [PDSeparation, PDDeviceN, PDIndexed, PDPattern]


def test_extends_pd_color_space():
    assert issubclass(PDSpecialColorSpace, PDColorSpace)


@pytest.mark.parametrize(
    "cls", _SPECIAL_SUBTYPES, ids=["separation", "device_n", "indexed", "pattern"]
)
def test_subclasses_extend_special_color_space(cls):
    assert issubclass(cls, PDSpecialColorSpace)
    # And transitively still a PDColorSpace.
    assert issubclass(cls, PDColorSpace)


def test_is_abstract_base_with_no_own_members():
    # Upstream declares no members; the Python port adds none beyond the
    # inherited PDColorSpace surface. ``_abc_impl`` is injected by ABCMeta
    # (inherited via ``PDColorSpace(ABC)``) and is not a real member.
    own = {n for n in vars(PDSpecialColorSpace) if not n.startswith("_")}
    assert own == set()


def test_default_separation_instance_is_special_color_space():
    sep = PDSeparation()
    assert isinstance(sep, PDSpecialColorSpace)
    assert isinstance(sep, PDColorSpace)
    # Default Separation name is "Separation" — re-parenting must not change it.
    assert sep.get_name() == "Separation"


def test_default_pattern_instance_is_special_color_space():
    pat = PDPattern()
    assert isinstance(pat, PDSpecialColorSpace)
    assert pat.get_name() == "Pattern"


def test_default_device_n_instance_is_special_color_space():
    dn = PDDeviceN()
    assert isinstance(dn, PDSpecialColorSpace)
    assert dn.get_name() == "DeviceN"
