from __future__ import annotations

from enum import Enum

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.cos.cos_object import COSObject

from .pd_optional_content_configuration import PDOptionalContentConfiguration
from .pd_optional_content_group import PDOptionalContentGroup


class BaseState(Enum):
    """OCG /D /BaseState. Mirrors upstream nested enum
    ``PDOptionalContentProperties.BaseState`` (``ON`` / ``OFF`` /
    ``UNCHANGED``). The ``value`` is the spec PDF name; use
    :meth:`get_pdf_name` for the COSName.
    """

    ON = "ON"
    OFF = "OFF"
    UNCHANGED = "Unchanged"

    def get_pdf_name(self) -> COSName:
        return COSName.get_pdf_name(self.value)

    def get_name(self) -> COSName:
        """Mirrors upstream ``BaseState.getName()`` — returns the COSName
        spelling of the state ("ON" / "OFF" / "Unchanged"). Identical to
        :meth:`get_pdf_name`; this is the upstream-spelled alias so callers
        porting Java code find it on first lookup."""
        return self.get_pdf_name()

    @classmethod
    def value_of(cls, name: str | COSName | None) -> BaseState:
        """Mirrors upstream ``BaseState.valueOf(String|COSName)`` — looks up
        by spec name (case-insensitive). Per upstream
        ``BaseState.valueOf(COSName)``, a ``None`` argument resolves to
        :attr:`BaseState.ON` rather than raising."""
        if name is None:
            return cls.ON
        if isinstance(name, COSName):
            name = name.name
        upper = name.upper()
        for member in cls:
            if member.value.upper() == upper:
                return member
        raise ValueError(f"BaseState has no member named {name!r}")


_BaseState = BaseState

_OCGS: COSName = COSName.get_pdf_name("OCGs")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_CONFIGS: COSName = COSName.get_pdf_name("Configs")
_NAME: COSName = COSName.get_pdf_name("Name")
_ORDER: COSName = COSName.get_pdf_name("Order")
_ON: COSName = COSName.get_pdf_name("ON")
_OFF: COSName = COSName.get_pdf_name("OFF")
_BASE_STATE: COSName = COSName.get_pdf_name("BaseState")
_UNCHANGED: COSName = COSName.get_pdf_name("Unchanged")
_AS: COSName = COSName.get_pdf_name("AS")
_EVENT: COSName = COSName.get_pdf_name("Event")
_CATEGORY: COSName = COSName.get_pdf_name("Category")
_USAGE: COSName = COSName.get_pdf_name("Usage")
_RBGROUPS: COSName = COSName.get_pdf_name("RBGroups")
_LOCKED: COSName = COSName.get_pdf_name("Locked")
_INTENT: COSName = COSName.get_pdf_name("Intent")

_BASE_STATE_NAMES = {
    "ON": _ON,
    "OFF": _OFF,
    "UNCHANGED": _UNCHANGED,
}


class PDOptionalContentProperties:
    """Wraps the catalog ``/OCProperties`` dictionary. Mirrors PDFBox
    ``PDOptionalContentProperties``."""

    # Expose the BaseState enum nested-style for upstream API parity:
    # callers can use ``PDOptionalContentProperties.BaseState.ON``.
    BaseState = BaseState

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

    def get_oc_gs(self) -> COSArray:
        """Return the ``/OCGs`` array, creating it when missing.

        Mirrors upstream private ``getOCGs()`` (PDOptionalContentProperties.java
        line 120). Upstream is package-private; pypdfbox exposes it (along with
        the underscore-prefixed alias :meth:`_get_ocgs`) so callers porting
        Java code can find it via the snake-cased upstream name."""
        ocgs = self._dict.get_dictionary_object(_OCGS)
        if not isinstance(ocgs, COSArray):
            ocgs = COSArray()
            self._dict.set_item(_OCGS, ocgs)
        return ocgs

    # Underscore-prefixed alias retained for prior internal callers.
    _get_ocgs = get_oc_gs

    def get_d(self) -> COSDictionary:
        """Return the ``/D`` (default configuration) dictionary, creating it
        with the ``/Name "Top"`` seed when missing.

        Mirrors upstream private ``getD()``
        (PDOptionalContentProperties.java line 136). Upstream is
        package-private; pypdfbox exposes it (along with the
        underscore-prefixed alias :meth:`_get_d`) so callers porting Java code
        can find it via the snake-cased upstream name."""
        d = self._dict.get_dictionary_object(_D)
        if not isinstance(d, COSDictionary):
            d = COSDictionary()
            d.set_string(_NAME, "Top")
            self._dict.set_item(_D, d)
        return d

    # Underscore-prefixed alias retained for prior internal callers.
    _get_d = get_d

    @staticmethod
    def to_dictionary(value: COSBase | None) -> COSDictionary | None:
        """Resolve ``value`` to a ``COSDictionary``, unwrapping ``COSObject``
        indirections. Returns ``None`` when the resolved value is not a
        dictionary.

        Mirrors upstream private ``toDictionary(COSBase)``
        (PDOptionalContentProperties.java line 358). Upstream is
        package-private; pypdfbox exposes it (along with the
        underscore-prefixed alias :meth:`_to_dictionary`) so callers porting
        Java code can find it via the snake-cased upstream name."""
        if isinstance(value, COSObject):
            value = value.get_object()
        if isinstance(value, COSDictionary):
            return value
        return None

    # Underscore-prefixed alias retained for prior internal callers.
    _to_dictionary = to_dictionary

    # ---------- group enumeration ----------

    def get_groups(self) -> list[PDOptionalContentGroup]:
        out: list[PDOptionalContentGroup] = []
        for entry in self._get_ocgs():
            ocg = self._to_dictionary(entry)
            if ocg is not None:
                out.append(PDOptionalContentGroup(ocg))
        return out

    def get_optional_content_groups(self) -> list[PDOptionalContentGroup]:
        """Return every optional content group in ``/OCProperties /OCGs``.

        Mirrors PDFBox ``PDOptionalContentProperties.getOptionalContentGroups()``.
        Equivalent to :meth:`get_groups`; exists to match the upstream
        spelling so callers porting Java code find it on first lookup.
        """
        return self.get_groups()

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

    def remove_group(
        self, name_or_group: str | PDOptionalContentGroup
    ) -> bool:
        """Deregister an OCG from ``/OCProperties/OCGs`` and scrub references
        to it from the default config (``/D``) — ``/Order``, ``/ON``, and
        ``/OFF``. Returns ``True`` when at least one ``/OCGs`` entry was
        removed.

        Not part of upstream PDFBox 3.0 — pypdfbox enrichment for symmetric
        write-side handling. The entry is matched by *identity* of the
        wrapped ``COSDictionary`` (so duplicates with the same /Name aren't
        accidentally collapsed); the string overload removes every group
        whose ``/Name`` equals ``name_or_group``."""
        if isinstance(name_or_group, str):
            removed = False
            for ocg in [
                self._to_dictionary(e) for e in list(self._get_ocgs())
            ]:
                if ocg is None:
                    continue
                if (
                    ocg.get_string(_NAME) == name_or_group
                    and self._remove_group_dict(ocg)
                ):
                    removed = True
            return removed
        return self._remove_group_dict(name_or_group.get_cos_object())

    def _remove_group_dict(self, target: COSDictionary) -> bool:
        ocgs = self._get_ocgs()
        removed_any = False
        for entry in list(ocgs):
            if self._to_dictionary(entry) is target:
                ocgs.remove(entry)
                removed_any = True
        if not removed_any:
            return False
        d = self._get_d()
        order = d.get_dictionary_object(_ORDER)
        if isinstance(order, COSArray):
            self._remove_group_from_order(order, target)
        for key in (_ON, _OFF):
            arr = d.get_dictionary_object(key)
            if isinstance(arr, COSArray):
                for entry in list(arr):
                    if self._to_dictionary(entry) is target:
                        arr.remove(entry)
        return True

    def _remove_group_from_order(
        self, order: COSArray, target: COSDictionary
    ) -> None:
        """Remove ``target`` from a possibly nested /Order hierarchy."""
        for index in reversed(range(order.size())):
            raw = order.get(index)
            if self._to_dictionary(raw) is target:
                order.remove_at(index)
                continue
            resolved = order.get_object(index)
            if isinstance(resolved, COSArray):
                self._remove_group_from_order(resolved, target)
                if resolved.is_empty():
                    order.remove_at(index)

    # ---------- visibility ----------

    def is_group_enabled(
        self, name_or_group: str | PDOptionalContentGroup | None
    ) -> bool:
        if isinstance(name_or_group, str):
            for entry in self._get_ocgs():
                ocg = self._to_dictionary(entry)
                if ocg is None:
                    continue
                if (
                    ocg.get_string(_NAME) == name_or_group
                    and self.is_group_enabled(PDOptionalContentGroup(ocg))
                ):
                    return True
            return False

        group = name_or_group
        base_state = self.get_base_state()
        enabled = base_state != "OFF"
        if group is None:
            # Mirrors upstream null-safety: isGroupEnabled((PDOCG) null)
            # returns the BaseState-derived flag without consulting
            # /D /ON or /D /OFF.
            return enabled
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
                if (
                    ocg.get_string(_NAME) == name_or_group
                    and self.set_group_enabled(PDOptionalContentGroup(ocg), enabled)
                ):
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
        was_on, on_entry = self._drain_group_state_entries(on, target)
        was_off, off_entry = self._drain_group_state_entries(off, target)
        found = was_on or was_off
        if enabled:
            target_entry = on_entry if on_entry is not None else off_entry
            on.add(target_entry if target_entry is not None else target)
        else:
            target_entry = off_entry if off_entry is not None else on_entry
            off.add(target_entry if target_entry is not None else target)
        if enabled:
            self._enforce_radio_button(group, on, off)
        return found

    def _drain_group_state_entries(
        self, state_array: COSArray, target: COSDictionary
    ) -> tuple[bool, COSBase | None]:
        """Remove all entries resolving to ``target`` and return the first."""
        first: COSBase | None = None
        found = False
        for entry in list(state_array):
            if self._to_dictionary(entry) is target:
                if first is None:
                    first = entry
                state_array.remove(entry)
                found = True
        return found, first

    def _enforce_radio_button(
        self,
        enabled_group: PDOptionalContentGroup,
        on: COSArray,
        off: COSArray,
    ) -> None:
        """When ``enabled_group`` is turned ON, force every sibling in the
        same /D /RBGroups radio-button group to OFF (PDF 32000-1 Table 101).

        Mirrors Acrobat's "radio-button group" behaviour and is *original*
        to pypdfbox — Apache PDFBox 3.0 stores /RBGroups but does not
        actively enforce the toggle in ``setGroupEnabled``."""
        d = self._get_d()
        rbgroups = d.get_dictionary_object(_RBGROUPS)
        if not isinstance(rbgroups, COSArray):
            return
        target = enabled_group.get_cos_object()
        for raw_group in rbgroups:
            group = (
                raw_group.get_object()
                if isinstance(raw_group, COSObject)
                else raw_group
            )
            if not isinstance(group, COSArray):
                continue
            members: list[COSDictionary] = []
            contains_target = False
            for entry in group:
                d_entry = self._to_dictionary(entry)
                if d_entry is None:
                    continue
                members.append(d_entry)
                if d_entry is target:
                    contains_target = True
            if not contains_target:
                continue
            for sibling in members:
                if sibling is target:
                    continue
                # Remove from /ON if present, then ensure /OFF lists it.
                for entry in list(on):
                    if self._to_dictionary(entry) is sibling:
                        on.remove(entry)
                already_off = False
                for entry in off:
                    if self._to_dictionary(entry) is sibling:
                        already_off = True
                        break
                if not already_off:
                    off.add(sibling)
            # An OCG normally appears in only one radio-button group; stop
            # at the first match to avoid double-walking nested duplicates.
            return

    def set_visibility(
        self, name_or_group: str | PDOptionalContentGroup, visible: bool
    ) -> bool:
        """Visibility-flavoured alias for :meth:`set_group_enabled`. Mirrors
        the user-facing terminology of PDF readers (Acrobat's "Show/Hide
        Layer") while routing through the same ``/D /ON`` / ``/D /OFF``
        bookkeeping. Not part of upstream PDFBox 3.0 — pypdfbox
        convenience.

        Returns ``True`` when the OCG was already tracked in /D /ON or /D
        /OFF (i.e. the call moved an existing entry); ``False`` when the
        group was added to the array for the first time. Same return
        contract as :meth:`set_group_enabled`."""
        return self.set_group_enabled(name_or_group, visible)

    def set_visible(
        self, name_or_group: str | PDOptionalContentGroup
    ) -> bool:
        """Convenience wrapper: ``set_visibility(name_or_group, True)``."""
        return self.set_group_enabled(name_or_group, True)

    def set_hidden(
        self, name_or_group: str | PDOptionalContentGroup
    ) -> bool:
        """Convenience wrapper: ``set_visibility(name_or_group, False)``."""
        return self.set_group_enabled(name_or_group, False)

    def is_group_visible(
        self, name_or_group: str | PDOptionalContentGroup
    ) -> bool:
        """Visibility-flavoured alias for :meth:`is_group_enabled` — mirrors
        Acrobat's "Show/Hide Layer" terminology while routing through the
        same /D BaseState + /D /ON + /D /OFF resolution. Not part of
        upstream PDFBox 3.0; pypdfbox convenience."""
        return self.is_group_enabled(name_or_group)

    # ---------- group names (upstream parity) ----------

    def get_group_names(self) -> list[str | None]:
        """Mirrors upstream ``getGroupNames()`` (PDOptionalContentProperties.java
        line 178) — returns each /OCGs entry's /Name in array order.

        Two distinct fallbacks, matching upstream bytecode exactly:

        - An entry that does *not* resolve to a dictionary becomes the empty
          string ``""``.
        - An entry that resolves to a dictionary becomes
          ``dict.getString(/Name)`` *uncoalesced* — i.e. ``None`` when /Name
          is absent or not a ``COSString``. Upstream stores the raw
          ``getString`` result without a null check, so a named-less OCG dict
          yields a genuine ``null`` slot (rendered ``"null"`` by Java
          ``String.join``); pypdfbox must preserve that rather than collapse
          it to ``""``."""
        names: list[str | None] = []
        for entry in self._get_ocgs():
            ocg = self._to_dictionary(entry)
            if ocg is None:
                names.append("")
            else:
                names.append(ocg.get_string(_NAME))
        return names

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

    def set_base_state(self, state: str | _BaseState | COSName) -> None:
        if isinstance(state, BaseState):
            self._get_d().set_item(_BASE_STATE, state.get_pdf_name())
            return
        if isinstance(state, COSName):
            # Round-trip through value_of so unknown spellings are rejected
            # with the same ValueError the str path uses.
            self._get_d().set_item(
                _BASE_STATE, BaseState.value_of(state).get_pdf_name()
            )
            return
        if not isinstance(state, str):
            raise TypeError(
                "base state must be str, BaseState, or COSName, "
                f"got {type(state).__name__}"
            )
        key = state.upper()
        cos_name = _BASE_STATE_NAMES.get(key)
        if cos_name is None:
            raise ValueError(
                f"base state must be 'ON', 'OFF', or 'Unchanged', got {state!r}"
            )
        self._get_d().set_item(_BASE_STATE, cos_name)

    def get_base_state_enum(self) -> _BaseState:
        """Typed-enum variant of :meth:`get_base_state`."""
        return BaseState.value_of(self.get_base_state())

    def is_base_state(self, state: str | _BaseState | COSName) -> bool:
        """Return ``True`` when the resolved /BaseState matches ``state``.

        Comparison is performed against the canonical :class:`BaseState`
        enum so spec-name strings (``"ON"`` / ``"OFF"`` / ``"Unchanged"``,
        case-insensitive), :class:`BaseState` members, and ``COSName``
        values are all accepted. Unknown spellings raise ``ValueError``
        — same contract as :meth:`set_base_state`.

        Not part of upstream PDFBox 3.0 — pypdfbox convenience predicate
        that mirrors :meth:`PDOptionalContentMembershipDictionary.is_visibility_policy`.
        """
        target = state if isinstance(state, BaseState) else BaseState.value_of(state)
        return self.get_base_state_enum() is target

    # ---------- group counts (Pythonic enrichment) ----------

    def get_group_count(self) -> int:
        """Number of dictionary-shaped entries in ``/OCProperties /OCGs``.

        Non-dictionary entries (e.g. malformed null slots) are skipped to
        match :meth:`get_groups`, so the count tracks the iterable result
        rather than the raw array size. Not part of upstream PDFBox 3.0
        — pypdfbox enrichment paralleling
        :meth:`PDOptionalContentMembershipDictionary.get_ocg_count`."""
        count = 0
        for entry in self._get_ocgs():
            if self._to_dictionary(entry) is not None:
                count += 1
        return count

    def __len__(self) -> int:
        """``len(props)`` returns :meth:`get_group_count`."""
        return self.get_group_count()

    def has_groups(self) -> bool:
        """Return ``True`` when at least one OCG is registered in
        ``/OCProperties /OCGs``. False for empty arrays *and* arrays
        containing only non-dictionary entries — same scoping rule as
        :meth:`get_group_count`. pypdfbox enrichment."""
        return self.get_group_count() > 0

    # ---------- aggregate visibility ----------

    def compute_visible_ocgs(self, destination: str | None = None) -> set[int]:
        """Return the set of ``id(ocg_cosdict)`` values for OCGs whose
        computed visibility is ON, per PDF 32000-1 §8.11.4.3 default
        configuration (/D) resolution rules.

        Algorithm:

        1. Start from the BaseState seed:
           - "ON" (default)  → every OCG in /OCGs.
           - "OFF"           → empty set.
           - "Unchanged"     → treated as "ON" baseline at first call (no
             prior session state to preserve in this stateless context).
        2. Remove every entry listed in /D /OFF.
        3. Add every entry listed in /D /ON.
        4. Apply the /D /AS auto-state usage array (PDF 32000-1 §8.11.4.4
           Table 102) for the supplied ``destination`` ("View" / "Print" /
           "Export"). For each /AS entry whose /Event matches ``destination``
           (case-sensitive), each OCG in its /OCGs array is looked up in
           the spec-ordered /Category names against the OCG's own /Usage
           dictionary, reading the ``<Event>State`` sibling. "ON" adds the
           id, "OFF" discards it, "Unchanged" leaves the prior decision.
           First non-"Unchanged" category result wins per (entry, OCG).
           When ``destination`` is ``None`` the /AS pass is skipped.

        Returns the resulting set of ``id()`` values, ready to feed into
        ``PDOptionalContentMembershipDictionary.is_visible``.
        """
        d = self._get_d()
        base_state = self.get_base_state()

        all_ocg_ids: set[int] = set()
        for entry in self._get_ocgs():
            ocg = self._to_dictionary(entry)
            if ocg is not None:
                all_ocg_ids.add(id(ocg))

        if base_state == "OFF":
            visible: set[int] = set()
        else:
            # "ON" (default) and "Unchanged" both seed with the full set
            # for a stateless first call.
            visible = set(all_ocg_ids)

        off = d.get_dictionary_object(_OFF)
        if isinstance(off, COSArray):
            for entry in off:
                ocg = self._to_dictionary(entry)
                if ocg is not None:
                    visible.discard(id(ocg))

        on = d.get_dictionary_object(_ON)
        if isinstance(on, COSArray):
            for entry in on:
                ocg = self._to_dictionary(entry)
                if ocg is not None:
                    visible.add(id(ocg))

        if destination is not None:
            self._apply_auto_state(d, destination, visible)

        return visible

    def _apply_auto_state(
        self,
        d: COSDictionary,
        destination: str,
        visible: set[int],
    ) -> None:
        """Apply /D /AS Usage Application entries for ``destination`` to
        ``visible`` in place. See PDF 32000-1 §8.11.4.4 Table 102."""
        as_arr = d.get_dictionary_object(_AS)
        if not isinstance(as_arr, COSArray):
            return
        state_key = COSName.get_pdf_name(f"{destination}State")
        for raw_entry in as_arr:
            entry = self._to_dictionary(raw_entry)
            if entry is None:
                continue
            event = entry.get_dictionary_object(_EVENT)
            if not isinstance(event, COSName) or event.name != destination:
                continue
            categories_obj = entry.get_dictionary_object(_CATEGORY)
            categories: list[COSName] = []
            if isinstance(categories_obj, COSName):
                categories = [categories_obj]
            elif isinstance(categories_obj, COSArray):
                categories = [c for c in categories_obj if isinstance(c, COSName)]
            if not categories:
                continue
            ocgs_obj = entry.get_dictionary_object(_OCGS)
            if not isinstance(ocgs_obj, COSArray):
                continue
            for raw_ocg in ocgs_obj:
                ocg = self._to_dictionary(raw_ocg)
                if ocg is None:
                    continue
                # Wrap in PDOptionalContentGroup to reuse the typed accessor
                # (validates /Type /OCG, mirrors PDFBox's typed lookup).
                try:
                    PDOptionalContentGroup(ocg)
                except (TypeError, ValueError):
                    continue
                usage = ocg.get_dictionary_object(_USAGE)
                if not isinstance(usage, COSDictionary):
                    continue
                for category in categories:
                    sub = usage.get_dictionary_object(category)
                    if not isinstance(sub, COSDictionary):
                        continue
                    state = sub.get_dictionary_object(state_key)
                    if not isinstance(state, COSName):
                        continue
                    upper = state.name.upper()
                    if upper == "UNCHANGED":
                        continue
                    if upper == "ON":
                        visible.add(id(ocg))
                    elif upper == "OFF":
                        visible.discard(id(ocg))
                    # First non-"Unchanged" category result wins per OCG.
                    break

    # ---------- /D default configuration wrapper ----------

    def get_default_configuration(self) -> PDOptionalContentConfiguration:
        """Return the typed wrapper for ``/OCProperties /D``. The wrapper
        shares the underlying ``COSDictionary`` so writes round-trip.

        Not part of upstream PDFBox 3.0 — pypdfbox enrichment. Apache
        PDFBox inlines /D accessors directly on
        ``PDOptionalContentProperties``; we keep those in place but also
        expose the typed configuration wrapper for symmetry with /Configs
        entries."""
        return PDOptionalContentConfiguration(self._get_d())

    # ---------- /D /Intent ----------

    def get_intent(self) -> str | list[str]:
        """Return the /D /Intent value. Defaults to "View" when absent.
        Mirrors :meth:`PDOptionalContentGroup.get_intent`."""
        return self.get_default_configuration().get_intent()

    def set_intent(self, value: str | list[str] | None) -> None:
        self.get_default_configuration().set_intent(value)

    def is_intent(self, name: str) -> bool:
        """Return ``True`` when the default configuration's /Intent
        declares ``name``. Delegates to
        :meth:`PDOptionalContentConfiguration.is_intent`, which honours the
        spec default of ``"View"`` when /Intent is absent (PDF 32000-1
        §8.11.4.3 Table 101). pypdfbox convenience."""
        return self.get_default_configuration().is_intent(name)

    # ---------- /D /RBGroups ----------

    def get_rbgroups(self) -> list[list[PDOptionalContentGroup]]:
        return self.get_default_configuration().get_rbgroups()

    def add_rbgroup(self, group: list[PDOptionalContentGroup]) -> None:
        self.get_default_configuration().add_rbgroup(group)

    # ---------- /D /Locked ----------

    def get_locked(self) -> list[PDOptionalContentGroup]:
        return self.get_default_configuration().get_locked()

    def is_locked(self, group: PDOptionalContentGroup) -> bool:
        return self.get_default_configuration().is_locked(group)

    def set_locked(
        self, groups: list[PDOptionalContentGroup] | None
    ) -> None:
        self.get_default_configuration().set_locked(groups)

    def add_locked(self, group: PDOptionalContentGroup) -> None:
        self.get_default_configuration().add_locked(group)

    # ---------- alternate configurations ----------

    def get_configurations(self) -> list[PDOptionalContentConfiguration]:
        """Return the typed wrappers around ``/OCProperties /Configs``
        entries. Empty list when /Configs absent or non-array."""
        configs = self._dict.get_dictionary_object(_CONFIGS)
        if not isinstance(configs, COSArray):
            return []
        out: list[PDOptionalContentConfiguration] = []
        for entry in configs:
            cfg = self._to_dictionary(entry)
            if cfg is None:
                continue
            out.append(PDOptionalContentConfiguration(cfg))
        return out

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

    def get_configuration(
        self, name: str
    ) -> PDOptionalContentConfiguration | None:
        for cfg in self.get_configurations():
            if cfg.get_name() == name:
                return cfg
        return None

    def has_configuration(self, name: str) -> bool:
        """Return ``True`` when ``/OCProperties /Configs`` contains an entry
        whose /Name matches ``name``. Mirrors :meth:`has_group` for the
        alternate-configuration array. pypdfbox enrichment — Apache PDFBox
        3.0 leaves callers to walk /Configs themselves."""
        return self.get_configuration(name) is not None

    def add_configuration(
        self,
        config: PDOptionalContentConfiguration | COSDictionary,
    ) -> PDOptionalContentConfiguration:
        """Append a configuration to ``/OCProperties /Configs``, creating
        the array when missing. Returns the typed wrapper."""
        if isinstance(config, PDOptionalContentConfiguration):
            cos = config.get_cos_object()
            wrapper = config
        elif isinstance(config, COSDictionary):
            cos = config
            wrapper = PDOptionalContentConfiguration(cos)
        else:
            raise TypeError(
                "config must be PDOptionalContentConfiguration or COSDictionary, "
                f"got {type(config).__name__}"
            )
        configs = self._dict.get_dictionary_object(_CONFIGS)
        if not isinstance(configs, COSArray):
            configs = COSArray()
            self._dict.set_item(_CONFIGS, configs)
        configs.add(cos)
        return wrapper


__all__ = ["BaseState", "PDOptionalContentProperties"]
