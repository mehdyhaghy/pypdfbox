"""Wave 1403 branch round-out for ``sig_utils``.

Closes two loop-continuation partials in ``SigUtils.get_mdp_permission``:

* ``53->51`` — a ``/Reference`` array element that is **not** a
  ``COSDictionary`` is skipped and the loop advances.
* ``57->51`` — a DocMDP reference whose ``/TransformParams`` is **not** a
  ``COSDictionary`` is skipped and the loop advances.
"""

from __future__ import annotations

from pypdfbox.cos import COSInteger
from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.pdmodel.pd_document import PDDocument


def _wire_perms(doc: PDDocument, ref_array: COSArray) -> None:
    catalog = doc.get_document_catalog().get_cos_object()
    perms = COSDictionary()
    docmdp_sig = COSDictionary()
    docmdp_sig.set_item(COSName.REFERENCE, ref_array)
    perms.set_item(COSName.DOCMDP, docmdp_sig)
    catalog.set_item(COSName.PERMS, perms)


def test_get_mdp_permission_skips_non_dictionary_reference_element() -> None:
    """A non-dictionary entry in the /Reference array is skipped (53->51)."""
    doc = PDDocument()
    try:
        ref_array = COSArray()
        ref_array.add(COSInteger.get(7))  # not a COSDictionary
        _wire_perms(doc, ref_array)
        # No DocMDP reference dictionary found → default 0.
        assert SigUtils.get_mdp_permission(doc) == 0
    finally:
        doc.close()


def test_get_mdp_permission_skips_reference_with_non_dict_params() -> None:
    """A DocMDP reference whose /TransformParams is not a dictionary is
    skipped (57->51)."""
    doc = PDDocument()
    try:
        ref = COSDictionary()
        ref.set_item(COSName.TRANSFORM_METHOD, COSName.DOCMDP)
        # /TransformParams present but a name, not a dictionary.
        ref.set_item(COSName.TRANSFORM_PARAMS, COSName.get_pdf_name("Bogus"))
        ref_array = COSArray()
        ref_array.add(ref)
        _wire_perms(doc, ref_array)
        assert SigUtils.get_mdp_permission(doc) == 0
    finally:
        doc.close()
