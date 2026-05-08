from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.multipdf import PDFCloneUtility
from pypdfbox.pdmodel import PDDocument


class _Wrap:
    def __init__(self, base: COSDictionary) -> None:
        self._base = base

    def get_cos_object(self) -> COSDictionary:
        return self._base


def test_clone_merge_handles_matching_dictionary_cycles() -> None:
    """Existing keys recurse during clone_merge; matching cycles must not
    revisit the same source/target pair forever."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("Type", "Source")
        src.set_item("Self", src)
        src.set_name("OnlySource", "copied")

        target = COSDictionary()
        target.set_name("Type", "Target")
        target.set_item("Self", target)

        cloner.clone_merge(_Wrap(src), _Wrap(target))

        assert target.get_name("Type") == "Target"
        assert target.get_item("Self") is target
        assert target.get_name("OnlySource") == "copied"
