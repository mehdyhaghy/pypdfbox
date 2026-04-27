"""Upstream-equivalent location for :class:`PDArtifactMarkedContent`.

Apache PDFBox 3.0.x places ``PDArtifactMarkedContent`` under
``org.apache.pdfbox.pdmodel.documentinterchange.markedcontent``. The pypdfbox
implementation historically grew up under
:mod:`pypdfbox.pdmodel.documentinterchange.taggedpdf`; this module re-exports
the same class at the upstream-equivalent import path so PDFBox developers
can find it where they expect.

The canonical class lives in
:mod:`pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_artifact_marked_content`
and ``isinstance`` checks resolve to the same identity regardless of the
import path used.
"""

from __future__ import annotations

from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_artifact_marked_content import (
    PDArtifactMarkedContent,
)

__all__ = ["PDArtifactMarkedContent"]
