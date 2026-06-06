from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)

_R: COSName = COSName.get_pdf_name("R")
_N: COSName = COSName.get_pdf_name("N")
_P: COSName = COSName.get_pdf_name("P")
_A: COSName = COSName.get_pdf_name("A")
_T: COSName = COSName.get_pdf_name("T")

_NAME_P: COSName = COSName.get_pdf_name("P")
_NAME_C: COSName = COSName.get_pdf_name("C")


class PDTargetDirectory:
    """Target dictionary specifying path information to the target document
    of an embedded GoTo action. Mirrors PDFBox ``PDTargetDirectory``
    (PDF 32000-1 Table 202).

    Per spec / upstream ``PDTargetDirectory``:
        /R — relationship name: ``P`` (parent) or ``C`` (child).
        /N — name of the file in the ``/EmbeddedFiles`` name tree.
        /P — either the integer page index of the target (0-based) or the
             name of a named destination in the target document.
        /A — either the integer index of an annotation on the target page
             or the value of its ``/NM`` entry.
        /T — chained ``PDTargetDirectory`` for the next nested target.

    Typed-return parity (Apache PDFBox 3.0.7, ``PDTargetDirectory.java``):
        * :meth:`get_relationship` returns a :class:`COSName` (or ``None``);
        * :meth:`get_page_number` / :meth:`get_annotation_index` are
          ``getInt(..., -1)``-backed — they return ``-1`` for an absent or
          non-integer (string-form) value, NOT ``None``;
        * :meth:`get_named_destination` returns a :class:`PDNamedDestination`
          wrapper (or ``None``).
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        # Upstream's no-arg constructor (PDTargetDirectory.java line 40-43)
        # creates a bare empty COSDictionary — it does NOT stamp a default /R
        # relationship. A fresh target therefore reports get_relationship() ==
        # None and saves an empty dictionary, matching Apache PDFBox 3.0.7.
        if dictionary is None:
            self._dict = COSDictionary()
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /R relationship ----------

    def get_relationship(self) -> COSName | None:
        """The ``/R`` relationship as a :class:`COSName`. Valid values are
        ``P`` (target is the parent of the current document) and ``C``
        (target is a child). Invalid values or ``None`` are also returned.
        Mirrors upstream ``getRelationship()`` (PDTargetDirectory.java
        line 74-77: ``dict.getCOSName(COSName.R)``)."""
        return self._dict.get_cos_name(_R)

    def set_relationship(self, relationship: COSName | str) -> None:
        """Set the ``/R`` relationship. Accepts a :class:`COSName` (the
        upstream contract — ``setRelationship(COSName)``) or, for
        snake_case caller convenience, the bare ``str`` ``"P"`` / ``"C"``.
        Mirrors upstream PDTargetDirectory.java line 88-95: rejects any
        value other than ``P`` or ``C`` (Java ``IllegalArgumentException``;
        here ``ValueError``)."""
        if isinstance(relationship, COSName):
            name = relationship
        else:
            name = COSName.get_pdf_name(relationship)
        if name != _NAME_P and name != _NAME_C:
            raise ValueError(
                f"The only valid are P or C, not {name.get_name()}"
            )
        self._dict.set_item(_R, name)

    # ---------- /N target embedded-file name ----------

    def get_filename(self) -> str | None:
        """The name of the embedded file in the target catalog's
        ``/EmbeddedFiles`` name tree (``/N``). Mirrors upstream
        ``getFilename()`` (PDTargetDirectory.java line 103-106:
        ``dict.getString(COSName.N)``)."""
        return self._dict.get_string(_N)

    def set_filename(self, name: str | None) -> None:
        """Set the embedded-file name (``/N``). ``None`` removes the entry.
        Mirrors upstream ``setFilename(String)`` (line 114-117:
        ``dict.setString(COSName.N, filename)`` — ``setString(null)``
        removes)."""
        self._dict.set_string(_N, name)

    # ---------- /N filename — pypdfbox descriptive alias ----------

    def get_target_filename(self) -> str | None:
        """Descriptive alias of :meth:`get_filename`."""
        return self.get_filename()

    def set_target_filename(self, name: str | None) -> None:
        """Descriptive alias of :meth:`set_filename`."""
        self.set_filename(name)

    # ---------- /P page number (int form) ----------

    def get_page_number(self) -> int:
        """The zero-based page index from ``/P``, or ``-1`` when ``/P`` is
        absent or not an integer (e.g. the named-destination string form —
        use :meth:`get_named_destination` for that case). Mirrors upstream
        ``getPageNumber()`` (PDTargetDirectory.java line 149-152:
        ``dict.getInt(COSName.P, -1)``)."""
        return self._dict.get_int(_P, -1)

    def set_page_number(self, page_number: int | None) -> None:
        """Set the zero-based page index (``/P``). A value ``< 0`` (or
        ``None``) removes the entry. Mirrors upstream ``setPageNumber(int)``
        (PDTargetDirectory.java line 160-170: ``if (pageNumber < 0)
        removeItem else setInt``)."""
        if page_number is None or page_number < 0:
            self._dict.remove_item(_P)
            return
        self._dict.set_int(_P, page_number)

    # ---------- /P named destination (string form) ----------

    def get_named_destination(self) -> PDNamedDestination | None:
        """The named destination from ``/P`` when ``/P`` holds the string
        form, otherwise ``None`` (e.g. for the integer page-index form —
        use :meth:`get_page_number`). Mirrors upstream
        ``getNamedDestination()`` (PDTargetDirectory.java line 178-186:
        a ``COSString`` ``/P`` is wrapped in a ``PDNamedDestination``)."""
        v = self._dict.get_dictionary_object(_P)
        if isinstance(v, COSString):
            return PDNamedDestination(v)
        return None

    def set_named_destination(
        self, dest: PDNamedDestination | str | None
    ) -> None:
        """Set a named destination on ``/P``. ``None`` removes the entry.
        Accepts a :class:`PDNamedDestination` (the upstream contract —
        ``setNamedDestination(PDNamedDestination)``, PDTargetDirectory.java
        line 194-204) or, for snake_case convenience, a bare ``str`` (wrapped
        in a ``COSString``, matching upstream's ``COSString``-backed form)."""
        if dest is None:
            self._dict.remove_item(_P)
            return
        if isinstance(dest, PDNamedDestination):
            cos = dest.get_cos_object()
            if cos is None:
                self._dict.remove_item(_P)
            else:
                self._dict.set_item(_P, cos)
            return
        self._dict.set_string(_P, dest)

    # ---------- /A annotation index (int) ----------

    def get_annotation_index(self) -> int:
        """The zero-based index of the annotation in the target page's
        ``/Annots`` array, or ``-1`` when ``/A`` is absent or not an integer
        (e.g. the annotation-name string form — use
        :meth:`get_annotation_name`). Mirrors upstream
        ``getAnnotationIndex()`` (PDTargetDirectory.java line 212-215:
        ``dict.getInt(COSName.A, -1)``)."""
        return self._dict.get_int(_A, -1)

    def set_annotation_index(self, index: int | None) -> None:
        """Set the zero-based annotation index (``/A``). A value ``< 0`` (or
        ``None``) removes the entry. Mirrors upstream
        ``setAnnotationIndex(int)`` (PDTargetDirectory.java line 223-233:
        ``if (index < 0) removeItem else setInt``)."""
        if index is None or index < 0:
            self._dict.remove_item(_A)
            return
        self._dict.set_int(_A, index)

    # ---------- /A annotation index — pypdfbox descriptive alias ----------

    def get_annotation_number(self) -> int | None:
        """None-form sibling of :meth:`get_annotation_index`: returns the
        integer index when ``/A`` is an integer, otherwise ``None`` (rather
        than the upstream ``-1`` sentinel). Convenience for callers that
        treat absence as ``None``."""
        v = self._dict.get_dictionary_object(_A)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def set_annotation_number(self, annotation_number: int | None) -> None:
        """Descriptive alias of :meth:`set_annotation_index`."""
        self.set_annotation_index(annotation_number)

    # ---------- /A annotation name (string form) ----------

    def get_annotation_name(self) -> str | None:
        """Annotation ``/NM`` value from ``/A`` (string form), or ``None``
        when ``/A`` is absent or an integer index (use
        :meth:`get_annotation_index`). Mirrors upstream
        ``getAnnotationName()`` (PDTargetDirectory.java line 242-245:
        ``dict.getString(COSName.A)``)."""
        return self._dict.get_string(_A)

    def set_annotation_name(self, name: str | None) -> None:
        """Set the annotation ``/NM`` value (string form of ``/A``).
        ``None`` removes the entry. Mirrors upstream
        ``setAnnotationName(String)`` (PDTargetDirectory.java line 252-255:
        ``dict.setString(COSName.A, name)``)."""
        self._dict.set_string(_A, name)

    # ---------- /T chained target ----------

    def get_target_directory(self) -> PDTargetDirectory | None:
        """The chained ``/T`` target, or ``None`` when the current document
        is the target file containing the destination. Mirrors upstream
        ``getTargetDirectory()`` (PDTargetDirectory.java line 126-130:
        a ``COSDictionary`` ``/T`` is wrapped, else ``null``)."""
        v = self._dict.get_cos_dictionary(_T)
        if v is not None:
            return PDTargetDirectory(v)
        return None

    def set_target_directory(self, target: PDTargetDirectory | None) -> None:
        """Set the chained ``/T`` target. ``None`` removes the entry.
        Mirrors upstream ``setTargetDirectory(PDTargetDirectory)``
        (PDTargetDirectory.java line 138-141: ``dict.setItem(COSName.T,
        targetDirectory)`` — a ``null`` argument removes)."""
        if target is None:
            self._dict.remove_item(_T)
            return
        self._dict.set_item(_T, target.get_cos_object())

    # ---------- /T chained target — pypdfbox descriptive alias ----------

    def get_target(self) -> PDTargetDirectory | None:
        """Descriptive alias of :meth:`get_target_directory`."""
        return self.get_target_directory()

    def set_target(self, target: PDTargetDirectory | None) -> None:
        """Descriptive alias of :meth:`set_target_directory`."""
        self.set_target_directory(target)


__all__ = ["PDTargetDirectory"]
