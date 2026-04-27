from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject, COSString

from .fdf_annotation import FDFAnnotation
from .fdf_field import FDFField

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

    def set_fields(self, fields: list[FDFField] | None) -> None:
        if fields is None:
            self._fdf.remove_item(_FIELDS)
            return
        arr = COSArray()
        for f in fields:
            arr.add(f.get_cos_object())
        self._fdf.set_item(_FIELDS, arr)

    # ---------- /F (source PDF file path) ----------

    def get_file(self) -> str | None:
        return self._fdf.get_string(_F)

    def set_file(self, file: str | None) -> None:
        self._fdf.set_string(_F, file)

    # Upstream-spelling aliases (PDFBox uses ``getF``/``setF``).

    def get_f(self) -> str | None:
        return self.get_file()

    def set_f(self, file: str | None) -> None:
        self.set_file(file)

    # ---------- /ID ----------

    def get_id(self) -> COSArray | None:
        v = self._fdf.get_dictionary_object(_ID)
        if isinstance(v, COSArray):
            return v
        return None

    def set_id(self, id_array: COSArray | None) -> None:
        if id_array is None:
            self._fdf.remove_item(_ID)
        else:
            self._fdf.set_item(_ID, id_array)

    # ---------- /Status ----------

    def get_status(self) -> str | None:
        return self._fdf.get_string(_STATUS)

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
                out.append(FDFAnnotation(resolved))
        return out

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

    def set_target(self, target: str | None) -> None:
        self._fdf.set_string(_TARGET, target)

    # ---------- /EmbeddedFDFs (array of filespec / stream entries) ----------

    def get_embedded_fdfs(self) -> COSArray | None:
        v = self._fdf.get_dictionary_object(_EMBEDDED_FDFS)
        if isinstance(v, COSArray):
            return v
        return None

    def set_embedded_fdfs(self, arr: COSArray | None) -> None:
        if arr is None:
            self._fdf.remove_item(_EMBEDDED_FDFS)
        else:
            self._fdf.set_item(_EMBEDDED_FDFS, arr)
