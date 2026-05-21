"""Port of upstream ``CFFCharsetTest`` from
``fontbox/src/test/java/org/apache/fontbox/cff/CFFCharsetTest.java``.

Exercises the four concrete :class:`CFFCharset` flavours:

- :class:`EmbeddedCharset` (the dispatching wrapper used during
  parse-time embedding — switches between CID and Type1 behaviour
  based on the ``is_cid_font`` flag passed to the constructor)
- :class:`CFFCharsetCID` (CID-keyed concrete charset)
- :class:`CFFCharsetType1` (name-keyed concrete charset)
- :class:`CFFExpertCharset` / :class:`CFFExpertSubsetCharset` /
  :class:`CFFISOAdobeCharset` (singleton built-in charsets accessed
  via ``get_instance()``)

Upstream tests assert ``IllegalStateException`` on type-mismatched
operations; pypdfbox raises plain ``RuntimeError`` (the canonical
analogue documented across the cff module), so the ``pytest.raises``
calls below use that.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_charset_cid import CFFCharsetCID
from pypdfbox.fontbox.cff.cff_charset_type1 import CFFCharsetType1
from pypdfbox.fontbox.cff.cff_expert_charset import CFFExpertCharset
from pypdfbox.fontbox.cff.cff_expert_subset_charset import CFFExpertSubsetCharset
from pypdfbox.fontbox.cff.cff_iso_adobe_charset import CFFISOAdobeCharset
from pypdfbox.fontbox.cff.embedded_charset import EmbeddedCharset


def test_embedded_charset() -> None:
    # true -> CFFCharsetCID
    embedded_charset_cid = EmbeddedCharset(True)
    assert embedded_charset_cid.is_cid_font()
    embedded_charset_cid.add_cid(10, 20)
    # test existing mapping
    assert embedded_charset_cid.get_gid_for_cid(20) == 10
    assert embedded_charset_cid.get_cid_for_gid(10) == 20
    # test not existing mapping
    assert embedded_charset_cid.get_gid_for_cid(99) == 0
    assert embedded_charset_cid.get_cid_for_gid(99) == 0
    # test not allowed method calls
    with pytest.raises(RuntimeError):
        embedded_charset_cid.get_sid_for_gid(0)
    with pytest.raises(RuntimeError):
        embedded_charset_cid.get_gid_for_sid(0)
    with pytest.raises(RuntimeError):
        embedded_charset_cid.add_sid(0, 0, "test")
    with pytest.raises(RuntimeError):
        embedded_charset_cid.get_sid("test")
    with pytest.raises(RuntimeError):
        embedded_charset_cid.get_name_for_gid(0)
    # false -> CFFCharsetType1
    embedded_charset_type1 = EmbeddedCharset(False)
    assert not embedded_charset_type1.is_cid_font()
    embedded_charset_type1.add_sid(10, 20, "test")
    # test existing mapping
    assert embedded_charset_type1.get_sid("test") == 20
    assert embedded_charset_type1.get_gid_for_sid(20) == 10
    assert embedded_charset_type1.get_sid_for_gid(10) == 20
    # test not existing mapping
    assert embedded_charset_type1.get_gid_for_sid(99) == 0
    assert embedded_charset_type1.get_sid_for_gid(99) == 0
    # test not allowed method calls
    with pytest.raises(RuntimeError):
        embedded_charset_type1.get_cid_for_gid(0)
    with pytest.raises(RuntimeError):
        embedded_charset_type1.get_gid_for_cid(0)
    with pytest.raises(RuntimeError):
        embedded_charset_type1.add_cid(0, 0)


def test_cff_charset_cid() -> None:
    cff_charset_cid = CFFCharsetCID()
    assert cff_charset_cid.is_cid_font()
    cff_charset_cid.add_cid(10, 20)
    # test existing mapping
    assert cff_charset_cid.get_gid_for_cid(20) == 10
    assert cff_charset_cid.get_cid_for_gid(10) == 20
    # test not existing mapping
    assert cff_charset_cid.get_gid_for_cid(99) == 0
    assert cff_charset_cid.get_cid_for_gid(99) == 0
    # test not allowed method calls
    with pytest.raises(RuntimeError):
        cff_charset_cid.get_sid_for_gid(0)
    with pytest.raises(RuntimeError):
        cff_charset_cid.get_gid_for_sid(0)
    with pytest.raises(RuntimeError):
        cff_charset_cid.add_sid(0, 0, "test")
    with pytest.raises(RuntimeError):
        cff_charset_cid.get_sid("test")
    with pytest.raises(RuntimeError):
        cff_charset_cid.get_name_for_gid(0)


def test_cff_charset_type1() -> None:
    cff_charset_type1 = CFFCharsetType1()
    assert not cff_charset_type1.is_cid_font()
    cff_charset_type1.add_sid(10, 20, "test")
    # test existing mapping
    assert cff_charset_type1.get_sid("test") == 20
    assert cff_charset_type1.get_gid_for_sid(20) == 10
    assert cff_charset_type1.get_sid_for_gid(10) == 20
    # test not existing mapping
    assert cff_charset_type1.get_gid_for_sid(99) == 0
    assert cff_charset_type1.get_sid_for_gid(99) == 0
    # test not allowed method calls
    with pytest.raises(RuntimeError):
        cff_charset_type1.get_cid_for_gid(0)
    with pytest.raises(RuntimeError):
        cff_charset_type1.get_gid_for_cid(0)
    with pytest.raises(RuntimeError):
        cff_charset_type1.add_cid(0, 0)


def test_cff_expert_charset() -> None:
    cff_expert_charset = CFFExpertCharset.get_instance()
    # check .notdef mapping
    assert cff_expert_charset.get_sid_for_gid(0) == 0
    assert cff_expert_charset.get_sid(".notdef") == 0
    assert cff_expert_charset.get_name_for_gid(0) == ".notdef"
    # check some randomly chosen mappings
    assert cff_expert_charset.get_sid_for_gid(32) == 253
    assert cff_expert_charset.get_sid("asuperior") == 253
    assert cff_expert_charset.get_name_for_gid(32) == "asuperior"

    assert cff_expert_charset.get_sid_for_gid(17) == 240
    assert cff_expert_charset.get_sid("oneoldstyle") == 240
    assert cff_expert_charset.get_name_for_gid(17) == "oneoldstyle"

    assert cff_expert_charset.get_sid_for_gid(134) == 347
    assert cff_expert_charset.get_sid("Agravesmall") == 347
    assert cff_expert_charset.get_name_for_gid(134) == "Agravesmall"


def test_cff_expert_subset_charset() -> None:
    cff_expert_subset_charset = CFFExpertSubsetCharset.get_instance()
    # check .notdef mapping
    assert cff_expert_subset_charset.get_sid_for_gid(0) == 0
    assert cff_expert_subset_charset.get_sid(".notdef") == 0
    assert cff_expert_subset_charset.get_name_for_gid(0) == ".notdef"
    # check some randomly chosen mappings
    assert cff_expert_subset_charset.get_sid_for_gid(19) == 246
    assert cff_expert_subset_charset.get_sid("sevenoldstyle") == 246
    assert cff_expert_subset_charset.get_name_for_gid(19) == "sevenoldstyle"

    assert cff_expert_subset_charset.get_sid_for_gid(61) == 324
    assert cff_expert_subset_charset.get_sid("onethird") == 324
    assert cff_expert_subset_charset.get_name_for_gid(61) == "onethird"

    assert cff_expert_subset_charset.get_sid_for_gid(85) == 345
    assert cff_expert_subset_charset.get_sid("periodinferior") == 345
    assert cff_expert_subset_charset.get_name_for_gid(85) == "periodinferior"


def test_cff_iso_adobe_charset() -> None:
    cff_iso_adobe_charset = CFFISOAdobeCharset.get_instance()
    # check .notdef mapping
    assert cff_iso_adobe_charset.get_sid_for_gid(0) == 0
    assert cff_iso_adobe_charset.get_sid(".notdef") == 0
    assert cff_iso_adobe_charset.get_name_for_gid(0) == ".notdef"

    # check some randomly chosen mappings
    assert cff_iso_adobe_charset.get_sid_for_gid(32) == 32
    assert cff_iso_adobe_charset.get_sid("question") == 32
    assert cff_iso_adobe_charset.get_name_for_gid(32) == "question"

    assert cff_iso_adobe_charset.get_sid_for_gid(76) == 76
    assert cff_iso_adobe_charset.get_sid("k") == 76
    assert cff_iso_adobe_charset.get_name_for_gid(76) == "k"

    assert cff_iso_adobe_charset.get_sid_for_gid(218) == 218
    assert cff_iso_adobe_charset.get_sid("odieresis") == 218
    assert cff_iso_adobe_charset.get_name_for_gid(218) == "odieresis"
