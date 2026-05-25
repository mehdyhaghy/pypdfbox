"""Wave 1403 branch-closure tests for the ``_encode_widths`` three-state
width compressor in :mod:`pypdfbox.pdmodel.font.pd_cid_font_type2_embedder`.

* ``598->604`` — while in the SERIAL state, the run *continues* (next
  CID is consecutive AND the width is unchanged), so the
  ``if cid != last_cid + 1 or value != last_value`` guard is false and
  the loop body skips the termination block.
* ``614->617`` — the loop ends in the SERIAL state, hitting the final
  ``elif state is _State.SERIAL`` true branch (614 -> 615) which then
  falls through to the ``return outer`` at 617.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger
from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import _encode_widths


def _cos_to_python(arr: COSArray) -> list[object]:
    out: list[object] = []
    for item in arr:
        if isinstance(item, COSArray):
            out.append(_cos_to_python(item))
        elif isinstance(item, COSInteger):
            out.append(item.int_value())
        else:
            out.append(item)
    return out


def test_encode_widths_serial_run_continues_across_multiple_entries() -> None:
    """A long run of identical widths for consecutive CIDs keeps the
    state machine in SERIAL across several iterations.

    The first transition into SERIAL happens at CID 2; CIDs 3, 4 and 5
    keep the run going — each of those iterations evaluates the SERIAL
    guard as *false* (``598->604``). The run terminates at the end of
    the loop in the SERIAL state (``614->617``).
    """
    # CIDs 1..5 all width 500 -> single serial run.
    arr = _encode_widths(
        [1, 500, 2, 500, 3, 500, 4, 500, 5, 500], scaling=1.0
    )
    py = _cos_to_python(arr)
    # Upstream serial form: [first_cid, last_cid, width].
    assert py == [1, 5, 500]
