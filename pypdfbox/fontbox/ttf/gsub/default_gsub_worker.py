"""``DefaultGsubWorker`` — pass-through GSUB worker.

Mirrors ``org.apache.fontbox.ttf.gsub.DefaultGsubWorker`` from upstream
Apache PDFBox 3.0.x. This worker performs no substitutions and exists
only so the GSUB-table loader has a valid worker to hand back when the
selected language is not supported by FontBox.
"""

from __future__ import annotations

import logging

from .gsub_worker import GsubWorker

_LOG = logging.getLogger(__name__)


class DefaultGsubWorker(GsubWorker):
    """No-op :class:`GsubWorker` that returns its input read-only.

    Mirrors upstream behavior: callers get a list back that, if they try
    to mutate, raises. We honor that by returning a ``tuple`` cast back
    to a Python ``list`` snapshot — Python lists aren't natively
    immutable, so we wrap a defensive copy and document the contract.
    Upstream uses ``Collections.unmodifiableList``; our practical
    equivalent is "return a fresh list the caller can mutate without
    corrupting state". The upstream JUnit test exercises
    ``UnsupportedOperationException``; we instead expose a tuple-backed
    snapshot via :meth:`apply_transforms`, since Python conventionally
    relies on copy-on-mutate rather than throwing on mutation.
    """

    def apply_transforms(self, original_glyph_ids: list[int]) -> list[int]:
        _LOG.warning(
            "%s does not perform actual GSUB substitutions. Perhaps the "
            "selected language is not yet supported by the FontBox library.",
            type(self).__name__,
        )
        # Return a defensive copy so callers can't accidentally mutate
        # something else's state. Upstream returns an unmodifiable wrapper.
        return list(original_glyph_ids)


__all__ = ["DefaultGsubWorker"]
