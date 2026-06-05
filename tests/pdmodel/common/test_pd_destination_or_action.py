from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.common.pd_destination_or_action import (
    PDDestinationOrAction,
    is_destination_or_action,
)
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_xyz_destination import (
    PDPageXYZDestination,
)


def _make_xyz_array() -> COSArray:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("XYZ"))
    arr.add(COSFloat(1.0))
    arr.add(COSFloat(2.0))
    arr.add(COSFloat(3.0))
    return arr


# ---------- create() — happy paths ----------


def test_create_array_returns_pd_destination() -> None:
    result = PDDestinationOrAction.create(_make_xyz_array())
    assert isinstance(result, PDDestination)
    assert isinstance(result, PDPageXYZDestination)


def test_create_name_returns_named_destination() -> None:
    result = PDDestinationOrAction.create(COSName.get_pdf_name("MyDest"))
    assert isinstance(result, PDNamedDestination)
    assert result.get_named_destination() == "MyDest"


def test_create_string_returns_named_destination() -> None:
    result = PDDestinationOrAction.create(COSString("ByString"))
    assert isinstance(result, PDNamedDestination)
    assert result.get_named_destination() == "ByString"


def test_create_dictionary_returns_pd_action() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "GoTo")
    result = PDDestinationOrAction.create(d)
    assert isinstance(result, PDAction)
    assert isinstance(result, PDActionGoTo)


def test_create_uri_action_dictionary_returns_uri_action() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "URI")
    d.set_string(COSName.get_pdf_name("URI"), "https://example.com/")
    result = PDDestinationOrAction.create(d)
    assert isinstance(result, PDActionURI)
    assert result.get_uri() == "https://example.com/"


# ---------- create() — passthrough / fallthrough ----------


def test_create_none_returns_none() -> None:
    assert PDDestinationOrAction.create(None) is None


def test_create_unknown_cos_type_returns_none() -> None:
    # Booleans and floats outside an array don't match any branch — we
    # silently return None to mirror the upstream catalog dispatch which
    # treats anything other than dict/array as absent.
    assert PDDestinationOrAction.create(COSBoolean.TRUE) is None
    assert PDDestinationOrAction.create(COSInteger.get(7)) is None


# ---------- create() — empty action dict still creates an unknown-typed PDAction ----------


def test_create_empty_dictionary_returns_pd_action_unknown() -> None:
    d = COSDictionary()
    result = PDDestinationOrAction.create(d)
    # PDAction.create returns PDActionUnknown when /S is absent.
    assert isinstance(result, PDAction)


# ---------- create() — /D-only shorthand (legacy GoTo without /S) ----------


def test_create_dictionary_with_only_d_returns_goto_shorthand() -> None:
    """Some legacy producers omit ``/S`` from a GoTo action and rely on
    the presence of ``/D`` alone to imply ``GoTo``. The factory must
    promote such dictionaries to :class:`PDActionGoTo`."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("D"), _make_xyz_array())
    result = PDDestinationOrAction.create(d)
    assert isinstance(result, PDActionGoTo)
    # The wrapped destination must round-trip through the GoTo accessor.
    inner = result.get_destination()
    assert isinstance(inner, PDPageXYZDestination)


def test_create_dictionary_with_only_d_named_destination_shorthand() -> None:
    d = COSDictionary()
    d.set_string(COSName.get_pdf_name("D"), "MyTarget")
    result = PDDestinationOrAction.create(d)
    assert isinstance(result, PDActionGoTo)
    resolved = result.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "MyTarget"


def test_create_dictionary_with_s_takes_precedence_over_d() -> None:
    """When both ``/S`` and ``/D`` are present, ``/S`` wins (we go through
    the normal :meth:`PDAction.create` dispatch which already handles
    GoTo with ``/D``)."""
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "GoTo")
    d.set_item(COSName.get_pdf_name("D"), _make_xyz_array())
    result = PDDestinationOrAction.create(d)
    assert isinstance(result, PDActionGoTo)


# ---------- is_destination_or_action() ----------


def test_is_destination_or_action_for_destination() -> None:
    dest = PDDestinationOrAction.create(_make_xyz_array())
    assert is_destination_or_action(dest)


def test_is_destination_or_action_for_action() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "GoTo")
    action = PDDestinationOrAction.create(d)
    assert is_destination_or_action(action)


def test_is_destination_or_action_for_other_objects() -> None:
    assert not is_destination_or_action(None)
    assert not is_destination_or_action("MyDest")
    assert not is_destination_or_action(COSDictionary())
    assert not is_destination_or_action(_make_xyz_array())


# ---------- catalog wiring spot-check ----------


def test_pd_document_catalog_open_action_uses_dispatcher() -> None:
    """The catalog's ``get_open_action`` must funnel through the
    dispatcher and return the same kind of object as ``create()`` does."""
    from pypdfbox.cos import COSDocument
    from pypdfbox.pdmodel.pd_document_catalog import PDDocumentCatalog

    # Action-shaped /OpenAction.
    catalog_dict = COSDictionary()
    action = COSDictionary()
    action.set_name(COSName.get_pdf_name("S"), "GoTo")
    catalog_dict.set_item(COSName.get_pdf_name("OpenAction"), action)
    doc = COSDocument()
    doc.set_trailer(COSDictionary())
    catalog = PDDocumentCatalog(document=None, catalog=catalog_dict)  # type: ignore[arg-type]
    assert isinstance(catalog.get_open_action(), PDAction)

    # Array-shaped /OpenAction.
    catalog_dict2 = COSDictionary()
    catalog_dict2.set_item(COSName.get_pdf_name("OpenAction"), _make_xyz_array())
    catalog2 = PDDocumentCatalog(document=None, catalog=catalog_dict2)  # type: ignore[arg-type]
    assert isinstance(catalog2.get_open_action(), PDDestination)

    # Absent /OpenAction.
    catalog3 = PDDocumentCatalog(document=None, catalog=COSDictionary())  # type: ignore[arg-type]
    assert catalog3.get_open_action() is None
