"""Wave 1349 coverage-boost tests for :class:`GlyfCompositeComp`.

Targets the point-anchored decode branch (lines 84-85 — when
``ARGS_ARE_XY_VALUES`` is clear, the two argument words are stored as
``_point1`` / ``_point2`` rather than translates) and the
``has_instructions()`` predicate (line 215).
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def test_decode_point_anchored_args_stores_into_point_fields() -> None:
    """With ``ARGS_ARE_XY_VALUES`` clear, the two byte args are stored
    on ``_point1`` / ``_point2``, leaving the translate slots at zero
    (lines 82-85 of glyf_composite_comp.py)."""
    # flags = 0 → byte-sized args, no scale, no xy-values flag.
    payload = bytes(
        [
            0x00, 0x00,  # flags = 0
            0x00, 0x11,  # glyph index = 17
            0x07,        # arg1 = 7 (signed byte)
            0x0A,        # arg2 = 10
        ]
    )
    stream = MemoryTTFDataStream(payload)
    c = GlyfCompositeComp(stream)
    # Argument fields populated as expected.
    assert c.get_argument1() == 7
    assert c.get_argument2() == 10
    assert c.args_are_xy_values() is False
    # Translate slots untouched (still default zero).
    assert c.get_x_translate() == 0
    assert c.get_y_translate() == 0
    # Point-anchored slots received the args.
    assert c._point1 == 7  # noqa: SLF001
    assert c._point2 == 10  # noqa: SLF001


def test_has_instructions_true_when_flag_set() -> None:
    """``has_instructions()`` returns True when WE_HAVE_INSTRUCTIONS is
    set (line 215)."""
    c = GlyfCompositeComp()
    assert c.has_instructions() is False
    c._flags = GlyfCompositeComp.WE_HAVE_INSTRUCTIONS  # noqa: SLF001
    assert c.has_instructions() is True
    # Combined with another flag still reports True.
    c._flags = (  # noqa: SLF001
        GlyfCompositeComp.WE_HAVE_INSTRUCTIONS
        | GlyfCompositeComp.MORE_COMPONENTS
    )
    assert c.has_instructions() is True
