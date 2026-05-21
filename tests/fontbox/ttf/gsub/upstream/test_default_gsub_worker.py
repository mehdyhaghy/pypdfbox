"""Port of upstream ``DefaultGsubWorkerTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/DefaultGsubWorkerTest.java``.

Upstream asserts the result of :meth:`DefaultGsubWorker.apply_transforms`
is an unmodifiable wrapper that raises :class:`UnsupportedOperationException`
on mutation. pypdfbox returns a defensive list copy instead (the
documented divergence on
:class:`pypdfbox.fontbox.ttf.gsub.default_gsub_worker.DefaultGsubWorker`)
— "return a fresh list the caller can mutate without corrupting state".

The port therefore keeps the equality assertion verbatim and replaces
the upstream ``assertThrows(UnsupportedOperationException, ...)`` with
the pypdfbox contract: the returned list *is* mutable, but mutating it
does not affect the worker's internal state.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.default_gsub_worker import DefaultGsubWorker


def test_apply_transforms() -> None:
    """Ported from ``DefaultGsubWorkerTest#applyTransforms``.

    pypdfbox divergence: the returned list is a defensive copy
    (mutable) rather than an unmodifiable wrapper. Equality with the
    input is preserved and mutation of the returned list does not
    affect the worker.
    """
    # given
    sut = DefaultGsubWorker()
    original_glyph_ids = [1, 2, 3, 4, 5]

    # when
    pseudo_transformed_ids = sut.apply_transforms(original_glyph_ids)

    # then — equality with the input (upstream parity)
    assert pseudo_transformed_ids == original_glyph_ids

    # pypdfbox divergence: result is a defensive copy. Mutating it
    # must not corrupt the input.
    pseudo_transformed_ids.clear()
    assert original_glyph_ids == [1, 2, 3, 4, 5]
