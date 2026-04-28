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
