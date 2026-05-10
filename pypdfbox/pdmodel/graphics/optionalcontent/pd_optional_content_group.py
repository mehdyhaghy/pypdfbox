from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName

from ..pd_property_list import PDPropertyList

if TYPE_CHECKING:
    from .pd_optional_content_group_usage import PDOptionalContentGroupUsage


class RenderState(Enum):
    """Render state for an OCG /Usage entry. Mirrors upstream nested enum
    ``PDOptionalContentGroup.RenderState`` (values "ON"/"OFF").

    Each member carries a ``COSName`` payload (``COSName.ON`` /
    ``COSName.OFF``) accessible via :meth:`get_name`, mirroring the
    upstream ``RenderState(COSName value)`` constructor that stores the
    PDF name as an instance field.
    """

    ON = "ON"
    OFF = "OFF"

    def get_name(self) -> COSName:
        """Mirrors upstream ``RenderState.getName()`` (Java line 91) —
        returns the PDF :class:`COSName` for this state, i.e.
        ``COSName.ON`` or ``COSName.OFF``."""
        return COSName.get_pdf_name(self.value)

    def get_pdf_name(self) -> COSName:
        """Convenience alias for :meth:`get_name` matching the
        :class:`BaseState` / :class:`MembershipDictionaryVisibilityPolicy`
        sibling-enum spelling used elsewhere in this package."""
        return self.get_name()

    @classmethod
    def value_of(cls, name: str | COSName | None) -> RenderState | None:
        """Mirrors upstream ``RenderState.valueOf(String|COSName)`` — look
        up by spec name (case-insensitive). Per upstream
        ``RenderState.valueOf(COSName)``, a ``None`` argument resolves to
        ``None`` rather than raising."""
        if name is None:
            return None
        if isinstance(name, COSName):
            name = name.name
        upper = name.upper()
        for member in cls:
            if member.value == upper:
                return member
        raise ValueError(f"RenderState has no member named {name!r}")


_RenderState = RenderState

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
_CREATOR_INFO: COSName = COSName.get_pdf_name("CreatorInfo")
_CREATOR: COSName = COSName.get_pdf_name("Creator")
_LANGUAGE: COSName = COSName.get_pdf_name("Language")
_LANG: COSName = COSName.get_pdf_name("Lang")

USAGE_STATE_ON = "ON"
USAGE_STATE_OFF = "OFF"


class PDOptionalContentGroup(PDPropertyList):
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

    def get_intent(self) -> str | list[str]:
        """Return the OCG ``/Intent`` as a string or list of strings.

        Mirrors PDFBox ``PDOptionalContentGroup.getIntent()``. Per PDF 32000-1
        §8.11.4.3 Table 100, ``/Intent`` defaults to ``"View"`` when absent.
        A single name returns as ``str``; an array of names returns as
        ``list[str]``.
        """
        item = self._dict.get_dictionary_object(_INTENT)
        if item is None:
            return "View"
        if isinstance(item, COSName):
            return item.name
        if isinstance(item, COSArray):
            return [v.name for v in item if isinstance(v, COSName)]
        return "View"

    def set_intent(self, value: str | list[str]) -> None:
        """Set the OCG ``/Intent``. Accepts a single name string or a list of
        name strings. Mirrors PDFBox ``PDOptionalContentGroup.setIntent()``.
        """
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
            f"intent must be str or list[str], got {type(value).__name__}"
        )

    def get_render_state(self, destination: object = None) -> str | None:
        """Return /Usage state name ("ON"/"OFF") for ``destination`` ("Print",
        "View", "Export"). Falls back to /Export if the targeted entry is
        missing. Returns ``None`` when no usage information is present.

        ``destination`` accepts either the spec-name string or a
        :class:`pypdfbox.rendering.RenderDestination` enum value (mirrors
        upstream ``getRenderState(RenderDestination)``). Unknown strings are
        treated as "no targeted entry" and fall through to the /Export
        fallback, matching upstream behaviour where any non-PRINT / non-VIEW
        destination leaves ``state`` null prior to the Export fallback.
        """
        dest_name = _normalize_render_destination(destination)
        usage = self._dict.get_dictionary_object(_USAGE)
        if not isinstance(usage, COSDictionary):
            return None
        state: COSName | None = None
        if dest_name == "Print":
            sub = usage.get_dictionary_object(_PRINT)
            if isinstance(sub, COSDictionary):
                state = _coerce_name(sub.get_dictionary_object(_PRINT_STATE))
        elif dest_name == "View":
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

    def set_render_state(self, state: str, destination: object = "Export") -> None:
        """Write the /Usage entry for ``destination`` with state name.

        ``destination`` accepts either the spec-name string or a
        :class:`pypdfbox.rendering.RenderDestination` enum value (mirrors
        the upstream typed parameter). Unknown destinations route to
        /Usage/Export (the upstream fallback target).
        """
        upper = state.upper()
        if upper not in ("ON", "OFF"):
            raise ValueError(f"render state must be 'ON' or 'OFF', got {state!r}")
        dest_name = _normalize_render_destination(destination) or "Export"
        usage = self._dict.get_dictionary_object(_USAGE)
        if not isinstance(usage, COSDictionary):
            usage = COSDictionary()
            self._dict.set_item(_USAGE, usage)
        if dest_name == "Print":
            sub_key, state_key = _PRINT, _PRINT_STATE
        elif dest_name == "View":
            sub_key, state_key = _VIEW, _VIEW_STATE
        else:
            sub_key, state_key = _EXPORT, _EXPORT_STATE
        sub = usage.get_dictionary_object(sub_key)
        if not isinstance(sub, COSDictionary):
            sub = COSDictionary()
            usage.set_item(sub_key, sub)
        sub.set_item(state_key, _ON if upper == "ON" else _OFF)

    # ---- /Usage typed accessors (PDF 32000-1 §8.11.4.4 Table 102) ------------

    def _get_usage_subdict_chain(
        self, *keys: COSName, create: bool = False
    ) -> COSDictionary | None:
        """Walk /Usage/<keys[0]>/<keys[1]>/... starting at the OCG dict.

        When ``create`` is False, returns ``None`` if any link in the chain is
        missing or not a dictionary. When ``create`` is True, missing
        intermediate dictionaries are created and stored in their parent.
        """
        parent = self._dict
        for key in (_USAGE, *keys):
            child = parent.get_dictionary_object(key)
            if not isinstance(child, COSDictionary):
                if not create:
                    return None
                child = COSDictionary()
                parent.set_item(key, child)
            parent = child
        return parent

    def _set_usage_state_entry(
        self, sub_key: COSName, state_key: COSName, state: str | None
    ) -> None:
        """Round-trip an ON/OFF state name under /Usage/<sub_key>/<state_key>.

        Setting ``None`` removes only the targeted state entry; if the
        containing sub-dict and /Usage become empty as a result, they are
        removed too so the OCG dict does not retain empty husks.
        """
        if state is None:
            sub = self._get_usage_subdict_chain(sub_key)
            if sub is None:
                return
            sub.remove_item(state_key)
            self._prune_usage_chain(sub_key)
            return
        upper = state.upper()
        if upper not in (USAGE_STATE_ON, USAGE_STATE_OFF):
            raise ValueError(
                f"usage state must be 'ON' or 'OFF', got {state!r}"
            )
        sub = self._get_usage_subdict_chain(sub_key, create=True)
        assert sub is not None
        sub.set_item(state_key, _ON if upper == USAGE_STATE_ON else _OFF)

    def _set_usage_string_entry(
        self, sub_key: COSName, value_key: COSName, value: str | None
    ) -> None:
        """Round-trip a string under /Usage/<sub_key>/<value_key>."""
        if value is None:
            sub = self._get_usage_subdict_chain(sub_key)
            if sub is None:
                return
            sub.remove_item(value_key)
            self._prune_usage_chain(sub_key)
            return
        sub = self._get_usage_subdict_chain(sub_key, create=True)
        assert sub is not None
        sub.set_string(value_key, value)

    def _prune_usage_chain(self, sub_key: COSName) -> None:
        """Drop /Usage/<sub_key> if empty, then drop /Usage if empty."""
        usage = self._dict.get_dictionary_object(_USAGE)
        if not isinstance(usage, COSDictionary):
            return
        sub = usage.get_dictionary_object(sub_key)
        if isinstance(sub, COSDictionary) and sub.is_empty():
            usage.remove_item(sub_key)
        if usage.is_empty():
            self._dict.remove_item(_USAGE)

    @staticmethod
    def _read_state(sub: COSDictionary, key: COSName) -> str | None:
        value = sub.get_dictionary_object(key)
        if not isinstance(value, COSName):
            return None
        return value.name.upper()

    def get_usage_view_state(self) -> str | None:
        sub = self._get_usage_subdict_chain(_VIEW)
        return self._read_state(sub, _VIEW_STATE) if sub is not None else None

    def set_usage_view_state(self, state: str | None) -> None:
        self._set_usage_state_entry(_VIEW, _VIEW_STATE, state)

    def get_usage_print_state(self) -> str | None:
        sub = self._get_usage_subdict_chain(_PRINT)
        return self._read_state(sub, _PRINT_STATE) if sub is not None else None

    def set_usage_print_state(self, state: str | None) -> None:
        self._set_usage_state_entry(_PRINT, _PRINT_STATE, state)

    def get_usage_export_state(self) -> str | None:
        sub = self._get_usage_subdict_chain(_EXPORT)
        return self._read_state(sub, _EXPORT_STATE) if sub is not None else None

    def set_usage_export_state(self, state: str | None) -> None:
        self._set_usage_state_entry(_EXPORT, _EXPORT_STATE, state)

    def get_usage_creator(self) -> str | None:
        sub = self._get_usage_subdict_chain(_CREATOR_INFO)
        if sub is None:
            return None
        return sub.get_string(_CREATOR)

    def set_usage_creator(self, creator: str | None) -> None:
        self._set_usage_string_entry(_CREATOR_INFO, _CREATOR, creator)

    def get_usage_language(self) -> str | None:
        sub = self._get_usage_subdict_chain(_LANGUAGE)
        if sub is None:
            return None
        return sub.get_string(_LANG)

    def set_usage_language(self, lang: str | None) -> None:
        self._set_usage_string_entry(_LANGUAGE, _LANG, lang)

    # ---- /Usage typed wrapper (PDF 32000-1 §8.11.4.4 Table 102) --------------

    def get_usage_dict(self) -> COSDictionary | None:
        """Return the raw ``/Usage`` ``COSDictionary``, or ``None`` if absent.

        Mirrors PDFBox ``PDOptionalContentGroup.getUsage()`` which returns
        the underlying ``COSDictionary``. The pypdfbox spelling is
        :meth:`get_usage` (returning a typed wrapper); this helper exists
        for callers that want the raw dictionary directly.
        """
        value = self._dict.get_dictionary_object(_USAGE)
        return value if isinstance(value, COSDictionary) else None

    def get_usage(self) -> PDOptionalContentGroupUsage | None:
        """Return a typed :class:`PDOptionalContentGroupUsage` wrapper for
        the OCG ``/Usage`` sub-dictionary, or ``None`` when absent.

        Note: this typed wrapper class is original to pypdfbox — Apache
        PDFBox returns a raw ``COSDictionary`` from ``getUsage()``. Use
        :meth:`get_usage_dict` for the upstream-shaped raw dictionary.
        """
        from .pd_optional_content_group_usage import (
            PDOptionalContentGroupUsage,
        )

        sub = self.get_usage_dict()
        return PDOptionalContentGroupUsage(sub) if sub is not None else None

    # Expose the enum as a class attribute so callers can use the upstream
    # spelling ``PDOptionalContentGroup.RenderState`` mirroring the Java
    # nested-enum form.
    RenderState = RenderState

    def get_render_state_enum(
        self, destination: object = None
    ) -> _RenderState | None:
        """Typed-enum variant of :meth:`get_render_state`.

        Returns the parsed :class:`RenderState` member or ``None`` when no
        usage information is present. ``destination`` accepts either a
        string or a :class:`RenderDestination` enum value.
        """
        name = self.get_render_state(destination)
        if name is None:
            return None
        return RenderState.value_of(name)

    def set_render_state_enum(
        self, state: _RenderState, destination: object = "Export"
    ) -> None:
        """Typed-enum variant of :meth:`set_render_state` — accepts a
        :class:`RenderState` member instead of a raw string. ``destination``
        accepts either a string or a :class:`RenderDestination` enum value."""
        if not isinstance(state, RenderState):
            raise TypeError(
                "state must be RenderState, got "
                f"{type(state).__name__}"
            )
        self.set_render_state(state.value, destination)

    def get_or_create_usage(self) -> PDOptionalContentGroupUsage:
        """Return a typed wrapper, creating an empty ``/Usage`` dict if
        none exists yet."""
        from .pd_optional_content_group_usage import (
            PDOptionalContentGroupUsage,
        )

        sub = self._get_usage_subdict_chain(create=True)
        # _get_usage_subdict_chain with no keys after _USAGE returns the
        # /Usage dict itself.
        assert sub is not None
        return PDOptionalContentGroupUsage(sub)

    # ---- Object identity / string representation -----------------------------

    def __str__(self) -> str:
        """Mirrors upstream ``PDOptionalContentGroup.toString`` — returns
        ``<PDPropertyList repr> (<name>)``. Used by Acrobat-style debug
        output where layer panels list "ColorLayer (Color)"-style entries.
        """
        return self.to_string()

    def to_string(self) -> str:
        """Mirrors upstream ``PDOptionalContentGroup.toString()`` —
        ``<super.toString> (<name>)``. Surfaced explicitly so callers
        porting from PDFBox can keep the literal ``.toString()``
        invocation spelled snake_case."""
        return f"{super().__repr__()} ({self.get_name()})"


def _coerce_name(value: object) -> COSName | None:
    return value if isinstance(value, COSName) else None


def _normalize_render_destination(destination: object) -> str | None:
    """Coerce a render destination to its spec-name string.

    Accepts:

    - ``None``                              → ``None``
    - a :class:`pypdfbox.rendering.RenderDestination` enum value → its
      string ``value`` ("Print" / "View" / "Export")
    - a plain ``str``                        → returned unchanged

    Mirrors the upstream typed-parameter contract where
    ``getRenderState(RenderDestination)`` accepts the enum directly. We
    keep the string overload for Pythonic ergonomics and pre-existing
    callers.
    """
    if destination is None:
        return None
    if isinstance(destination, str):
        return destination
    # Defer the import so render_destination doesn't pull rendering at
    # optionalcontent import time.
    from pypdfbox.rendering.render_destination import RenderDestination

    if isinstance(destination, RenderDestination):
        return destination.value
    raise TypeError(
        "destination must be str, RenderDestination, or None, got "
        f"{type(destination).__name__}"
    )


__all__ = [
    "PDOptionalContentGroup",
    "RenderState",
    "USAGE_STATE_ON",
    "USAGE_STATE_OFF",
]
