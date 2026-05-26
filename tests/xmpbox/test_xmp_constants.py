"""Hand-written tests for ``pypdfbox.xmpbox.XmpConstants``.

Mirror of ``org.apache.xmpbox.XmpConstants`` — a non-instantiable holder of the
XMP wire-format constants.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XmpConstants
from pypdfbox.xmpbox import xmp_metadata as md


def test_constant_values() -> None:
    assert XmpConstants.RDF_NAMESPACE == "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    assert XmpConstants.DEFAULT_XPACKET_BEGIN == "﻿"
    assert XmpConstants.DEFAULT_XPACKET_ID == "W5M0MpCehiHzreSzNTczkc9d"
    assert XmpConstants.DEFAULT_XPACKET_ENCODING == "UTF-8"
    assert XmpConstants.DEFAULT_XPACKET_BYTES is None
    assert XmpConstants.DEFAULT_XPACKET_END == "w"
    assert XmpConstants.DEFAULT_RDF_PREFIX == "rdf"
    assert XmpConstants.DEFAULT_RDF_LOCAL_NAME == "RDF"
    assert XmpConstants.LIST_NAME == "li"
    assert XmpConstants.LANG_NAME == "lang"
    assert XmpConstants.ABOUT_NAME == "about"
    assert XmpConstants.DESCRIPTION_NAME == "Description"
    assert XmpConstants.RESOURCE_NAME == "Resource"
    assert XmpConstants.PARSE_TYPE == "parseType"
    assert XmpConstants.X_DEFAULT == "x-default"


def test_constants_match_module_level_source_of_truth() -> None:
    # The class re-exports the module constants — single source of truth.
    assert XmpConstants.RDF_NAMESPACE == md.RDF_NAMESPACE
    assert XmpConstants.DEFAULT_XPACKET_ID == md.DEFAULT_XPACKET_ID
    assert XmpConstants.X_DEFAULT == md.X_DEFAULT
    assert XmpConstants.PARSE_TYPE == md.PARSE_TYPE


def test_constructor_is_hidden() -> None:
    with pytest.raises(TypeError):
        XmpConstants()
