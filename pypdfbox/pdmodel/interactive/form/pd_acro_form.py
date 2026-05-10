from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSName,
    COSNumber,
    COSStream,
    COSString,
)

from .pd_field_factory import PDFieldFactory

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resources import PDResources

    from .pd_field import PDField
    from .pd_field_tree import PDFieldTree
    from .pd_terminal_field import PDTerminalField
    from .pd_xfa_resource import PDXFAResource

_logger = logging.getLogger(__name__)

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_SIG_FLAGS: COSName = COSName.get_pdf_name("SigFlags")
_NEED_APPEARANCES: COSName = COSName.get_pdf_name("NeedAppearances")
_XFA: COSName = COSName.get_pdf_name("XFA")
_DR: COSName = COSName.get_pdf_name("DR")
_DA: COSName = COSName.get_pdf_name("DA")
_Q: COSName = COSName.get_pdf_name("Q")
_CO: COSName = COSName.get_pdf_name("CO")

# Names referenced by ``flatten`` — kept module-local to avoid leaking
# AcroForm-only intern requests into the global COSName cache via callers.
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_AS: COSName = COSName.get_pdf_name("AS")
_RECT: COSName = COSName.get_pdf_name("Rect")
_P: COSName = COSName.get_pdf_name("P")
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_CONTENTS: COSName = COSName.get_pdf_name("Contents")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_X_OBJECT: COSName = COSName.get_pdf_name("XObject")
_ACRO_FORM: COSName = COSName.get_pdf_name("AcroForm")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")

_FLAG_SIGNATURES_EXIST = 1
_FLAG_APPEND_ONLY = 1 << 1


class PDAcroForm:
    """The /AcroForm dictionary. Mirrors PDFBox ``PDAcroForm`` lite surface.

    Deferred: ``import_fdf``/``export_fdf`` (FDF document module not yet
    ported) and signature scripting handler. Appearance generation remains
    intentionally narrow; :meth:`xfa` returns a :class:`PDXFAResource`
    wrapper around the raw XFA COS entry.
    """

    def __init__(
        self,
        document: object | None = None,
        dictionary: COSDictionary | None = None,
    ) -> None:
        self._document = document
        if dictionary is None:
            self._dictionary = COSDictionary()
            self._dictionary.set_item(_FIELDS, COSArray())
        else:
            self._dictionary = dictionary
        self._cache_fields = False
        self._field_cache: dict[str, PDField] | None = None
        # Optional handler for JavaScript form actions. Upstream stores
        # this as a ``ScriptingHandler`` instance — that interface is not
        # yet ported, so we accept any object the caller wants to pass.
        self._scripting_handler: object | None = None

    # ---------- core ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def get_dictionary(self) -> COSDictionary:
        return self._dictionary

    def get_document(self) -> object | None:
        return self._document

    # ---------- /Fields ----------

    def get_fields(self) -> list[PDField]:
        raw = self._dictionary.get_dictionary_object(_FIELDS)
        if not isinstance(raw, COSArray):
            return []
        out: list[PDField] = []
        for i in range(raw.size()):
            entry = raw.get_object(i)
            if not isinstance(entry, COSDictionary):
                continue
            field = PDFieldFactory.create_field(self, entry, None)
            if field is not None:
                out.append(field)
        return out

    def set_fields(self, fields: list[PDField] | None) -> None:
        """Replace the form's root ``/Fields`` array.

        ``None`` is normalised to an empty array (matching the
        constructor's behaviour) — upstream's ``setFields(null)`` would
        NPE in ``new COSArray(null)``; we treat it as a clear instead so
        callers can reset the form to "no fields" with a single call.
        """
        arr = COSArray()
        if fields is not None:
            for f in fields:
                arr.add(f.get_cos_object())
        self._dictionary.set_item(_FIELDS, arr)
        self._invalidate_field_cache()

    def has_fields(self) -> bool:
        """Return ``True`` when this form has at least one root field.

        Pypdfbox-only predicate (mirrors the ``hasXFA`` pattern). Equivalent
        to ``len(form.get_fields()) > 0`` but avoids the per-call list
        allocation. Useful when guarding flatten/refresh calls or when
        deciding whether to drop the AcroForm dictionary entirely.
        """
        raw = self._dictionary.get_dictionary_object(_FIELDS)
        if not isinstance(raw, COSArray):
            return False
        return any(isinstance(raw.get_object(i), COSDictionary) for i in range(raw.size()))

    def is_empty(self) -> bool:
        """Return ``True`` when the form has no fields and no XFA payload.

        Pypdfbox-only convenience: an "empty" AcroForm is one whose
        catalog entry could be safely dropped without losing user data —
        no widget references and no XFA datasets. Combines
        :meth:`has_fields` and :meth:`has_xfa`.
        """
        return not self.has_fields() and not self.has_xfa()

    def get_field_tree(self) -> PDFieldTree:
        """Return an iterable view over every field in the AcroForm tree.

        The top-level ``/Fields`` entries are returned first, followed by each
        non-terminal field's descendants in ``/Kids`` order. This mirrors the
        iteration order used by PDFBox's ``PDFieldTree`` and by
        :meth:`get_field`.
        """
        from .pd_field_tree import PDFieldTree

        return PDFieldTree(self)

    def get_field_iterator(self) -> Iterator[PDField]:
        return iter(self.get_field_tree())

    def set_cache_fields(self, cache: bool) -> None:
        self._cache_fields = bool(cache)
        self._field_cache = self._build_field_cache() if self._cache_fields else None

    # Upstream-named alias (PDFBox ``cacheFields`` — synonym for
    # ``setCacheFields(true)``).
    def cache_fields(self) -> None:
        self.set_cache_fields(True)

    def is_caching_fields(self) -> bool:
        return self._cache_fields

    def get_signature_fields(self) -> list[PDField]:
        """Return every ``/FT /Sig`` field reachable from this form's
        field tree, depth-first.

        Mirrors upstream ``PDAcroForm.getSignatureFields`` (provided via
        ``PDDocument.getSignatureFields`` in 3.x — same predicate). The
        list is fresh; mutating it does not modify ``/Fields``."""
        from .pd_signature_field import PDSignatureField

        return [field for field in self.get_field_tree() if isinstance(field, PDSignatureField)]

    def get_field(self, fully_qualified_name: str) -> PDField | None:
        """Locate a field by its fully-qualified name (".\"-joined)."""
        if fully_qualified_name is None:
            return None
        if self._cache_fields:
            if self._field_cache is None:
                self._field_cache = self._build_field_cache()
            return self._field_cache.get(fully_qualified_name)
        for top in self.get_fields():
            found = self._find_field(top, fully_qualified_name)
            if found is not None:
                return found
        return None

    def _append_field_subtree(self, field: PDField, out: list[PDField]) -> None:
        out.append(field)
        if field.is_terminal():
            return
        from .pd_non_terminal_field import PDNonTerminalField

        if not isinstance(field, PDNonTerminalField):
            return
        for child in field.get_children():
            self._append_field_subtree(child, out)

    def _find_field(
        self, field: PDField, fqn: str, seen: set[int] | None = None
    ) -> PDField | None:
        if seen is None:
            seen = set()
        key = id(field.get_cos_object())
        if key in seen:
            return None
        seen.add(key)
        if field.get_fully_qualified_name() == fqn:
            return field
        if not field.is_terminal():
            from .pd_non_terminal_field import PDNonTerminalField

            assert isinstance(field, PDNonTerminalField)
            for child in field.get_children():
                found = self._find_field(child, fqn, seen)
                if found is not None:
                    return found
        return None

    def _build_field_cache(self) -> dict[str, PDField]:
        cache: dict[str, PDField] = {}
        for field in self.get_field_tree():
            name = field.get_fully_qualified_name()
            if name not in cache:
                cache[name] = field
        return cache

    def _invalidate_field_cache(self) -> None:
        if self._cache_fields:
            self._field_cache = None

    def remove_field(self, field: PDField) -> bool:
        """Detach ``field`` from the form's tree without flattening.

        When the field has a parent, it is dropped from the parent's
        ``/Kids`` array; otherwise from the form's root ``/Fields``
        array. Returns ``True`` when an entry was removed, ``False``
        when the field was not found in the expected container.

        Mirrors upstream ``PDAcroForm.removeFields`` (package-private in
        3.0.x) — exposed here as a public single-field helper since the
        lite surface uses :meth:`flatten` for the multi-field path."""
        parent = field.get_parent()
        if parent is None:
            container = self._dictionary.get_dictionary_object(_FIELDS)
            if not isinstance(container, COSArray):
                return False
            removed = container.remove_object(field.get_cos_object())
        else:
            kids = parent.get_cos_object().get_dictionary_object(
                COSName.get_pdf_name("Kids")
            )
            if not isinstance(kids, COSArray):
                return False
            removed = kids.remove_object(field.get_cos_object())
        if removed:
            self._invalidate_field_cache()
        return bool(removed)

    def remove_fields(self, fields: list[PDField]) -> int:
        """Detach each entry in ``fields`` from the form's tree.

        Returns the number of fields actually removed. Mirrors upstream
        ``PDAcroForm.removeFields`` — each field is removed from its
        parent's ``/Kids`` (or the form's root ``/Fields`` when there is
        no parent)."""
        count = 0
        for field in fields:
            if self.remove_field(field):
                count += 1
        return count

    # ---------- /SigFlags ----------

    # Bit positions in /SigFlags (PDF 32000-1 §12.7.3 Table 219). Mirror
    # upstream's package-private ``FLAG_SIGNATURES_EXIST`` and
    # ``FLAG_APPEND_ONLY`` constants — exposed publicly here so callers
    # who want to drive ``set_signature_flags`` directly don't have to
    # re-derive the bit positions.
    FLAG_SIGNATURES_EXIST: int = _FLAG_SIGNATURES_EXIST
    FLAG_APPEND_ONLY: int = _FLAG_APPEND_ONLY

    # /Q quadding constants (PDF 32000-1 §12.7.3.3, Table 222 — same
    # values as ``PDVariableText.QUADDING_*``). Re-exposed at class scope
    # so callers driving ``set_q`` directly don't have to import
    # PDVariableText.
    QUADDING_LEFT: int = 0
    QUADDING_CENTERED: int = 1
    QUADDING_RIGHT: int = 2

    def _get_sig_flags(self) -> int:
        return self._dictionary.get_int(_SIG_FLAGS, 0)

    def _set_sig_flag(self, mask: int, value: bool) -> None:
        flags = self._get_sig_flags()
        if value:
            flags |= mask
        else:
            flags &= ~mask
        self._dictionary.set_int(_SIG_FLAGS, flags)

    def get_signature_flags(self) -> int:
        """Return the raw ``/SigFlags`` integer (0 when absent).

        Pypdfbox-only convenience over upstream's bit-by-bit
        ``isSignaturesExist`` / ``isAppendOnly``: useful when you want
        to round-trip the flag bitmask without losing reserved bits or
        when persisting the AcroForm state across calls. The two
        documented flag bits are :attr:`FLAG_SIGNATURES_EXIST` and
        :attr:`FLAG_APPEND_ONLY`."""
        return self._get_sig_flags()

    def set_signature_flags(self, flags: int) -> None:
        """Replace the raw ``/SigFlags`` integer.

        Pypdfbox-only convenience — mirrors :meth:`get_signature_flags`.
        Pass ``0`` to clear all signature flags (the entry stays present
        as an integer 0; use the document-level helper to drop the entry
        entirely)."""
        self._dictionary.set_int(_SIG_FLAGS, int(flags))

    def is_signatures_exist(self) -> bool:
        return bool(self._get_sig_flags() & _FLAG_SIGNATURES_EXIST)

    def set_signatures_exist(self, value: bool) -> None:
        self._set_sig_flag(_FLAG_SIGNATURES_EXIST, value)

    def is_appendonly(self) -> bool:
        return bool(self._get_sig_flags() & _FLAG_APPEND_ONLY)

    def set_appendonly(self, value: bool) -> None:
        self._set_sig_flag(_FLAG_APPEND_ONLY, value)

    # Upstream-named aliases (PDFBox ``isAppendOnly`` / ``setAppendOnly``).
    def is_append_only(self) -> bool:
        return self.is_appendonly()

    def set_append_only(self, value: bool) -> None:
        self.set_appendonly(value)

    # ---------- /NeedAppearances ----------

    def is_need_appearances(self) -> bool:
        return self._dictionary.get_boolean(_NEED_APPEARANCES, False)

    def set_need_appearances(self, value: bool | None) -> None:
        """Set ``/NeedAppearances``.

        Upstream's signature is ``setNeedAppearances(Boolean value)`` —
        the boxed ``Boolean`` type allows ``null``. We mirror that by
        treating ``None`` as "remove the entry" so callers can drop
        ``/NeedAppearances`` without reaching into the underlying
        dictionary."""
        if value is None:
            self._dictionary.remove_item(_NEED_APPEARANCES)
            return
        self._dictionary.set_boolean(_NEED_APPEARANCES, value)

    # Upstream-named alias (PDFBox ``getNeedAppearances`` /
    # ``setNeedAppearances``).
    def get_need_appearances(self) -> bool:
        return self.is_need_appearances()

    def get_need_appearances_if_exists(self) -> bool | None:
        """Return ``/NeedAppearances`` as a tri-state — ``None`` when the
        entry is absent or malformed, otherwise the boolean value.

        Used by writers that want to round-trip ``/NeedAppearances``
        without inventing a default. Mirrors the convention upstream's
        ``getNeedAppearancesIfExists`` follows in 4.x."""
        value = self._dictionary.get_dictionary_object(_NEED_APPEARANCES)
        if isinstance(value, COSBoolean):
            return value.value
        return None

    def has_need_appearances(self) -> bool:
        """Return ``True`` when ``/NeedAppearances`` is present as a boolean."""
        return isinstance(
            self._dictionary.get_dictionary_object(_NEED_APPEARANCES), COSBoolean
        )

    def clear_need_appearances(self) -> None:
        """Remove ``/NeedAppearances`` so readers fall back to the default."""
        self._dictionary.remove_item(_NEED_APPEARANCES)

    # ---------- /DR (default resources) ----------

    def get_default_resources(self) -> PDResources | None:
        """Return the form-wide default ``/DR`` resources, or ``None``.

        Mirrors PDFBox ``getDefaultResources`` — used by widget appearance
        generation to resolve fonts referenced from ``/DA`` strings."""
        from pypdfbox.pdmodel.pd_resources import PDResources

        raw = self._dictionary.get_dictionary_object(_DR)
        if isinstance(raw, COSDictionary):
            return PDResources(raw)
        return None

    def set_default_resources(self, resources: PDResources | None) -> None:
        """Set the form-wide default ``/DR`` resources. ``None`` removes
        the entry."""
        if resources is None:
            self._dictionary.remove_item(_DR)
            return
        self._dictionary.set_item(_DR, resources.get_cos_object())

    def has_default_resources(self) -> bool:
        """Return ``True`` when this form has a ``/DR`` entry that resolves
        to a dictionary.

        Pypdfbox-only predicate (mirrors the ``has_xfa`` pattern). Lets
        callers branch on default-resources presence without paying the
        cost of materialising the full :meth:`get_default_resources`
        wrapper. A ``/DR`` entry whose value is not a dictionary (e.g.
        ``null`` or a stray non-dict) returns ``False`` — matching the
        guard in :meth:`get_default_resources`."""
        raw = self._dictionary.get_dictionary_object(_DR)
        return isinstance(raw, COSDictionary)

    def clear_default_resources(self) -> None:
        """Remove the form-wide default ``/DR`` resources entry."""
        self._dictionary.remove_item(_DR)

    # ---------- /DA (default appearance) ----------

    def get_default_appearance(self) -> str:
        """Return the default appearance string ``/DA``.

        Upstream returns ``""`` (not ``None``) when absent — preserved
        here for parity with ``PDAcroForm.getDefaultAppearance``."""
        value = self._dictionary.get_string(_DA, "")
        return value if value is not None else ""

    def get_default_appearance_if_exists(self) -> str | None:
        """Return ``/DA`` as a tri-state — ``None`` when the entry is
        absent or malformed, otherwise the string value (which may be empty).

        Used by writers that want to round-trip ``/DA`` without inventing
        an empty default. Mirrors the convention of
        :meth:`get_need_appearances_if_exists`."""
        value = self._dictionary.get_dictionary_object(_DA)
        if isinstance(value, COSString):
            return value.get_string()
        if isinstance(value, COSName):
            return value.name
        return None

    def set_default_appearance(self, da: str) -> None:
        self._dictionary.set_string(_DA, da)

    def has_default_appearance(self) -> bool:
        """Return ``True`` when this form has a ``/DA`` entry.

        Pypdfbox-only predicate — distinguishes missing/malformed entries from
        a parsable empty string, which :meth:`get_default_appearance` collapses
        to ``""``. Useful when a writer wants to round-trip ``/DA`` only when
        the source PDF actually carries one."""
        return self.get_default_appearance_if_exists() is not None

    def clear_default_appearance(self) -> None:
        """Remove the form-wide ``/DA`` entry."""
        self._dictionary.remove_item(_DA)

    # ---------- /Q (quadding / form-wide alignment) ----------

    def get_q(self) -> int:
        """Return the form-wide quadding value (``0``=left, ``1``=center,
        ``2``=right). Defaults to ``0`` when ``/Q`` is absent."""
        return self._dictionary.get_int(_Q, 0)

    def get_q_if_exists(self) -> int | None:
        """Return ``/Q`` as a tri-state — ``None`` when the entry is
        absent or malformed, otherwise the integer value.

        Used by writers that want to round-trip ``/Q`` without inventing
        a default of ``0`` (left-justified). Mirrors the convention of
        :meth:`get_default_appearance_if_exists` and
        :meth:`get_need_appearances_if_exists`."""
        value = self._dictionary.get_dictionary_object(_Q)
        if isinstance(value, COSNumber):
            return value.int_value()
        return None

    def set_q(self, value: int) -> None:
        self._dictionary.set_int(_Q, value)

    def has_q(self) -> bool:
        """Return ``True`` when the form has a parsable local ``/Q`` value."""
        return self.get_q_if_exists() is not None

    def clear_q(self) -> None:
        """Remove the form-wide ``/Q`` quadding entry."""
        self._dictionary.remove_item(_Q)

    # ---------- /CO (calculation order) ----------

    def get_calc_order(self) -> list[PDField]:
        """Return the ``/CO`` calculation order — fields whose values are
        recomputed (in order) when any field's value changes.

        Mirrors PDFBox ``getCalculationOrder``: each entry must be a
        terminal field dictionary; non-dictionary or non-resolvable
        entries are skipped."""
        raw = self._dictionary.get_dictionary_object(_CO)
        if not isinstance(raw, COSArray):
            return []
        out: list[PDField] = []
        for i in range(raw.size()):
            entry = raw.get_object(i)
            if not isinstance(entry, COSDictionary):
                continue
            field = PDFieldFactory.create_field(self, entry, None)
            if field is not None:
                out.append(field)
        return out

    def has_calc_order(self) -> bool:
        """Return ``True`` when this form has a non-empty ``/CO`` array.

        Pypdfbox-only predicate — mirrors the ``hasXFA`` pattern. Lets
        callers branch on calculation-order presence without paying the
        cost of materialising the full :meth:`get_calc_order` list (which
        resolves every entry through :class:`PDFieldFactory`)."""
        raw = self._dictionary.get_dictionary_object(_CO)
        if not isinstance(raw, COSArray):
            return False
        return any(isinstance(raw.get_object(i), COSDictionary) for i in range(raw.size()))

    def set_calc_order(self, fields: list[PDField] | None) -> None:
        """Replace the ``/CO`` array. ``None`` or an empty list removes
        the entry."""
        if not fields:
            self._dictionary.remove_item(_CO)
            return
        arr = COSArray()
        for f in fields:
            arr.add(f.get_cos_object())
        self._dictionary.set_item(_CO, arr)

    def clear_calc_order(self) -> None:
        """Remove the ``/CO`` calculation-order array."""
        self._dictionary.remove_item(_CO)

    # ---------- scripting handler ----------

    def get_scripting_handler(self) -> object | None:
        """Return the optional handler for JavaScript form actions, or
        ``None``. Mirrors upstream ``PDAcroForm.getScriptingHandler`` —
        the handler interface itself is not yet ported, so this round-
        trips whatever opaque object the caller registered."""
        return self._scripting_handler

    def set_scripting_handler(self, handler: object | None) -> None:
        """Register a handler for JavaScript form actions. Mirrors
        upstream ``PDAcroForm.setScriptingHandler``."""
        self._scripting_handler = handler

    # ---------- appearance regeneration ----------

    def refresh_appearances(self, fields: list[PDField] | None = None) -> None:
        """Rebuild appearance streams + dictionaries for the widget
        annotations of every field (or only ``fields`` when supplied).

        Mirrors upstream ``PDAcroForm.refreshAppearances`` — iterates
        terminal fields and dispatches to ``construct_appearances`` on
        each. Non-terminal fields are skipped (matches upstream's
        ``instanceof PDTerminalField`` guard).

        Per-``/FT`` appearance construction (text/button/choice/sig) is
        the responsibility of the field's own
        :meth:`~PDTerminalField.construct_appearances`; on the lite
        surface that delegates into :class:`PDAppearanceGenerator` for
        the implemented field types and is a debug-logged no-op for the
        rest.
        """
        from .pd_terminal_field import PDTerminalField

        targets: Iterator[PDField] = iter(self.get_field_tree()) if fields is None else iter(fields)
        for field in targets:
            if isinstance(field, PDTerminalField):
                field.construct_appearances()

    # ---------- FDF (deferred) ----------

    def import_fdf(self, fdf: object) -> None:
        """Apply an :class:`FDFDocument`'s field values to this form.

        The ``pypdfbox.pdmodel.fdf`` module is not yet ported; calling
        this raises :class:`NotImplementedError`.
        """
        raise NotImplementedError(
            "PDAcroForm.import_fdf: FDFDocument support is not yet implemented"
        )

    def export_fdf(self) -> object:
        """Export this form's field values as a new :class:`FDFDocument`.

        The ``pypdfbox.pdmodel.fdf`` module is not yet ported; calling
        this raises :class:`NotImplementedError`.
        """
        raise NotImplementedError(
            "PDAcroForm.export_fdf: FDFDocument support is not yet implemented"
        )

    # ---------- /XFA ----------

    def xfa(self) -> PDXFAResource | None:
        from .pd_xfa_resource import PDXFAResource

        raw = self._dictionary.get_dictionary_object(_XFA)
        if raw is None:
            return None
        return PDXFAResource(raw)

    # Upstream-named alias (PDFBox ``getXFA``).
    def get_xfa(self) -> PDXFAResource | None:
        return self.xfa()

    def set_xfa(self, xfa: PDXFAResource | None) -> None:
        """Set the XFA resource (only used for PDF 1.5+ forms).

        ``None`` removes the entry; otherwise the resource's COS payload
        is written to ``/XFA``. Mirrors upstream ``PDAcroForm.setXFA``.
        """
        if xfa is None:
            self._dictionary.remove_item(_XFA)
            return
        self._dictionary.set_item(_XFA, xfa.get_cos_object())

    def has_xfa(self) -> bool:
        """Return ``True`` when this form has an ``/XFA`` entry. Mirrors
        upstream ``PDAcroForm.hasXFA``."""
        return self._dictionary.contains_key(_XFA)

    def clear_xfa(self) -> None:
        """Remove the XFA resource entry."""
        self._dictionary.remove_item(_XFA)

    def xfa_is_dynamic(self) -> bool:
        """Return ``True`` for a *dynamic* XFA form — i.e. ``/XFA`` is
        present but ``/Fields`` is empty. Mirrors upstream
        ``PDAcroForm.xfaIsDynamic``: dynamic XFA forms carry no AcroForm
        widget representation, so flattening is not supported."""
        return self.has_xfa() and not self.get_fields()

    # ---------- flatten (PDF 32000-1 §12.7.5.5) ----------

    def flatten(
        self,
        fields: list[PDField] | None = None,
        refresh_appearances: bool = False,
    ) -> None:
        """Flatten widgets for ``fields`` (default = every field in the
        form) into their host pages' content streams.

        For each widget this:

        1. Resolves the host page via the widget's ``/P`` back-pointer; when
           absent, falls back to scanning every page's ``/Annots`` array for
           a match (mirrors upstream's lookup loop).
        2. Looks up the widget's normal appearance (``/AP /N``). If ``/AS``
           is set and ``/AP /N`` is a state dictionary, the per-state stream
           is used; otherwise the entry must be a stream directly. Widgets
           with no usable appearance are skipped (matches upstream's
           ``hasValidAppearance`` guard).
        3. Registers the appearance Form XObject on the host page's
           ``/Resources /XObject`` under a unique ``Fm<n>``-prefixed key
           (collisions are resolved by incrementing ``<n>``).
        4. Appends ``q <ctm> cm /<name> Do Q`` to the page's content stream
           (promoting a single-stream ``/Contents`` to a 2-element array
           rather than mutating the original stream body).
        5. Removes the widget from the host page's ``/Annots`` array.

        After every requested field has been processed, the widget's
        underlying field dictionaries are removed from the form's
        ``/Fields`` array. When the call flattens **all** fields, the
        document catalog's ``/AcroForm`` entry is dropped entirely.

        ``refresh_appearances=True`` first walks the fields and calls
        :meth:`refresh_appearances` on each terminal — on the lite
        surface that uses :class:`PDAppearanceGenerator` for implemented
        field types and is a no-op for the rest, mirroring the
        ``PDTerminalField.constructAppearances`` dispatch upstream.

        Mirrors the upstream early-outs:

        * Dynamic XFA (``xfa_is_dynamic`` true) → log a warning and
          return; flattening would require rendering XFA into a static
          PDF.
        * ``need_appearances`` true with ``refresh_appearances=False`` →
          log a warning recommending the caller pass
          ``refresh_appearances=True`` or call
          :meth:`refresh_appearances` first.

        After the per-widget loop the form's ``/XFA`` entry is dropped
        (matches upstream's hybrid-form cleanup) and ``/SigFlags`` is
        cleared when no signature dictionaries remain.
        """
        # Dynamic XFA forms have no static appearance to flatten —
        # mirrors upstream's early-out.
        if self.xfa_is_dynamic():
            _logger.warning("Flatten for a dynamic XFA form is not supported")
            return

        targets: list[PDField] = list(self.get_fields()) if fields is None else list(fields)
        if not targets:
            return

        if not refresh_appearances and self.get_need_appearances():
            _logger.warning(
                "acroForm.get_need_appearances() returns true, "
                "visual field appearances may not have been set"
            )
            _logger.warning(
                "call acroForm.refresh_appearances() or "
                "use the flatten() method with refresh_appearances parameter"
            )

        # Flatten input is a list of root fields; walk descendants once
        # to collect every terminal exactly once. ``refresh_appearances``
        # operates on the same terminal set.
        from .pd_terminal_field import PDTerminalField

        terminal_fields: list[PDField] = []
        for field in targets:
            terminal_fields.extend(self._collect_terminals(field))
        if not terminal_fields:
            return

        if refresh_appearances:
            self.refresh_appearances(terminal_fields)

        flatten_all = fields is None

        for field in terminal_fields:
            if not isinstance(field, PDTerminalField):
                continue
            for widget in field.get_widgets():
                self._flatten_widget(widget.get_cos_object())

        # Drop the flattened fields from /Fields (or wipe the entry when
        # the caller asked for "everything").
        if flatten_all:
            # Mirrors upstream's "remove the AcroForm dict outright" path:
            # nothing remains to be referenced.
            self._dictionary.remove_item(_FIELDS)
            self._remove_acro_form_from_catalog()
        else:
            arr = self._dictionary.get_dictionary_object(_FIELDS)
            if isinstance(arr, COSArray):
                victims = {id(f.get_cos_object()) for f in terminal_fields}
                # Walk a copy so removals don't perturb iteration.
                from pypdfbox.cos import COSObject

                for entry in list(arr):
                    resolved = entry.get_object() if isinstance(entry, COSObject) else entry
                    if id(resolved) in victims:
                        arr.remove(entry)

        # /XFA cleanup for hybrid forms (upstream parity).
        self._dictionary.remove_item(_XFA)

        # Drop /SigFlags when no signatures remain (upstream parity).
        document = self._document
        if document is not None:
            from pypdfbox.pdmodel.pd_document import PDDocument

            if isinstance(document, PDDocument) and not document.get_signature_dictionaries():
                self._dictionary.remove_item(_SIG_FLAGS)

        self._invalidate_field_cache()

    # ---------- flatten internals ----------

    def _collect_terminals(
        self, field: PDField, seen: set[int] | None = None
    ) -> list[PDTerminalField]:
        """Depth-first walk of a field subtree returning every terminal
        descendant. Mirrors the implicit recursion in PDFBox's
        ``flatten`` which only emits content for terminal fields with
        widgets."""
        if seen is None:
            seen = set()
        field_id = id(field.get_cos_object())
        if field_id in seen:
            _logger.error(
                "Field '%s' already exists in flatten traversal, ignored to avoid recursion",
                field.get_fully_qualified_name(),
            )
            return []
        seen.add(field_id)

        from .pd_terminal_field import PDTerminalField

        if field.is_terminal():
            if not isinstance(field, PDTerminalField):
                return []
            return [field]
        from .pd_non_terminal_field import PDNonTerminalField

        if not isinstance(field, PDNonTerminalField):
            return []
        out: list[PDTerminalField] = []
        for child in field.get_children():
            out.extend(self._collect_terminals(child, seen))
        return out

    def _flatten_widget(self, widget: COSDictionary) -> None:
        """Render a single widget's normal appearance into its host page."""
        appearance_stream = self._select_appearance_stream(widget)
        if appearance_stream is None:
            return
        rect = widget.get_dictionary_object(_RECT)
        if not isinstance(rect, COSArray) or rect.size() < 4:
            return
        page = self._resolve_widget_page(widget)
        if page is None:
            return
        rect_values = self._read_rect(rect)
        if rect_values is None:
            return
        bbox_values, matrix_values = self._read_form_geometry(appearance_stream)
        if bbox_values is None:
            return

        cm = self._compute_ctm(rect_values, bbox_values, matrix_values)
        name = self._add_xobject_to_page(page, appearance_stream)
        self._append_do_to_page(page, cm, name)
        self._remove_widget_from_page(page, widget)

    @staticmethod
    def _select_appearance_stream(widget: COSDictionary) -> COSStream | None:
        """Return the widget's effective ``/AP /N`` stream.

        ``/AP /N`` may be a single ``COSStream`` (stateless widgets, e.g.
        text fields) or a state ``COSDictionary`` keyed by appearance
        state name (checkboxes / radio buttons → /Yes, /Off, …). When
        the entry is a state dict we honour ``/AS`` to pick the active
        stream; missing /AS or unknown state → no flattening, matching
        upstream's silent skip."""
        ap = widget.get_dictionary_object(_AP)
        if not isinstance(ap, COSDictionary):
            return None
        normal = ap.get_dictionary_object(_N)
        if isinstance(normal, COSStream):
            return normal
        if isinstance(normal, COSDictionary):
            state = widget.get_name(_AS)
            if state is None:
                return None
            entry = normal.get_dictionary_object(COSName.get_pdf_name(state))
            if isinstance(entry, COSStream):
                return entry
        return None

    def _resolve_widget_page(self, widget: COSDictionary) -> COSDictionary | None:
        """Find the page dictionary hosting ``widget``.

        Preferred path is the widget's ``/P`` back-pointer (PDF 32000-1
        §12.5.2 Table 164 — required for widget annotations). When that
        is absent or doesn't resolve to a dictionary, fall back to
        scanning every page's ``/Annots`` for a matching reference."""
        host = widget.get_dictionary_object(_P)
        if isinstance(host, COSDictionary):
            return host

        document = self._document
        if document is None:
            return None
        # Local import — pdmodel is the same package; we keep the import
        # lazy to mirror the rest of the form module's deferred typing.
        from pypdfbox.pdmodel.pd_document import PDDocument

        if not isinstance(document, PDDocument):
            return None
        for page in document.get_pages():
            page_dict = page.get_cos_object()
            annots = page_dict.get_dictionary_object(_ANNOTS)
            if not isinstance(annots, COSArray):
                continue
            for i in range(annots.size()):
                entry = annots.get_object(i)
                if entry is widget:
                    return page_dict
        return None

    @staticmethod
    def _read_rect(arr: COSArray) -> tuple[float, float, float, float] | None:
        """Resolve a 4-entry numeric COSArray to ``(llx, lly, urx, ury)``.

        Mirrors upstream's normalisation step — PDF spec §7.9.5 lets the
        two corner pairs appear in any order, so we ``min``/``max`` them
        before computing the placement transform."""
        from pypdfbox.cos import COSFloat, COSInteger

        nums: list[float] = []
        for i in range(4):
            entry = arr.get_object(i)
            if isinstance(entry, (COSInteger, COSFloat)):
                nums.append(float(entry.value))
            else:
                return None
        x0, y0, x1, y1 = nums
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    @staticmethod
    def _read_form_geometry(
        stream: COSStream,
    ) -> tuple[
        tuple[float, float, float, float] | None, tuple[float, float, float, float, float, float]
    ]:
        """Pull ``/BBox`` + ``/Matrix`` off a Form XObject stream.

        Returns ``(bbox, matrix)`` with ``matrix`` defaulting to identity
        when ``/Matrix`` is absent (PDF 32000-1 §8.10). ``bbox`` is
        ``None`` when the Form XObject lacks a usable bounding box —
        callers treat that as "skip this widget" since the placement
        transform would be undefined."""
        from pypdfbox.cos import COSFloat, COSInteger

        bbox_arr = stream.get_dictionary_object(_BBOX)
        bbox: tuple[float, float, float, float] | None = None
        if isinstance(bbox_arr, COSArray) and bbox_arr.size() >= 4:
            try:
                vals = [float(bbox_arr.get_object(i).value) for i in range(4)]  # type: ignore[union-attr]
            except (AttributeError, TypeError):
                vals = []
            if len(vals) == 4:
                bbox = (
                    min(vals[0], vals[2]),
                    min(vals[1], vals[3]),
                    max(vals[0], vals[2]),
                    max(vals[1], vals[3]),
                )

        matrix: tuple[float, float, float, float, float, float] = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        m_arr = stream.get_dictionary_object(_MATRIX)
        if isinstance(m_arr, COSArray) and m_arr.size() >= 6:
            mvals: list[float] = []
            for i in range(6):
                e = m_arr.get_object(i)
                if isinstance(e, (COSInteger, COSFloat)):
                    mvals.append(float(e.value))
                else:
                    mvals = []
                    break
            if len(mvals) == 6:
                matrix = (mvals[0], mvals[1], mvals[2], mvals[3], mvals[4], mvals[5])

        return bbox, matrix

    @staticmethod
    def _compute_ctm(
        rect: tuple[float, float, float, float],
        bbox: tuple[float, float, float, float],
        matrix: tuple[float, float, float, float, float, float],
    ) -> tuple[float, float, float, float, float, float]:
        """Compute the placement CTM that maps the form's transformed
        ``/BBox`` onto the widget's ``/Rect``.

        Per PDF 32000-1 §8.10.4 the form is first transformed by its
        ``/Matrix``, then placed by the ``Do`` operator's CTM. We compose
        the two: scale the matrix-transformed BBox to the rect's
        width/height, then translate to the rect's lower-left corner.
        Zero-area BBoxes are scaled by 1.0 (no-op) — defensive, mirrors
        upstream's ``Math.max(epsilon, ...)`` guard."""
        bx0, by0, bx1, by1 = bbox
        # Apply the form's /Matrix to the four BBox corners and rebuild
        # the axis-aligned bounding box of the transformed shape (the
        # /Matrix may rotate or skew, in which case the simple rect-fit
        # below is an approximation — full upstream parity would emit a
        # non-uniform CTM here).
        a, b, c, d, e, f = matrix
        corners = [
            (a * bx0 + c * by0 + e, b * bx0 + d * by0 + f),
            (a * bx1 + c * by0 + e, b * bx1 + d * by0 + f),
            (a * bx1 + c * by1 + e, b * bx1 + d * by1 + f),
            (a * bx0 + c * by1 + e, b * bx0 + d * by1 + f),
        ]
        xs = [pt[0] for pt in corners]
        ys = [pt[1] for pt in corners]
        tx0, ty0, tx1, ty1 = min(xs), min(ys), max(xs), max(ys)
        tw = tx1 - tx0 if tx1 != tx0 else 1.0
        th = ty1 - ty0 if ty1 != ty0 else 1.0

        rx0, ry0, rx1, ry1 = rect
        rw = rx1 - rx0
        rh = ry1 - ry0
        sx = rw / tw
        sy = rh / th
        # Final CTM = translate(rect.ll) * scale(sx, sy) * translate(-tx0, -ty0)
        return (sx, 0.0, 0.0, sy, rx0 - tx0 * sx, ry0 - ty0 * sy)

    @staticmethod
    def _add_xobject_to_page(page: COSDictionary, form: COSStream) -> COSName:
        """Register ``form`` under a unique key in the page's
        ``/Resources /XObject`` and return that key.

        Collision avoidance scans the existing key set and picks the
        first ``Fm<n>`` slot that isn't taken — matches the prefix
        upstream's ``createKey(PDFormXObject)`` uses (``Form`` in
        :class:`PDResources` map; PDFBox's flatten emits ``Fm`` to keep
        the synthesised names visually distinct from author-emitted Form
        XObjects)."""
        resources = page.get_dictionary_object(_RESOURCES)
        if not isinstance(resources, COSDictionary):
            resources = COSDictionary()
            page.set_item(_RESOURCES, resources)
        x_objects = resources.get_dictionary_object(_X_OBJECT)
        if not isinstance(x_objects, COSDictionary):
            x_objects = COSDictionary()
            resources.set_item(_X_OBJECT, x_objects)
        # Find the first Fm<n> not already in the dict.
        n = 0
        while True:
            candidate = COSName.get_pdf_name(f"Fm{n}")
            if not x_objects.contains_key(candidate):
                x_objects.set_item(candidate, form)
                return candidate
            n += 1

    @staticmethod
    def _append_do_to_page(
        page: COSDictionary,
        cm: tuple[float, float, float, float, float, float],
        name: COSName,
    ) -> None:
        """Append ``q <cm> cm /<name> Do Q`` to ``page``'s ``/Contents``.

        Matches the append pattern used by ``PDPageContentStream`` —
        single existing stream is promoted to a 2-element array rather
        than rewriting the original body in place. Preserves byte-for-byte
        the operators that were already on the page."""
        a, b, c, d, e, f = cm
        snippet = (
            f"\nq {_fmt(a)} {_fmt(b)} {_fmt(c)} {_fmt(d)} {_fmt(e)} {_fmt(f)} cm "
            f"/{name.name} Do Q\n"
        ).encode("ascii")

        new_stream = COSStream()
        new_stream.set_raw_data(snippet)

        existing = page.get_dictionary_object(_CONTENTS)
        if existing is None:
            page.set_item(_CONTENTS, new_stream)
            return
        if isinstance(existing, COSArray):
            existing.add(new_stream)
            return
        # Single stream: promote to array.
        arr = COSArray()
        arr.add(existing)
        arr.add(new_stream)
        page.set_item(_CONTENTS, arr)

    @staticmethod
    def _remove_widget_from_page(page: COSDictionary, widget: COSDictionary) -> None:
        """Drop ``widget`` from the page's ``/Annots`` array.

        Both direct and indirect entries are matched — we resolve each
        annotation reference and compare by object identity rather than
        by ``COSObject`` wrapper so a freshly-parsed indirect ref still
        finds its target. Walks a snapshot to keep iteration safe under
        mutation."""
        annots = page.get_dictionary_object(_ANNOTS)
        if not isinstance(annots, COSArray):
            return
        # Walk a snapshot — remove() shifts the underlying list.
        from pypdfbox.cos import COSObject

        for entry in list(annots):
            resolved = entry.get_object() if isinstance(entry, COSObject) else entry
            if resolved is widget:
                annots.remove(entry)

    def _remove_acro_form_from_catalog(self) -> None:
        """Drop the catalog's ``/AcroForm`` entry when we own a document.

        We hold the document via :attr:`_document` (the wrapping
        ``PDDocument``); when present we use its catalog accessor.
        Synthesised forms with no document attachment are a no-op — the
        in-memory dict can stay live for the caller to inspect."""
        document = self._document
        if document is None:
            return
        from pypdfbox.pdmodel.pd_document import PDDocument

        if not isinstance(document, PDDocument):
            return
        catalog = document.get_document_catalog()
        catalog.get_cos_object().remove_item(_ACRO_FORM)

    # ---------- upstream-named internal helpers (PDFBox parity) ----------
    #
    # These mirror the package-private helpers used by upstream's
    # ``flatten`` implementation. They are not part of the public API but
    # are exposed under their upstream snake-case names so writers driving
    # the same algorithm step-by-step (oracle/parity tests, downstream
    # subclasses) can rely on the same building blocks.

    @staticmethod
    def is_visible_annotation(widget: COSDictionary) -> bool:
        """Return ``True`` when ``widget`` has a non-empty normal appearance.

        Mirrors upstream ``PDAcroForm.isVisibleAnnotation`` (line 319): a
        widget is "visible" for flattening purposes when it is neither
        invisible nor hidden (``/F`` flag bits 1 / 2) and its ``/AP /N``
        resolves to a stream with a positive-area ``/BBox``.

        On the lite surface we don't yet carry the ``PDAnnotation`` class,
        so this operates directly on the widget COS dictionary — same
        observable contract."""
        from pypdfbox.cos import COSFloat, COSInteger

        flags = widget.get_int(COSName.get_pdf_name("F"), 0)
        # /F flag bit 1 = Invisible, bit 2 = Hidden (PDF 32000-1 §12.5.3).
        if flags & (1 << 0) or flags & (1 << 1):
            return False
        ap = widget.get_dictionary_object(_AP)
        if not isinstance(ap, COSDictionary):
            return False
        normal = ap.get_dictionary_object(_N)
        if not isinstance(normal, COSStream):
            return False
        bbox = normal.get_dictionary_object(_BBOX)
        if not isinstance(bbox, COSArray) or bbox.size() < 4:
            return False
        try:
            vals = []
            for i in range(4):
                entry = bbox.get_object(i)
                if not isinstance(entry, (COSInteger, COSFloat)):
                    return False
                vals.append(float(entry.value))
        except (AttributeError, TypeError):
            return False
        width = abs(vals[2] - vals[0])
        height = abs(vals[3] - vals[1])
        return width > 0 and height > 0

    @staticmethod
    def get_transformed_appearance_b_box(
        appearance_stream: COSStream,
    ) -> tuple[float, float, float, float] | None:
        """Apply the appearance stream's ``/Matrix`` to its ``/BBox`` and
        return the axis-aligned bounding box of the transformed shape.

        Mirrors upstream ``PDAcroForm.getTransformedAppearanceBBox`` (line
        755). Returns ``None`` when the form lacks a usable ``/BBox`` —
        upstream throws ``NullPointerException`` on this path; we prefer
        a clean ``None`` so callers can short-circuit.

        The pypdfbox ``flatten`` path uses :meth:`_read_form_geometry` for
        the same job — this method is the upstream-named entry point."""
        bbox, matrix = PDAcroForm._read_form_geometry(appearance_stream)
        if bbox is None:
            return None
        bx0, by0, bx1, by1 = bbox
        a, b, c, d, e, f = matrix
        corners = [
            (a * bx0 + c * by0 + e, b * bx0 + d * by0 + f),
            (a * bx1 + c * by0 + e, b * bx1 + d * by0 + f),
            (a * bx1 + c * by1 + e, b * bx1 + d * by1 + f),
            (a * bx0 + c * by1 + e, b * bx0 + d * by1 + f),
        ]
        xs = [pt[0] for pt in corners]
        ys = [pt[1] for pt in corners]
        return (min(xs), min(ys), max(xs), max(ys))

    def resolve_transformation_matrix(
        self, widget: COSDictionary, appearance_stream: COSStream
    ) -> tuple[float, float, float, float, float, float] | None:
        """Compute the placement CTM that maps ``appearance_stream`` onto
        ``widget``'s ``/Rect``.

        Mirrors upstream ``PDAcroForm.resolveTransformationMatrix`` (line
        733). Returns ``None`` when either the widget rectangle or the
        appearance bounding box can't be resolved — upstream throws on
        these paths; we prefer a soft ``None`` so flatten can skip the
        widget cleanly.

        The 6-tuple is ``(a, b, c, d, e, f)`` per PDF 32000-1 §8.3.4 —
        compatible with :class:`Matrix` and the ``cm`` operator."""
        rect = widget.get_dictionary_object(_RECT)
        if not isinstance(rect, COSArray) or rect.size() < 4:
            return None
        rect_values = self._read_rect(rect)
        if rect_values is None:
            return None
        bbox_values, matrix_values = self._read_form_geometry(appearance_stream)
        if bbox_values is None:
            return None
        return self._compute_ctm(rect_values, bbox_values, matrix_values)

    def build_pages_widgets_map(
        self,
        fields: list[PDField],
        pages: object | None = None,
    ) -> dict[int, set[int]]:
        """Build a ``{page id → {widget id, ...}}`` map for ``fields``.

        Mirrors upstream ``PDAcroForm.buildPagesWidgetsMap`` (line 770).
        Page lookup prefers each widget's ``/P`` back-pointer; widgets
        with no resolvable ``/P`` fall back to scanning every page's
        ``/Annots``. Identity is keyed by Python ``id()`` so the result
        round-trips object identity (the upstream version uses
        ``COSDictionary`` reference equality — same shape).

        ``pages`` is accepted for upstream signature parity; when
        ``None`` we fall back to the document's page tree. Returns an
        empty map when no widgets resolve."""
        out: dict[int, set[int]] = {}
        has_missing_page_ref = False

        for field in fields:
            for widget in field.get_widgets():
                widget_dict = widget.get_cos_object()
                page_dict = self._resolve_widget_page(widget_dict)
                if page_dict is not None:
                    self.fill_pages_annotation_map(out, page_dict, widget_dict)
                else:
                    has_missing_page_ref = True

        if not has_missing_page_ref:
            return out

        # Reverse-walk fallback when at least one widget has no /P.
        document = self._document if pages is None else pages
        if document is None:
            return out
        from pypdfbox.pdmodel.pd_document import PDDocument

        if not isinstance(document, PDDocument):
            return out
        widget_set = self.create_widget_dictionary_set(fields)
        for page in document.get_pages():
            page_dict = page.get_cos_object()
            annots = page_dict.get_dictionary_object(_ANNOTS)
            if not isinstance(annots, COSArray):
                continue
            for i in range(annots.size()):
                entry = annots.get_object(i)
                if isinstance(entry, COSDictionary) and id(entry) in widget_set:
                    self.fill_pages_annotation_map(out, page_dict, entry)
        return out

    @staticmethod
    def create_widget_dictionary_set(fields: list[PDField]) -> set[int]:
        """Return the set of widget COS-dictionary identities referenced
        by ``fields``.

        Mirrors upstream ``PDAcroForm.createWidgetDictionarySet`` (line
        823) — used by :meth:`build_pages_widgets_map` when at least one
        widget lacks a ``/P`` back-pointer. Identity is keyed by Python
        ``id()`` for parity with upstream's reference equality."""
        out: set[int] = set()
        for field in fields:
            for widget in field.get_widgets():
                out.add(id(widget.get_cos_object()))
        return out

    @staticmethod
    def fill_pages_annotation_map(
        pages_map: dict[int, set[int]],
        page: COSDictionary,
        widget: COSDictionary,
    ) -> None:
        """Add ``widget`` to ``pages_map[id(page)]``, creating the bucket
        when absent.

        Mirrors upstream ``PDAcroForm.fillPagesAnnotationMap`` (line 837)
        — small helper kept separate so :meth:`build_pages_widgets_map`
        and the reverse-walk fallback share a single insertion path."""
        bucket = pages_map.get(id(page))
        if bucket is None:
            pages_map[id(page)] = {id(widget)}
        else:
            bucket.add(id(widget))


def _fmt(value: float) -> str:
    """Format a CTM operand the same way :class:`PDPageContentStream`
    does — up to four fractional digits, trailing zeros trimmed,
    integers emitted without a decimal point."""
    if value == int(value):
        return str(int(value))
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


__all__ = ["PDAcroForm"]
