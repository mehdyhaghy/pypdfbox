"""Wave 1495 — coverage round-out for ``Type1CharString`` module helpers.

Pins three helper surfaces the existing suite left unexercised:

* ``_font_subrs_as_charstrings`` — the parent-font ``/Private /Subrs``
  normaliser invoked from the constructor when the underlying fontTools
  ``T1CharString`` carries no ``subrs`` of its own: a font whose
  ``get_subrs_array`` raises, and one returning a heterogeneous list of an
  already-wrapped ``T1CharString``, raw bytes, and an unrecognised entry
  (which degrades to an empty no-op charstring, keeping the index aligned);
* ``_apply_affine`` — the per-command affine transform used by the seac
  composite pen for ``moveto`` / ``lineto`` / ``curveto`` and the
  passthrough for any other command tag;
* ``_make_path_pen(...).addComponent`` — the seac component replay hook,
  including its no-op fallbacks for a missing reader and a lookup that
  raises.
"""

from __future__ import annotations

from typing import Any

from fontTools.misc import psCharStrings

from pypdfbox.fontbox.cff.type1_char_string import (
    Type1CharString,
    _apply_affine,
    _font_subrs_as_charstrings,
    _make_path_pen,
)

# ----------------------------------------------- _font_subrs_as_charstrings


def test_font_subrs_returns_empty_when_no_accessor() -> None:
    class _NoSubrs:
        pass

    assert _font_subrs_as_charstrings(_NoSubrs(), psCharStrings) == []


def test_font_subrs_returns_empty_when_accessor_raises() -> None:
    class _Boom:
        def get_subrs_array(self) -> list[Any]:
            raise RuntimeError("subrs unavailable")

    assert _font_subrs_as_charstrings(_Boom(), psCharStrings) == []


def test_font_subrs_normalises_mixed_entries() -> None:
    already = psCharStrings.T1CharString()

    class _Font:
        def get_subrs_array(self) -> list[Any]:
            # one already-wrapped, one raw bytes, one unrecognised int.
            return [already, b"\x0d", 1234]

    wrapped = _font_subrs_as_charstrings(_Font(), psCharStrings)
    assert len(wrapped) == 3
    assert wrapped[0] is already
    assert all(isinstance(w, psCharStrings.T1CharString) for w in wrapped)
    # The bytes entry carries its bytecode; the unknown entry is a blank no-op.
    assert wrapped[1].bytecode == b"\x0d"


def test_font_subrs_wired_via_constructor_when_t1_has_none() -> None:
    # A list-form sequence builds a fresh T1CharString with no subrs, so the
    # constructor pulls the parent font's subrs through the normaliser.
    class _Font:
        def get_subrs_array(self) -> list[Any]:
            return [b"\x0d"]

    cs = Type1CharString(_Font(), "F", "A", [0])
    assert cs.t1.subrs is not None
    assert len(cs.t1.subrs) == 1


# ----------------------------------------------------------- _apply_affine


def test_apply_affine_translates_moveto_and_lineto() -> None:
    transform = (1.0, 0.0, 0.0, 1.0, 5.0, 7.0)  # pure translate (+5, +7)
    assert _apply_affine(("moveto", 1.0, 2.0), transform) == ("moveto", 6.0, 9.0)
    assert _apply_affine(("lineto", 0.0, 0.0), transform) == ("lineto", 5.0, 7.0)


def test_apply_affine_transforms_curveto_control_points() -> None:
    transform = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)  # uniform 2x scale
    out = _apply_affine(
        ("curveto", 1.0, 1.0, 2.0, 2.0, 3.0, 3.0), transform
    )
    assert out == ("curveto", 2.0, 2.0, 4.0, 4.0, 6.0, 6.0)


def test_apply_affine_passes_through_unknown_command() -> None:
    transform = (1.0, 0.0, 0.0, 1.0, 9.0, 9.0)
    assert _apply_affine(("closepath",), transform) == ("closepath",)


# ---------------------------------------------------- _make_path_pen.addComponent


def test_add_component_replays_transformed_component_outline() -> None:
    class _Component:
        def get_path(self) -> list[tuple[Any, ...]]:
            return [("moveto", 1.0, 1.0), ("lineto", 2.0, 2.0)]

    class _Reader:
        def get_type1_char_string(self, name: str) -> _Component:
            return _Component()

    pen = _make_path_pen(_Reader())
    pen.addComponent("agrave", (1.0, 0.0, 0.0, 1.0, 10.0, 20.0))
    assert pen.commands == [
        ("moveto", 11.0, 21.0),
        ("lineto", 12.0, 22.0),
    ]


def test_add_component_no_reader_is_silent() -> None:
    class _FontWithoutLookup:
        pass

    pen = _make_path_pen(_FontWithoutLookup())
    pen.addComponent("agrave", (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    assert pen.commands == []


def test_add_component_lookup_exception_is_swallowed() -> None:
    class _Reader:
        def get_type1_char_string(self, name: str) -> Any:
            raise KeyError(name)

    pen = _make_path_pen(_Reader())
    pen.addComponent("missing", (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    assert pen.commands == []
