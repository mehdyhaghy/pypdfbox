from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_resources import PDResources

# ---------- PDType3Font ----------


def test_type3_font_sub_type_constant() -> None:
    assert PDType3Font.SUB_TYPE == "Type3"


def test_type3_font_construction_sets_type_and_subtype() -> None:
    font = PDType3Font()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "Type3"  # type: ignore[attr-defined]
    assert font.get_subtype() == "Type3"


def test_type3_font_char_procs_round_trip() -> None:
    font = PDType3Font()
    assert font.get_char_procs() is None

    char_procs = COSDictionary()
    font.set_char_procs(char_procs)
    assert font.get_char_procs() is char_procs
    # Underlying dict reflects the set.
    assert font.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("CharProcs")
    ) is char_procs

    font.set_char_procs(None)
    assert font.get_char_procs() is None


def test_type3_font_font_b_box_round_trip() -> None:
    font = PDType3Font()
    assert font.get_font_b_box() is None

    bbox = COSArray(
        [
            COSInteger.get(0),
            COSInteger.get(0),
            COSInteger.get(750),
            COSInteger.get(1000),
        ]
    )
    font.set_font_b_box(bbox)
    assert font.get_font_b_box() is bbox

    font.set_font_b_box(None)
    assert font.get_font_b_box() is None


def test_type3_font_font_matrix_round_trip() -> None:
    font = PDType3Font()
    # Default per PDF 32000-1 §9.2.4 when /FontMatrix is absent.
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    # Use exactly-representable IEEE-754 single-precision values (COSFloat is 32-bit).
    font.set_font_matrix([0.5, 0.0, 0.0, 0.5, 0.0, 0.0])
    assert font.get_font_matrix() == [0.5, 0.0, 0.0, 0.5, 0.0, 0.0]


def test_type3_font_resources_round_trip() -> None:
    font = PDType3Font()
    assert font.get_resources() is None

    resources = PDResources()
    # Stash a marker on the resources dict so we can prove identity is preserved.
    resources.get_cos_object().set_name(COSName.get_pdf_name("ProcSetMarker"), "X")
    font.set_resources(resources)

    out = font.get_resources()
    assert isinstance(out, PDResources)
    assert out.get_cos_object() is resources.get_cos_object()
    # Underlying font dict carries the same /Resources entry.
    assert font.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Resources")
    ) is resources.get_cos_object()

    font.set_resources(None)
    assert font.get_resources() is None


# ---------- PDMMType1Font ----------


def test_mm_type1_font_sub_type_constant() -> None:
    assert PDMMType1Font.SUB_TYPE == "MMType1"


def test_mm_type1_font_construction_sets_type_and_subtype() -> None:
    font = PDMMType1Font()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "MMType1"  # type: ignore[attr-defined]
    assert font.get_subtype() == "MMType1"


def test_mm_type1_font_extends_type1_font() -> None:
    assert issubclass(PDMMType1Font, PDType1Font)


# ---------- PDType1CFont ----------


def test_type1c_font_sub_type_constant_matches_type1() -> None:
    # Type1C is NOT a separate /Subtype on the font dict; it's signalled
    # by /FontFile3 + /Subtype /Type1C on the FontDescriptor.
    assert PDType1CFont.SUB_TYPE == "Type1"


def test_type1c_font_construction_sets_type_and_subtype() -> None:
    font = PDType1CFont()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "Type1"  # type: ignore[attr-defined]
    assert font.get_subtype() == "Type1"


def test_type1c_font_extends_type1_font() -> None:
    assert issubclass(PDType1CFont, PDType1Font)
