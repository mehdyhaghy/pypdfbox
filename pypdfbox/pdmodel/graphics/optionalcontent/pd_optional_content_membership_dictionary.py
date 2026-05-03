from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from pypdfbox.cos import COSArray, COSDictionary, COSName

from ..pd_property_list import PDPropertyList
from .pd_optional_content_group import PDOptionalContentGroup

# A state resolver callable maps a PDOptionalContentGroup wrapper to its
# current visibility state (``True`` == ON, ``False`` == OFF). Mirrors
# upstream PDFBox usage of an ``isVisible(PDOptionalContentGroup)``
# predicate when evaluating OCMD/VE trees.
StateResolver = Callable[[PDOptionalContentGroup], bool]


class MembershipDictionaryVisibilityPolicy(Enum):
    """OCMD /P visibility policy. Mirrors upstream nested enum
    ``PDOptionalContentMembershipDictionary.VisibilityPolicy`` with values
    ``AllOn`` / ``AnyOn`` / ``AnyOff`` / ``AllOff`` (PDF 32000-1
    §8.11.2.2).
    """

    ALL_ON = "AllOn"
    ANY_ON = "AnyOn"
    ANY_OFF = "AnyOff"
    ALL_OFF = "AllOff"

    def get_pdf_name(self) -> COSName:
        return COSName.get_pdf_name(self.value)

    @classmethod
    def value_of(cls, name: str) -> "MembershipDictionaryVisibilityPolicy":
        """Look up a member by its spec name. Mirrors upstream
        ``VisibilityPolicy.valueOf(String)``."""
        for member in cls:
            if member.value == name:
                return member
        raise ValueError(
            f"MembershipDictionaryVisibilityPolicy has no member named {name!r}"
        )

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OCMD: COSName = COSName.get_pdf_name("OCMD")
_OCGS: COSName = COSName.get_pdf_name("OCGs")
_P: COSName = COSName.get_pdf_name("P")
_VE: COSName = COSName.get_pdf_name("VE")
_ANY_ON: COSName = COSName.get_pdf_name("AnyOn")

_VALID_POLICIES: frozenset[str] = frozenset(
    {"AllOn", "AnyOn", "AnyOff", "AllOff"}
)


class PDOptionalContentMembershipDictionary(PDPropertyList):
    """Optional content membership dictionary (OCMD).

    Mirrors PDFBox ``PDOptionalContentMembershipDictionary``.
    """

    # Visibility policy constants per PDF 32000-1 §8.11.2.2 / Table 102.
    VISIBILITY_POLICY_ALL_ON: str = "AllOn"
    VISIBILITY_POLICY_ANY_ON: str = "AnyOn"
    VISIBILITY_POLICY_ANY_OFF: str = "AnyOff"
    VISIBILITY_POLICY_ALL_OFF: str = "AllOff"

    # Expose the typed enum for upstream API parity:
    # ``PDOptionalContentMembershipDictionary.VisibilityPolicy.AllOn``.
    VisibilityPolicy = MembershipDictionaryVisibilityPolicy

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            super().__init__()
            self._dict.set_item(_TYPE, _OCMD)
            return
        existing = dictionary.get_dictionary_object(_TYPE)
        if existing is not None and existing != _OCMD:
            raise ValueError(f"Provided dictionary is not of type '{_OCMD}'")
        super().__init__(dictionary)
        if existing is None:
            self._dict.set_item(_TYPE, _OCMD)

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Type ----------

    def get_type(self) -> COSName:
        """Return the /Type value, always ``/OCMD`` for an OCMD.

        Mirrors the PDFBox convention of exposing a ``getType()`` accessor on
        typed COS wrappers — handy when callers need to round-trip without
        hard-coding the literal name.
        """
        value = self._dict.get_dictionary_object(_TYPE)
        if isinstance(value, COSName):
            return value
        # Defensive: if /Type was somehow stripped, return the canonical name.
        return _OCMD

    # ---------- /OCGs ----------

    def get_o_cgs(self) -> list[PDOptionalContentGroup]:
        """Return the referenced optional content groups, never ``None``.

        /OCGs may be either a single OCG dictionary or a COSArray of them.
        Non-OCG dictionaries (e.g. nested OCMDs) are skipped — this lite
        port returns only ``PDOptionalContentGroup`` instances.
        """
        base = self._dict.get_dictionary_object(_OCGS)
        if base is None:
            return []
        if isinstance(base, COSDictionary):
            wrapped = PDPropertyList.create(base)
            if isinstance(wrapped, PDOptionalContentGroup):
                return [wrapped]
            return []
        if isinstance(base, COSArray):
            result: list[PDOptionalContentGroup] = []
            for i in range(base.size()):
                elem = base.get_object(i)
                if isinstance(elem, COSDictionary):
                    wrapped = PDPropertyList.create(elem)
                    if isinstance(wrapped, PDOptionalContentGroup):
                        result.append(wrapped)
            return result
        return []

    def set_o_cgs(
        self,
        ocgs: list[PDOptionalContentGroup | COSDictionary],
    ) -> None:
        """Write /OCGs as a COSArray.

        Accepts ``PDOptionalContentGroup`` wrappers or raw ``COSDictionary``
        entries.
        """
        arr = COSArray()
        for item in ocgs:
            if isinstance(item, PDOptionalContentGroup):
                arr.add(item.get_cos_object())
            elif isinstance(item, COSDictionary):
                arr.add(item)
            else:
                raise TypeError(
                    "ocgs entries must be PDOptionalContentGroup or "
                    f"COSDictionary, got {type(item).__name__}"
                )
        self._dict.set_item(_OCGS, arr)

    # Upstream PDFBox spelling: ``getOCGs`` / ``setOCGs``. The auto
    # camelCase→snake_case rule splits at every uppercase boundary which
    # produces ``get_o_cgs``; PDFBox developers reach for ``get_ocgs`` first,
    # so expose that as the canonical name with the split form kept as an
    # alias for back-compat with earlier callers.
    def get_ocgs(self) -> list[PDOptionalContentGroup]:
        """Return the referenced optional content groups, never ``None``.

        Mirrors PDFBox ``PDOptionalContentMembershipDictionary.getOCGs``.
        """
        return self.get_o_cgs()

    def get_ocgs_property_list(self) -> list[PDPropertyList]:
        """Return /OCGs entries as ``PDPropertyList`` instances.

        Strict parity with upstream ``getOCGs() : List<PDPropertyList>`` —
        unlike :meth:`get_ocgs` (which filters down to
        ``PDOptionalContentGroup`` only), this preserves every
        ``PDPropertyList`` subclass returned by ``PDPropertyList.create``,
        including nested ``PDOptionalContentMembershipDictionary`` entries.
        """
        base = self._dict.get_dictionary_object(_OCGS)
        if base is None:
            return []
        if isinstance(base, COSDictionary):
            wrapped = PDPropertyList.create(base)
            return [wrapped] if wrapped is not None else []
        if isinstance(base, COSArray):
            result: list[PDPropertyList] = []
            for i in range(base.size()):
                elem = base.get_object(i)
                if isinstance(elem, COSDictionary):
                    wrapped = PDPropertyList.create(elem)
                    if wrapped is not None:
                        result.append(wrapped)
            return result
        return []

    def set_ocgs(
        self,
        ocgs: (
            PDOptionalContentGroup
            | COSDictionary
            | list[PDOptionalContentGroup | COSDictionary]
        ),
    ) -> None:
        """Write /OCGs.

        When given a single ``PDOptionalContentGroup`` or ``COSDictionary``,
        writes the value directly (PDF 32000-1 §8.11.2.2 allows /OCGs to be
        either a single OCG dictionary or an array). Lists become a
        ``COSArray`` via :meth:`set_o_cgs`.
        """
        if isinstance(ocgs, PDOptionalContentGroup):
            self._dict.set_item(_OCGS, ocgs.get_cos_object())
            return
        if isinstance(ocgs, COSDictionary):
            self._dict.set_item(_OCGS, ocgs)
            return
        if isinstance(ocgs, list):
            self.set_o_cgs(ocgs)
            return
        raise TypeError(
            "ocgs must be PDOptionalContentGroup, COSDictionary, or list, "
            f"got {type(ocgs).__name__}"
        )

    # ---------- /OCGs membership helpers ----------

    def contains_ocg(self, group: PDOptionalContentGroup | COSDictionary) -> bool:
        """Return ``True`` when ``group`` is referenced by /OCGs.

        Membership is matched by *identity* of the wrapped
        ``COSDictionary`` (mirrors :meth:`PDOptionalContentConfiguration.is_on`)
        so OCGs sharing a /Name aren't accidentally collapsed. Accepts
        either a :class:`PDOptionalContentGroup` wrapper or the raw
        ``COSDictionary``.

        Not present in upstream PDFBox (``getOCGs`` returns the list and
        callers walk it themselves); pypdfbox enrichment for the common
        "is this OCG part of the membership?" predicate.
        """
        if isinstance(group, PDOptionalContentGroup):
            target = group.get_cos_object()
        elif isinstance(group, COSDictionary):
            target = group
        else:
            raise TypeError(
                "group must be PDOptionalContentGroup or COSDictionary, "
                f"got {type(group).__name__}"
            )
        base = self._dict.get_dictionary_object(_OCGS)
        if base is None:
            return False
        if isinstance(base, COSDictionary):
            return base is target
        if isinstance(base, COSArray):
            for i in range(base.size()):
                if base.get_object(i) is target:
                    return True
            return False
        return False

    def add_ocg(self, group: PDOptionalContentGroup | COSDictionary) -> None:
        """Append a single OCG to /OCGs.

        Promotes a single-dictionary /OCGs entry to a ``COSArray`` on
        first append. No-ops when ``group`` is already referenced (matched
        by identity of the wrapped ``COSDictionary``). Symmetric
        single-element counterpart to :meth:`set_ocgs` for the common
        "build OCMD incrementally" pattern. pypdfbox enrichment.
        """
        if isinstance(group, PDOptionalContentGroup):
            target = group.get_cos_object()
        elif isinstance(group, COSDictionary):
            target = group
        else:
            raise TypeError(
                "group must be PDOptionalContentGroup or COSDictionary, "
                f"got {type(group).__name__}"
            )
        base = self._dict.get_dictionary_object(_OCGS)
        if base is None:
            arr = COSArray()
            arr.add(target)
            self._dict.set_item(_OCGS, arr)
            return
        if isinstance(base, COSDictionary):
            if base is target:
                return
            promoted = COSArray()
            promoted.add(base)
            promoted.add(target)
            self._dict.set_item(_OCGS, promoted)
            return
        if isinstance(base, COSArray):
            for i in range(base.size()):
                if base.get_object(i) is target:
                    return
            base.add(target)
            return
        # /OCGs holds something exotic — replace with a fresh single-item array.
        arr = COSArray()
        arr.add(target)
        self._dict.set_item(_OCGS, arr)

    def remove_ocg(
        self, group: PDOptionalContentGroup | COSDictionary
    ) -> bool:
        """Drop ``group`` from /OCGs. Returns ``True`` when an entry was
        removed.

        Membership is matched by *identity* of the wrapped
        ``COSDictionary`` (mirrors :meth:`contains_ocg` and
        :meth:`add_ocg`). Handles all three /OCGs storage shapes:

        - missing /OCGs                       → returns ``False``
        - single-dict form, identity match    → /OCGs key removed entirely
        - single-dict form, no match          → returns ``False``
        - array form                          → removes every identity match;
          if the array becomes empty /OCGs is removed entirely so the dict
          does not retain an empty husk.

        Symmetric counterpart to :meth:`add_ocg`. pypdfbox enrichment —
        Apache PDFBox 3.0 leaves callers to manipulate the COSArray in
        place.
        """
        if isinstance(group, PDOptionalContentGroup):
            target = group.get_cos_object()
        elif isinstance(group, COSDictionary):
            target = group
        else:
            raise TypeError(
                "group must be PDOptionalContentGroup or COSDictionary, "
                f"got {type(group).__name__}"
            )
        base = self._dict.get_dictionary_object(_OCGS)
        if base is None:
            return False
        if isinstance(base, COSDictionary):
            if base is target:
                self._dict.remove_item(_OCGS)
                return True
            return False
        if isinstance(base, COSArray):
            removed = False
            # Walk in reverse so index-based removals don't shift subsequent
            # entries before we visit them.
            for i in reversed(range(base.size())):
                if base.get_object(i) is target:
                    base.remove_at(i)
                    removed = True
            if removed and base.size() == 0:
                self._dict.remove_item(_OCGS)
            return removed
        return False

    def clear_ocgs(self) -> None:
        """Remove /OCGs entirely.

        No-op when /OCGs is already absent. Symmetric counterpart to the
        build-up sequence ``set_ocgs`` / ``add_ocg``. pypdfbox enrichment
        — handy when a caller wants to reuse the OCMD with a fresh set of
        groups (and matches the prune-empty semantics used elsewhere in
        this module).
        """
        self._dict.remove_item(_OCGS)

    def get_ocg_count(self) -> int:
        """Return the number of OCG references in /OCGs.

        Counts every entry under /OCGs regardless of storage shape:

        - missing /OCGs       → ``0``
        - single-dict form    → ``1``
        - array form          → number of entries (including non-OCG
          dictionaries — matches the loose read shape of
          :meth:`get_ocgs_property_list`).

        pypdfbox enrichment. PDFBox callers have to materialize
        ``getOCGs().size()``; exposing the count avoids the full wrap.
        """
        base = self._dict.get_dictionary_object(_OCGS)
        if base is None:
            return 0
        if isinstance(base, COSDictionary):
            return 1
        if isinstance(base, COSArray):
            return base.size()
        return 0

    def __len__(self) -> int:
        """Pythonic alias for :meth:`get_ocg_count`. Lets callers write
        ``len(ocmd)`` or ``if not ocmd: ...`` to inspect membership size.
        """
        return self.get_ocg_count()

    def has_ocgs(self) -> bool:
        """``True`` when /OCGs is present and non-empty.

        pypdfbox enrichment — predicate counterpart to
        :meth:`get_ocg_count`. Rejects both missing-/OCGs and empty-array
        states so callers don't have to inspect the count themselves.
        """
        return self.get_ocg_count() > 0

    # ---------- /P (visibility policy) ----------

    def get_visibility_policy(self) -> str:
        """Return /P name. Defaults to "AnyOn" per PDF 1.7 §8.11.2.2."""
        value = self._dict.get_dictionary_object(_P)
        if isinstance(value, COSName):
            return value.name
        return _ANY_ON.name

    def set_visibility_policy(
        self, policy: str | MembershipDictionaryVisibilityPolicy
    ) -> None:
        if isinstance(policy, MembershipDictionaryVisibilityPolicy):
            self._dict.set_item(_P, policy.get_pdf_name())
            return
        if policy not in _VALID_POLICIES:
            raise ValueError(
                "visibility_policy must be one of "
                f"{sorted(_VALID_POLICIES)}, got {policy!r}"
            )
        self._dict.set_item(_P, COSName.get_pdf_name(policy))

    def get_visibility_policy_enum(
        self,
    ) -> MembershipDictionaryVisibilityPolicy:
        """Typed-enum variant of :meth:`get_visibility_policy`."""
        return MembershipDictionaryVisibilityPolicy.value_of(
            self.get_visibility_policy()
        )

    def is_visibility_policy(
        self,
        policy: str | MembershipDictionaryVisibilityPolicy,
    ) -> bool:
        """Return ``True`` when /P matches ``policy``.

        Accepts either a spec-name string (e.g. ``"AnyOff"``) or a
        :class:`MembershipDictionaryVisibilityPolicy` enum member. The
        comparison honours the spec default — ``is_visibility_policy("AnyOn")``
        returns ``True`` when /P is absent because ``"AnyOn"`` is the
        default per PDF 32000-1 §8.11.2.2.

        pypdfbox enrichment — Apache PDFBox 3.0 makes callers compare
        ``getVisibilityPolicy().equals(COSName.ALL_ON)`` themselves; this
        is the common predicate they end up writing.
        """
        if isinstance(policy, MembershipDictionaryVisibilityPolicy):
            target = policy.value
        elif isinstance(policy, str):
            target = policy
        else:
            raise TypeError(
                "policy must be str or MembershipDictionaryVisibilityPolicy, "
                f"got {type(policy).__name__}"
            )
        return self.get_visibility_policy() == target

    def get_visibility_policy_name(self) -> COSName:
        """Return /P as a ``COSName``, defaulting to ``/AnyOn``.

        Strict parity with upstream
        ``getVisibilityPolicy() : COSName`` (which returns the raw
        ``COSName`` rather than its string form).
        """
        value = self._dict.get_dictionary_object(_P)
        if isinstance(value, COSName):
            return value
        return _ANY_ON

    def set_visibility_policy_name(self, visibility_policy: COSName) -> None:
        """Write /P with a raw ``COSName``.

        Strict parity with upstream
        ``setVisibilityPolicy(COSName visibilityPolicy)`` — accepts any
        ``COSName`` without enum-style validation. Use
        :meth:`set_visibility_policy` if you want the spec-name guard.
        """
        if not isinstance(visibility_policy, COSName):
            raise TypeError(
                "visibility_policy must be COSName, "
                f"got {type(visibility_policy).__name__}"
            )
        self._dict.set_item(_P, visibility_policy)

    # ---------- /VE (visibility expression) ----------

    def get_visibility_expression(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_VE)
        return value if isinstance(value, COSArray) else None

    def set_visibility_expression(self, ve: COSArray | None) -> None:
        if ve is None:
            self._dict.remove_item(_VE)
            return
        if not isinstance(ve, COSArray):
            raise TypeError(
                "visibility_expression must be COSArray or None, "
                f"got {type(ve).__name__}"
            )
        self._dict.set_item(_VE, ve)

    # ---------- /VE evaluation (PDF 32000-1 §8.11.2.4) ----------

    def evaluate_visibility(self, visible_ocgs: set[int]) -> bool:
        """Evaluate the /VE visibility expression tree.

        ``visible_ocgs`` is the set of ``id(cos_dictionary)`` values for
        OCGs that are currently ON. Returns ``True`` if the expression
        evaluates to "visible".

        Falls back to /P + /OCGs evaluation when /VE is absent.
        """
        ve = self.get_visibility_expression()
        if ve is None:
            return self._evaluate_policy(visible_ocgs)
        return self._eval_node(ve, visible_ocgs)

    def is_visible(self, visible_ocgs: set[int]) -> bool:
        """Combined visibility test.

        Prefers /VE when present; otherwise applies /P + /OCGs policy.
        """
        if self.get_visibility_expression() is not None:
            return self.evaluate_visibility(visible_ocgs)
        return self._evaluate_policy(visible_ocgs)

    # ---------- Resolver-callable variants (PDFBox-style) ----------
    #
    # Upstream PDFBox queries OCG state through a predicate / lookup rather
    # than threading a precomputed visibility set. Expose a parallel API
    # here so callers can pass a ``StateResolver`` callable directly.

    def is_visible_with(self, state_resolver: StateResolver) -> bool:
        """Resolver-callable form of :meth:`is_visible`.

        ``state_resolver`` maps a :class:`PDOptionalContentGroup` to its
        current visibility (``True`` == ON, ``False`` == OFF).

        Prefers /VE when present; otherwise applies /P + /OCGs policy.
        """
        if self.get_visibility_expression() is not None:
            return self.evaluate_ve(
                self.get_visibility_expression(), state_resolver
            )
        return self._evaluate_policy_with(state_resolver)

    def evaluate_ve(
        self,
        ve: COSArray | None,
        state_resolver: StateResolver,
    ) -> bool:
        """Evaluate a /VE visibility expression tree (PDF 32000-1 §8.11.2.4).

        ``ve`` is the raw COSArray expression (typically the value of /VE).
        Operator dispatch:
        - ``[/And  child1 child2 ...]`` — True iff every child is True
        - ``[/Or   child1 child2 ...]`` — True iff at least one child is True
        - ``[/Not  child]``             — True iff the single child is False

        Children may be either OCG dictionaries (leaves) or further VE
        sub-arrays (recursive). When ``ve`` is ``None`` the dict is treated
        as having no expression and the policy fallback is applied.
        """
        if ve is None:
            return self._evaluate_policy_with(state_resolver)
        return self._eval_node_with(ve, state_resolver)

    @classmethod
    def _eval_node_with(
        cls,
        node: object,
        state_resolver: StateResolver,
    ) -> bool:
        """Recursive /VE walker that dispatches via a state-resolver
        callable instead of a precomputed visibility set."""
        if isinstance(node, COSDictionary):
            wrapped = PDPropertyList.create(node)
            if isinstance(wrapped, PDOptionalContentGroup):
                return bool(state_resolver(wrapped))
            # Non-OCG dictionary leaves are treated as "not visible" — the
            # spec only allows OCG references at leaf positions.
            return False
        if isinstance(node, COSArray):
            if node.size() == 0:
                raise ValueError(
                    "Empty /VE sub-array — missing operator"
                )
            head = node.get_object(0)
            if not isinstance(head, COSName):
                raise ValueError(
                    "First element of /VE array must be a COSName operator"
                )
            op = head.name
            rest = [node.get_object(i) for i in range(1, node.size())]
            if op == "Not":
                if len(rest) != 1:
                    raise ValueError(
                        "/VE 'Not' requires exactly 1 operand, "
                        f"got {len(rest)}"
                    )
                return not cls._eval_node_with(rest[0], state_resolver)
            if op == "And":
                if not rest:
                    raise ValueError("/VE 'And' requires >= 1 operand")
                return all(
                    cls._eval_node_with(child, state_resolver)
                    for child in rest
                )
            if op == "Or":
                if not rest:
                    raise ValueError("/VE 'Or' requires >= 1 operand")
                return any(
                    cls._eval_node_with(child, state_resolver)
                    for child in rest
                )
            raise ValueError(f"Unknown /VE operator: {op!r}")
        return False

    def _evaluate_policy_with(
        self, state_resolver: StateResolver
    ) -> bool:
        """Resolver-callable form of :meth:`_evaluate_policy`.

        Per PDF 32000-1 §8.11.2.2:
        - "AllOn":  visible iff every OCG is on
        - "AnyOn":  visible iff at least one OCG is on (default)
        - "AnyOff": visible iff at least one OCG is off
        - "AllOff": visible iff every OCG is off
        With no /OCGs entries, AllOn/AllOff are vacuously True and
        AnyOn/AnyOff are vacuously False (matches PDFBox semantics).
        """
        groups = self.get_o_cgs()
        states = [bool(state_resolver(g)) for g in groups]
        policy = self.get_visibility_policy()
        if policy == "AllOn":
            return all(states)
        if policy == "AnyOn":
            return any(states)
        if policy == "AnyOff":
            return any(not s for s in states)
        if policy == "AllOff":
            return all(not s for s in states)
        # Unknown policy: be conservative, treat as default AnyOn.
        return any(states)

    @classmethod
    def _eval_node(cls, node: object, visible: set[int]) -> bool:
        """Recursively evaluate a /VE tree node.

        - ``COSDictionary``: True iff ``id(node)`` is in ``visible``.
        - ``COSArray``: dispatch on the first element ("And"/"Or"/"Not").
        """
        if isinstance(node, COSDictionary):
            return id(node) in visible
        if isinstance(node, COSArray):
            if node.size() == 0:
                raise ValueError("Empty /VE sub-array — missing operator")
            head = node.get_object(0)
            if not isinstance(head, COSName):
                raise ValueError(
                    "First element of /VE array must be a COSName operator"
                )
            op = head.name
            rest = [node.get_object(i) for i in range(1, node.size())]
            if op == "Not":
                if len(rest) != 1:
                    raise ValueError(
                        f"/VE 'Not' requires exactly 1 operand, got {len(rest)}"
                    )
                return not cls._eval_node(rest[0], visible)
            if op == "And":
                if not rest:
                    raise ValueError("/VE 'And' requires >= 1 operand")
                return all(cls._eval_node(child, visible) for child in rest)
            if op == "Or":
                if not rest:
                    raise ValueError("/VE 'Or' requires >= 1 operand")
                return any(cls._eval_node(child, visible) for child in rest)
            raise ValueError(f"Unknown /VE operator: {op!r}")
        # Anything else (e.g. unresolved indirect ref to a non-dict, or null)
        # is treated as "not visible".
        return False

    def _evaluate_policy(self, visible_ocgs: set[int]) -> bool:
        """Apply the /P policy to the /OCGs list.

        Per PDF 32000-1 §8.11.2.2:
        - "AllOn":  visible iff every OCG is on
        - "AnyOn":  visible iff at least one OCG is on (default)
        - "AnyOff": visible iff at least one OCG is off
        - "AllOff": visible iff every OCG is off
        With no /OCGs entries, AllOn/AllOff are vacuously True and
        AnyOn/AnyOff are vacuously False (matches PDFBox semantics).
        """
        groups = self.get_o_cgs()
        states = [id(g.get_cos_object()) in visible_ocgs for g in groups]
        policy = self.get_visibility_policy()
        if policy == "AllOn":
            return all(states)
        if policy == "AnyOn":
            return any(states)
        if policy == "AnyOff":
            return any(not s for s in states)
        if policy == "AllOff":
            return all(not s for s in states)
        # Unknown policy: be conservative, treat as default AnyOn.
        return any(states)


__all__ = [
    "MembershipDictionaryVisibilityPolicy",
    "PDOptionalContentMembershipDictionary",
    "StateResolver",
]
