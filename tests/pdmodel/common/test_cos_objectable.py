from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common import COSObjectable
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class _Wrapper:
    def __init__(self) -> None:
        self._dict = COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def test_protocol_matches_wrapper_via_isinstance() -> None:
    assert isinstance(_Wrapper(), COSObjectable)


def test_protocol_rejects_unrelated() -> None:
    class _NoMethod:
        pass

    assert not isinstance(_NoMethod(), COSObjectable)


def test_protocol_matches_real_pd_classes() -> None:
    rect = PDRectangle()
    # PDRectangle exposes to_cos_array; isinstance with structural protocol
    # checks duck-typed match on the get_cos_object method name. Concrete
    # wrappers like PDDictionaryWrapper subclasses should match.
    from pypdfbox.pdmodel.common import PDDictionaryWrapper

    pdw = PDDictionaryWrapper()
    assert isinstance(pdw, COSObjectable)
    # COSName is its own COSBase root so the protocol should recognise PD
    # wrappers regardless of their backing COS type.
    _ = COSName.get_pdf_name("X")
    _ = rect
