from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.graphics import PDXObject


def test_get_subtype_returns_image() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Image"))
    assert xobject.get_subtype() == "Image"


def test_get_subtype_returns_form() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))
    assert xobject.get_subtype() == "Form"


def test_get_subtype_returns_custom_subtype_name() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("PS"))
    assert xobject.get_subtype() == "PS"


def test_get_sub_type_alias_matches_get_subtype() -> None:
    # Mechanical snake_case translation of upstream ``getSubType()``.
    # Both spellings must remain live and agree.
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Image"))
    assert xobject.get_sub_type() == xobject.get_subtype() == "Image"


def test_get_sub_type_returns_none_when_subtype_missing() -> None:
    # ``PDXObject`` without a stamped /Subtype (constructed indirectly).
    stream = COSStream()
    # Drop the /Subtype entry to simulate a malformed stream.
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))
    stream.remove_item(COSName.SUBTYPE)  # type: ignore[attr-defined]
    assert xobject.get_sub_type() is None
    assert xobject.get_subtype() is None


def test_get_metadata_returns_none_when_absent() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))
    assert xobject.get_metadata() is None


def test_get_metadata_returns_pd_metadata_when_present() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Image"))

    metadata_stream = COSStream()
    xobject.get_cos_object().set_item(
        COSName.METADATA,  # type: ignore[attr-defined]
        metadata_stream,
    )

    metadata = xobject.get_metadata()
    assert metadata is not None
    assert isinstance(metadata, PDMetadata)
    assert metadata.get_cos_object() is metadata_stream


def test_set_metadata_round_trip() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))

    metadata = PDMetadata(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    xobject.set_metadata(metadata)

    fetched = xobject.get_metadata()
    assert fetched is not None
    assert fetched.get_cos_object() is metadata.get_cos_object()


def test_set_metadata_none_removes_key() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Image"))

    metadata = PDMetadata(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    xobject.set_metadata(metadata)
    assert xobject.get_metadata() is not None

    xobject.set_metadata(None)
    assert xobject.get_metadata() is None
    assert xobject.get_cos_object().get_item(COSName.METADATA) is None  # type: ignore[attr-defined]


def test_eq_uses_backing_stream_identity() -> None:
    stream = COSStream()
    a = PDXObject(stream, COSName.get_pdf_name("Image"))
    b = PDXObject(stream, COSName.get_pdf_name("Image"))
    assert a == b
    assert hash(a) == hash(b)


def test_eq_distinguishes_separate_streams() -> None:
    a = PDXObject(COSStream(), COSName.get_pdf_name("Image"))
    b = PDXObject(COSStream(), COSName.get_pdf_name("Image"))
    assert a != b


def test_eq_returns_notimplemented_for_other_types() -> None:
    a = PDXObject(COSStream(), COSName.get_pdf_name("Image"))
    assert (a == "not an x-object") is False


def test_repr_includes_subtype() -> None:
    a = PDXObject(COSStream(), COSName.get_pdf_name("Form"))
    text = repr(a)
    assert "Form" in text
    assert "PDXObject" in text


# ---------- constructor type-error guard ----------


def test_init_rejects_non_stream_input() -> None:
    """The protected constructor accepts only ``PDStream``, ``COSStream``,
    or ``PDDocument`` — anything else (e.g. a raw ``COSDictionary`` or a
    Python ``str``) must raise ``TypeError`` rather than silently mis-typing
    the wrapper. Mirrors upstream Java's compile-time overload disambiguation.
    """
    import pytest

    from pypdfbox.cos import COSDictionary

    with pytest.raises(TypeError, match="PDXObject expects"):
        PDXObject(COSDictionary(), COSName.get_pdf_name("Form"))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="PDXObject expects"):
        PDXObject("not a stream", COSName.get_pdf_name("Form"))  # type: ignore[arg-type]


# ---------- create_x_object: transparency-group dispatch ----------
#
# Mirrors upstream:
#     COSDictionary group = stream.getCOSDictionary(COSName.GROUP);
#     if (group != null && COSName.TRANSPARENCY.equals(group.getCOSName(COSName.S)))
#         return new PDTransparencyGroup(stream, cache);
#     return new PDFormXObject(stream, cache);


def test_create_x_object_form_with_transparency_group_returns_transparency_group() -> None:
    """A ``/Subtype /Form`` stream carrying ``/Group << /S /Transparency >>``
    must dispatch to :class:`PDTransparencyGroup`, NOT a plain
    :class:`PDFormXObject`. PDF 32000-1 §11.6.6.
    """
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
        PDTransparencyGroup,
    )

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    group = COSDictionary()
    group.set_name(COSName.get_pdf_name("S"), "Transparency")
    stream.set_item(COSName.get_pdf_name("Group"), group)

    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDTransparencyGroup)
    # Identity preserved through the factory — same backing stream.
    assert obj.get_cos_object() is stream


def test_create_x_object_form_with_non_transparency_group_returns_plain_form() -> None:
    """A ``/Subtype /Form`` with a ``/Group`` that is NOT a transparency
    group (``/S != /Transparency``) must fall back to a plain
    :class:`PDFormXObject`. Common case: ``/Group << /S /Foo >>`` —
    well-formed but unrecognized; upstream still returns PDFormXObject
    rather than promoting to PDTransparencyGroup.
    """
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.graphics.form import PDFormXObject
    from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
        PDTransparencyGroup,
    )

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    group = COSDictionary()
    group.set_name(COSName.get_pdf_name("S"), "NotTransparency")
    stream.set_item(COSName.get_pdf_name("Group"), group)

    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDFormXObject)
    assert not isinstance(obj, PDTransparencyGroup)


def test_create_x_object_form_with_group_missing_s_returns_plain_form() -> None:
    """A ``/Subtype /Form`` with a ``/Group`` dictionary that lacks ``/S``
    altogether must NOT promote to :class:`PDTransparencyGroup`. The
    upstream check is strictly ``group.getCOSName(COSName.S).equals(
    COSName.TRANSPARENCY)`` — a missing ``/S`` fails the equality.
    """
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.graphics.form import PDFormXObject
    from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
        PDTransparencyGroup,
    )

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    stream.set_item(COSName.get_pdf_name("Group"), COSDictionary())

    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDFormXObject)
    assert not isinstance(obj, PDTransparencyGroup)


def test_create_x_object_form_with_non_dict_group_returns_plain_form() -> None:
    """When ``/Group`` is present but isn't a ``COSDictionary`` (malformed
    PDF), the factory must fall through to the plain
    :class:`PDFormXObject` path — upstream's ``getCOSDictionary`` returns
    null and the transparency-group branch is skipped.
    """
    from pypdfbox.pdmodel.graphics.form import PDFormXObject
    from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
        PDTransparencyGroup,
    )

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    # /Group entry is a COSName, not a dict — malformed.
    stream.set_item(COSName.get_pdf_name("Group"), COSName.get_pdf_name("Bogus"))

    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDFormXObject)
    assert not isinstance(obj, PDTransparencyGroup)


# ---------- create_x_object: missing /Subtype ----------


def test_create_x_object_missing_subtype_raises_oserror() -> None:
    """A stream with NO ``/Subtype`` entry at all must raise
    ``OSError`` with the upstream-shaped "Invalid XObject Subtype: None"
    message — there's no other branch to fall through to.

    Live PDFBox 3.0.7 raises ``IOException("Invalid XObject Subtype: null")``
    (Java renders a missing name as ``null``); pypdfbox renders the absent
    name as Python ``None`` — an accepted Java/Python idiom difference. The
    message prefix and exception class are identical. (Oracle-confirmed in
    ``oracle/probes/FormXObjectModelProbe.java`` →
    ``test_form_xobject_model_oracle.py``.)
    """
    import pytest

    stream = COSStream()
    with pytest.raises(OSError) as excinfo:
        PDXObject.create_x_object(stream)
    assert str(excinfo.value) == "Invalid XObject Subtype: None"


def test_create_x_object_non_stream_base_message_is_exact() -> None:
    """A non-stream ``base`` raises ``OSError`` whose message reproduces
    upstream's ``"Unexpected object type: <type>"`` shape. Live PDFBox
    uses the fully-qualified Java class name
    (``org.apache.pdfbox.cos.COSDictionary``); pypdfbox uses the Python
    short class name (``COSDictionary``) — an accepted idiom difference,
    prefix identical. (Oracle-confirmed.)
    """
    import pytest

    from pypdfbox.cos import COSDictionary

    with pytest.raises(OSError) as excinfo:
        PDXObject.create_x_object(COSDictionary())
    assert str(excinfo.value) == "Unexpected object type: COSDictionary"


# ---------- create_x_object: ResourceCache propagation ----------
#
# Mirrors upstream:
#     ResourceCache cache = resources != null
#         ? resources.getResourceCache() : null;
#     ...
#     return new PDFormXObject(stream, cache);
#     return new PDTransparencyGroup(stream, cache);
#
# The resources argument is NOT cosmetic — its cache must be threaded
# through to the new form-xobject so font / X-object look-ups inside
# the form share the page's cache. A bug in this branch silently
# blows the cache in every nested form, so it earns dedicated tests.


def test_create_x_object_form_threads_resource_cache_from_resources() -> None:
    """A plain ``/Subtype /Form`` stream constructed via the factory
    must receive ``resources.get_resource_cache()`` as its cache —
    upstream parity for the ``cache`` parameter passed to the
    ``PDFormXObject(stream, cache)`` constructor."""
    from pypdfbox.pdmodel.graphics.form import PDFormXObject
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
    from pypdfbox.pdmodel.pd_resources import PDResources

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]

    cache = DefaultResourceCache()
    resources = PDResources(resource_cache=cache)

    obj = PDXObject.create_x_object(stream, resources)
    assert isinstance(obj, PDFormXObject)
    # The form must have captured the *same* cache instance, not None
    # and not a fresh cache.
    assert obj._cache is cache  # noqa: SLF001 — invariant we want to lock down


def test_create_x_object_transparency_group_threads_resource_cache() -> None:
    """A transparency-group form (``/Group /S /Transparency``) must
    also receive the resources' cache — upstream's branch:
    ``return new PDTransparencyGroup(stream, cache);``"""
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
        PDTransparencyGroup,
    )
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
    from pypdfbox.pdmodel.pd_resources import PDResources

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    group = COSDictionary()
    group.set_name(COSName.get_pdf_name("S"), "Transparency")
    stream.set_item(COSName.get_pdf_name("Group"), group)

    cache = DefaultResourceCache()
    resources = PDResources(resource_cache=cache)

    obj = PDXObject.create_x_object(stream, resources)
    assert isinstance(obj, PDTransparencyGroup)
    assert obj._cache is cache  # noqa: SLF001


def test_create_x_object_form_has_no_cache_when_resources_none() -> None:
    """When ``resources`` is ``None`` (factory called without context),
    the cache passed to ``PDFormXObject`` must be ``None`` — upstream's
    ternary collapses to null."""
    from pypdfbox.pdmodel.graphics.form import PDFormXObject

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    obj = PDXObject.create_x_object(stream, None)
    assert isinstance(obj, PDFormXObject)
    assert obj._cache is None  # noqa: SLF001


def test_create_x_object_form_has_no_cache_when_resources_lack_cache() -> None:
    """When ``resources`` is given but lacks a configured
    ``ResourceCache`` (the default), the threaded cache value is
    ``None`` — i.e. ``getResourceCache()`` returns null and that null
    flows through to the form constructor unchanged."""
    from pypdfbox.pdmodel.graphics.form import PDFormXObject
    from pypdfbox.pdmodel.pd_resources import PDResources

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]

    resources = PDResources()  # no cache configured
    obj = PDXObject.create_x_object(stream, resources)
    assert isinstance(obj, PDFormXObject)
    assert obj._cache is None  # noqa: SLF001


def test_create_x_object_image_ignores_resource_cache() -> None:
    """Sanity: the image branch in upstream does NOT take a cache
    parameter (``new PDImageXObject(new PDStream(stream), resources)``
    — it takes the resources directly, not the cache). The dispatch
    should not error when resources are supplied; we only check it
    still returns the expected typed wrapper."""
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
    from pypdfbox.pdmodel.pd_resources import PDResources

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]

    cache = DefaultResourceCache()
    resources = PDResources(resource_cache=cache)

    obj = PDXObject.create_x_object(stream, resources)
    assert isinstance(obj, PDImageXObject)
    assert obj.get_cos_object() is stream
