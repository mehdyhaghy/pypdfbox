"""Wave 1531 — malformed-input fuzz coverage for the rich-media
rendition / media-clip / media-play cluster.

NO LIVE ORACLE EXISTS for this surface. The pinned upstream baseline is
Apache PDFBox **3.0.7**, and that release ships NO ``PDRendition`` /
``PDMediaRendition`` / ``PDSelectorRendition`` / ``PDMediaClip`` /
``PDMediaClipData`` / ``PDMediaClipSection`` / ``PDMediaPlayParameters``
classes at all — verified by ``unzip -l oracle/jars/pdfbox-app-3.0.7.jar |
grep -iE 'rendition|mediaclip|mediaplay'`` returning zero hits. The
``org.apache.pdfbox.pdmodel.interactive.action`` package in 3.0.7 contains
only the action classes (PDActionMovie, PDActionSound, ...), none of the
rendition/media-clip dictionaries. PROVENANCE.md records these pypdfbox
classes as "original Python additions, no upstream class".

Because there is no Java counterpart to project, a differential probe is
impossible. This module is therefore the hand-test fuzz layer the wave-1531
brief mandates for accessors with NO upstream counterpart: it pins the
malformed-/Rendition, media-clip, and media-play behaviour against the
PDFBox-modelled COS accessor semantics the production code is built on
(``getName``/``getNameAsString``/``getString``/``getDictionaryObject``).

Fuzz areas covered: ``/S`` subtype missing/unknown/wrong-type (create
dispatch), ``/N`` name non-string, ``/C`` clip missing/wrong-type, ``/D``
media-clip-data missing/wrong-type, content-type accessor on absent entries,
nested clip/section, and indirect references (resolved, unresolved, null,
cyclic, wrong-type-after-deref).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.pdmodel.interactive.measurement import (
    PDMediaClip,
    PDMediaClipData,
    PDMediaClipSection,
    PDMediaPlayParameters,
    PDMediaRendition,
    PDRendition,
    PDSelectorRendition,
)

_TYPE = COSName.get_pdf_name("Type")
_S = COSName.get_pdf_name("S")
_N = COSName.get_pdf_name("N")
_C = COSName.get_pdf_name("C")
_D = COSName.get_pdf_name("D")
_R = COSName.get_pdf_name("R")
_CT = COSName.get_pdf_name("CT")


def _dict(**items: object) -> COSDictionary:
    d = COSDictionary()
    for key, value in items.items():
        d.set_item(COSName.get_pdf_name(key), value)  # type: ignore[arg-type]
    return d


# --------------------------------------------------------------------------
# PDRendition.create — /S dispatch
# --------------------------------------------------------------------------


def test_create_none_returns_none() -> None:
    assert PDRendition.create(None) is None


def test_create_null_returns_none() -> None:
    assert PDRendition.create(COSNull.NULL) is None


def test_create_missing_s_returns_none() -> None:
    # No /S key -> getNameAsString -> None -> no subtype matches.
    assert PDRendition.create(COSDictionary()) is None


def test_create_unknown_s_returns_none() -> None:
    assert PDRendition.create(_dict(S=COSName.get_pdf_name("ZZ"))) is None


def test_create_s_wrong_type_integer_returns_none() -> None:
    # /S as a number is not a name nor string -> getNameAsString -> None.
    assert PDRendition.create(_dict(S=COSInteger.get(7))) is None


def test_create_s_as_cosstring_mr_dispatches() -> None:
    # getNameAsString coerces a COSString too, mirroring PDFBox.
    r = PDRendition.create(_dict(S=COSString("MR")))
    assert isinstance(r, PDMediaRendition)


def test_create_mr_dispatches_media_rendition() -> None:
    r = PDRendition.create(_dict(S=COSName.get_pdf_name("MR")))
    assert isinstance(r, PDMediaRendition)


def test_create_sr_dispatches_selector_rendition() -> None:
    r = PDRendition.create(_dict(S=COSName.get_pdf_name("SR")))
    assert isinstance(r, PDSelectorRendition)


def test_create_non_dictionary_raises_type_error() -> None:
    with pytest.raises(TypeError):
        PDRendition.create(COSString("x"))


def test_create_resolves_indirect_dictionary() -> None:
    raw = _dict(S=COSName.get_pdf_name("MR"))
    r = PDRendition.create(COSObject(1, 0, resolved=raw))
    assert isinstance(r, PDMediaRendition)
    assert r.get_cos_object() is raw


def test_create_unresolved_indirect_returns_none() -> None:
    assert PDRendition.create(COSObject(2, 0)) is None


def test_create_indirect_null_returns_none() -> None:
    assert PDRendition.create(COSObject(3, 0, resolved=COSNull.NULL)) is None


def test_create_indirect_to_non_dictionary_raises() -> None:
    with pytest.raises(TypeError):
        PDRendition.create(COSObject(4, 0, resolved=COSString("nope")))


def test_create_self_referential_indirect_returns_none() -> None:
    ref = COSObject(5, 0)
    ref.set_object(ref)
    assert PDRendition.create(ref) is None


# --------------------------------------------------------------------------
# PDRendition base accessors on a malformed dictionary
# --------------------------------------------------------------------------


def test_get_n_non_string_returns_none() -> None:
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), N=COSName.get_pdf_name("x")))
    # /N as a name is not a COSString -> getString -> None.
    assert r.get_n() is None


def test_get_n_string_returns_value() -> None:
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), N=COSString("clip")))
    assert r.get_n() == "clip"


def test_get_n_absent_returns_none() -> None:
    assert PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"))).get_n() is None


def test_get_mh_wrong_type_returns_none() -> None:
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), MH=COSString("x")))
    assert r.get_mh() is None


def test_get_be_wrong_type_returns_none() -> None:
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), BE=COSInteger.get(1)))
    assert r.get_be() is None


def test_get_subtype_reflects_s() -> None:
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR")))
    assert r.get_subtype() == "MR"


def test_constructor_stamps_type_when_absent() -> None:
    r = PDRendition(COSDictionary())
    assert r.get_cos_object().get_name(_TYPE) == "Rendition"


def test_constructor_preserves_existing_type() -> None:
    d = _dict(Type=COSName.get_pdf_name("Other"))
    r = PDRendition(d)
    assert r.get_cos_object().get_name(_TYPE) == "Other"


# --------------------------------------------------------------------------
# PDMediaRendition — /C clip and /P play parameters
# --------------------------------------------------------------------------


def test_media_rendition_c_missing_returns_none() -> None:
    assert PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"))).get_c() is None


def test_media_rendition_c_wrong_type_returns_none() -> None:
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), C=COSString("x")))
    assert r.get_c() is None


def test_media_rendition_c_clip_without_s_returns_none() -> None:
    # /C present but the clip has no /S -> PDMediaClip.create -> None.
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), C=COSDictionary()))
    assert r.get_c() is None


def test_media_rendition_c_valid_mcd() -> None:
    clip = _dict(S=COSName.get_pdf_name("MCD"))
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), C=clip))
    assert isinstance(r.get_c(), PDMediaClipData)


def test_media_rendition_c_indirect_resolved() -> None:
    clip = _dict(S=COSName.get_pdf_name("MCD"))
    r = PDMediaRendition(
        _dict(S=COSName.get_pdf_name("MR"), C=COSObject(10, 0, resolved=clip))
    )
    assert isinstance(r.get_c(), PDMediaClipData)


def test_media_rendition_p_missing_returns_none() -> None:
    assert PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"))).get_p() is None


def test_media_rendition_p_wrong_type_returns_none() -> None:
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), P=COSInteger.get(3)))
    assert r.get_p() is None


def test_media_rendition_p_valid() -> None:
    r = PDMediaRendition(_dict(S=COSName.get_pdf_name("MR"), P=COSDictionary()))
    assert isinstance(r.get_p(), PDMediaPlayParameters)


# --------------------------------------------------------------------------
# PDMediaClip.create — /S dispatch
# --------------------------------------------------------------------------


def test_clip_create_none_returns_none() -> None:
    assert PDMediaClip.create(None) is None


def test_clip_create_missing_s_returns_none() -> None:
    assert PDMediaClip.create(COSDictionary()) is None


def test_clip_create_unknown_s_returns_none() -> None:
    assert PDMediaClip.create(_dict(S=COSName.get_pdf_name("XX"))) is None


def test_clip_create_s_wrong_type_returns_none() -> None:
    assert PDMediaClip.create(_dict(S=COSArray())) is None


def test_clip_create_mcd_dispatches() -> None:
    assert isinstance(
        PDMediaClip.create(_dict(S=COSName.get_pdf_name("MCD"))), PDMediaClipData
    )


def test_clip_create_mcs_dispatches() -> None:
    assert isinstance(
        PDMediaClip.create(_dict(S=COSName.get_pdf_name("MCS"))), PDMediaClipSection
    )


def test_clip_create_non_dictionary_raises() -> None:
    with pytest.raises(TypeError):
        PDMediaClip.create(COSInteger.get(0))


def test_clip_create_indirect_null_returns_none() -> None:
    assert PDMediaClip.create(COSObject(20, 0, resolved=COSNull.NULL)) is None


def test_clip_create_cyclic_indirect_returns_none() -> None:
    ref = COSObject(21, 0)
    ref.set_object(ref)
    assert PDMediaClip.create(ref) is None


# --------------------------------------------------------------------------
# PDMediaClipData — /CT content type and /D data
# --------------------------------------------------------------------------


def test_clip_data_ct_absent_returns_none() -> None:
    assert PDMediaClipData(_dict(S=COSName.get_pdf_name("MCD"))).get_ct() is None


def test_clip_data_ct_non_string_returns_none() -> None:
    c = PDMediaClipData(_dict(S=COSName.get_pdf_name("MCD"), CT=COSName.get_pdf_name("v")))
    assert c.get_ct() is None


def test_clip_data_ct_string_returns_value() -> None:
    c = PDMediaClipData(_dict(S=COSName.get_pdf_name("MCD"), CT=COSString("video/mp4")))
    assert c.get_ct() == "video/mp4"


def test_clip_data_d_absent_returns_none() -> None:
    assert PDMediaClipData(_dict(S=COSName.get_pdf_name("MCD"))).get_d() is None


def test_clip_data_d_returns_resolved_object() -> None:
    spec = COSDictionary()
    c = PDMediaClipData(_dict(S=COSName.get_pdf_name("MCD"), D=spec))
    assert c.get_d() is spec


def test_clip_data_d_indirect_resolved() -> None:
    spec = COSDictionary()
    c = PDMediaClipData(
        _dict(S=COSName.get_pdf_name("MCD"), D=COSObject(30, 0, resolved=spec))
    )
    assert c.get_d() is spec


# --------------------------------------------------------------------------
# PDMediaClipSection — /D nested clip
# --------------------------------------------------------------------------


def test_clip_section_d_absent_returns_none() -> None:
    assert PDMediaClipSection(_dict(S=COSName.get_pdf_name("MCS"))).get_d() is None


def test_clip_section_d_wrong_type_returns_none() -> None:
    c = PDMediaClipSection(_dict(S=COSName.get_pdf_name("MCS"), D=COSString("x")))
    assert c.get_d() is None


def test_clip_section_d_clip_without_s_returns_none() -> None:
    c = PDMediaClipSection(_dict(S=COSName.get_pdf_name("MCS"), D=COSDictionary()))
    assert c.get_d() is None


def test_clip_section_d_nested_mcd() -> None:
    nested = _dict(S=COSName.get_pdf_name("MCD"))
    c = PDMediaClipSection(_dict(S=COSName.get_pdf_name("MCS"), D=nested))
    assert isinstance(c.get_d(), PDMediaClipData)


def test_clip_section_d_nested_section() -> None:
    nested = _dict(S=COSName.get_pdf_name("MCS"))
    c = PDMediaClipSection(_dict(S=COSName.get_pdf_name("MCS"), D=nested))
    assert isinstance(c.get_d(), PDMediaClipSection)


# --------------------------------------------------------------------------
# PDSelectorRendition — /R sub-rendition array
# --------------------------------------------------------------------------


def test_selector_r_absent_returns_empty() -> None:
    assert PDSelectorRendition(_dict(S=COSName.get_pdf_name("SR"))).get_r() == []


def test_selector_r_wrong_type_returns_empty() -> None:
    sel = PDSelectorRendition(_dict(S=COSName.get_pdf_name("SR"), R=COSString("x")))
    assert sel.get_r() == []


def test_selector_r_skips_non_dictionary_entries() -> None:
    arr = COSArray()
    arr.add(COSString("junk"))
    arr.add(COSInteger.get(5))
    sel = PDSelectorRendition(_dict(S=COSName.get_pdf_name("SR"), R=arr))
    assert sel.get_r() == []


def test_selector_r_skips_dicts_without_valid_s() -> None:
    arr = COSArray()
    arr.add(COSDictionary())  # no /S
    arr.add(_dict(S=COSName.get_pdf_name("MR")))  # valid
    sel = PDSelectorRendition(_dict(S=COSName.get_pdf_name("SR"), R=arr))
    out = sel.get_r()
    assert len(out) == 1
    assert isinstance(out[0], PDMediaRendition)


def test_selector_r_nested_selector() -> None:
    arr = COSArray()
    arr.add(_dict(S=COSName.get_pdf_name("SR")))
    sel = PDSelectorRendition(_dict(S=COSName.get_pdf_name("SR"), R=arr))
    out = sel.get_r()
    assert len(out) == 1
    assert isinstance(out[0], PDSelectorRendition)


# --------------------------------------------------------------------------
# PDMediaPlayParameters — MH / BE sub-dicts on a malformed dictionary
# --------------------------------------------------------------------------


def test_play_params_mh_absent_returns_none() -> None:
    assert PDMediaPlayParameters(COSDictionary()).get_mh() is None


def test_play_params_mh_wrong_type_returns_none() -> None:
    p = PDMediaPlayParameters(_dict(MH=COSString("x")))
    assert p.get_mh() is None


def test_play_params_be_wrong_type_returns_none() -> None:
    p = PDMediaPlayParameters(_dict(BE=COSInteger.get(2)))
    assert p.get_be() is None


def test_play_params_get_or_create_replaces_nothing_when_present() -> None:
    existing = COSDictionary()
    p = PDMediaPlayParameters(_dict(MH=existing))
    assert p.get_or_create_mh() is existing


def test_play_params_get_or_create_mints_when_wrong_type() -> None:
    p = PDMediaPlayParameters(_dict(MH=COSString("x")))
    fresh = p.get_or_create_mh()
    assert isinstance(fresh, COSDictionary)
    assert p.get_mh() is fresh
