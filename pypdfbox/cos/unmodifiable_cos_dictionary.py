"""Read-only ``COSDictionary`` view module.

Mirrors ``org.apache.pdfbox.cos.UnmodifiableCOSDictionary``
(``UnmodifiableCOSDictionary.java``, Apache PDFBox 3.0) — the small
final wrapper class whose only behavioural addition over its
:class:`COSDictionary` parent is rejecting every mutator with an
``UnsupportedOperationException``.

The bulk of the read-only enforcement (set_item, set_name, set_boolean,
set_date, set_int, set_long, set_float, set_string, set_flag,
add_all, clear, remove_item, __setitem__, __delitem__, …) lives on the
``UnmodifiableCOSDictionary`` class in
:mod:`pypdfbox.cos.cos_dictionary` — re-exported here so callers can
import it from the mirror path ``pypdfbox.cos.unmodifiable_cos_dictionary``
that matches upstream's per-class Java file. This module additionally
exposes :meth:`UnmodifiableCOSDictionary.set_need_to_be_updated` (the
strict snake_case rendering of upstream's overridden
``setNeedToBeUpdated``, java L40-44), which is the *only* method the
upstream class declares.

Note on naming: the project's existing ``COSDictionary`` mutator is
spelled ``set_needs_to_be_updated`` (parent's preferred Python style),
while upstream Java is ``setNeedToBeUpdated``. Strict snake-case of the
Java name is ``set_need_to_be_updated`` (singular "need"), which the
parity tooling counts independently. Both forms are wired here.
"""

from __future__ import annotations

from .cos_dictionary import UnmodifiableCOSDictionary as _BaseUnmodifiableCOSDictionary


class UnmodifiableCOSDictionary(_BaseUnmodifiableCOSDictionary):
    """Read-only ``COSDictionary`` view that rejects every mutator.

    Java upstream: ``final class UnmodifiableCOSDictionary extends
    COSDictionary`` in ``org.apache.pdfbox.cos``
    (``UnmodifiableCOSDictionary.java``, Apache PDFBox 3.0). Upstream
    overrides exactly one method —
    :meth:`set_need_to_be_updated` — and inherits everything else,
    relying on the constructor's ``Collections.unmodifiableMap`` wrapper
    around the underlying items map (java L34) to enforce read-only on
    all the bulk-mutator paths via Java's standard
    ``UnsupportedOperationException`` from the wrapped map.

    Python doesn't have a frozen-dict view as cheap as Java's, so the
    parent
    :class:`pypdfbox.cos.cos_dictionary.UnmodifiableCOSDictionary`
    already enumerates every individual mutator and raises
    ``TypeError("COSDictionary is unmodifiable")`` from each — that
    behaviour is preserved here unchanged.
    """

    def set_need_to_be_updated(self, flag: bool) -> None:
        """Reject the per-object incremental-save flag.

        Mirrors upstream
        ``public void setNeedToBeUpdated(boolean flag)``
        (``UnmodifiableCOSDictionary.java`` L40-44), which unconditionally
        throws ``new UnsupportedOperationException()`` — Python's closest
        analogue for an "operation not supported on this subclass"
        contract is :class:`RuntimeError`, matching the project's
        Java → Python exception mapping for ``UnsupportedOperationException``.

        Note this is the strict snake-case rendering of
        ``setNeedToBeUpdated`` (``set_need_to_be_updated``, singular
        "need"); the parent ``COSDictionary`` exposes the plural form
        ``set_needs_to_be_updated`` for its own writer-side bookkeeping,
        and the parent ``UnmodifiableCOSDictionary`` already rejects
        that spelling too — both routes raise on this read-only view.
        """
        raise RuntimeError(
            "UnmodifiableCOSDictionary: setNeedToBeUpdated is not supported"
        )


__all__ = ["UnmodifiableCOSDictionary"]
