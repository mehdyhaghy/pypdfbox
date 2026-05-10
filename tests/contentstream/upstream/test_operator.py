"""Upstream-derived parity tests for ``Operator``.

Upstream Apache PDFBox does not ship a dedicated ``OperatorTest.java``
for ``org.apache.pdfbox.contentstream.operator.Operator``. The contract
exercised here is read directly from the upstream source
(``Operator.java`` v3.0.x) and asserts the eight public surface
methods: the private constructor's ``/``-prefix rejection, the
``getOperator`` singleton cache (with ``BI`` / ``ID`` deliberately
bypassed), ``getName``, ``getImageData`` / ``setImageData``,
``getImageParameters`` / ``setImageParameters``, and ``toString`` —
the canonical ``"PDFOperator{<name>}"`` shape.

These tests intentionally target the parser-side ``Operator`` in
``pypdfbox.pdfparser.pdf_stream_parser`` (the cluster covered by this
parity wave). The richer contentstream-level ``Operator`` (with
operand storage and a ``with_operands`` factory) is exercised
separately by ``tests/contentstream/test_operator.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.pdfparser.pdf_stream_parser import Operator

# ---------- private constructor: rejects leading slash ----------


def test_constructor_rejects_leading_slash() -> None:
    """Upstream constructor throws ``IllegalArgumentException`` when the
    name starts with ``/`` (those are name-object operands, not
    operators). Translated to ``ValueError`` per project convention."""
    with pytest.raises(ValueError):
        Operator("/Bad")


def test_constructor_accepts_ordinary_keyword() -> None:
    op = Operator("Tj")
    assert op.get_name() == "Tj"


# ---------- getOperator: singleton cache + inline-image bypass ----------


def test_get_operator_returns_cached_singleton_for_ordinary_op() -> None:
    a = Operator.get_operator("Tj")
    b = Operator.get_operator("Tj")
    assert a is b


def test_get_operator_distinct_names_yield_distinct_instances() -> None:
    assert Operator.get_operator("BT") is not Operator.get_operator("ET")


def test_get_operator_inline_image_bypasses_cache() -> None:
    # Upstream comment: "we can't cache the ID operators."
    a = Operator.get_operator("BI")
    b = Operator.get_operator("BI")
    assert a is not b
    assert a.get_name() == "BI"


def test_get_operator_inline_image_data_bypasses_cache() -> None:
    a = Operator.get_operator("ID")
    b = Operator.get_operator("ID")
    assert a is not b
    assert a.get_name() == "ID"


# ---------- getName ----------


def test_get_name_returns_keyword() -> None:
    assert Operator.get_operator("re").get_name() == "re"


# ---------- toString ----------


def test_to_string_returns_pdfoperator_brace_form() -> None:
    """Upstream ``toString`` returns ``"PDFOperator{" + theOperator + "}"``."""
    assert Operator.get_operator("Tj").to_string() == "PDFOperator{Tj}"


def test_to_string_agrees_with_str_and_repr() -> None:
    op = Operator.get_operator("BT")
    assert str(op) == op.to_string()
    assert repr(op) == op.to_string()


def test_to_string_for_inline_image_operator() -> None:
    assert Operator.get_operator("BI").to_string() == "PDFOperator{BI}"


# ---------- getImageData / setImageData round-trip ----------


def test_image_data_default_is_none() -> None:
    op = Operator.get_operator("ID")
    assert op.get_image_data() is None


def test_image_data_round_trip() -> None:
    op = Operator.get_operator("ID")
    payload = b"\x00\x01\x02\x03"
    op.set_image_data(payload)
    assert op.get_image_data() is payload


# ---------- getImageParameters / setImageParameters round-trip ----------


def test_image_parameters_default_is_none() -> None:
    op = Operator.get_operator("BI")
    assert op.get_image_parameters() is None


def test_image_parameters_round_trip() -> None:
    op = Operator.get_operator("BI")
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("W"), COSInteger.get(8))
    op.set_image_parameters(params)
    assert op.get_image_parameters() is params
