from __future__ import annotations

from collections.abc import Iterator
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
        # Local import to avoid the markedcontent -> artifact -> markedcontent
        # cycle at module-load time. Mirrors upstream
        # ``PDMarkedContent.create``.
        if tag is not None and tag.get_name() == "Artifact":
            from .pd_artifact_marked_content import PDArtifactMarkedContent

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

    # ---------- predicate helpers ----------

    def is_artifact(self) -> bool:
        """Return ``True`` iff this is an ``/Artifact`` marked-content sequence.

        Mirrors the dispatch condition in :meth:`create` — artifact
        marked-content is the only tag PDFBox treats specially. Useful when
        traversing a heterogeneous content list without performing an
        ``isinstance`` check against ``PDArtifactMarkedContent``.
        """
        return self._tag == "Artifact"

    def has_mcid(self) -> bool:
        """Return ``True`` iff a non-negative ``/MCID`` is present.

        Convenience over comparing :meth:`get_mcid` against the ``-1``
        sentinel. PDF/UA-aware callers want to skip marked-content sequences
        that lack an MCID without remembering the sentinel value.
        """
        return self.get_mcid() != -1

    # ---------- container protocol over contents ----------

    def __len__(self) -> int:
        """Number of items in :meth:`get_contents`.

        Matches the Pythonic ``len(mc)`` shorthand for ``len(mc.get_contents())``.
        """
        return len(self._contents)

    def __iter__(self) -> Iterator[Any]:
        """Iterate items in :meth:`get_contents` in order.

        Lets callers write ``for item in mc:`` instead of
        ``for item in mc.get_contents():``.
        """
        return iter(self._contents)

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

    # Mirror upstream's ``toString()`` — Java's ``Object.toString`` is
    # accessible via ``str(obj)`` in Python, which calls ``__str__``.
    # Delegate to ``__repr__`` so both paths produce the same upstream
    # string. Upstream body is literally
    # ``"tag=" + tag + ", properties=" + properties + ", contents=" + contents``.
    __str__ = __repr__
