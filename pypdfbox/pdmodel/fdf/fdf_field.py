from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
    COSString,
)

_T: COSName = COSName.get_pdf_name("T")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_KIDS: COSName = COSName.get_pdf_name("Kids")
_TM: COSName = COSName.get_pdf_name("TM")
_FF: COSName = COSName.get_pdf_name("Ff")
_SET_FF: COSName = COSName.get_pdf_name("SetFf")
_CLR_FF: COSName = COSName.get_pdf_name("ClrFf")
_F: COSName = COSName.get_pdf_name("F")
_SET_F: COSName = COSName.get_pdf_name("SetF")
_CLR_F: COSName = COSName.get_pdf_name("ClrF")
_AP: COSName = COSName.get_pdf_name("AP")
_OPT: COSName = COSName.get_pdf_name("Opt")
_AA: COSName = COSName.get_pdf_name("AA")
_A: COSName = COSName.get_pdf_name("A")
_RV: COSName = COSName.get_pdf_name("RV")


class FDFField:
    """A single FDF form field — mirrors
    ``org.apache.pdfbox.pdmodel.fdf.FDFField``.

    An FDF field is a dictionary entry inside the parent FDF dictionary's
    ``/Fields`` array. It carries the partial field name (``/T``), an
    optional value (``/V``), default value (``/DV``), nested kids
    (``/Kids``), and the various flag-mutation entries that AcroForm
    expects (``/Ff``, ``/SetFf``, ``/ClrFf``, ``/F``, ``/SetF``, ``/ClrF``).
    """

    def __init__(self, field: COSDictionary | None = None) -> None:
        self._field: COSDictionary = field if field is not None else COSDictionary()

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._field

    # ---------- /T partial name ----------

    def get_partial_field_name(self) -> str | None:
        return self._field.get_string(_T)

    def set_partial_field_name(self, name: str | None) -> None:
        self._field.set_string(_T, name)

    # ---------- /V value ----------

    def get_value(self) -> object | None:
        """Return the field's ``/V`` entry as a Python value.

        - ``COSString`` → ``str``
        - ``COSName`` → ``str`` (without leading slash)
        - ``COSArray`` (multi-select) → list of strings
        - ``COSStream`` (rich text / large value) → underlying ``COSStream``
        - anything else → returned as-is (rare)
        """
        v = self._field.get_dictionary_object(_V)
        return _cos_value_to_python(v)

    def set_value(self, value: object | None) -> None:
        """Set the field's ``/V`` entry.

        Accepts ``str`` (stored as ``COSString``), ``list[str]`` (stored as
        ``COSArray`` of ``COSString`` — for multi-select choice fields),
        ``COSBase`` (stored verbatim — used for ``COSName`` button values
        or pre-built ``COSStream``s), or ``None`` to remove the entry.
        """
        if value is None:
            self._field.remove_item(_V)
            return
        if isinstance(value, COSBase):
            self._field.set_item(_V, value)
            return
        if isinstance(value, str):
            self._field.set_string(_V, value)
            return
        if isinstance(value, list):
            arr = COSArray()
            for item in value:
                if isinstance(item, COSBase):
                    arr.add(item)
                elif isinstance(item, str):
                    arr.add(COSString(item))
                else:
                    raise TypeError(
                        f"FDFField value list entries must be str or COSBase, "
                        f"got {type(item).__name__}"
                    )
            self._field.set_item(_V, arr)
            return
        raise TypeError(
            f"FDFField.set_value expected None, str, list, or COSBase; "
            f"got {type(value).__name__}"
        )

    # ---------- /DV default value ----------

    def get_default_value(self) -> object | None:
        v = self._field.get_dictionary_object(_DV)
        return _cos_value_to_python(v)

    def set_default_value(self, value: object | None) -> None:
        if value is None:
            self._field.remove_item(_DV)
            return
        if isinstance(value, COSBase):
            self._field.set_item(_DV, value)
            return
        if isinstance(value, str):
            self._field.set_string(_DV, value)
            return
        raise TypeError(
            f"FDFField.set_default_value expected None, str, or COSBase; "
            f"got {type(value).__name__}"
        )

    # ---------- /Kids ----------

    def get_kids(self) -> list[FDFField] | None:
        """Return nested fields (``/Kids``) as a list of ``FDFField``,
        or ``None`` when the entry is absent (matches upstream which
        returns ``null`` when there are no kids).
        """
        v = self._field.get_dictionary_object(_KIDS)
        if not isinstance(v, COSArray):
            return None
        kids: list[FDFField] = []
        for entry in v:
            resolved = entry.get_object() if isinstance(entry, COSObject) else entry
            if isinstance(resolved, COSDictionary):
                kids.append(FDFField(resolved))
        return kids

    def set_kids(self, kids: list[FDFField] | None) -> None:
        if kids is None:
            self._field.remove_item(_KIDS)
            return
        arr = COSArray()
        for k in kids:
            arr.add(k.get_cos_object())
        self._field.set_item(_KIDS, arr)

    # ---------- /TM mapping name ----------

    def get_mapping_name(self) -> str | None:
        return self._field.get_string(_TM)

    def set_mapping_name(self, name: str | None) -> None:
        self._field.set_string(_TM, name)

    # ---------- /Ff field flags ----------

    def get_field_flags(self) -> int:
        return self._field.get_int(_FF, 0)

    def set_field_flags(self, flags: int) -> None:
        self._field.set_int(_FF, flags)

    # ---------- /SetFf, /ClrFf flag mutations ----------

    def get_set_field_flags(self) -> int:
        return self._field.get_int(_SET_FF, 0)

    def set_set_field_flags(self, flags: int) -> None:
        self._field.set_int(_SET_FF, flags)

    def get_clear_field_flags(self) -> int:
        return self._field.get_int(_CLR_FF, 0)

    def set_clear_field_flags(self, flags: int) -> None:
        self._field.set_int(_CLR_FF, flags)

    # ---------- /F widget flags ----------

    def get_widget_field_flags(self) -> int:
        return self._field.get_int(_F, 0)

    def set_widget_field_flags(self, flags: int) -> None:
        self._field.set_int(_F, flags)

    def get_set_widget_field_flags(self) -> int:
        return self._field.get_int(_SET_F, 0)

    def set_set_widget_field_flags(self, flags: int) -> None:
        self._field.set_int(_SET_F, flags)

    def get_clear_widget_field_flags(self) -> int:
        return self._field.get_int(_CLR_F, 0)

    def set_clear_widget_field_flags(self, flags: int) -> None:
        self._field.set_int(_CLR_F, flags)

    # ---------- /Opt (choice options) ----------

    def get_options(self) -> list[object] | None:
        v = self._field.get_dictionary_object(_OPT)
        if not isinstance(v, COSArray):
            return None
        out: list[object] = []
        for entry in v:
            out.append(_cos_value_to_python(entry))
        return out


def _cos_value_to_python(v: COSBase | None) -> object | None:
    if v is None:
        return None
    if isinstance(v, COSObject):
        v = v.get_object()
    if isinstance(v, COSString):
        return v.get_string()
    if isinstance(v, COSName):
        return v.name
    if isinstance(v, COSInteger):
        return v.value
    if isinstance(v, COSArray):
        return [_cos_value_to_python(e) for e in v]
    if isinstance(v, COSStream):
        return v
    return v
