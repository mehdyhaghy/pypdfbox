from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDPropBuild,
    PDPropBuildDataDict,
    PDSignature,
)


# ---------------------------------------------------------------------------
# PDPropBuildDataDict
# ---------------------------------------------------------------------------


def test_data_dict_default_constructor_creates_direct_cos_dict() -> None:
    d = PDPropBuildDataDict()
    cos = d.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.is_direct() is True
    assert cos.is_empty() is True


def test_data_dict_constructor_marks_existing_dict_direct() -> None:
    raw = COSDictionary()
    assert raw.is_direct() is False
    d = PDPropBuildDataDict(raw)
    assert d.get_cos_object() is raw
    assert raw.is_direct() is True


def test_data_dict_name_round_trip() -> None:
    d = PDPropBuildDataDict()
    assert d.get_name() is None
    d.set_name("Acrobat")
    assert d.get_name() == "Acrobat"
    # /Name is stored as a COSName
    assert isinstance(d.get_cos_object().get_item("Name"), COSName)
    d.set_name(None)
    assert d.get_name() is None


def test_data_dict_date_round_trip() -> None:
    d = PDPropBuildDataDict()
    assert d.get_date() is None
    d.set_date("Mar 12 2014 12:34:56")
    assert d.get_date() == "Mar 12 2014 12:34:56"
    d.set_date(None)
    assert d.get_date() is None


def test_data_dict_version_uses_REx_key() -> None:
    d = PDPropBuildDataDict()
    assert d.get_version() is None
    d.set_version("7.0.7")
    assert d.get_version() == "7.0.7"
    # stored under /REx, not /Version
    assert d.get_cos_object().contains_key("REx")
    assert not d.get_cos_object().contains_key("Version")
    d.set_version(None)
    assert d.get_version() is None


def test_data_dict_revision_round_trip() -> None:
    d = PDPropBuildDataDict()
    # default when missing matches PDFBox getLong default (-1)
    assert d.get_revision() == -1
    d.set_revision(2042)
    assert d.get_revision() == 2042


def test_data_dict_minimum_revision_round_trip() -> None:
    d = PDPropBuildDataDict()
    assert d.get_minimum_revision() == -1
    d.set_minimum_revision(7)
    assert d.get_minimum_revision() == 7


def test_data_dict_pre_release_default_false() -> None:
    d = PDPropBuildDataDict()
    assert d.get_pre_release() is False
    d.set_pre_release(True)
    assert d.get_pre_release() is True
    d.set_pre_release(False)
    assert d.get_pre_release() is False


def test_data_dict_os_set_creates_direct_cos_array_of_names() -> None:
    d = PDPropBuildDataDict()
    assert d.get_os() is None
    d.set_os("Linux")
    arr = d.get_cos_object().get_dictionary_object("OS")
    assert isinstance(arr, COSArray)
    assert arr.is_direct() is True
    assert arr.get_name(0) == "Linux"
    assert d.get_os() == "Linux"


def test_data_dict_os_string_form_supported_on_read() -> None:
    """PDF v1.5 stored OS as a plain string. Both encodings must read."""
    raw = COSDictionary()
    raw.set_string("OS", "MacOS")
    d = PDPropBuildDataDict(raw)
    assert d.get_os() == "MacOS"


def test_data_dict_os_set_none_removes_entry() -> None:
    d = PDPropBuildDataDict()
    d.set_os("Linux")
    d.set_os(None)
    assert not d.get_cos_object().contains_key("OS")
    assert d.get_os() is None


def test_data_dict_non_e_font_no_warn_default_true() -> None:
    """Upstream getNonEFontNoWarn default is true (mirror exactly)."""
    d = PDPropBuildDataDict()
    assert d.get_non_e_font_no_warn() is True
    d.set_non_e_font_no_warn(False)
    assert d.get_non_e_font_no_warn() is False


def test_data_dict_trusted_mode_default_false() -> None:
    d = PDPropBuildDataDict()
    assert d.get_trusted_mode() is False
    d.set_trusted_mode(True)
    assert d.get_trusted_mode() is True


# ---------------------------------------------------------------------------
# PDPropBuild
# ---------------------------------------------------------------------------


def test_prop_build_default_constructor_marks_dict_direct() -> None:
    pb = PDPropBuild()
    cos = pb.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.is_direct() is True
    assert cos.is_empty() is True


def test_prop_build_constructor_marks_existing_dict_direct() -> None:
    raw = COSDictionary()
    pb = PDPropBuild(raw)
    assert pb.get_cos_object() is raw
    assert raw.is_direct() is True


def test_prop_build_filter_round_trip() -> None:
    pb = PDPropBuild()
    assert pb.get_filter() is None
    inner = PDPropBuildDataDict()
    inner.set_name("Adobe.PPKLite")
    inner.set_revision(123)
    pb.set_pd_prop_build_filter(inner)

    got = pb.get_filter()
    assert got is not None
    assert got.get_name() == "Adobe.PPKLite"
    assert got.get_revision() == 123
    # /Filter sub-dict is the same COS object we set.
    assert got.get_cos_object() is inner.get_cos_object()


def test_prop_build_pub_sec_round_trip() -> None:
    pb = PDPropBuild()
    assert pb.get_pub_sec() is None
    inner = PDPropBuildDataDict()
    inner.set_name("Adobe.PubSec")
    inner.set_version("11.0.6")
    pb.set_pd_prop_build_pub_sec(inner)

    got = pb.get_pub_sec()
    assert got is not None
    assert got.get_name() == "Adobe.PubSec"
    assert got.get_version() == "11.0.6"


def test_prop_build_app_round_trip() -> None:
    pb = PDPropBuild()
    assert pb.get_app() is None
    inner = PDPropBuildDataDict()
    inner.set_name("Acrobat")
    inner.set_version("11.0.6")
    inner.set_os("Linux")
    inner.set_trusted_mode(True)
    pb.set_pd_prop_build_app(inner)

    got = pb.get_app()
    assert got is not None
    assert got.get_name() == "Acrobat"
    assert got.get_version() == "11.0.6"
    assert got.get_os() == "Linux"
    assert got.get_trusted_mode() is True


def test_prop_build_set_none_removes_entry() -> None:
    pb = PDPropBuild()
    inner = PDPropBuildDataDict()
    inner.set_name("Acrobat")
    pb.set_pd_prop_build_app(inner)
    assert pb.get_cos_object().contains_key("App")
    pb.set_pd_prop_build_app(None)
    assert not pb.get_cos_object().contains_key("App")
    assert pb.get_app() is None


def test_prop_build_get_filter_returns_none_when_entry_absent() -> None:
    pb = PDPropBuild()
    assert pb.get_filter() is None
    assert pb.get_pub_sec() is None
    assert pb.get_app() is None


# ---------------------------------------------------------------------------
# PDSignature integration
# ---------------------------------------------------------------------------


def test_pd_signature_get_prop_build_default_none() -> None:
    sig = PDSignature()
    assert sig.get_prop_build() is None


def test_pd_signature_set_prop_build_round_trip() -> None:
    sig = PDSignature()

    inner_app = PDPropBuildDataDict()
    inner_app.set_name("Acrobat")
    inner_app.set_version("11.0.6")
    inner_app.set_os("Linux")

    pb = PDPropBuild()
    pb.set_pd_prop_build_app(inner_app)
    sig.set_prop_build(pb)

    got = sig.get_prop_build()
    assert got is not None
    assert got.get_app() is not None
    assert got.get_app().get_name() == "Acrobat"
    assert got.get_app().get_version() == "11.0.6"
    assert got.get_app().get_os() == "Linux"

    # /Prop_Build sub-dictionary must be present under that exact key.
    assert sig.get_cos_object().contains_key("Prop_Build")


def test_pd_signature_set_prop_build_none_removes_entry() -> None:
    sig = PDSignature()
    pb = PDPropBuild()
    sig.set_prop_build(pb)
    assert sig.get_cos_object().contains_key("Prop_Build")
    sig.set_prop_build(None)
    assert not sig.get_cos_object().contains_key("Prop_Build")
    assert sig.get_prop_build() is None
