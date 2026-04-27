"""Ported upstream tests for :class:`PDMMType1Font`.

PDFBox 3.0.x has **no dedicated** ``PDMMType1FontTest.java`` — the
upstream class is a marker subclass of ``PDType1Font`` with a single
constructor and no behaviour of its own, so upstream covers it
indirectly through ``PDFontTest#testPDFontFactoryMMType1`` (already
ported in :mod:`tests.pdmodel.font.upstream.test_pd_font_factory`).

The cases below mirror what an explicit ``PDMMType1FontTest`` *would*
have asserted if upstream had written one, derived from the Java class
shape:

```java
public class PDMMType1Font extends PDType1Font {
    public PDMMType1Font(COSDictionary fontDictionary) throws IOException {
        super(fontDictionary);
    }
}
```

The hand-written file in :mod:`tests.pdmodel.font.test_pd_mm_type1_font`
covers the broader inherited surface; this file pins the contract that
*would* be ported one-to-one if upstream ever adds a dedicated test.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font


# Mirrors the implicit upstream contract: constructing with a font dict
# preserves identity (no defensive copy).
def test_constructor_preserves_dict_identity() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "MMType1")  # type: ignore[attr-defined]
    font = PDMMType1Font(raw)
    assert font.get_cos_object() is raw


# Mirrors the upstream class declaration: PDMMType1Font extends
# PDType1Font. PDFBox callers rely on this for ``instanceof`` dispatch.
def test_is_instance_of_pd_type1_font() -> None:
    font = PDMMType1Font(COSDictionary())
    assert isinstance(font, PDType1Font)


# Mirrors the upstream constant — the subtype name must round-trip
# through the dict so writers re-serialize ``/Subtype /MMType1``.
def test_subtype_round_trips_through_dict() -> None:
    font = PDMMType1Font()
    cos = font.get_cos_object()
    sub = cos.get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
    assert sub == "MMType1"


# Skipped: upstream has no dedicated test fixture (no ``MMType1.pdf``)
# and the embedded MM Type 1 program path is covered by the parent
# class's tests in ``test_pd_type1_font_parity.py``. If upstream adds
# a ``MMType1FontTest`` that loads a real MM font, port that here.
