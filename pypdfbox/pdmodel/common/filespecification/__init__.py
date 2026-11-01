from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_complex_file_specification import PDComplexFileSpecification
    from .pd_embedded_file import PDEmbeddedFile
    from .pd_file_specification import PDFileSpecification
    from .pd_simple_file_specification import PDSimpleFileSpecification

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDComplexFileSpecification": ".pd_complex_file_specification",
        "PDEmbeddedFile": ".pd_embedded_file",
        "PDFileSpecification": ".pd_file_specification",
        "PDSimpleFileSpecification": ".pd_simple_file_specification",
    },
)

__all__ = [
    "PDComplexFileSpecification",
    "PDEmbeddedFile",
    "PDFileSpecification",
    "PDSimpleFileSpecification",
]
