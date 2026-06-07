"""Live PDFBox differential parity for ``PDResources`` key allocation.

Does pypdfbox's :meth:`PDResources.add` / ``_create_key`` mint exactly the same
generated resource names as Apache PDFBox 3.0.7 ``PDResources.createKey``?

Upstream ``createKey`` (PDResources.java) seeds an integer to the category
sub-dictionary's ``keySet().size()`` and *pre-increments* it, then walks upward
past any collision:

    int counter = subDict.keySet().size();
    do { counter++; key = prefix + counter; } while (subDict.containsKey(key));

So the numbering is **1-based** (``/gs1`` / ``/Im1`` / ``/Form1`` …), and it is
*not* the smallest free integer — a sub-dict holding only ``{gs5}`` (size 1)
yields ``gs2``, and a gap ``{F0, F2}`` (size 2) yields ``F3``. pypdfbox
previously minted 0-based smallest-free keys (``/gs0`` …); wave 1509 aligned
``_create_key`` to upstream byte-for-byte.

The Java side is ``oracle/probes/ResourceCreateKeyProbe.java``; here we rebuild
the identical scenarios in pypdfbox and assert the dumped key sequence matches.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.shading import PDShadingType2
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState
from tests.oracle.harness import requires_oracle, run_probe_text


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _plain_property_list() -> PDPropertyList:
    return PDPropertyList.create(COSDictionary())


def _reproduce() -> dict[str, str]:
    """Rebuild every ResourceCreateKeyProbe scenario in pypdfbox and return the
    same ``label -> key`` mapping the Java probe prints."""
    out: dict[str, str] = {}

    # First / second / third ExtGState key on empty resources.
    r1 = PDResources()
    out["extgstate_first"] = r1.add(PDExtendedGraphicsState()).get_name()
    out["extgstate_second"] = r1.add(PDExtendedGraphicsState()).get_name()
    out["extgstate_third"] = r1.add(PDExtendedGraphicsState()).get_name()

    # Pre-existing /gs1 collision (size 1) -> gs2.
    r2 = PDResources()
    e2 = COSDictionary()
    e2.set_item(_name("gs1"), COSDictionary())
    r2.get_cos_object().set_item(PDResources.EXT_G_STATE, e2)
    out["collision_gs1"] = r2.add(PDExtendedGraphicsState()).get_name()

    # Pre-existing /gs5 only (size 1) -> gs2 (not the lowest free gs1).
    r3 = PDResources()
    e3 = COSDictionary()
    e3.set_item(_name("gs5"), COSDictionary())
    r3.get_cos_object().set_item(PDResources.EXT_G_STATE, e3)
    out["seed_from_size_gs5"] = r3.add(PDExtendedGraphicsState()).get_name()

    # Gap {F0, F2} (size 2) -> F3 (no gap fill).
    r4 = PDResources()
    f4 = COSDictionary()
    f4.set_item(_name("F0"), COSDictionary())
    f4.set_item(_name("F2"), COSDictionary())
    r4.get_cos_object().set_item(PDResources.FONT, f4)
    out["gap_F0_F2"] = r4.add(PDType1Font()).get_name()

    # First key per prefix on empty resources.
    out["prefix_extgstate"] = PDResources().add(PDExtendedGraphicsState()).get_name()
    out["prefix_shading"] = PDResources().add(PDShadingType2(COSDictionary())).get_name()
    out["prefix_colorspace"] = PDResources().add(PDDeviceRGB.INSTANCE).get_name()
    out["prefix_pattern"] = PDResources().add(PDTilingPattern()).get_name()
    out["prefix_properties"] = PDResources().add(_plain_property_list()).get_name()
    out["prefix_ocg"] = PDResources().add(PDOptionalContentGroup("L")).get_name()
    out["prefix_font"] = PDResources().add(PDType1Font()).get_name()
    out["prefix_form"] = PDResources().add(PDFormXObject(COSStream())).get_name()

    # Two distinct resources in the same /Properties sub-dict: the second
    # seeds from size 1 -> index 2 regardless of prefix.
    r5 = PDResources()
    out["mixed_properties_ocg"] = r5.add(PDOptionalContentGroup("L")).get_name()
    out["mixed_properties_plain"] = r5.add(_plain_property_list()).get_name()

    return out


def _parse_probe(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.strip().splitlines():
        if "=" in line:
            label, key = line.split("=", 1)
            result[label.strip()] = key.strip()
    return result


def test_create_key_sequence_matches_pdfbox() -> None:
    # Standalone value pins (independent of the live oracle) so the expected
    # 1-based upstream sequence is documented even when the jar is absent.
    py = _reproduce()
    assert py == {
        "extgstate_first": "gs1",
        "extgstate_second": "gs2",
        "extgstate_third": "gs3",
        "collision_gs1": "gs2",
        "seed_from_size_gs5": "gs2",
        "gap_F0_F2": "F3",
        "prefix_extgstate": "gs1",
        "prefix_shading": "sh1",
        "prefix_colorspace": "cs1",
        "prefix_pattern": "p1",
        "prefix_properties": "Prop1",
        "prefix_ocg": "oc1",
        "prefix_font": "F1",
        "prefix_form": "Form1",
        "mixed_properties_ocg": "oc1",
        "mixed_properties_plain": "Prop2",
    }


@requires_oracle
def test_create_key_sequence_matches_live_oracle() -> None:
    java = _parse_probe(run_probe_text("ResourceCreateKeyProbe"))
    py = _reproduce()
    assert py == java
