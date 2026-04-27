from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName


class PDMarkedContent:
    """
    A marked content sequence. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDMarkedContent``.

    Holds the BMC/BDC tag (a name like ``/P``, ``/Span``, ``/Artifact``), the
    optional property dictionary parsed from the BDC operand, and the ordered
    list of contained items. Upstream's content list is heterogeneous —
    ``TextPosition``, child ``PDMarkedContent``, or ``PDXObject`` — so this
    port keeps the contents typed as ``list[Any]`` rather than a tight union.
    """

    __slots__ = ("_tag", "_properties", "_contents")

    def __init__(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        self._tag: str | None = tag.get_name() if tag is not None else None
        self._properties: COSDictionary | None = properties
        self._contents: list[Any] = []

    # ---------- factory ----------

    @classmethod
    def create(
        cls,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> PDMarkedContent:
        """Mirror upstream ``PDMarkedContent.create``: dispatch on the tag.

        ``/Artifact`` returns a ``PDArtifactMarkedContent``; everything else
        returns a plain ``PDMarkedContent``.
        """
        # Local import to avoid the taggedpdf -> markedcontent -> taggedpdf
        # cycle at module-load time.
        if tag is not None and tag.get_name() == "Artifact":
            from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_artifact_marked_content import (
                PDArtifactMarkedContent,
            )

            return PDArtifactMarkedContent(properties)
        return cls(tag, properties)

    # ---------- accessors ----------

    def get_tag(self) -> str | None:
        return self._tag

    def get_properties(self) -> COSDictionary | None:
        return self._properties

    def get_mcid(self) -> int:
        """Marked-content identifier (``/MCID``), or ``-1`` if absent."""
        if self._properties is None:
            return -1
        return self._properties.get_int(COSName.get_pdf_name("MCID"))

    def get_language(self) -> str | None:
        if self._properties is None:
            return None
        return self._properties.get_name(COSName.get_pdf_name("Lang"))

    def get_actual_text(self) -> str | None:
        if self._properties is None:
            return None
        return self._properties.get_string(COSName.get_pdf_name("ActualText"))

    def get_alternate_description(self) -> str | None:
        if self._properties is None:
            return None
        return self._properties.get_string(COSName.get_pdf_name("Alt"))

    def get_expanded_form(self) -> str | None:
        if self._properties is None:
            return None
        return self._properties.get_string(COSName.get_pdf_name("E"))

    def get_contents(self) -> list[Any]:
        return self._contents

    # ---------- mutators ----------

    def add_text(self, text: Any) -> None:
        """Append a ``TextPosition``-like item. Typed loosely because the
        ``text`` cluster has not landed yet."""
        self._contents.append(text)

    def add_marked_content(self, marked_content: PDMarkedContent) -> None:
        self._contents.append(marked_content)

    def add_x_object(self, xobject: Any) -> None:
        """Append a ``PDXObject``-like item. Typed loosely because the
        graphics-XObject cluster has not landed yet."""
        self._contents.append(xobject)

    # ---------- repr ----------

    def __repr__(self) -> str:
        return (
            f"tag={self._tag}, "
            f"properties={self._properties!r}, "
            f"contents={self._contents!r}"
        )
