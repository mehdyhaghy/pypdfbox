from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

# Page label dictionary keys (PDF 32000-1:2008 §12.4.2, Table 159).
_KEY_START: COSName = COSName.get_pdf_name("St")
_KEY_PREFIX: COSName = COSName.get_pdf_name("P")
_KEY_STYLE: COSName = COSName.get_pdf_name("S")


class PDPageLabelRange:
    """
    One entry in a ``PDPageLabels`` number tree. Mirrors
    ``org.apache.pdfbox.pdmodel.common.PDPageLabelRange``.
    """

    # Style entry values (PDF 32000-1:2008 §12.4.2, Table 159).
    STYLE_DECIMAL: str = "D"
    STYLE_ROMAN_UPPER: str = "R"
    STYLE_ROMAN_LOWER: str = "r"
    STYLE_LETTERS_UPPER: str = "A"
    STYLE_LETTERS_LOWER: str = "a"

    def __init__(self, dict_: COSDictionary | None = None) -> None:
        self._root = dict_ if dict_ is not None else COSDictionary()

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._root

    # ---------- style ----------

    def get_style(self) -> str | None:
        return self._root.get_name(_KEY_STYLE)

    def set_style(self, style: str | None) -> None:
        if style is None:
            self._root.remove_item(_KEY_STYLE)
        else:
            self._root.set_name(_KEY_STYLE, style)

    # ---------- start ----------

    def get_start(self) -> int:
        # Upstream defaults to 1 when /St is absent.
        v = self._root.get_int(_KEY_START, 1)
        return v if v != -1 else 1

    def set_start(self, start: int) -> None:
        if start <= 0:
            raise ValueError(
                "The page numbering start value must be a positive integer"
            )
        self._root.set_int(_KEY_START, start)

    # ---------- prefix ----------

    def get_prefix(self) -> str | None:
        return self._root.get_string(_KEY_PREFIX)

    def set_prefix(self, prefix: str | None) -> None:
        if prefix is None:
            self._root.remove_item(_KEY_PREFIX)
        else:
            self._root.set_string(_KEY_PREFIX, prefix)

    def __repr__(self) -> str:
        return (
            f"PDPageLabelRange(style={self.get_style()!r}, "
            f"start={self.get_start()}, prefix={self.get_prefix()!r})"
        )


__all__ = ["PDPageLabelRange"]
