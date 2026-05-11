"""Type 1 font encoding — built-in or AFM-derived.

Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.Type1Encoding`` (PDFBox
3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/
Type1Encoding.java`` lines 25-76).

A :class:`Type1Encoding` is an :class:`Encoding` whose ``(code, name)``
pairs come from the Type 1 font program itself rather than from a PDF
``/Encoding`` dictionary. Two factory paths:

* :meth:`from_font_box` — copy the code-to-name map from a FontBox-level
  :class:`fontbox.encoding.Encoding` (e.g. the ``Encoding`` array
  parsed out of a Type 1 ``Encoding`` block).
* Constructor taking AFM ``FontMetrics`` — pull ``(C, N)`` pairs from
  the AFM ``CharMetric`` records.

The encoding never serialises as a COS object (it's font-program
intrinsic), so :meth:`get_cos_object` returns ``None`` matching
upstream.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSBase

from .encoding import Encoding

if TYPE_CHECKING:
    from collections.abc import Mapping


class Type1Encoding(Encoding):
    """Type 1 font's built-in encoding.

    Mirrors upstream Java line 28-76. Three constructor paths:

    * No args — empty encoding, callers populate via :meth:`add`.
    * From a FontBox :class:`Encoding` via :meth:`from_font_box`.
    * From AFM :class:`FontMetrics` (passed through ``fontMetrics``
      keyword for compatibility with the upstream second constructor).
    """

    def __init__(self, font_metrics: Any | None = None) -> None:
        # Upstream offers two constructors (Java line 48-63):
        # (1) no-args -> empty encoding (callers add manually).
        # (2) FontMetrics -> populated from the AFM CharMetrics list.
        super().__init__()
        if font_metrics is not None:
            # Mirror upstream constructor body (Java line 57-63):
            # ``for (CharMetric nextMetric : fontMetrics.getCharMetrics())
            # add(nextMetric.getCharacterCode(), nextMetric.getName());``
            for metric in font_metrics.get_char_metrics():
                code = metric.get_character_code()
                name = metric.get_name()
                if code >= 0:
                    # AFM uses -1 for unencoded glyphs; upstream's add()
                    # accepts them but the resulting code is meaningless.
                    # Skip them so callers don't have to filter.
                    self.add(code, name)

    @classmethod
    def from_font_box(cls, encoding: Any) -> Type1Encoding:
        """Build a :class:`Type1Encoding` from a FontBox encoding.

        Mirrors upstream static factory ``fromFontBox`` (Java line 36-43):
        copies the FontBox encoding's ``code -> name`` map into a fresh
        :class:`Type1Encoding`.
        """
        # Upstream ``codeToName.forEach(enc::add)``; we accept any
        # mapping-like object (FontBox encoders expose
        # ``get_code_to_name_map`` returning a dict).
        code_to_name: Mapping[int, str] = encoding.get_code_to_name_map()
        enc = cls()
        for code, name in code_to_name.items():
            enc.add(code, name)
        return enc

    def get_cos_object(self) -> COSBase | None:
        # Upstream returns ``null`` here (Java line 66-69) — built-in
        # encodings cannot be serialised as a COS object.
        return None

    def get_encoding_name(self) -> str:
        # Upstream returns the literal "built-in (Type 1)" (Java
        # line 72-75).
        return "built-in (Type 1)"


__all__ = ["Type1Encoding"]
