"""Live PDFBox differential parity for half-populated ``/Limits`` padding.

``PDNumberTreeNode.setLowerLimit`` / ``setUpperLimit`` are PRIVATE upstream; the
public ``test_number_tree_setter_oracle`` battery (which drives ``setNumbers`` /
``setKids``) never leaves a ``/Limits`` slot half-set because ``calculateLimits``
always writes both ends. This module reaches the private setters by reflection
(``NumberTreeLimitsPadProbe``) to pin the byte-level behaviour of the
not-yet-set slot: upstream pads the array with a Java ``null`` element while
pypdfbox pads with ``COSNull.NULL``.

The probe dumps, for each of "lower only" / "upper only" / "both":

  - ``slotN.get`` — raw (non-resolving) element type. This is the ONE place the
    two libraries differ: upstream reports ``null`` (Java null list element),
    pypdfbox would report ``COSNull``. Not asserted here as a string match for
    that reason — the difference is non-observable.
  - ``slotN.getObject`` — resolving accessor. Both libraries return ``null`` /
    ``None`` for the empty slot. ASSERTED equal.
  - ``serialized`` — the exact bytes ``COSWriter`` emits for the ``/Limits``
    array. Both libraries write the token ``null`` for the empty slot. ASSERTED
    byte-for-byte equal.

So the representation choice (``COSNull.NULL`` vs Java ``null``) is invisible
through both the resolving accessor and the writer. Parity is byte-for-byte.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSInteger, COSName
from pypdfbox.pdfwriter.cos_writer import COSWriter
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode
from tests.oracle.harness import requires_oracle, run_probe_text

_LIMITS = COSName.get_pdf_name("Limits")


class _IntNode(PDNumberTreeNode[int]):
    def convert_cos_to_value(self, base: COSBase) -> int:
        assert isinstance(base, COSInteger)
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNode:
        return _IntNode(dic)


def _limits(node: _IntNode) -> COSArray:
    arr = node.get_cos_object().get_dictionary_object(_LIMITS)
    assert isinstance(arr, COSArray)
    return arr


def _serialized(arr: COSArray) -> str:
    arr.set_direct(True)
    buf = io.BytesIO()
    arr.accept(COSWriter(buf))
    return buf.getvalue().hex()


# PDFBox 3.0.7's verbatim NumberTreeLimitsPadProbe output. The "[5 null]" /
# "[null 9]" / "[5 9]" serializations decode the recorded hex below.
_PDFBOX_REPORT = (
    "# setLowerLimit only\n"
    "  size=2\n"
    "  slot0.get=COSInteger(5)\n"
    "  slot1.get=null\n"
    "  slot0.getObject=COSInteger(5)\n"
    "  slot1.getObject=null\n"
    "  serialized=5b35206e756c6c5d0a\n"  # [5 null]\n
    "# setUpperLimit only\n"
    "  size=2\n"
    "  slot0.get=null\n"
    "  slot1.get=COSInteger(9)\n"
    "  slot0.getObject=null\n"
    "  slot1.getObject=COSInteger(9)\n"
    "  serialized=5b6e756c6c20395d0a\n"  # [null 9]\n
    "# setLowerLimit+setUpperLimit\n"
    "  size=2\n"
    "  slot0.get=COSInteger(5)\n"
    "  slot1.get=COSInteger(9)\n"
    "  slot0.getObject=COSInteger(5)\n"
    "  slot1.getObject=COSInteger(9)\n"
    "  serialized=5b3520395d0a\n"  # [5 9]\n
)


def test_pdfbox_limits_pad_baseline_recorded() -> None:
    """Guard the recorded oracle baseline against silent edits."""
    # The empty slot serializes to the token "null" (6e 75 6c 6c).
    assert "6e756c6c" in _PDFBOX_REPORT
    assert _PDFBOX_REPORT.count("serialized=") == 3


def test_pypdfbox_half_populated_limits_match_recorded() -> None:
    """pypdfbox's resolving accessor + serialized bytes equal the PDFBox
    baseline for every half-populated case (no live JVM required)."""
    lower = _IntNode()
    lower.set_lower_limit(5)
    assert _limits(lower).get_object(0) == COSInteger.get(5)
    assert _limits(lower).get_object(1) is None
    assert _serialized(_limits(lower)) == "5b35206e756c6c5d0a"

    upper = _IntNode()
    upper.set_upper_limit(9)
    assert _limits(upper).get_object(0) is None
    assert _limits(upper).get_object(1) == COSInteger.get(9)
    assert _serialized(_limits(upper)) == "5b6e756c6c20395d0a"

    both = _IntNode()
    both.set_lower_limit(5)
    both.set_upper_limit(9)
    assert _serialized(_limits(both)) == "5b3520395d0a"


@requires_oracle
def test_number_tree_limits_pad_matches_pdfbox() -> None:
    """Live probe still emits the recorded baseline AND pypdfbox's resolving
    accessor + serialized bytes agree on every slot.

    The only line that differs between the libraries is ``slotN.get`` (raw
    non-resolving element: upstream ``null`` vs pypdfbox ``COSNull``), which is
    never written to disk; we assert agreement on ``getObject`` + ``serialized``.
    """
    java = run_probe_text("NumberTreeLimitsPadProbe")
    java = java if java.endswith("\n") else java + "\n"
    assert java == _PDFBOX_REPORT

    # pypdfbox side: serialized bytes + resolving accessor match the baseline.
    lower = _IntNode()
    lower.set_lower_limit(5)
    assert _serialized(_limits(lower)) == "5b35206e756c6c5d0a"
    assert _limits(lower).get_object(1) is None
    upper = _IntNode()
    upper.set_upper_limit(9)
    assert _serialized(_limits(upper)) == "5b6e756c6c20395d0a"
    assert _limits(upper).get_object(0) is None
