"""Wave 1403 branch round-out for
``populate_fdf_dictionary_from_xfdf``.

Closes the False-branch arrow in
``pypdfbox/pdmodel/fdf/xfdf_parser.py``:

* 361->318 — a direct child of ``<xfdf>`` whose tag is none of ``f`` /
  ``ids`` / ``fields`` / ``annots`` makes the final ``elif tag ==
  "annots"`` arm False, so control returns to the ``for child`` loop and
  the unknown element is simply ignored.
"""

from __future__ import annotations

from xml.dom.minidom import parseString

from pypdfbox.pdmodel.fdf.fdf_dictionary import FDFDictionary
from pypdfbox.pdmodel.fdf.xfdf_parser import populate_fdf_dictionary_from_xfdf


def test_populate_fdf_dictionary_ignores_unknown_top_level_child() -> None:
    """Closes 361->318: an unrecognised ``<xfdf>`` child (here ``<custom>``)
    matches none of the known tags, so all the ``if/elif`` arms are False
    and the loop advances without touching the dictionary."""
    fdf_dict = FDFDictionary()
    doc = parseString(
        "<xfdf>"
        "<custom>ignored content</custom>"
        "</xfdf>"
    )
    populate_fdf_dictionary_from_xfdf(fdf_dict, doc.documentElement)

    # Nothing recognised was populated.
    assert fdf_dict.get_fields() is None or fdf_dict.get_fields() == []
    assert fdf_dict.get_annotations() is None or fdf_dict.get_annotations() == []
    assert fdf_dict.get_id() is None
