"""Wave 1396 branch-coverage tests for ``PDOptionalContentProperties``.

Closes False-branch arrows where the visibility-walk skips an /OCGs,
/ON, or /OFF array entry that isn't coercible to a dictionary:

* 580->578 — ``_get_ocgs`` walker skips non-dict entries
* 594->592 — ``compute_visible_ocgs`` /OFF walker skips non-dict entries
* 601->599 — ``compute_visible_ocgs`` /ON walker skips non-dict entries
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def test_compute_visible_ocgs_skips_non_dict_off_entries() -> None:
    """Non-dict entries in /OFF are silently skipped.

    Closes False arms at lines 594 (and the ``all_ocg_ids`` walker
    at 580 — same predicate).
    """
    props = PDOptionalContentProperties()
    grp = PDOptionalContentGroup("Layer1")
    props.add_group(grp)

    d = props.get_cos_object().get_dictionary_object(COSName.get_pdf_name("D"))
    assert isinstance(d, COSDictionary)
    off = COSArray()
    off.add(COSInteger.get(99))  # non-dict — must be skipped
    off.add(grp.get_cos_object())
    d.set_item(COSName.get_pdf_name("OFF"), off)

    visible = props.compute_visible_ocgs()
    # The /OFF entry (grp) was removed from the visible set; the bogus
    # int entry didn't trip an exception.
    assert id(grp.get_cos_object()) not in visible


def test_compute_visible_ocgs_skips_non_dict_on_entries() -> None:
    """Non-dict entries in /ON are silently skipped.

    Closes False arm at line 601.
    """
    props = PDOptionalContentProperties()
    grp = PDOptionalContentGroup("Layer1")
    props.add_group(grp)

    d = props.get_cos_object().get_dictionary_object(COSName.get_pdf_name("D"))
    assert isinstance(d, COSDictionary)
    on = COSArray()
    on.add(COSInteger.get(42))  # non-dict — must be skipped
    on.add(grp.get_cos_object())
    d.set_item(COSName.get_pdf_name("ON"), on)

    visible = props.compute_visible_ocgs()
    # grp explicitly turned ON.
    assert id(grp.get_cos_object()) in visible


def test_compute_visible_ocgs_skips_non_dict_ocgs_entries() -> None:
    """Non-dict entries in /OCGs are silently skipped.

    Closes False arm at line 580 (the all_ocg_ids walker).
    """
    props = PDOptionalContentProperties()
    grp = PDOptionalContentGroup("Layer1")
    props.add_group(grp)
    # Inject a non-dict entry directly into /OCGs.
    ocgs_arr = props.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("OCGs"),
    )
    assert isinstance(ocgs_arr, COSArray)
    ocgs_arr.add(COSInteger.get(42))

    visible = props.compute_visible_ocgs()
    # Layer1 visible by default (base state /ON); int entry didn't
    # contribute or crash.
    assert id(grp.get_cos_object()) in visible
