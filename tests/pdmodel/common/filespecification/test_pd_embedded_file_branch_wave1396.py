"""Wave 1396 branch-coverage tests for ``PDEmbeddedFile`` helpers.

Closes False-branch arrows:

* 76->78 — ``_parse_pdf_date`` with positive offset (no negation)
* 122->124 — ``_set_embedded_string`` with value=None when nested isn't
  a dictionary
* 207->exit — ``clear_mac_info`` no-op when /Params is absent
* 491->493 — ``set_mac_resource_fork(None)`` when /Params/Mac is absent
"""

from __future__ import annotations

import datetime as _dt

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import (
    PDEmbeddedFile,
    _parse_pdf_date,
    _set_embedded_string,
)


def test_parse_pdf_date_positive_offset_keeps_delta_positive() -> None:
    """A ``+HH'mm'`` offset keeps the tz delta positive.

    Closes False arm at line 76 (the negation only fires when sign is "-").
    """
    parsed = _parse_pdf_date("D:20240501123045+05'30'")
    assert parsed is not None
    assert parsed.utcoffset() == _dt.timedelta(hours=5, minutes=30)


def test_set_embedded_string_none_when_outer_dict_absent_is_noop() -> None:
    """``_set_embedded_string(parent, outer, inner, None)`` is a no-op
    when /outer dict doesn't exist.

    Closes False arm at line 122 (``isinstance(nested, COSDictionary)``).
    """
    parent = COSDictionary()
    _set_embedded_string(
        parent, COSName.get_pdf_name("CIInfo"), COSName.get_pdf_name("Creator"), None,
    )
    # Nothing was added — parent stays empty.
    assert len(list(parent.key_set())) == 0


def test_clear_mac_info_when_params_absent_is_noop() -> None:
    """``clear_mac_info`` is a no-op when /Params is absent.

    Closes False arm at line 207.
    """
    ef = PDEmbeddedFile()
    # No /Params on a freshly-created PDEmbeddedFile.
    ef.clear_mac_info()  # must not raise
    assert ef.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Params"),
    ) is None


def test_set_mac_resource_fork_none_when_mac_absent_is_noop() -> None:
    """``set_mac_resource_fork(None)`` is a no-op when /Params/Mac is absent.

    Closes False arm at line 491.
    """
    ef = PDEmbeddedFile()
    # Create /Params (without /Mac) so the inner code reaches the
    # ``mac = params.get_dictionary_object(_MAC)`` line.
    params = COSDictionary()
    ef.get_cos_object().set_item(COSName.get_pdf_name("Params"), params)
    ef.set_mac_resource_fork(None)  # must not raise
    # /Mac was never created.
    assert params.get_dictionary_object(COSName.get_pdf_name("Mac")) is None
