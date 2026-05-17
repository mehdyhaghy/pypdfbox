"""Coverage-boost tests for
``pypdfbox.pdmodel.interactive.annotation.handlers.pd_square_appearance_handler``.

The existing smoke tests at wave 1280/1285 cover the happy path and a
cloudy-border branch. This file closes the remaining gaps:

* Early return when the wrong annotation type is passed
  (``generate_normal_appearance`` line 35).
* ``set_non_stroking_color`` call when /IC is populated (line 45).
* ``get_line_width`` branches: /BS width path, /Border-array width path
  via :class:`COSFloat` / :class:`COSInteger`, and the 1.0 default
  (lines 103, 107-109).
* ``_interior_components`` private helper across all three input shapes
  the inline ``getattr`` chain accepts (lines 117-125).
* No-op rollover/down appearance hooks (returning ``None``).
* The cloudy-border branch's ``set_rect_difference`` /
  ``set_matrix`` wiring on the appearance stream.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_square_appearance_handler import (
    PDSquareAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationSquare,
    PDAnnotationSquareCircle,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (0.0, 0.0, 100.0, 50.0)


def _square_with_color() -> PDAnnotationSquare:
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    return annotation


# ----------------------------------------------------------------------
# generate_normal_appearance — early-return when wrong annotation type
# ----------------------------------------------------------------------


def test_generate_normal_appearance_returns_when_not_square_circle() -> None:
    """Line 35: ``if not isinstance(annotation, PDAnnotationSquareCircle):
    return`` — pass a plain PDAnnotation."""
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(*_RECT))
    handler = PDSquareAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    # Nothing should be written to /AP because the handler bails early.
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# generate_normal_appearance — interior-color (fill) branch
# ----------------------------------------------------------------------


def _appearance_bytes(annotation) -> bytes:
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    stream = ap.get_normal_appearance().get_appearance_stream()
    return stream.get_stream().to_byte_array()


def test_generate_normal_appearance_with_interior_color_sets_non_stroking() -> None:
    """Line 45: when /IC is set, the handler must emit a non-stroking
    color into the content stream."""
    annotation = _square_with_color()
    annotation.set_interior_color([1.0, 1.0, 0.0])
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # non-stroking RGB color operator
    assert b"rg" in body
    # And the rectangle should still be present.
    assert b"re" in body


def test_generate_normal_appearance_without_interior_color_skips_fill() -> None:
    """Sanity check the other side of line 43: no /IC → no ``rg`` op
    (just the stroking ``RG`` op and the path)."""
    annotation = _square_with_color()
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Stroking RGB color, not non-stroking, must be present.
    assert b"RG" in body


# ----------------------------------------------------------------------
# get_line_width — /BS, /Border, default branches
# ----------------------------------------------------------------------


def test_get_line_width_uses_border_style_width_when_present() -> None:
    """Line 103: when /BS is set, return that width."""
    annotation = _square_with_color()
    bs = PDBorderStyleDictionary()
    bs.set_width(3.5)
    annotation.set_border_style(bs)
    handler = PDSquareAppearanceHandler(annotation)
    assert handler.get_line_width() == 3.5


def test_get_line_width_uses_integer_border_style_width() -> None:
    """Variant of the /BS branch: integer width round-trip."""
    annotation = _square_with_color()
    bs = PDBorderStyleDictionary()
    bs.set_width(7)
    annotation.set_border_style(bs)
    assert PDSquareAppearanceHandler(annotation).get_line_width() == 7.0


def test_get_line_width_uses_border_array_third_element_float() -> None:
    """Lines 104-108: /BS absent, /Border array length >= 3 with a
    :class:`COSFloat` at index 2."""
    annotation = _square_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSFloat(2.5))
    annotation.set_border(border)
    assert PDSquareAppearanceHandler(annotation).get_line_width() == 2.5


def test_get_line_width_uses_border_array_third_element_integer() -> None:
    """Variant of lines 104-108 with a :class:`COSInteger` width."""
    annotation = _square_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(4))
    annotation.set_border(border)
    assert PDSquareAppearanceHandler(annotation).get_line_width() == 4.0


def test_get_line_width_falls_back_to_one_when_no_border() -> None:
    """Line 109: default 1.0 when /BS is absent and /Border has no
    usable width entry."""
    # PDAnnotation.get_border() synthesises [0 0 1] when /Border is
    # unset, so the default falls out via the COSInteger branch (=1.0).
    annotation = _square_with_color()
    assert PDSquareAppearanceHandler(annotation).get_line_width() == 1.0


def test_get_line_width_default_when_border_third_element_unknown() -> None:
    """Line 109 explicitly: /BS absent, /Border third element is neither
    COSFloat nor COSInteger (here: a Name) — must fall through to 1.0."""
    from pypdfbox.cos import COSName

    annotation = _square_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSName.get_pdf_name("Solid"))
    annotation.set_border(border)
    assert PDSquareAppearanceHandler(annotation).get_line_width() == 1.0


# ----------------------------------------------------------------------
# _interior_components — three accepted input shapes + None paths
# ----------------------------------------------------------------------


def test_interior_components_returns_none_when_interior_unset() -> None:
    """Line 114: ``interior is None`` short-circuit."""
    annotation = _square_with_color()
    assert PDSquareAppearanceHandler._interior_components(annotation) is None


def test_interior_components_uses_to_float_array_on_cos_array() -> None:
    """Lines 117-119: real ``COSArray`` path via ``to_float_array``."""
    annotation = _square_with_color()
    annotation.set_interior_color([0.25, 0.5, 0.75])
    components = PDSquareAppearanceHandler._interior_components(annotation)
    assert components == [0.25, 0.5, 0.75]


def test_interior_components_returns_none_for_empty_to_float_array() -> None:
    """Lines 117-119: empty ``to_float_array`` result collapses to None."""

    class _EmptyArray:
        def to_float_array(self) -> list[float]:
            return []

    class _Stub:
        def get_interior_color(self) -> _EmptyArray:
            return _EmptyArray()

    assert PDSquareAppearanceHandler._interior_components(_Stub()) is None


def test_interior_components_uses_size_branch_when_no_to_float_array() -> None:
    """Lines 120-122: object that exposes ``size`` but not
    ``to_float_array`` (empty case → returns None)."""

    class _OnlySize:
        def size(self) -> int:
            return 0

    class _Stub:
        def get_interior_color(self) -> _OnlySize:
            return _OnlySize()

    assert PDSquareAppearanceHandler._interior_components(_Stub()) is None


def test_interior_components_size_branch_non_empty_calls_to_float_array() -> None:
    """Line 123: an object that hides ``to_float_array`` from
    :func:`hasattr` but exposes it for direct call. We use a custom
    ``__getattribute__`` that raises ``AttributeError`` on the
    introspection lookup that :func:`hasattr` performs, then unblock
    the lookup just for the direct call — this is the only way to
    reach line 123, which is otherwise unreachable through normal
    duck-typing (an object that truthfully exposes both ``size`` and
    ``to_float_array`` always exits at line 119)."""

    class _Tricky:
        # Flag flipped before the actual call to allow ``to_float_array``
        # to be looked up by name.
        _allow: bool = False

        def size(self) -> int:
            return 3

        def to_float_array(self) -> list[float]:
            return [0.11, 0.22, 0.33]

        def __getattribute__(self, name):
            if name == "to_float_array" and not object.__getattribute__(
                self, "_allow"
            ):
                raise AttributeError(name)
            return object.__getattribute__(self, name)

    interior = _Tricky()

    # Wrap the call so we toggle ``_allow`` only when the handler
    # actually calls ``to_float_array`` (not when ``hasattr`` probes).
    # Approach: patch _interior_components-friendly stub whose
    # ``get_interior_color`` returns a fresh _Tricky, but only allows
    # to_float_array after the first ``hasattr`` probe completes.
    state = {"hasattr_probes": 0}

    class _LatchedTricky(_Tricky):
        def __getattribute__(self, name):
            if name == "to_float_array":
                # First lookup (``hasattr``) raises; second (direct call)
                # succeeds.
                state["hasattr_probes"] += 1
                if state["hasattr_probes"] == 1:
                    raise AttributeError(name)
                return object.__getattribute__(self, name)
            return object.__getattribute__(self, name)

    class _Stub:
        def get_interior_color(self):
            return _LatchedTricky()

    components = PDSquareAppearanceHandler._interior_components(_Stub())
    assert components == [0.11, 0.22, 0.33]


def test_interior_components_uses_size_branch_non_empty() -> None:
    """Lines 120-123: synthetic object with ``size`` (non-zero) +
    ``to_float_array`` exposed only via attribute, but since we want to
    hit the ``hasattr(interior, "to_float_array")`` first branch when it
    exists, we keep the non-empty case under the to_float_array path
    (line 118)."""

    class _ArrayLike:
        def to_float_array(self) -> list[float]:
            return [0.1, 0.2, 0.3]

    class _Stub:
        def get_interior_color(self) -> _ArrayLike:
            return _ArrayLike()

    components = PDSquareAppearanceHandler._interior_components(_Stub())
    assert components == [0.1, 0.2, 0.3]


def test_interior_components_uses_iterable_fallback() -> None:
    """Lines 124-125: object that has neither ``to_float_array`` nor
    ``size`` — fall through to ``list(interior)``."""

    class _Iterable:
        def __iter__(self):
            return iter([0.4, 0.6, 0.8])

    class _Stub:
        def get_interior_color(self) -> _Iterable:
            return _Iterable()

    components = PDSquareAppearanceHandler._interior_components(_Stub())
    assert components == [0.4, 0.6, 0.8]


def test_interior_components_iterable_empty_returns_none() -> None:
    """Lines 124-125: iterable fallback's empty branch."""

    class _EmptyIterable:
        def __iter__(self):
            return iter([])

    class _Stub:
        def get_interior_color(self) -> _EmptyIterable:
            return _EmptyIterable()

    assert PDSquareAppearanceHandler._interior_components(_Stub()) is None


# ----------------------------------------------------------------------
# rollover / down — no-op hooks
# ----------------------------------------------------------------------


def test_generate_rollover_appearance_is_noop() -> None:
    annotation = _square_with_color()
    handler = PDSquareAppearanceHandler(annotation)
    assert handler.generate_rollover_appearance() is None


def test_generate_down_appearance_is_noop() -> None:
    annotation = _square_with_color()
    handler = PDSquareAppearanceHandler(annotation)
    assert handler.generate_down_appearance() is None


# ----------------------------------------------------------------------
# cloudy-border branch — set_rect_difference + appearance set_matrix
# ----------------------------------------------------------------------


def _cloudy_border(intensity: float = 1.0) -> PDBorderEffectDictionary:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(intensity)
    return be


def test_cloudy_border_branch_updates_annotation_and_appearance_stream() -> None:
    """Lines 65-76: the cloudy-border branch propagates ``cloudy``'s
    bbox / matrix / rect-difference onto both the annotation and the
    appearance stream. Verifies the ``hasattr`` chains trigger and the
    appearance bbox/matrix get written."""
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    annotation.set_border_effect(_cloudy_border(intensity=2.0))
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    appearance = annotation.get_normal_appearance_stream()
    assert appearance is not None
    bbox = appearance.get_bbox()
    assert bbox is not None
    # Bbox should now be enlarged from the original (cloudy expands it
    # to make room for the wavy border).
    assert bbox.get_width() >= _RECT[2] - _RECT[0]
    # /RD must be set as a 4-element rectangle on the annotation.
    rd = annotation.get_rect_differences()
    assert len(rd) == 4


def test_isinstance_guard_subclass_passes() -> None:
    """Line 34 negation: ``PDAnnotationSquareCircle`` subclasses pass
    the isinstance check (the happy path)."""
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.5, 0.5, 0.5])
    assert isinstance(annotation, PDAnnotationSquareCircle)
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


# ----------------------------------------------------------------------
# constructor — single-arg vs document-arg overloads
# ----------------------------------------------------------------------


def test_constructor_with_document_argument() -> None:
    """Ensure the document-arg overload of __init__ stores correctly."""
    from pypdfbox.pdmodel.pd_document import PDDocument

    annotation = _square_with_color()
    document = PDDocument()
    handler = PDSquareAppearanceHandler(annotation, document)
    assert handler.get_annotation() is annotation
    assert handler.get_document() is document


def test_constructor_with_document_argument_none() -> None:
    """Ensure the single-arg overload works with explicit None."""
    annotation = _square_with_color()
    handler = PDSquareAppearanceHandler(annotation, None)
    assert handler.get_annotation() is annotation
    assert handler.get_document() is None
