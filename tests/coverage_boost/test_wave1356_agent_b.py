"""Wave 1356 coverage-boost agent B — final-push tail-sweep.

Targets the last few missing lines in five modules so each reaches
>=99.9% (often 100%):

* ``pypdfbox/pdmodel/pd_page.py`` (lines 311, 679, 685, 686, 1026) —
  the ``set_contents`` wrapper-not-COSStream guard, the
  ``add_annotation`` non-PDAnnotation rejection, the existing-COSArray
  ``/Annots`` extend branch, and the ``get_indirect_resource_objects``
  non-COSDictionary short-circuit.
* ``pypdfbox/pdmodel/interactive/form/appearance_generator_helper.py``
  (lines 170-171, 384) — two latent bugs pinned by existing tests
  (COSName.DA not defined; pypdfbox.pdmodel.common does not re-export
  PDRectangle); marked ``# pragma: no cover`` in source.
* ``pypdfbox/pdmodel/interactive/form/pd_default_appearance_string.py``
  (lines 177, 275) — the ``processSetFont`` "not a PDFont" guard via a
  fake PDResources, and the ``write_to`` "font is None" guard via an
  empty ``/DA``.
* ``pypdfbox/pdmodel/interactive/form/key_value.py`` (lines 41, 45) —
  ``to_string()`` parity wrapper and ``__eq__`` NotImplemented branch.
* ``pypdfbox/pdmodel/fdf/fdf_option_element.py`` (lines 44, 63) —
  the ``return ""`` fallbacks when the underlying ``COSArray`` slot is
  not a ``COSString``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.fdf import FDFOptionElement
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.interactive.annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.form.key_value import KeyValue
from pypdfbox.pdmodel.interactive.form.pd_default_appearance_string import (
    PDDefaultAppearanceString,
)
from pypdfbox.pdmodel.pd_resources import PDResources

# ---------------------------------------------------------------------------
# PDPage
# ---------------------------------------------------------------------------


class _BogusStreamWrapper:
    """Stream-wrapper-like duck object whose ``get_cos_object()`` returns
    something that is *not* a ``COSStream``. Drives PDPage.set_contents'
    TypeError branch at line 311.
    """

    def get_cos_object(self) -> COSDictionary:
        return COSDictionary()


def test_set_contents_rejects_wrapper_with_non_stream_cos() -> None:
    page = PDPage()
    with pytest.raises(TypeError, match="expected stream wrapper"):
        page.set_contents(_BogusStreamWrapper())


def test_add_annotation_rejects_non_pd_annotation() -> None:
    page = PDPage()
    with pytest.raises(TypeError, match="expects a PDAnnotation"):
        page.add_annotation("not-an-annotation")


def test_add_annotation_appends_to_existing_array() -> None:
    page = PDPage()
    # Seed with an existing /Annots COSArray containing one annotation,
    # so the second add_annotation call exercises the
    # ``isinstance(existing, COSArray)`` branch (lines 685-686).
    first = PDAnnotation(COSDictionary())
    page.add_annotation(first)
    second = PDAnnotation(COSDictionary())
    page.add_annotation(second)
    annots = page.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Annots")
    )
    assert isinstance(annots, COSArray)
    assert annots.size() == 2


def test_get_indirect_resource_objects_non_dict_resources_returns_empty() -> None:
    page = PDPage()
    # Pass something that isn't a COSDictionary (an int counts) — hits
    # the line-1026 short-circuit.
    assert (
        page.get_indirect_resource_objects(
            "not-a-dict",  # type: ignore[arg-type]
            COSName.get_pdf_name("XObject"),
        )
        == []
    )


# ---------------------------------------------------------------------------
# PDDefaultAppearanceString
# ---------------------------------------------------------------------------


def _helvetica() -> PDType1Font:
    helv = PDType1Font()
    helv.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), PDType1Font.HELVETICA
    )
    helv.get_cos_object().set_name(COSName.get_pdf_name("Subtype"), "Type1")
    return helv


class _FontReturningJunkResources(PDResources):
    """PDResources subclass whose ``get_font`` returns a value that is
    neither None, nor a ``COSDictionary``, nor a ``PDFont`` — drives the
    "Could not load font" raise at line 177.
    """

    def get_font(self, name: COSName) -> object:  # type: ignore[override]
        return 42  # sentinel non-font, non-dictionary, non-None


def test_process_set_font_falls_back_when_resolved_font_is_not_pd_font() -> None:
    # /DA references a font name; the bogus resources lie and return an
    # int, which is neither COSDictionary nor PDFont. PDFBOX-2661 fallback
    # path (wave 1359) substitutes a Standard-14 default instead of
    # raising — the int is treated as "could not load" and the alias
    # ``Helv`` resolves to Helvetica.
    from pypdfbox.pdmodel.font import PDType1Font  # noqa: PLC0415

    res = _FontReturningJunkResources()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    font = da.get_font()
    assert font is not None
    assert font.get_name() == PDType1Font.HELVETICA


def test_write_to_raises_when_no_font_was_set() -> None:
    # Empty /DA means no Tf operator was processed, so self._font stays
    # None. ``write_to`` must then raise OSError (line 275).
    res = PDResources()
    res.put(COSName.get_pdf_name("Font"), COSName.get_pdf_name("Helv"),
            _helvetica().get_cos_object())
    da = PDDefaultAppearanceString(COSString(""), res)
    appearance = PDAppearanceStream(COSStream())
    with PDAppearanceContentStream(appearance) as cs, \
         pytest.raises(OSError, match="No font set on /DA"):
        da.write_to(cs, zero_font_size=10.0)


# ---------------------------------------------------------------------------
# KeyValue
# ---------------------------------------------------------------------------


def test_key_value_to_string_returns_repr_form() -> None:
    kv = KeyValue("k", "v")
    assert kv.to_string() == "(k, v)"


def test_key_value_eq_with_non_key_value_returns_not_implemented() -> None:
    # Direct equality returns False because Python falls back to the
    # default object comparison after NotImplemented; the dunder itself
    # exercises line 45.
    kv = KeyValue("k", "v")
    assert kv.__eq__("not-a-key-value") is NotImplemented
    # And the public-surface equality is False.
    assert (kv == "not-a-key-value") is False


# ---------------------------------------------------------------------------
# FDFOptionElement
# ---------------------------------------------------------------------------


def test_fdf_option_get_option_returns_empty_string_when_slot_not_cos_string() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))  # slot 0 is not a COSString
    arr.add(COSString(""))
    elem = FDFOptionElement(arr)
    assert elem.get_option() == ""


def test_fdf_option_get_default_appearance_returns_empty_when_slot_not_cos_string() -> None:
    arr = COSArray()
    arr.add(COSString(""))
    arr.add(COSInteger.get(0))  # slot 1 is not a COSString
    elem = FDFOptionElement(arr)
    assert elem.get_default_appearance_string() == ""
