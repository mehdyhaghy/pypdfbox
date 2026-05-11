from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
    COSString,
)

_BEFORE: COSName = COSName.get_pdf_name("Before")
_AFTER: COSName = COSName.get_pdf_name("After")
_DOC: COSName = COSName.get_pdf_name("Doc")


class FDFJavaScript:
    """FDF JavaScript dictionary — represents the ``/JavaScript`` entry in an
    ``FDFDictionary``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFJavaScript`` (Java
    lines 37-182). Provides accessors for ``/Before`` (JavaScript executed
    before import), ``/After`` (executed after import), and ``/Doc`` (a list
    of named JavaScript actions added to the document's JavaScript name
    tree).
    """

    def __init__(self, java_script: COSDictionary | None = None) -> None:
        self._dictionary: COSDictionary = (
            java_script if java_script is not None else COSDictionary()
        )

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``. Mirrors upstream
        ``getCOSObject()`` (Java line 65)."""
        return self._dictionary

    # ---------- /Before ----------

    def get_before(self) -> str | None:
        """Return the JavaScript executed before import (``/Before``).

        Accepts either a ``COSString`` or a ``COSStream`` (the entry may be
        an indirect reference to a stream). Mirrors upstream ``getBefore()``
        (Java line 75).
        """
        base = self._dictionary.get_dictionary_object(_BEFORE)
        if isinstance(base, COSString):
            return base.get_string()
        if isinstance(base, COSStream):
            return _stream_to_text(base)
        return None

    def set_before(self, before: str | None) -> None:
        """Set the JavaScript executed before import.

        Mirrors upstream ``setBefore(String)`` (Java line 97).
        """
        if before is None:
            self._dictionary.remove_item(_BEFORE)
            return
        self._dictionary.set_item(_BEFORE, COSString(before))

    # ---------- /After ----------

    def get_after(self) -> str | None:
        """Return the JavaScript executed after import (``/After``).

        Mirrors upstream ``getAfter()`` (Java line 107).
        """
        base = self._dictionary.get_dictionary_object(_AFTER)
        if isinstance(base, COSString):
            return base.get_string()
        if isinstance(base, COSStream):
            return _stream_to_text(base)
        return None

    def set_after(self, after: str | None) -> None:
        """Set the JavaScript executed after import.

        Mirrors upstream ``setAfter(String)`` (Java line 129).
        """
        if after is None:
            self._dictionary.remove_item(_AFTER)
            return
        self._dictionary.set_item(_AFTER, COSString(after))

    # ---------- /Doc ----------

    def get_doc(self) -> dict[str, COSDictionary] | None:
        """Return the ``/Doc`` map (name → JavaScript action dictionary).

        Mirrors upstream ``getDoc()`` (Java line 140). The returned ``dict``
        preserves insertion order, mirroring Java's ``LinkedHashMap``.
        Values are bare ``COSDictionary`` action objects — the typed
        ``PDActionJavaScript`` wrapper is not yet ported in pypdfbox so we
        surface the raw dictionaries (callers can wrap manually).
        """
        array = self._dictionary.get_dictionary_object(_DOC)
        if not isinstance(array, COSArray):
            return None
        out: dict[str, COSDictionary] = {}
        i = 0
        while i + 1 < array.size():
            key_obj = array.get_object(i)
            base = array.get_object(i + 1)
            i += 2
            if isinstance(key_obj, COSString):
                name: str | None = key_obj.get_string()
            else:
                name = array.get_name(i - 2)
            if name is not None and isinstance(base, COSDictionary):
                out[name] = base
        return out

    def set_doc(self, mapping: dict[str, COSDictionary] | None) -> None:
        """Set the ``/Doc`` map. Mirrors upstream ``setDoc(Map)`` (Java
        line 172)."""
        if mapping is None:
            self._dictionary.remove_item(_DOC)
            return
        array = COSArray()
        for key, value in mapping.items():
            array.add(COSString(key))
            array.add(value)
        self._dictionary.set_item(_DOC, array)


def _stream_to_text(stream: COSStream) -> str:
    """Decode a ``COSStream`` payload as text.

    Mirrors upstream ``COSStream.toTextString()`` semantics — used by
    ``/Before`` and ``/After`` when the JavaScript body is stored as an
    indirect stream rather than a literal string.
    """
    try:
        return stream.to_text_string()
    except Exception:  # pragma: no cover - defensive
        return ""


__all__ = ["FDFJavaScript"]
