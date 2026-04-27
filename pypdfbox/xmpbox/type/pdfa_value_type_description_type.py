"""
Convenience alias module for the PDF/A Extension schema's value-type
description structure.

Upstream Apache PDFBox (3.0) names this class :class:`PDFATypeType` and
locates it at ``org.apache.xmpbox.type.PDFATypeType``. Inside the
``pdfaSchema:valueType`` Seq it plays the role of *value type description*
— the structured record paired with each custom value type a third-party
schema contributes. This module re-exports the canonical class under the
schema-level naming for callers that prefer the descriptive form.

The real definition is in :mod:`pypdfbox.xmpbox.type.pdfa_type_type`. No
new class is introduced here so structural identity (``isinstance`` checks
against :class:`PDFATypeType`) keeps working unchanged.
"""

from __future__ import annotations

from .pdfa_type_type import PDFATypeType

# Alias preserves the upstream class name; both spellings resolve to the
# same object so existing isinstance / equality semantics are preserved.
PDFAValueTypeDescriptionType = PDFATypeType

__all__ = ["PDFATypeType", "PDFAValueTypeDescriptionType"]
