from __future__ import annotations

from typing import IO

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

from .fdf_annotation import FDFAnnotation
from .fdf_field import FDFField
from .fdf_java_script import FDFJavaScript
from .fdf_page import FDFPage

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_F: COSName = COSName.get_pdf_name("F")
_ID: COSName = COSName.get_pdf_name("ID")
_STATUS: COSName = COSName.get_pdf_name("Status")
_PAGES: COSName = COSName.get_pdf_name("Pages")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_DIFFERENCES: COSName = COSName.get_pdf_name("Differences")
_TARGET: COSName = COSName.get_pdf_name("Target")
_EMBEDDED_FDFS: COSName = COSName.get_pdf_name("EmbeddedFDFs")
_JAVA_SCRIPT: COSName = COSName.get_pdf_name("JavaScript")


class FDFDictionary:
    """The ``/FDF`` sub-dictionary inside the FDF catalog. Mirrors
    ``org.apache.pdfbox.pdmodel.fdf.FDFDictionary``.

    Carries the form fields (``/Fields``), the source PDF reference
    (``/F``), file ID (``/ID``), status text (``/Status``), encoding
    (``/Encoding``), and any FDF annotations (``/Annots``).
    """

    def __init__(self, fdf: COSDictionary | None = None) -> None:
        self._fdf: COSDictionary = fdf if fdf is not None else COSDictionary()

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._fdf

    # ---------- /Fields ----------

    def get_fields(self) -> list[FDFField] | None:
        v = self._fdf.get_dictionary_object(_FIELDS)
        if not isinstance(v, COSArray):
            return None
        out: list[FDFField] = []
        for entry in v:
            resolved = entry.get_object() if isinstance(entry, COSObject) else entry
            if isinstance(resolved, COSDictionary):
                out.append(FDFField(resolved))
        return out

    def has_fields(self) -> bool:
        return isinstance(self._fdf.get_dictionary_object(_FIELDS), COSArray)

    def clear_fields(self) -> None:
        self.set_fields(None)

    def set_fields(self, fields: list[FDFField] | None) -> None:
        if fields is None:
            self._fdf.remove_item(_FIELDS)
            return
        arr = COSArray()
        for f in fields:
            arr.add(f.get_cos_object())
        self._fdf.set_item(_FIELDS, arr)

    # ---------- /F (source PDF file specification) ----------

    def get_file(self) -> PDFileSpecification | None:
        """Return ``/F`` typed as a :class:`PDFileSpecification`.

        PDFBox exposes FDF ``/F`` as a file specification, not as a raw
        string. A simple string-backed ``/F`` therefore returns a
        :class:`PDSimpleFileSpecification`, while a dictionary-backed entry
        returns a :class:`PDComplexFileSpecification`.
        """
        return PDFileSpecification.create_fs(self._fdf.get_dictionary_object(_F))

    def has_file(self) -> bool:
        return self._fdf.get_dictionary_object(_F) is not None

    def clear_file(self) -> None:
        self.set_file(None)

    def set_file(self, file: PDFileSpecification | COSBase | str | bytes | None) -> None:
        if file is None:
            self._fdf.remove_item(_F)
            return
        if isinstance(file, PDFileSpecification):
            self._fdf.set_item(_F, file.get_cos_object())
            return
        if isinstance(file, (str, bytes)):
            self._fdf.set_string(_F, file)
            return
        self._fdf.set_item(_F, file)

    # Plain string convenience over /F.

    def get_file_path(self) -> str | None:
        try:
            fs = self.get_file()
        except OSError:
            return None
        if fs is None:
            return None
        return fs.get_file()

    def get_f(self) -> str | None:
        return self.get_file_path()

    def set_f(self, file: str | None) -> None:
        self.set_file(file)

    # ---------- /ID ----------

    def get_id(self) -> COSArray | None:
        v = self._fdf.get_dictionary_object(_ID)
        if isinstance(v, COSArray):
            return v
        return None

    def has_id(self) -> bool:
        return self.get_id() is not None

    def clear_id(self) -> None:
        self.set_id(None)

    def set_id(self, id_array: COSArray | None) -> None:
        if id_array is None:
            self._fdf.remove_item(_ID)
        else:
            self._fdf.set_item(_ID, id_array)

    # ---------- /Status ----------

    def get_status(self) -> str | None:
        return self._fdf.get_string(_STATUS)

    def has_status(self) -> bool:
        return self.get_status() is not None

    def clear_status(self) -> None:
        self.set_status(None)

    def set_status(self, status: str | None) -> None:
        self._fdf.set_string(_STATUS, status)

    # ---------- /Encoding (a name like /UTF-8 / /Shift-JIS) ----------

    def get_encoding(self) -> str | None:
        v = self._fdf.get_dictionary_object(_ENCODING)
        if isinstance(v, COSName):
            return v.name
        if isinstance(v, COSString):
            return v.get_string()
        return None

    def has_encoding(self) -> bool:
        return self.get_encoding() is not None

    def clear_encoding(self) -> None:
        self.set_encoding(None)

    def set_encoding(self, encoding: str | None) -> None:
        if encoding is None:
            self._fdf.remove_item(_ENCODING)
        else:
            self._fdf.set_item(_ENCODING, COSName.get_pdf_name(encoding))

    # ---------- /Annots ----------

    def get_annotations(self) -> list[FDFAnnotation] | None:
        v = self._fdf.get_dictionary_object(_ANNOTS)
        if not isinstance(v, COSArray):
            return None
        out: list[FDFAnnotation] = []
        for entry in v:
            resolved = entry.get_object() if isinstance(entry, COSObject) else entry
            if isinstance(resolved, COSDictionary):
                out.append(FDFAnnotation.create(resolved))
        return out

    def has_annotations(self) -> bool:
        return isinstance(self._fdf.get_dictionary_object(_ANNOTS), COSArray)

    def clear_annotations(self) -> None:
        self.set_annotations(None)

    def set_annotations(self, annots: list[FDFAnnotation] | None) -> None:
        if annots is None:
            self._fdf.remove_item(_ANNOTS)
            return
        arr = COSArray()
        for a in annots:
            arr.add(a.get_cos_object())
        self._fdf.set_item(_ANNOTS, arr)

    # ---------- /Target (named destination shortcut) ----------

    def get_target(self) -> str | None:
        return self._fdf.get_string(_TARGET)

    def has_target(self) -> bool:
        return self.get_target() is not None

    def clear_target(self) -> None:
        self.set_target(None)

    def set_target(self, target: str | None) -> None:
        self._fdf.set_string(_TARGET, target)

    # ---------- /EmbeddedFDFs (array of filespec / stream entries) ----------

    def get_embedded_fdfs(self) -> COSArray | None:
        v = self._fdf.get_dictionary_object(_EMBEDDED_FDFS)
        if isinstance(v, COSArray):
            return v
        return None

    def has_embedded_fdfs(self) -> bool:
        return self.get_embedded_fdfs() is not None

    def clear_embedded_fdfs(self) -> None:
        self.set_embedded_fdfs(None)

    def set_embedded_fdfs(self, arr: COSArray | None) -> None:
        if arr is None:
            self._fdf.remove_item(_EMBEDDED_FDFS)
        else:
            self._fdf.set_item(_EMBEDDED_FDFS, arr)

    # Strict mechanical-snake_case aliases for upstream ``getEmbeddedFDFs``
    # / ``setEmbeddedFDFs``. The pythonic spelling (``get_embedded_fdfs``)
    # remains the primary form; these aliases exist only so the parity
    # report matches upstream method names exactly.
    def get_embedded_fd_fs(self) -> COSArray | None:
        return self.get_embedded_fdfs()

    def set_embedded_fd_fs(self, arr: COSArray | None) -> None:
        self.set_embedded_fdfs(arr)

    # ---------- /Pages (FDFPage list) ----------

    def get_pages(self) -> list[FDFPage] | None:
        """Return the ``/Pages`` entry as a list of :class:`FDFPage`, or
        ``None`` when unset. Mirrors upstream
        ``FDFDictionary.getPages() -> List<FDFPage>``.
        """
        v = self._fdf.get_dictionary_object(_PAGES)
        if not isinstance(v, COSArray):
            return None
        pages: list[FDFPage] = []
        for i in range(v.size()):
            entry = v.get_object(i)
            if isinstance(entry, COSDictionary):
                pages.append(FDFPage(entry))
        return pages

    def set_pages(self, pages: list[FDFPage] | None) -> None:
        """Set the ``/Pages`` entry from a list of :class:`FDFPage`.

        Pass ``None`` to drop the entry. Mirrors upstream
        ``FDFDictionary.setPages(List<FDFPage>)``.
        """
        if pages is None:
            self._fdf.remove_item(_PAGES)
            return
        arr = COSArray()
        for page in pages:
            arr.add(page.get_cos_object())
        self._fdf.set_item(_PAGES, arr)

    def get_pages_cos_array(self) -> COSArray | None:
        """Return the raw ``/Pages`` :class:`COSArray`, or ``None`` when
        unset.

        Deprecated low-level accessor: prefer :meth:`get_pages`, which wraps
        each entry in :class:`FDFPage` matching upstream PDFBox. Retained
        for back-compat with callers that need direct COS access (e.g.
        XFDF serialisation helpers); new code should migrate to the typed
        accessor.
        """
        v = self._fdf.get_dictionary_object(_PAGES)
        if isinstance(v, COSArray):
            return v
        return None

    # ---------- /Differences (incremental updates stream) ----------

    def get_differences(self) -> COSStream | None:
        """Return the ``/Differences`` stream entry, or ``None`` when unset.

        Mirrors upstream ``FDFDictionary.getDifferences``.
        """
        v = self._fdf.get_dictionary_object(_DIFFERENCES)
        if isinstance(v, COSStream):
            return v
        return None

    def set_differences(self, diff: COSStream | None) -> None:
        """Set the ``/Differences`` stream entry; pass ``None`` to drop it.

        Mirrors upstream ``FDFDictionary.setDifferences``.
        """
        if diff is None:
            self._fdf.remove_item(_DIFFERENCES)
        else:
            self._fdf.set_item(_DIFFERENCES, diff)

    # ---------- /JavaScript (FDFJavaScript sub-dict) ----------

    def get_javascript(self) -> FDFJavaScript | None:
        """Return the ``/JavaScript`` entry wrapped in
        :class:`FDFJavaScript`, or ``None`` when unset. Mirrors upstream
        ``FDFDictionary.getJavaScript() -> FDFJavaScript``.
        """
        v = self._fdf.get_dictionary_object(_JAVA_SCRIPT)
        if isinstance(v, COSDictionary):
            return FDFJavaScript(v)
        return None

    def set_javascript(self, js: FDFJavaScript | None) -> None:
        """Set the ``/JavaScript`` entry from an :class:`FDFJavaScript`;
        ``None`` removes the entry. Mirrors upstream
        ``FDFDictionary.setJavaScript(FDFJavaScript)``.
        """
        if js is None:
            self._fdf.remove_item(_JAVA_SCRIPT)
        else:
            self._fdf.set_item(_JAVA_SCRIPT, js.get_cos_object())

    def get_javascript_cos_dictionary(self) -> COSDictionary | None:
        """Return the raw ``/JavaScript`` :class:`COSDictionary`, or ``None``.

        Deprecated low-level accessor: prefer :meth:`get_javascript`, which
        wraps the entry in :class:`FDFJavaScript` matching upstream PDFBox.
        Retained for back-compat with callers that need direct COS access;
        new code should migrate to the typed accessor.
        """
        v = self._fdf.get_dictionary_object(_JAVA_SCRIPT)
        if isinstance(v, COSDictionary):
            return v
        return None

    # Strict mechanical-snake_case aliases for upstream ``getJavaScript`` /
    # ``setJavaScript``. The pythonic ``get_javascript`` / ``set_javascript``
    # remain primary.
    def get_java_script(self) -> FDFJavaScript | None:
        return self.get_javascript()

    def set_java_script(self, js: FDFJavaScript | None) -> None:
        self.set_javascript(js)

    # ---------- XFDF XML serialisation ----------

    def write_xml(self, output: IO[str]) -> None:
        """Serialise this dictionary as XFDF XML to ``output``.

        Mirrors upstream ``FDFDictionary.writeXML(Writer)``: emits the
        ``<f>``, ``<ids>``, and ``<fields>`` sub-elements when the
        corresponding entries are present. Annotations are not emitted by
        upstream ``writeXML`` either.
        """
        fs = self.get_file()
        if fs is not None:
            output.write('<f href="' + (fs.get_file() or "") + '" />\n')
        ids = self.get_id()
        if ids is not None:
            original = ids.get_object(0)
            modified = ids.get_object(1)
            if isinstance(original, COSString) and isinstance(modified, COSString):
                output.write('<ids original="' + original.to_hex_string() + '" ')
                output.write('modified="' + modified.to_hex_string() + '" />\n')
        fields = self.get_fields()
        if fields:
            output.write("<fields>\n")
            for field in fields:
                field.write_xml(output)
            output.write("</fields>\n")
