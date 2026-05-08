from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSNull, COSObject, COSString


class PDFileSpecification:
    """Abstract base for PDF file specifications. Mirrors PDFBox
    ``PDFileSpecification``."""

    @staticmethod
    def create_fs(base: COSBase | None) -> PDFileSpecification | None:
        """Dispatch on the COS form: ``COSString`` → simple, ``COSDictionary``
        → complex. Returns ``None`` when ``base`` is ``None``. Raises
        ``OSError`` on an unrecognised type (mirrors upstream ``IOException``).

        If ``base`` is a ``COSObject`` (indirect reference), it is dereferenced
        first so callers don't have to. Upstream Java relies on the parser
        having already resolved indirect references before classification;
        in pypdfbox we resolve here so callers with raw refs work too."""
        from .pd_complex_file_specification import PDComplexFileSpecification
        from .pd_simple_file_specification import PDSimpleFileSpecification

        seen_refs: set[int] = set()
        while isinstance(base, COSObject):
            ref_id = id(base)
            if ref_id in seen_refs:
                return None
            seen_refs.add(ref_id)
            base = base.get_object()
            if base is None:
                return None
        if base is None or base is COSNull.NULL:
            return None
        if isinstance(base, COSString):
            return PDSimpleFileSpecification(base)
        if isinstance(base, COSDictionary):
            return PDComplexFileSpecification(base)
        raise OSError(f"Error: Unknown file specification {base!r}")

    def get_cos_object(self) -> COSBase:
        raise NotImplementedError

    def get_file(self) -> str | None:
        raise NotImplementedError

    def set_file(self, file: str | None) -> None:
        raise NotImplementedError


__all__ = ["PDFileSpecification"]
