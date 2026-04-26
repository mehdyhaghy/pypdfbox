from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OCG: COSName = COSName.get_pdf_name("OCG")
_NAME: COSName = COSName.get_pdf_name("Name")
_INTENT: COSName = COSName.get_pdf_name("Intent")
_USAGE: COSName = COSName.get_pdf_name("Usage")
_PRINT: COSName = COSName.get_pdf_name("Print")
_VIEW: COSName = COSName.get_pdf_name("View")
_EXPORT: COSName = COSName.get_pdf_name("Export")
_PRINT_STATE: COSName = COSName.get_pdf_name("PrintState")
_VIEW_STATE: COSName = COSName.get_pdf_name("ViewState")
_EXPORT_STATE: COSName = COSName.get_pdf_name("ExportState")
_ON: COSName = COSName.get_pdf_name("ON")
_OFF: COSName = COSName.get_pdf_name("OFF")


class PDOptionalContentGroup:
    """Optional content group (OCG). Mirrors PDFBox ``PDOptionalContentGroup``."""

    def __init__(self, name_or_dict: str | COSDictionary) -> None:
        if isinstance(name_or_dict, COSDictionary):
            existing_type = name_or_dict.get_dictionary_object(_TYPE)
            if existing_type is not None and existing_type != _OCG:
                raise ValueError(f"Provided dictionary is not of type '{_OCG}'")
            self._dict = name_or_dict
            if existing_type is None:
                self._dict.set_item(_TYPE, _OCG)
        elif isinstance(name_or_dict, str):
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _OCG)
            self.set_name(name_or_dict)
        else:
            raise TypeError(
                "PDOptionalContentGroup expects str or COSDictionary, "
                f"got {type(name_or_dict).__name__}"
            )

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_name(self) -> str | None:
        return self._dict.get_string(_NAME)

    def set_name(self, name: str) -> None:
        self._dict.set_string(_NAME, name)

    def get_intents(self) -> list[COSName]:
        item = self._dict.get_dictionary_object(_INTENT)
        if item is None:
            return []
        if isinstance(item, COSName):
            return [item]
        if isinstance(item, COSArray):
            return [v for v in item if isinstance(v, COSName)]
        return []

    def set_intents(self, intents: COSName | list[COSName] | None) -> None:
        if intents is None:
            self._dict.remove_item(_INTENT)
            return
        if isinstance(intents, COSName):
            self._dict.set_item(_INTENT, intents)
            return
        arr = COSArray()
        for intent in intents:
            if not isinstance(intent, COSName):
                raise TypeError(
                    f"intents entries must be COSName, got {type(intent).__name__}"
                )
            arr.add(intent)
        self._dict.set_item(_INTENT, arr)

    def get_render_state(self, destination: str | None = None) -> str | None:
        """Return /Usage state name ("ON"/"OFF") for ``destination`` ("Print",
        "View", "Export"). Falls back to /Export if the targeted entry is
        missing. Returns ``None`` when no usage information is present."""
        usage = self._dict.get_dictionary_object(_USAGE)
        if not isinstance(usage, COSDictionary):
            return None
        state: COSName | None = None
        if destination == "Print":
            sub = usage.get_dictionary_object(_PRINT)
            if isinstance(sub, COSDictionary):
                state = _coerce_name(sub.get_dictionary_object(_PRINT_STATE))
        elif destination == "View":
            sub = usage.get_dictionary_object(_VIEW)
            if isinstance(sub, COSDictionary):
                state = _coerce_name(sub.get_dictionary_object(_VIEW_STATE))
        if state is None:
            sub = usage.get_dictionary_object(_EXPORT)
            if isinstance(sub, COSDictionary):
                state = _coerce_name(sub.get_dictionary_object(_EXPORT_STATE))
        if state is None:
            return None
        return state.name.upper()

    def set_render_state(self, state: str, destination: str = "Export") -> None:
        """Write the /Usage entry for ``destination`` with state name."""
        upper = state.upper()
        if upper not in ("ON", "OFF"):
            raise ValueError(f"render state must be 'ON' or 'OFF', got {state!r}")
        usage = self._dict.get_dictionary_object(_USAGE)
        if not isinstance(usage, COSDictionary):
            usage = COSDictionary()
            self._dict.set_item(_USAGE, usage)
        if destination == "Print":
            sub_key, state_key = _PRINT, _PRINT_STATE
        elif destination == "View":
            sub_key, state_key = _VIEW, _VIEW_STATE
        else:
            sub_key, state_key = _EXPORT, _EXPORT_STATE
        sub = usage.get_dictionary_object(sub_key)
        if not isinstance(sub, COSDictionary):
            sub = COSDictionary()
            usage.set_item(sub_key, sub)
        sub.set_item(state_key, _ON if upper == "ON" else _OFF)


def _coerce_name(value: object) -> COSName | None:
    return value if isinstance(value, COSName) else None


__all__ = ["PDOptionalContentGroup"]
