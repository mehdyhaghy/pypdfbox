"""Upstream port of ``TestUtils.java``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/TestUtils.java``
(PDFBox 3.0.x).

Upstream ``TestUtils`` is a helper class with a single static method
``getStringsFromStream`` used by ``ControlCharacterTest``. This port
exposes the same helper as a module-level function so other upstream
ports (``test_control_character.py``) can import it.

The file also smoke-tests the helper itself so it counts as a real
pytest module rather than a pure utility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSFloat, COSName, COSString
from pypdfbox.pdfparser import PDFStreamParser
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.form.pd_field import PDField


def get_strings_from_stream(field: PDField) -> list[str]:
    """Extract trimmed COSString tokens from a field widget's
    normal-appearance content stream.

    Mirrors upstream ``TestUtils.getStringsFromStream`` (line 39).
    """
    widget = field.get_widgets()[0]
    appearance = widget.get_normal_appearance_stream()
    if appearance is None:
        return []
    parser = PDFStreamParser.from_content_stream(appearance)
    tokens = parser.parse()
    return [t.get_string().strip() for t in tokens if isinstance(t, COSString)]


def test_get_strings_from_stream_extracts_cos_strings() -> None:
    """Smoke test for :func:`get_strings_from_stream` against a synthetic
    appearance stream. The upstream helper has no unit test of its own —
    its contract is exercised indirectly by ``ControlCharacterTest``."""
    acro_form = PDAcroForm()
    tf = PDTextField(acro_form)
    tf.get_cos_object().set_item(
        COSName.get_pdf_name("Rect"),
        COSArray([COSFloat(0), COSFloat(0), COSFloat(200), COSFloat(20)]),
    )
    tf.get_cos_object().set_string(COSName.get_pdf_name("DA"), "/Helv 12 Tf 0 g")
    tf.set_value("hello", regenerate_appearance=True)

    strings = get_strings_from_stream(tf)
    assert "hello" in strings
