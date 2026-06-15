"""Shared helpers for the marked-content operators (``BMC``, ``BDC``,
``EMC``, ``MP``, ``DP``).

Centralises the small surface area that all five operators share:

* tag extraction from the operand list
* property-list resolution (inline ``COSDictionary`` vs named lookup via
  the engine's resources)
* ``/MCID`` accessor with the upstream sentinel default of ``-1``
* ``/Artifact`` tag predicate (mirrors ``COSName.ARTIFACT.equals(tag)``
  used by ``PDMarkedContent.create`` upstream)

These helpers are intentionally module-level functions so the
``OperatorProcessor`` subclasses stay thin and the resolution semantics
can be reused — and tested — without instantiating a stream engine.
"""
from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSBase, COSDictionary, COSName

# ---- Constants -------------------------------------------------------
# These mirror upstream ``COSName`` constants used by the marked-content
# subsystem. ``pypdfbox.cos.COSName`` does not (yet) ship pre-baked
# constants for every well-known PDF name, so we cache them locally to
# avoid repeated ``get_pdf_name`` lookups in the hot path.

#: ``/MCID`` — the marked-content identifier key in a property list.
MCID_KEY: COSName = COSName.get_pdf_name("MCID")

#: ``/Artifact`` — the standard structure tag for non-content artifacts
#: (header / footer / decoration), special-cased by upstream's
#: ``PDMarkedContent.create``.
ARTIFACT_TAG: COSName = COSName.get_pdf_name("Artifact")

#: Sentinel returned by ``get_mcid`` when no ``/MCID`` entry is present.
#: Matches the upstream ``PDMarkedContent.getMCID()`` contract.
MCID_DEFAULT: int = -1


# ---- Tag extraction --------------------------------------------------

def extract_tag(operands: list[COSBase]) -> COSName | None:
    """Return the **last** ``COSName`` among the operands, or ``None``.

    Mirrors upstream ``BeginMarkedContentSequence.process`` /
    ``MarkedContentPoint.process``: both iterate the entire operand list
    and keep the most recent ``COSName`` seen
    (``for (COSBase b : arguments) if (b instanceof COSName) tag = ...``).
    The *last* name wins, and any leading non-name junk (numbers,
    strings) is skipped rather than aborting tag selection — so
    ``1 (x) /Span BMC`` yields the tag ``/Span`` and ``/A /B BMC`` yields
    ``/B``.

    The marked-content operators tolerate malformed input by simply
    dropping the tag (returning ``None``) when no name is present —
    upstream throws ``MissingOperandException`` for the
    property-list-bearing operators (BDC/DP) but the bare BMC/MP forms
    proceed with a ``null`` tag. pypdfbox is uniformly tolerant: caller
    code branches on ``tag is None``.
    """
    tag: COSName | None = None
    for argument in operands:
        if isinstance(argument, COSName):
            tag = argument
    return tag


# ---- Property resolution --------------------------------------------

def resolve_property_dict(
    operands: list[COSBase],
    context: Any | None,
) -> COSDictionary | None:
    """Resolve the property list operand for ``BDC`` / ``DP``.

    The second operand is either:

    * an inline ``COSDictionary`` — returned as-is, or
    * a ``COSName`` — looked up in the engine's current page resources
      under ``/Properties``, returning the resolved ``COSDictionary`` or
      ``None`` if the named property list is absent / malformed.

    Returns ``None`` when:

    * the operand list is shorter than 2 entries
    * the second operand is neither a name nor a dictionary
    * the named lookup fails (resources missing, name absent, malformed
      property list entry)
    * any defensive try/except path catches a malformed-PDF exception

    Mirrors the resolution logic in upstream
    ``BeginMarkedContentSequenceWithProperties.process`` and
    ``MarkedContentPointWithProperties.process``.
    """
    if len(operands) < 2:
        return None
    prop = operands[1]
    if isinstance(prop, COSDictionary):
        return prop
    if not isinstance(prop, COSName) or context is None:
        return None
    getter = getattr(context, "get_resources", None)
    if getter is None:
        return None
    try:
        resources = getter()
    except Exception:  # noqa: BLE001 — defensive
        return None
    if resources is None:
        return None
    try:
        pl = resources.get_property_list(prop)
    except Exception:  # noqa: BLE001 — defensive: malformed dict
        return None
    if pl is None:
        return None
    try:
        cos_object = pl.get_cos_object()
    except Exception:  # noqa: BLE001 — defensive
        return None
    if isinstance(cos_object, COSDictionary):
        return cos_object
    return None


# ---- Typed accessors -------------------------------------------------

def get_mcid(properties: COSDictionary | None) -> int:
    """Return ``/MCID`` from a marked-content property list.

    Returns :data:`MCID_DEFAULT` (``-1``) when:

    * ``properties`` is ``None``
    * the dictionary has no ``/MCID`` entry
    * the entry is not an integer

    Mirrors ``PDMarkedContent.getMCID()`` upstream — the ``-1`` sentinel
    is the documented "absent" marker, not an error.
    """
    if properties is None:
        return MCID_DEFAULT
    return properties.get_int(MCID_KEY, MCID_DEFAULT)


def has_mcid(properties: COSDictionary | None) -> bool:
    """Predicate: is a real ``/MCID`` entry present?

    Distinguishes "no property list / no key" from "MCID is set to -1"
    (which would be malformed but is technically representable). Useful
    for callers that want to log structural mismatches.
    """
    if properties is None:
        return False
    return properties.contains_key(MCID_KEY)


def is_artifact_tag(tag: COSName | None) -> bool:
    """Predicate: is ``tag`` the ``/Artifact`` structural tag?

    Mirrors the ``COSName.ARTIFACT.equals(tag)`` branch in upstream
    ``PDMarkedContent.create`` — used by extractors / structure builders
    to route a marked-content sequence into the artifact subclass.
    """
    return tag is not None and tag == ARTIFACT_TAG


__all__ = [
    "ARTIFACT_TAG",
    "MCID_DEFAULT",
    "MCID_KEY",
    "extract_tag",
    "get_mcid",
    "has_mcid",
    "is_artifact_tag",
    "resolve_property_dict",
]
