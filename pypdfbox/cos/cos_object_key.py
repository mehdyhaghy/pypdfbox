from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class COSObjectKey:
    """
    Value type identifying an indirect PDF object by its
    ``(object_number, generation_number)`` pair.

    Used as the key in ``COSDocument``'s object pool / xref table.
    Frozen so it can be a dict key; ordered so callers can sort
    objects by number for serialization.
    """

    object_number: int
    generation_number: int = 0

    def __post_init__(self) -> None:
        if self.object_number < 0:
            raise ValueError("object_number must be non-negative")
        if self.generation_number < 0:
            raise ValueError("generation_number must be non-negative")

    def __str__(self) -> str:
        return f"{self.object_number} {self.generation_number} R"
