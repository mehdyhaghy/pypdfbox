"""Parity check that upstream PDFBox class names resolve to the existing
concrete pypdfbox handlers under the ``graphics`` package.

Pypdfbox initially shipped these path/clip/paint operators with longer
descriptive names (``FillPathNonZeroWinding``, ``ClipNonZeroWinding``,
``EndPathNoOp``). The aliases re-bind those classes to their upstream
identifiers (``FillNonZeroRule``, ``ClipNonZeroRule``, ``EndPath``,
``DrawObject``) so code ported from PDFBox can keep its original
imports without forcing a rename across pypdfbox.
"""

from __future__ import annotations

from pypdfbox.contentstream.operator.graphics import (
    ClipEvenOdd,
    ClipEvenOddRule,
    ClipNonZeroRule,
    ClipNonZeroWinding,
    ClosePath,
    DrawObject,
    EndPath,
    EndPathNoOp,
    FillEvenOddRule,
    FillNonZeroRule,
    FillPathEvenOdd,
    FillPathNonZeroWinding,
    InvokeNamedXObject,
    StrokePath,
)


def test_draw_object_aliases_invoke_named_xobject() -> None:
    assert DrawObject is InvokeNamedXObject


def test_fill_non_zero_rule_aliases_fill_path_non_zero_winding() -> None:
    assert FillNonZeroRule is FillPathNonZeroWinding


def test_fill_even_odd_rule_aliases_fill_path_even_odd() -> None:
    assert FillEvenOddRule is FillPathEvenOdd


def test_clip_non_zero_rule_aliases_clip_non_zero_winding() -> None:
    assert ClipNonZeroRule is ClipNonZeroWinding


def test_clip_even_odd_rule_aliases_clip_even_odd() -> None:
    assert ClipEvenOddRule is ClipEvenOdd


def test_end_path_aliases_end_path_no_op() -> None:
    assert EndPath is EndPathNoOp


def test_stroke_path_re_export_matches_path_module() -> None:
    """``StrokePath`` already uses its upstream name; expose the same
    class object via the graphics package for parity-by-import-path."""
    from pypdfbox.contentstream.operator.path import (
        StrokePath as PathStrokePath,
    )

    assert StrokePath is PathStrokePath


def test_close_path_re_export_matches_path_module() -> None:
    from pypdfbox.contentstream.operator.path import (
        ClosePath as PathClosePath,
    )

    assert ClosePath is PathClosePath


def test_draw_object_operator_name_is_do() -> None:
    assert DrawObject.OPERATOR_NAME == "Do"
    assert DrawObject().get_name() == "Do"


def test_fill_non_zero_rule_operator_name_is_lowercase_f() -> None:
    assert FillNonZeroRule.OPERATOR_NAME == "f"
    assert FillNonZeroRule().get_name() == "f"


def test_fill_even_odd_rule_operator_name_is_f_star() -> None:
    assert FillEvenOddRule.OPERATOR_NAME == "f*"
    assert FillEvenOddRule().get_name() == "f*"


def test_clip_non_zero_rule_operator_name_is_w() -> None:
    assert ClipNonZeroRule.OPERATOR_NAME == "W"
    assert ClipNonZeroRule().get_name() == "W"


def test_clip_even_odd_rule_operator_name_is_w_star() -> None:
    assert ClipEvenOddRule.OPERATOR_NAME == "W*"
    assert ClipEvenOddRule().get_name() == "W*"


def test_end_path_operator_name_is_n() -> None:
    assert EndPath.OPERATOR_NAME == "n"
    assert EndPath().get_name() == "n"
