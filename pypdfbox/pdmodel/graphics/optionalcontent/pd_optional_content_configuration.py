"""Optional content configuration dictionary (PDF 32000-1 §8.11.4.3,
Table 101).

The default configuration sits under ``/OCProperties /D`` and alternative
configurations live in the ``/OCProperties /Configs`` array. Both share the
same dictionary shape — name, creator, base state, ON/OFF lists, /Order
hierarchy, /RBGroups radio-button groups, /Locked groups, /AS auto-state
arrays, /Intent, etc. ``PDOptionalContentConfiguration`` wraps either one
with a single typed surface.

This class is *original* to pypdfbox — Apache PDFBox 3.0 inlines all of
these accessors inside ``PDOptionalContentProperties`` (which only ever
operates on the default ``/D`` entry). Splitting it out lets the same code
path service alternative configurations from ``/Configs`` and gives
:class:`PDOptionalContentProperties` a clean place to delegate /D
operations.
"""
from __future__ import annotations

from collections.abc import Iterable

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.cos.cos_object import COSObject

from .pd_optional_content_group import PDOptionalContentGroup

_NAME: COSName = COSName.get_pdf_name("Name")
_CREATOR: COSName = COSName.get_pdf_name("Creator")
_BASE_STATE: COSName = COSName.get_pdf_name("BaseState")
_ON: COSName = COSName.get_pdf_name("ON")
_OFF: COSName = COSName.get_pdf_name("OFF")
_INTENT: COSName = COSName.get_pdf_name("Intent")
_AS: COSName = COSName.get_pdf_name("AS")
_ORDER: COSName = COSName.get_pdf_name("Order")
_RBGROUPS: COSName = COSName.get_pdf_name("RBGroups")
_LOCKED: COSName = COSName.get_pdf_name("Locked")
_VIEW: COSName = COSName.get_pdf_name("View")
_EVENT: COSName = COSName.get_pdf_name("Event")
_CATEGORY: COSName = COSName.get_pdf_name("Category")
_OCGS: COSName = COSName.get_pdf_name("OCGs")
_LIST_MODE: COSName = COSName.get_pdf_name("ListMode")

_BASE_STATE_NAMES: dict[str, COSName] = {
    "ON": _ON,
    "OFF": _OFF,
    "UNCHANGED": COSName.get_pdf_name("Unchanged"),
}

_LIST_MODE_VALUES: frozenset[str] = frozenset(("AllPages", "VisiblePages"))


def _to_dict(value: COSBase | None) -> COSDictionary | None:
    if isinstance(value, COSObject):
        value = value.get_object()
    if isinstance(value, COSDictionary):
        return value
    return None


class PDOptionalContentConfiguration:
    """Wraps a configuration dictionary — either ``/OCProperties /D`` or an
    entry from ``/OCProperties /Configs``. Mirrors the PDF 32000-1 §8.11.4.3
    Optional Content Configuration Dictionary."""

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Name + /Creator ----------

    def get_name(self) -> str | None:
        return self._dict.get_string(_NAME)

    def set_name(self, name: str | None) -> None:
        self._dict.set_string(_NAME, name)

    def get_creator(self) -> str | None:
        return self._dict.get_string(_CREATOR)

    def set_creator(self, creator: str | None) -> None:
        self._dict.set_string(_CREATOR, creator)

    # ---------- /BaseState ----------

    def get_base_state(self) -> str:
        name = self._dict.get_name(_BASE_STATE, "ON")
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
        self._dict.set_item(_BASE_STATE, cos_name)

    # ---------- /ListMode (PDF 32000-1 Table 101) ----------

    def get_list_mode(self) -> str:
        """Return /ListMode. Spec default ``"AllPages"`` when absent.

        Per PDF 32000-1 §8.11.4.3 Table 101, /ListMode controls which OCGs
        are surfaced in a viewer's layer panel: ``"AllPages"`` (every
        group) or ``"VisiblePages"`` (only groups referenced by visible
        pages). pypdfbox enrichment — Apache PDFBox 3.0 does not expose
        this key on ``PDOptionalContentProperties``."""
        name = self._dict.get_name(_LIST_MODE, "AllPages")
        return name if name is not None else "AllPages"

    def set_list_mode(self, mode: str | None) -> None:
        if mode is None:
            self._dict.remove_item(_LIST_MODE)
            return
        if mode not in _LIST_MODE_VALUES:
            raise ValueError(
                "list mode must be 'AllPages' or 'VisiblePages', "
                f"got {mode!r}"
            )
        self._dict.set_item(_LIST_MODE, COSName.get_pdf_name(mode))

    # ---------- /Intent (View / Design / array) ----------

    def get_intents(self) -> list[str]:
        """Return /Intent as a list of names. ``[]`` when absent (which
        defaults to ``["View"]`` per spec; callers wanting the typed default
        should use :meth:`get_intent`)."""
        item = self._dict.get_dictionary_object(_INTENT)
        if item is None:
            return []
        if isinstance(item, COSName):
            return [item.name]
        if isinstance(item, COSArray):
            return [v.name for v in item if isinstance(v, COSName)]
        return []

    def get_intent(self) -> str | list[str]:
        """Spec-default ``"View"`` when /Intent absent. Single name returns
        ``str``; array returns ``list[str]``. Mirrors the same shape as
        :meth:`PDOptionalContentGroup.get_intent`."""
        item = self._dict.get_dictionary_object(_INTENT)
        if item is None:
            return "View"
        if isinstance(item, COSName):
            return item.name
        if isinstance(item, COSArray):
            return [v.name for v in item if isinstance(v, COSName)]
        return "View"

    def set_intent(self, value: str | list[str] | None) -> None:
        if value is None:
            self._dict.remove_item(_INTENT)
            return
        if isinstance(value, str):
            self._dict.set_item(_INTENT, COSName.get_pdf_name(value))
            return
        if isinstance(value, list):
            arr = COSArray()
            for entry in value:
                if not isinstance(entry, str):
                    raise TypeError(
                        f"intent entries must be str, got {type(entry).__name__}"
                    )
                arr.add(COSName.get_pdf_name(entry))
            self._dict.set_item(_INTENT, arr)
            return
        raise TypeError(
            f"intent must be str, list[str], or None, got {type(value).__name__}"
        )

    # ---------- /ON + /OFF arrays ----------

    def _ensure_array(self, key: COSName) -> COSArray:
        arr = self._dict.get_dictionary_object(key)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            self._dict.set_item(key, arr)
        return arr

    def get_on(self) -> list[PDOptionalContentGroup]:
        return self._wrap_ocg_list(self._dict.get_dictionary_object(_ON))

    def get_off(self) -> list[PDOptionalContentGroup]:
        return self._wrap_ocg_list(self._dict.get_dictionary_object(_OFF))

    def is_on(self, group: PDOptionalContentGroup) -> bool:
        """``True`` when ``group`` is explicitly listed in /ON. Membership
        is matched by *identity* of the wrapped ``COSDictionary`` so OCGs
        that share a /Name aren't accidentally collapsed."""
        target = group.get_cos_object()
        for g in self.get_on():
            if g.get_cos_object() is target:
                return True
        return False

    def is_off(self, group: PDOptionalContentGroup) -> bool:
        """``True`` when ``group`` is explicitly listed in /OFF. See
        :meth:`is_on` for the matching contract."""
        target = group.get_cos_object()
        for g in self.get_off():
            if g.get_cos_object() is target:
                return True
        return False

    @staticmethod
    def _wrap_ocg_list(value: COSBase | None) -> list[PDOptionalContentGroup]:
        if not isinstance(value, COSArray):
            return []
        out: list[PDOptionalContentGroup] = []
        for entry in value:
            d = _to_dict(entry)
            if d is None:
                continue
            try:
                out.append(PDOptionalContentGroup(d))
            except (TypeError, ValueError):
                continue
        return out

    # ---------- /Order ----------

    def get_order(self) -> COSArray | None:
        arr = self._dict.get_dictionary_object(_ORDER)
        return arr if isinstance(arr, COSArray) else None

    def set_order(self, order: COSArray | None) -> None:
        if order is None:
            self._dict.remove_item(_ORDER)
            return
        if not isinstance(order, COSArray):
            raise TypeError(
                f"order must be COSArray or None, got {type(order).__name__}"
            )
        self._dict.set_item(_ORDER, order)

    # ---------- /RBGroups (radio-button groups) ----------

    def get_rbgroups(self) -> list[list[PDOptionalContentGroup]]:
        """Return the /RBGroups array as a list of OCG lists. Each inner
        list is a radio-button group: turning one OCG ON forces the others
        OFF (PDF 32000-1 Table 101)."""
        arr = self._dict.get_dictionary_object(_RBGROUPS)
        if not isinstance(arr, COSArray):
            return []
        out: list[list[PDOptionalContentGroup]] = []
        for entry in arr:
            if isinstance(entry, COSObject):
                entry = entry.get_object()
            if isinstance(entry, COSArray):
                out.append(self._wrap_ocg_list(entry))
        return out

    def add_rbgroup(self, group: Iterable[PDOptionalContentGroup]) -> None:
        """Append a radio-button group. Each member is recorded by the
        underlying ``COSDictionary``."""
        arr = self._dict.get_dictionary_object(_RBGROUPS)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            self._dict.set_item(_RBGROUPS, arr)
        sub = COSArray()
        for g in group:
            if not isinstance(g, PDOptionalContentGroup):
                raise TypeError(
                    "radio-button group members must be PDOptionalContentGroup, "
                    f"got {type(g).__name__}"
                )
            sub.add(g.get_cos_object())
        arr.add(sub)

    def get_rbgroup_for(
        self, group: PDOptionalContentGroup
    ) -> list[PDOptionalContentGroup] | None:
        """Return the radio-button group containing ``group`` (matched by
        identity of the wrapped ``COSDictionary``), or ``None``."""
        target = group.get_cos_object()
        for sibling_group in self.get_rbgroups():
            for g in sibling_group:
                if g.get_cos_object() is target:
                    return sibling_group
        return None

    def remove_rbgroup(self, group: PDOptionalContentGroup) -> bool:
        """Drop the radio-button group containing ``group`` from /RBGroups.
        Returns ``True`` when a sub-array was removed. Symmetric counterpart
        to :meth:`add_rbgroup`. Pass any member of the target sub-array to
        identify it; the *whole* sub-array is removed."""
        arr = self._dict.get_dictionary_object(_RBGROUPS)
        if not isinstance(arr, COSArray):
            return False
        target = group.get_cos_object()
        for entry in list(arr):
            sub = entry
            if isinstance(sub, COSObject):
                sub = sub.get_object()
            if not isinstance(sub, COSArray):
                continue
            for member in sub:
                if _to_dict(member) is target:
                    arr.remove(entry)
                    return True
        return False

    # ---------- /Locked ----------

    def get_locked(self) -> list[PDOptionalContentGroup]:
        return self._wrap_ocg_list(self._dict.get_dictionary_object(_LOCKED))

    def is_locked(self, group: PDOptionalContentGroup) -> bool:
        target = group.get_cos_object()
        for g in self.get_locked():
            if g.get_cos_object() is target:
                return True
        return False

    def set_locked(
        self, groups: Iterable[PDOptionalContentGroup] | None
    ) -> None:
        if groups is None:
            self._dict.remove_item(_LOCKED)
            return
        arr = COSArray()
        for g in groups:
            if not isinstance(g, PDOptionalContentGroup):
                raise TypeError(
                    "locked entries must be PDOptionalContentGroup, "
                    f"got {type(g).__name__}"
                )
            arr.add(g.get_cos_object())
        self._dict.set_item(_LOCKED, arr)

    def add_locked(self, group: PDOptionalContentGroup) -> None:
        if self.is_locked(group):
            return
        arr = self._ensure_array(_LOCKED)
        arr.add(group.get_cos_object())

    def remove_locked(self, group: PDOptionalContentGroup) -> bool:
        """Drop ``group`` from /Locked. Returns ``True`` when an entry
        was removed. Symmetric counterpart to :meth:`add_locked`. Matches
        by *identity* of the wrapped ``COSDictionary``."""
        arr = self._dict.get_dictionary_object(_LOCKED)
        if not isinstance(arr, COSArray):
            return False
        target = group.get_cos_object()
        removed = False
        for entry in list(arr):
            if _to_dict(entry) is target:
                arr.remove(entry)
                removed = True
        return removed

    # ---------- /AS auto-state ----------

    def get_as_array(self) -> COSArray | None:
        arr = self._dict.get_dictionary_object(_AS)
        return arr if isinstance(arr, COSArray) else None

    def add_as_entry(
        self,
        event: str,
        categories: Iterable[str],
        ocgs: Iterable[PDOptionalContentGroup],
    ) -> COSDictionary:
        """Append a Usage Application dictionary to /AS (PDF 32000-1
        §8.11.4.4 Table 102). Returns the new entry dict so callers can
        layer extra keys on top."""
        arr = self._dict.get_dictionary_object(_AS)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            self._dict.set_item(_AS, arr)
        entry = COSDictionary()
        entry.set_item(_EVENT, COSName.get_pdf_name(event))
        cat_arr = COSArray()
        for c in categories:
            cat_arr.add(COSName.get_pdf_name(c))
        entry.set_item(_CATEGORY, cat_arr)
        ocg_arr = COSArray()
        for g in ocgs:
            ocg_arr.add(g.get_cos_object())
        entry.set_item(_OCGS, ocg_arr)
        arr.add(entry)
        return entry


__all__ = ["PDOptionalContentConfiguration"]
