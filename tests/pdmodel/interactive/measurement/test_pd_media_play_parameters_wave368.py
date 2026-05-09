from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSString
from pypdfbox.pdmodel.interactive.measurement import PDMediaPlayParameters

_MH = COSName.get_pdf_name("MH")
_BE = COSName.get_pdf_name("BE")


def test_wave368_play_parameters_wraps_provided_dictionary_by_identity() -> None:
    raw = COSDictionary()
    mh = COSDictionary()
    raw.set_item(_MH, mh)

    params = PDMediaPlayParameters(raw)

    assert params.get_cos_object() is raw
    assert params.get_mh() is mh


def test_wave368_play_parameters_filters_non_dictionary_mh_and_be() -> None:
    params = PDMediaPlayParameters()
    params.get_cos_object().set_item(_MH, COSString("must-honor"))
    params.get_cos_object().set_item(_BE, COSString("best-effort"))

    assert params.get_mh() is None
    assert params.get_be() is None


def test_wave368_play_parameters_setters_store_and_remove_raw_dicts() -> None:
    params = PDMediaPlayParameters()
    mh = COSDictionary()
    be = COSDictionary()

    params.set_mh(mh)
    params.set_be(be)

    assert params.get_cos_object().get_dictionary_object(_MH) is mh
    assert params.get_cos_object().get_dictionary_object(_BE) is be

    params.set_mh(None)
    params.set_be(None)

    assert not params.get_cos_object().contains_key(_MH)
    assert not params.get_cos_object().contains_key(_BE)
    assert params.get_mh() is None
    assert params.get_be() is None


def test_wave368_play_parameters_get_or_create_replaces_non_dictionary_entries() -> None:
    params = PDMediaPlayParameters()
    params.get_cos_object().set_item(_MH, COSString("bad-mh"))
    params.get_cos_object().set_item(_BE, COSString("bad-be"))

    mh = params.get_or_create_mh()
    be = params.get_or_create_be()

    assert isinstance(mh, COSDictionary)
    assert isinstance(be, COSDictionary)
    assert params.get_cos_object().get_dictionary_object(_MH) is mh
    assert params.get_cos_object().get_dictionary_object(_BE) is be


def test_wave368_play_parameters_get_or_create_reuses_indirect_dictionaries() -> None:
    params = PDMediaPlayParameters()
    mh = COSDictionary()
    be = COSDictionary()
    mh_ref = COSObject(368, 0, resolved=mh)
    be_ref = COSObject(368, 1, resolved=be)
    params.get_cos_object().set_item(_MH, mh_ref)
    params.get_cos_object().set_item(_BE, be_ref)

    assert params.get_mh() is mh
    assert params.get_be() is be
    assert params.get_or_create_mh() is mh
    assert params.get_or_create_be() is be
    assert params.get_cos_object().get_item(_MH) is mh_ref
    assert params.get_cos_object().get_item(_BE) is be_ref


def test_wave368_play_parameters_repr_reports_both_states() -> None:
    params = PDMediaPlayParameters()

    assert repr(params) == "PDMediaPlayParameters(MH=unset, BE=unset)"

    params.set_mh(COSDictionary())
    params.set_be(COSDictionary())

    assert repr(params) == "PDMediaPlayParameters(MH=set, BE=set)"
