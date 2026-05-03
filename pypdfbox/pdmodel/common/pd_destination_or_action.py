from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSName,
    COSString,
)


class PDDestinationOrAction:
    """
    Marker base for values that can be either a destination or an action.

    Mirrors ``org.apache.pdfbox.pdmodel.common.PDDestinationOrAction`` — an
    interface in upstream that has no methods (it just composes
    ``COSObjectable``) and is implemented by both
    :class:`pypdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination`
    and :class:`pypdfbox.pdmodel.interactive.action.PDAction`. Used by
    catalog-level entries like ``/OpenAction`` and per-element entries that
    accept either form (link annotations' ``/Dest`` + ``/A``, outline
    items' ``/Dest`` + ``/A``, etc.).

    Python doesn't have Java's interface-only contract, so we expose this
    as a lightweight base class. Subclasses (``PDDestination``,
    ``PDAction``) do not currently inherit from it for compatibility with
    their own existing inheritance chains; ``isinstance`` checks against
    this marker should be done structurally via :func:`is_destination_or_action`
    or by checking the two concrete bases directly.

    This module also exposes a static factory :meth:`create` that mirrors
    the dispatch logic upstream inlines in
    ``PDDocumentCatalog.getOpenAction()``: arrays / names / strings →
    :meth:`PDDestination.create`, dictionaries → :meth:`PDAction.create`,
    ``None`` → ``None``.
    """

    @staticmethod
    def create(value: COSBase | None) -> Any:
        """Dispatch a raw COS value to either a :class:`PDDestination` or a
        :class:`PDAction`.

        - ``COSArray``, ``COSName``, ``COSString`` → :meth:`PDDestination.create`
        - ``COSDictionary`` with ``/S`` (subtype) → :meth:`PDAction.create`
        - ``COSDictionary`` with only ``/D`` (no ``/S``) → wrapped as a
          :class:`PDActionGoTo` shorthand. PDF 32000-1 §12.6.2 / §12.3.2.2
          describe an action dictionary; some legacy producers omit ``/S``
          and rely on the presence of ``/D`` alone to imply a GoTo action.
        - ``COSDictionary`` (otherwise) → :meth:`PDAction.create` (which
          falls back to ``PDActionUnknown``)
        - ``None`` → ``None``
        - any other type → ``None`` (matches upstream
          ``PDDocumentCatalog.getOpenAction()`` which silently drops
          unrecognized COS values)
        """
        if value is None:
            return None
        if isinstance(value, COSDictionary):
            from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
            from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo

            sub_type = value.get_name(COSName.get_pdf_name("S"))
            if sub_type is None and value.contains_key(COSName.get_pdf_name("D")):
                # Action-shaped dictionary lacking /S but carrying /D —
                # treat as an implicit GoTo action.
                return PDActionGoTo(value)
            return PDAction.create(value)
        if isinstance(value, (COSArray, COSName, COSString)):
            from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
                PDDestination,
            )

            return PDDestination.create(value)
        return None

    def get_cos_object(self) -> Any:  # pragma: no cover - marker default
        raise NotImplementedError


def is_destination_or_action(value: Any) -> bool:
    """Return ``True`` if ``value`` is a :class:`PDDestination` or a
    :class:`PDAction` instance.

    Provided for callers that want a single ``isinstance``-style check
    without importing both concrete bases. Mirrors upstream Java code
    that does ``instanceof PDDestinationOrAction`` against either
    subclass.
    """
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
        PDDestination,
    )

    return isinstance(value, (PDDestination, PDAction))


def is_action(value: Any) -> bool:
    """Return ``True`` if ``value`` is a :class:`PDAction` instance.

    Single-arm counterpart of :func:`is_destination_or_action`. pypdfbox
    extension — surfaced for callers that branch on the action arm without
    wanting the broader marker check (e.g. catalog-level dispatch where a
    destination would be handled separately by the caller)."""
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

    return isinstance(value, PDAction)


def is_destination(value: Any) -> bool:
    """Return ``True`` if ``value`` is a :class:`PDDestination` instance.

    Single-arm counterpart of :func:`is_destination_or_action`. pypdfbox
    extension — paired with :func:`is_action` for callers that want a
    typed yes/no on the destination arm without the marker-level union."""
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
        PDDestination,
    )

    return isinstance(value, PDDestination)


def kind_of(value: Any) -> str | None:
    """Return ``"action"`` for a :class:`PDAction`, ``"destination"`` for a
    :class:`PDDestination`, or ``None`` otherwise.

    pypdfbox extension — a string-shaped discriminator paired with the
    :class:`PDDestinationOrAction` factory for callers that prefer to
    branch on a tag rather than a chain of ``isinstance`` checks. The
    return values match the natural English names of the two arms in the
    PDF Reference (and in :class:`PDDestinationOrAction`'s docstring)."""
    if is_destination(value):
        return "destination"
    if is_action(value):
        return "action"
    return None


def create_from_open_action_entry(value: COSBase | None) -> Any:
    """Module-level factory mirroring :meth:`PDDestinationOrAction.create`.

    pypdfbox extension — provides a verbose, function-shaped entry point
    for callers that want the same dispatch as the static method but
    spelled out as a free function (handier for ``map`` / list-comprehension
    use). Delegates directly to :meth:`PDDestinationOrAction.create`."""
    return PDDestinationOrAction.create(value)


__all__ = [
    "PDDestinationOrAction",
    "create_from_open_action_entry",
    "is_action",
    "is_destination",
    "is_destination_or_action",
    "kind_of",
]
