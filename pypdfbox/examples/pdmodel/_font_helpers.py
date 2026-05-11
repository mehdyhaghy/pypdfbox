"""Internal helpers for the ``pdmodel`` examples.

The Java ``PDType1Font`` constructor accepts a ``FontName`` enum directly
(``new PDType1Font(FontName.HELVETICA_BOLD)``). The pypdfbox equivalent
currently takes only an optional ``COSDictionary``, so this helper bridges
the gap by constructing the dictionary that upstream's enum-accepting
constructor would emit.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.util.matrix import Matrix


def apply_transform(content_stream: Any, matrix: Matrix) -> None:
    """Apply ``matrix`` to ``content_stream`` via the six-float ``cm``
    operator. Mirrors the Java overload ``PDPageContentStream.transform(Matrix)``
    that the pypdfbox port has not yet surfaced.
    """
    content_stream.transform(
        matrix.get_scale_x(),
        matrix.get_shear_y(),
        matrix.get_shear_x(),
        matrix.get_scale_y(),
        matrix.get_translate_x(),
        matrix.get_translate_y(),
    )


def make_standard14_type1_font(name: FontName | str) -> PDType1Font:
    """Return a :class:`PDType1Font` backed by a minimal Standard-14
    font dictionary. Mirrors the Java ``new PDType1Font(FontName)`` ctor
    shape used pervasively throughout the upstream examples.
    """
    value = name.value if isinstance(name, FontName) else name
    font_dict = COSDictionary()
    font_dict.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), value)
    return PDType1Font(font_dict)
