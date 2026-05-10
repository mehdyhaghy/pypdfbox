from __future__ import annotations

from collections.abc import Sequence
from typing import IO, TYPE_CHECKING, cast

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

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
    from pypdfbox.pdmodel.interactive.action.pd_additional_actions import (
        PDAdditionalActions,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
        PDAppearanceDictionary,
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

    def has_partial_field_name(self) -> bool:
        return self.get_partial_field_name() is not None

    def clear_partial_field_name(self) -> None:
        self.set_partial_field_name(None)

    def set_partial_field_name(self, name: str | None) -> None:
        self._field.set_string(_T, name)

    # ---------- /V value ----------

    def get_value(self) -> object | None:
        """Return the field's ``/V`` entry as a Python value.

        Mirrors upstream ``FDFField.getValue()``:

        - ``COSString`` → ``str``
        - ``COSName`` → ``str`` (without leading slash)
        - ``COSArray`` (multi-select) → list of strings
        - ``COSStream`` → decoded text (``COSStream.to_text_string()``)
        - anything else → ``OSError`` (matches upstream ``IOException``)
        """
        v = self._field.get_dictionary_object(_V)
        if v is None:
            return None
        if isinstance(v, COSObject):
            v = v.get_object()
        if isinstance(v, COSName):
            return v.name
        if isinstance(v, COSArray):
            return [_cos_value_to_python(e) for e in v]
        if isinstance(v, COSString):
            return v.get_string()
        if isinstance(v, COSStream):
            return v.to_text_string()
        raise OSError(f"Error: Unknown type for field import: {v!r}")

    def get_cos_value(self) -> COSBase | None:
        """Return the raw COS value of this field (``/V`` entry).

        Mirrors upstream ``FDFField.getCOSValue()``: only ``COSName``,
        ``COSArray``, ``COSString`` and ``COSStream`` are accepted; any
        other non-null value raises ``OSError``.
        """
        v = self._field.get_dictionary_object(_V)
        if v is None:
            return None
        if isinstance(v, COSObject):
            v = v.get_object()
        if isinstance(v, (COSName, COSArray, COSString, COSStream)):
            return v
        raise OSError(f"Error: Unknown type for field import: {v!r}")

    def has_value(self) -> bool:
        return self._field.contains_key(_V)

    def clear_value(self) -> None:
        self.set_value(None)

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

    def has_default_value(self) -> bool:
        return self._field.contains_key(_DV)

    def clear_default_value(self) -> None:
        self.set_default_value(None)

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

    def has_kids(self) -> bool:
        return isinstance(self._field.get_dictionary_object(_KIDS), COSArray)

    def clear_kids(self) -> None:
        self.set_kids(None)

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

    def has_mapping_name(self) -> bool:
        return self.get_mapping_name() is not None

    def clear_mapping_name(self) -> None:
        self.set_mapping_name(None)

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

    def has_options(self) -> bool:
        return isinstance(self._field.get_dictionary_object(_OPT), COSArray)

    def clear_options(self) -> None:
        self._field.remove_item(_OPT)

    def set_options(self, options: Sequence[object] | None) -> None:
        """Set the field's ``/Opt`` entry.

        Mirrors PDFBox ``FDFField.setOptions(List<Object>)``. Each option may
        be a string, a two-string sequence (export value + default appearance
        string), or a pre-built ``COSBase`` value.
        """
        if options is None:
            self._field.remove_item(_OPT)
            return

        arr = COSArray()
        for option in options:
            if isinstance(option, COSBase):
                arr.add(option)
            elif isinstance(option, str):
                arr.add(COSString(option))
            elif isinstance(option, (list, tuple)):
                arr.add(_option_pair_to_cos_array(option))
            else:
                raise TypeError(
                    "FDFField options must be str, two-string list/tuple, or COSBase; "
                    f"got {type(option).__name__}"
                )
        self._field.set_item(_OPT, arr)

    # ---------- /RV rich text value ----------

    def get_rich_text(self) -> str | None:
        """Return the field's rich text value from ``/RV``.

        Mirrors upstream ``FDFField.getRichText()``: ``COSString`` is
        decoded to ``str``; ``COSStream`` is decoded via
        ``COSStream.to_text_string()``; absent → ``None``.
        """
        v = self._field.get_dictionary_object(_RV)
        if v is None:
            return None
        if isinstance(v, COSObject):
            v = v.get_object()
        if isinstance(v, COSString):
            return v.get_string()
        if isinstance(v, COSStream):
            return v.to_text_string()
        return None

    def has_rich_text(self) -> bool:
        return self._field.contains_key(_RV)

    def clear_rich_text(self) -> None:
        self.set_rich_text(None)

    def set_rich_text(self, rich_text: str | COSString | COSStream | None) -> None:
        if rich_text is None:
            self._field.remove_item(_RV)
            return
        if isinstance(rich_text, str):
            self._field.set_string(_RV, rich_text)
            return
        if isinstance(rich_text, (COSString, COSStream)):
            self._field.set_item(_RV, rich_text)
            return
        raise TypeError(
            f"FDFField.set_rich_text expected None, str, COSString, or COSStream; "
            f"got {type(rich_text).__name__}"
        )

    # ---------- /AP appearance dictionary ----------

    def get_appearance_dictionary(self) -> PDAppearanceDictionary | None:
        """Return the ``/AP`` appearance dictionary or ``None`` if absent.

        Mirrors upstream ``FDFField.getAppearanceDictionary()``.
        """
        from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
            PDAppearanceDictionary,
        )

        d = self._field.get_cos_dictionary(_AP)
        return PDAppearanceDictionary(d) if d is not None else None

    def set_appearance_dictionary(self, ap: PDAppearanceDictionary | None) -> None:
        """Set the ``/AP`` appearance dictionary.

        Mirrors upstream ``FDFField.setAppearanceDictionary(PDAppearanceDictionary)``.
        Passing ``None`` removes the entry.
        """
        if ap is None:
            self._field.remove_item(_AP)
            return
        self._field.set_item(_AP, ap.get_cos_object())

    # ---------- /A action ----------

    def get_action(self) -> PDAction | None:
        """Return the ``/A`` action wrapper or ``None`` if absent.

        Mirrors upstream ``FDFField.getAction()``.
        """
        from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

        return PDAction.create(self._field.get_cos_dictionary(_A))

    def set_action(self, action: PDAction | None) -> None:
        """Set the ``/A`` action.

        Mirrors upstream ``FDFField.setAction(PDAction)``. Passing ``None``
        removes the entry.
        """
        if action is None:
            self._field.remove_item(_A)
            return
        self._field.set_item(_A, action.get_cos_object())

    # ---------- /AA additional actions ----------

    def get_additional_actions(self) -> PDAdditionalActions | None:
        """Return the ``/AA`` additional-actions wrapper or ``None``.

        Mirrors upstream ``FDFField.getAdditionalActions()``.
        """
        from pypdfbox.pdmodel.interactive.action.pd_additional_actions import (
            PDAdditionalActions,
        )

        d = self._field.get_cos_dictionary(_AA)
        return PDAdditionalActions(d) if d is not None else None

    def set_additional_actions(self, aa: PDAdditionalActions | None) -> None:
        """Set the ``/AA`` additional actions.

        Mirrors upstream ``FDFField.setAdditionalActions(PDAdditionalActions)``.
        Passing ``None`` removes the entry.
        """
        if aa is None:
            self._field.remove_item(_AA)
            return
        self._field.set_item(_AA, aa.get_cos_object())

    # ---------- XML serialisation ----------

    def write_xml(self, output: IO[str]) -> None:
        """Serialise this field as XFDF XML to ``output``.

        Mirrors upstream ``FDFField.writeXML(Writer)``: emits the partial
        field name, value (string or list of strings), rich-text value, and
        recurses into ``/Kids``.
        """
        name = self.get_partial_field_name() or ""
        output.write('<field name="')
        output.write(name)
        output.write('">\n')

        value = self.get_value()
        if isinstance(value, str):
            output.write("<value>")
            output.write(_escape_xml(value))
            output.write("</value>\n")
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    continue
                output.write("<value>")
                output.write(_escape_xml(item))
                output.write("</value>\n")

        rich = self.get_rich_text()
        if isinstance(rich, str):
            output.write("<value-richtext>")
            output.write(_escape_xml(rich))
            output.write("</value-richtext>\n")
        elif isinstance(rich, COSStream):
            output.write("<value-richtext>")
            output.write(_escape_xml(rich.to_text_string()))
            output.write("</value-richtext>\n")

        kids = self.get_kids()
        if kids is not None:
            for kid in kids:
                kid.write_xml(output)
        output.write("</field>\n")


def _escape_xml(text: str) -> str:
    """Mirrors upstream ``FDFField.escapeXML(String)``."""
    out: list[str] = []
    for ch in text:
        if ch == "<":
            out.append("&lt;")
        elif ch == ">":
            out.append("&gt;")
        elif ch == '"':
            out.append("&quot;")
        elif ch == "&":
            out.append("&amp;")
        elif ch == "'":
            out.append("&apos;")
        elif ord(ch) > 0x7E:
            out.append(f"&#{ord(ch)};")
        else:
            out.append(ch)
    return "".join(out)


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


def _option_pair_to_cos_array(option: Sequence[object]) -> COSArray:
    if len(option) != 2 or not all(isinstance(part, str) for part in option):
        raise TypeError(
            "FDFField option pairs must contain exactly two strings "
            "(option, default appearance string)"
        )
    first = cast(str, option[0])
    second = cast(str, option[1])
    arr = COSArray()
    arr.add(COSString(first))
    arr.add(COSString(second))
    return arr
