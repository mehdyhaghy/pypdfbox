from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSeedValue,
    PDSeedValueTimeStamp,
)

_FF: COSName = COSName.get_pdf_name("Ff")
_URL: COSName = COSName.get_pdf_name("URL")


# ---------- construction ----------


def test_default_constructor_creates_empty_direct_dict() -> None:
    ts = PDSeedValueTimeStamp()
    cos = ts.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert _URL not in cos
    assert _FF not in cos
    assert ts.get_url() is None
    assert ts.is_url_required() is False


def test_constructor_accepts_existing_dict() -> None:
    cos = COSDictionary()
    cos.set_string("URL", "https://tsa.example.org/")
    cos.set_int("Ff", 1)
    ts = PDSeedValueTimeStamp(cos)
    assert ts.get_cos_object() is cos
    assert ts.get_url() == "https://tsa.example.org/"
    assert ts.is_url_required() is True


# ---------- /URL round-trip ----------


def test_set_url_round_trip() -> None:
    ts = PDSeedValueTimeStamp()
    ts.set_url("https://tsa.example.org/sign")
    assert ts.get_url() == "https://tsa.example.org/sign"


def test_set_url_none_clears() -> None:
    ts = PDSeedValueTimeStamp()
    ts.set_url("https://tsa.example.org/sign")
    ts.set_url(None)
    assert ts.get_url() is None
    assert _URL not in ts.get_cos_object()


# ---------- /Ff URL-required flag ----------


def test_url_required_flag_round_trip() -> None:
    ts = PDSeedValueTimeStamp()
    assert ts.is_url_required() is False
    ts.set_url_required(True)
    assert ts.is_url_required() is True
    assert (ts.get_cos_object().get_int(_FF) & 1) == 1
    ts.set_url_required(False)
    assert ts.is_url_required() is False
    assert ts.get_cos_object().get_int(_FF) == 0


def test_setting_false_when_unset_keeps_flag_unset() -> None:
    ts = PDSeedValueTimeStamp()
    ts.set_url_required(False)
    assert ts.is_url_required() is False
    cos = ts.get_cos_object()
    # /Ff is created as 0 by the set_flag helper, mirroring upstream.
    assert cos.get_int(_FF, default=-1) == 0


# ---------- integration with PDSeedValue ----------


def test_pd_seed_value_get_time_stamp_returns_typed_wrapper() -> None:
    sv = PDSeedValue()
    assert sv.get_time_stamp() is None  # absent by default

    ts = PDSeedValueTimeStamp()
    ts.set_url("https://tsa.example.org/")
    ts.set_url_required(True)
    sv.set_time_stamp(ts)

    got = sv.get_time_stamp()
    assert isinstance(got, PDSeedValueTimeStamp)
    assert got.get_url() == "https://tsa.example.org/"
    assert got.is_url_required() is True
    # Underlying COSDictionary identity preserved.
    assert got.get_cos_object() is ts.get_cos_object()


def test_pd_seed_value_set_time_stamp_none_clears() -> None:
    sv = PDSeedValue()
    ts = PDSeedValueTimeStamp()
    ts.set_url("https://tsa.example.org/")
    sv.set_time_stamp(ts)
    assert sv.get_time_stamp() is not None
    sv.set_time_stamp(None)
    assert sv.get_time_stamp() is None


def test_pd_seed_value_set_time_stamp_accepts_raw_dict() -> None:
    sv = PDSeedValue()
    cos = COSDictionary()
    cos.set_string("URL", "https://tsa.example.org/")
    cos.set_int("Ff", 1)
    sv.set_time_stamp(cos)
    got = sv.get_time_stamp()
    assert got is not None
    assert got.get_url() == "https://tsa.example.org/"
    assert got.is_url_required() is True
    assert got.get_cos_object() is cos


def test_signature_field_seed_value_time_stamp_round_trip() -> None:
    """End-to-end: PDSignatureField -> PDSeedValue -> PDSeedValueTimeStamp."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm.__new__(PDAcroForm)
    # Bypass full PDAcroForm wiring; PDSignatureField only needs ``form``
    # bound for its parent constructor's TYPE_CHECKING reference.
    field = PDSignatureField(form)

    sv = PDSeedValue()
    ts = PDSeedValueTimeStamp()
    ts.set_url("https://tsa.example.org/sign")
    ts.set_url_required(True)
    sv.set_time_stamp(ts)
    field.set_seed_value(sv)

    got_sv = field.get_seed_value()
    assert got_sv is not None
    got_ts = got_sv.get_time_stamp()
    assert got_ts is not None
    assert got_ts.get_url() == "https://tsa.example.org/sign"
    assert got_ts.is_url_required() is True
