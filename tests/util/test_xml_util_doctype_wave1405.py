"""Robustness (wave 1405): XML DTD rejection in ``XMLUtil.parse``.

XFDF input does not use DTDs; a ``<!DOCTYPE`` declaration is the entry point for
XML internal-entity expansion ("billion laughs") and external-entity (XXE)
attacks. ``defusedxml`` is not a pypdfbox dependency, so the production fallback
is plain ``minidom``/expat, which expands entities. The fuzz harness found that
the previous guard only scanned the first 2048 bytes, so a large leading comment
could push the DOCTYPE past the window and bypass it. The guard now scans the
whole buffer (``contains_doctype``).
"""

from __future__ import annotations

import pytest

from pypdfbox.util.xml_util import XMLUtil, contains_doctype


def test_contains_doctype_helper() -> None:
    assert contains_doctype(b'<r/>') is False
    assert contains_doctype(b'<!DOCTYPE html>') is True
    assert contains_doctype(b'<!doctype x>') is True  # case-insensitive
    # Anywhere in the buffer, not just the prefix.
    assert contains_doctype(b'<?xml?>' + b'A' * 5000 + b'<!DOCTYPE x>') is True


def test_plain_doctype_rejected() -> None:
    payload = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "v">]><r>&e;</r>'
    with pytest.raises(OSError):
        XMLUtil.parse(payload)


def test_comment_padded_doctype_rejected_past_2048_window() -> None:
    """The historical bypass: a leading comment pushes ``<!DOCTYPE`` past the
    old fixed-size guard window. The full-buffer scan now catches it."""
    payload = (
        b'<?xml version="1.0"?><!-- ' + b"A" * 2100 + b" -->"
        b'<!DOCTYPE x [<!ENTITY e "v">]><r>&e;</r>'
    )
    assert payload.find(b"<!DOCTYPE") > 2048
    with pytest.raises(OSError):
        XMLUtil.parse(payload)


def test_valid_xfdf_still_parses() -> None:
    doc = XMLUtil.parse(
        b'<?xml version="1.0"?>'
        b'<xfdf xmlns="http://ns.adobe.com/xfdf/"><fields/></xfdf>'
    )
    assert doc is not None
