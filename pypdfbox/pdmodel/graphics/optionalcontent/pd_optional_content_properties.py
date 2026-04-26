from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.cos.cos_object import COSObject

from .pd_optional_content_group import PDOptionalContentGroup

_OCGS: COSName = COSName.get_pdf_name("OCGs")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_CONFIGS: COSName = COSName.get_pdf_name("Configs")
_NAME: COSName = COSName.get_pdf_name("Name")
_ORDER: COSName = COSName.get_pdf_name("Order")
_ON: COSName = COSName.get_pdf_name("ON")
_OFF: COSName = COSName.get_pdf_name("OFF")
_BASE_STATE: COSName = COSName.get_pdf_name("BaseState")
_UNCHANGED: COSName = COSName.get_pdf_name("Unchanged")

_BASE_STATE_NAMES = {
    "ON": _ON,
    "OFF": _OFF,
    "UNCHANGED": _UNCHANGED,
}


class PDOptionalContentProperties:
    """Wraps the catalog ``/OCProperties`` dictionary. Mirrors PDFBox
    ``PDOptionalContentProperties``."""

    def __init__(self, props: COSDictionary | None = None) -> None:
        if props is None:
            self._dict = COSDictionary()
            self._dict.set_item(_OCGS, COSArray())
            d = COSDictionary()
            # Name optional but required for PDF/A-3
            d.set_string(_NAME, "Top")
            self._dict.set_item(_D, d)
        else:
            self._dict = props

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- internal helpers ----------

    def _get_ocgs(self) -> COSArray:
        ocgs = self._dict.get_dictionary_object(_OCGS)
        if not isinstance(ocgs, COSArray):
            ocgs = COSArray()
            self._dict.set_item(_OCGS, ocgs)
        return ocgs

    def _get_d(self) -> COSDictionary:
        d = self._dict.get_dictionary_object(_D)
        if not isinstance(d, COSDictionary):
            d = COSDictionary()
            d.set_string(_NAME, "Top")
            self._dict.set_item(_D, d)
        return d

    @staticmethod
    def _to_dictionary(value: COSBase | None) -> COSDictionary | None:
        if isinstance(value, COSObject):
            value = value.get_object()
        if isinstance(value, COSDictionary):
            return value
        return None

    # ---------- group enumeration ----------

    def get_groups(self) -> list[PDOptionalContentGroup]:
        out: list[PDOptionalContentGroup] = []
        for entry in self._get_ocgs():
            ocg = self._to_dictionary(entry)
            if ocg is not None:
                out.append(PDOptionalContentGroup(ocg))
        return out

    def get_group(self, name: str) -> PDOptionalContentGroup | None:
        for entry in self._get_ocgs():
            ocg = self._to_dictionary(entry)
            if ocg is None:
                continue
            if ocg.get_string(_NAME) == name:
                return PDOptionalContentGroup(ocg)
        return None

    def has_group(self, name: str) -> bool:
        return self.get_group(name) is not None

    def add_group(self, group: PDOptionalContentGroup) -> None:
        cos = group.get_cos_object()
        # Ensure /Type /OCG is present.
        if cos.get_dictionary_object(COSName.TYPE) is None:  # type: ignore[attr-defined]
            cos.set_item(COSName.TYPE, COSName.get_pdf_name("OCG"))  # type: ignore[attr-defined]
        self._get_ocgs().add(cos)
        d = self._get_d()
        order = d.get_dictionary_object(_ORDER)
        if not isinstance(order, COSArray):
            order = COSArray()
            d.set_item(_ORDER, order)
        order.add(cos)

    # ---------- visibility ----------

    def is_group_enabled(self, name_or_group: str | PDOptionalContentGroup) -> bool:
        if isinstance(name_or_group, str):
            for entry in self._get_ocgs():
                ocg = self._to_dictionary(entry)
                if ocg is None:
                    continue
                if ocg.get_string(_NAME) == name_or_group:
                    if self.is_group_enabled(PDOptionalContentGroup(ocg)):
                        return True
            return False

        group = name_or_group
        base_state = self.get_base_state()
        enabled = base_state != "OFF"
        d = self._get_d()
        target = group.get_cos_object()

        on = d.get_dictionary_object(_ON)
        if isinstance(on, COSArray):
            for entry in on:
                if self._to_dictionary(entry) is target:
                    return True
        off = d.get_dictionary_object(_OFF)
        if isinstance(off, COSArray):
            for entry in off:
                if self._to_dictionary(entry) is target:
                    return False
        return enabled

    def set_group_enabled(
        self, name_or_group: str | PDOptionalContentGroup, enabled: bool
    ) -> bool:
        if isinstance(name_or_group, str):
            result = False
            for entry in self._get_ocgs():
                ocg = self._to_dictionary(entry)
                if ocg is None:
                    continue
                if ocg.get_string(_NAME) == name_or_group:
                    if self.set_group_enabled(PDOptionalContentGroup(ocg), enabled):
                        result = True
            return result

        group = name_or_group
        d = self._get_d()
        on = d.get_dictionary_object(_ON)
        if not isinstance(on, COSArray):
            on = COSArray()
            d.set_item(_ON, on)
        off = d.get_dictionary_object(_OFF)
        if not isinstance(off, COSArray):
            off = COSArray()
            d.set_item(_OFF, off)

        target = group.get_cos_object()
        found = False
        if enabled:
            for entry in list(off):
                if self._to_dictionary(entry) is target:
                    off.remove(entry)
                    on.add(entry)
                    found = True
                    break
        else:
            for entry in list(on):
                if self._to_dictionary(entry) is target:
                    on.remove(entry)
                    off.add(entry)
                    found = True
                    break
        if not found:
            if enabled:
                on.add(target)
            else:
                off.add(target)
        return found

    # ---------- base state ----------

    def get_base_state(self) -> str:
        d = self._get_d()
        name = d.get_name(_BASE_STATE, "ON")
        if name is None:
            return "ON"
        upper = name.upper()
        if upper == "UNCHANGED":
            return "Unchanged"
        return upper

    def set_base_state(self, state: str) -> None:
        key = state.upper()
        cos_name = _BASE_STATE_NAMES.get(key)
        if cos_name is None:
            raise ValueError(
                f"base state must be 'ON', 'OFF', or 'Unchanged', got {state!r}"
            )
        self._get_d().set_item(_BASE_STATE, cos_name)

    # ---------- alternate configurations ----------

    def get_configuration_names(self) -> list[str]:
        configs = self._dict.get_dictionary_object(_CONFIGS)
        if not isinstance(configs, COSArray):
            return []
        names: list[str] = []
        for entry in configs:
            cfg = self._to_dictionary(entry)
            if cfg is None:
                continue
            n = cfg.get_string(_NAME)
            if n is not None:
                names.append(n)
        return names


__all__ = ["PDOptionalContentProperties"]
