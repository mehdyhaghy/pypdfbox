"""Wave 1275 — explicit ``to_string()`` parity and ``transform()`` for PDRectangle."""

from __future__ import annotations

from pypdfbox.pdmodel.common.pd_matrix import PDMatrix
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_to_string_matches_upstream_format_no_spaces() -> None:
    # Upstream PDRectangle.toString prints without spaces between commas.
    rect = PDRectangle(0.0, 0.0, 10.0, 20.0)
    assert rect.to_string() == "[0.0,0.0,10.0,20.0]"


def test_str_delegates_to_to_string() -> None:
    rect = PDRectangle(1.5, 2.5, 3.5, 4.5)
    assert str(rect) == rect.to_string()
    assert str(rect) == "[1.5,2.5,3.5,4.5]"


def test_to_string_default_constructor() -> None:
    assert PDRectangle().to_string() == "[0.0,0.0,0.0,0.0]"


def test_transform_with_identity_matrix() -> None:
    rect = PDRectangle(1.0, 2.0, 3.0, 4.0)
    identity = PDMatrix()  # default is identity
    corners = rect.transform(identity)
    assert corners == [(1.0, 2.0), (3.0, 2.0), (3.0, 4.0), (1.0, 4.0)]


def test_transform_with_translation() -> None:
    rect = PDRectangle(0.0, 0.0, 10.0, 20.0)
    # PDMatrix.translate offsets by (tx, ty)
    matrix = PDMatrix.get_translate_instance(5.0, 7.0)
    corners = rect.transform(matrix)
    assert corners == [(5.0, 7.0), (15.0, 7.0), (15.0, 27.0), (5.0, 27.0)]


def test_transform_corner_order_matches_upstream() -> None:
    # Upstream order: (llx,lly), (urx,lly), (urx,ury), (llx,ury).
    rect = PDRectangle(1.0, 2.0, 5.0, 8.0)
    identity = PDMatrix()
    corners = rect.transform(identity)
    assert corners[0] == (1.0, 2.0)  # ll
    assert corners[1] == (5.0, 2.0)  # lr
    assert corners[2] == (5.0, 8.0)  # ur
    assert corners[3] == (1.0, 8.0)  # ul
