"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/type/AttributeTest.java
"""

from __future__ import annotations

from pypdfbox.xmpbox import Attribute


def test_att() -> None:
    ns_uri = "nsUri"
    local_name = "localName"
    value = "value"

    att = Attribute(ns_uri, local_name, value)

    assert att.get_namespace() == ns_uri
    assert att.get_name() == local_name
    assert att.get_value() == value

    ns_uri2 = "nsUri2"
    local_name2 = "localName2"
    value2 = "value2"

    att.set_ns_uri(ns_uri2)
    att.set_name(local_name2)
    att.set_value(value2)

    assert att.get_namespace() == ns_uri2
    assert att.get_name() == local_name2
    assert att.get_value() == value2


def test_att_without_prefix() -> None:
    ns_uri = "nsUri"
    local_name = "localName"
    value = "value"

    att = Attribute(ns_uri, local_name, value)

    assert att.get_namespace() == ns_uri
    assert att.get_name() == local_name

    att = Attribute(ns_uri, local_name, value)
    assert att.get_namespace() == ns_uri
    assert att.get_name() == local_name
