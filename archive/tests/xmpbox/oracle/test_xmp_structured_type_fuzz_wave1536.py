"""Live Apache xmpbox differential parity for the STRUCTURED property types.

Where ``test_xmp_property_type_fuzz_wave1535.py`` fuzzes the simple
value-conversion classes (``IntegerType`` / ``RealType`` / ...), this file
fuzzes the *field-access* layer of the structured types built on
``AbstractStructuredType``: ``DimensionsType`` / ``JobType`` / ``LayerType`` /
``ResourceRefType`` / ``ThumbnailType`` / ``VersionType``.

Each case constructs one structured type, exercises a malformed / missing /
round-trip field scenario, and projects a small ``k=v|...`` payload that both
the live ``XmpStructuredTypeFuzzProbe`` (Apache xmpbox 3.0.7) and the pypdfbox
port emit. Parity is asserted on the normalized payload.

Two normalizations bridge unalignable cross-language renderings (both pinned
here so a future change to either side is caught):

  * **Float repr.** ``String.valueOf(Float)`` renders ``Float.NaN`` /
    ``Float.POSITIVE_INFINITY`` as ``NaN`` / ``Infinity`` and a finite value
    like ``2.5`` as ``2.5``; Python ``str(float)`` renders the same stored
    value as ``nan`` / ``inf`` / ``2.5``. The stored single-precision value is
    identical (proven for finite values by the matching token); only the
    special-value spelling differs, so it is canonicalized.
  * **Exception class.** A field whose value the underlying simple type rejects
    (``getW`` on a non-numeric ``w``, ``setHeight``/``addSimpleProperty`` with a
    non-integer, ``setId(null)``) raises ``IllegalArgumentException`` upstream
    and ``ValueError`` in pypdfbox (the project's ``IllegalArgumentException ->
    ValueError`` convention). Both collapse to the ``ERR`` classification.

Key parities pinned (wave 1536):

  * Every typed getter on an empty structured value returns ``None`` (Java
    ``null``) — w/h/unit, id/name/url, LayerName/LayerText, documentID/...,
    width/height/format/image, comments/modifier/version/event.
  * Set/get round-trips through the ``_FIELD_TYPES`` registry preserve the
    value and its string form (incl. empty-string fields).
  * ``addProperty`` *replaces* a same-named field (``getAllProperties`` size
    stays 1 after a second ``setId``), and ``getAllProperties`` preserves
    insertion order.
  * Child fields carry a ``None`` namespace and the structured type's preferred
    prefix (``stJob`` / ``stRef``) — matching upstream ``addSimpleProperty``.
  * ``DimensionsType.toString`` renders ``DimensionsType{<w> x <h> <unit>}``
    with ``None`` for missing fields.
  * ``ResourceRefType.getAlternatePaths`` returns ``None`` when absent, a
    populated list (incl. an empty-string element) once seeded.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.xmpbox.type.dimensions_type import DimensionsType
from pypdfbox.xmpbox.type.job_type import JobType
from pypdfbox.xmpbox.type.layer_type import LayerType
from pypdfbox.xmpbox.type.resource_ref_type import ResourceRefType
from pypdfbox.xmpbox.type.thumbnail_type import ThumbnailType
from pypdfbox.xmpbox.type.version_type import VersionType
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from tests.oracle.harness import requires_oracle, run_probe_text

_US = chr(0x1F)

# Every probe case id. The probe is self-contained (it builds the structure
# internally), so the test only needs to name the case for both sides.
_CASES: list[str] = [
    "dim_empty",
    "job_empty",
    "layer_empty",
    "ref_empty",
    "thumb_empty",
    "ver_empty",
    "dim_set_floats",
    "dim_set_nan",
    "dim_set_zero",
    "dim_unit_empty",
    "dim_w_wrong_type",
    "dim_tostring_empty",
    "dim_tostring_set",
    "job_set_get",
    "job_ns_prefix",
    "job_field_ns",
    "job_set_twice",
    "job_order",
    "job_set_null",
    "thumb_set_get",
    "thumb_zero",
    "thumb_img_empty",
    "thumb_h_wrong_type",
    "thumb_order",
    "layer_set_get",
    "layer_empty_str",
    "layer_order",
    "ref_set_get",
    "ref_alt_paths",
    "ref_alt_empty",
    "ref_alt_one_empty",
    "ref_field_ns",
    "ref_mask_markers",
    "ver_set_get",
    "ver_ns_prefix",
    "ver_order",
]


def _canon(payload: str) -> str:
    """Canonicalize a ``k=v`` payload so cross-language renderings collapse to
    a single comparable form.

    The probe joins ``k=v`` pairs with the ASCII unit separator (0x1f); the
    pypdfbox mirror joins them with ``|``. Both separators are accepted so the
    two sides land on the same canonical ``key=value|...`` string.
    """
    if payload.startswith("ERR"):
        return "ERR"
    fields = payload.replace(_US, "|").split("|")
    out = []
    for field in fields:
        key, _, value = field.partition("=")
        out.append(f"{key}={_canon_value(value)}")
    return "|".join(out)


def _canon_value(value: str) -> str:
    # Null: Java String.valueOf(null) -> "null"; Python str(None) -> "None".
    if value in ("null", "None"):
        return "null"
    # Booleans: Java String.valueOf renders true/false; Python str(bool) -> True/False.
    if value in ("True", "true"):
        return "true"
    if value in ("False", "false"):
        return "false"
    # Special float values: Java NaN/Infinity vs Python nan/inf.
    low = value.lower().lstrip("-")
    if low in ("nan", "infinity", "inf"):
        sign = "-" if value.startswith("-") else ""
        return sign + ("nan" if low == "nan" else "inf")
    return value


def _java(case: str) -> str:
    return _canon(run_probe_text("XmpStructuredTypeFuzzProbe", case).rstrip("\n"))


# --- pypdfbox side: mirror each probe case ---------------------------------


def _meta() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def _names(struct) -> str:
    return ",".join(p.get_property_name() for p in struct.get_all_properties())


def _py(case: str) -> str:  # noqa: C901 - flat case dispatch mirrors the probe
    try:
        return _canon(_py_run(case))
    except (ValueError, TypeError):
        return "ERR"


def _py_run(case: str) -> str:  # noqa: C901 - flat case dispatch mirrors the probe
    m = _meta()
    if case == "dim_empty":
        d = DimensionsType(m)
        return f"w={d.get_w()}|h={d.get_h()}|unit={d.get_unit()}"
    if case == "job_empty":
        j = JobType(m)
        return f"id={j.get_id()}|name={j.get_name()}|url={j.get_url()}"
    if case == "layer_empty":
        layer = LayerType(m)
        return f"name={layer.get_layer_name()}|text={layer.get_layer_text()}"
    if case == "ref_empty":
        r = ResourceRefType(m)
        date = "cal" if r.get_last_modify_date() is not None else None
        alt = "list" if r.get_alternate_paths() is not None else None
        return (
            f"doc={r.get_document_id()}|inst={r.get_instance_id()}"
            f"|date={date}|alt={alt}|rc={r.get_rendition_class()}"
        )
    if case == "thumb_empty":
        t = ThumbnailType(m)
        return (
            f"w={t.get_width()}|h={t.get_height()}"
            f"|fmt={t.get_format()}|img={t.get_image()}"
        )
    if case == "ver_empty":
        v = VersionType(m)
        date = "cal" if v.get_modify_date() is not None else None
        event = "evt" if v.get_event() is not None else None
        return (
            f"comments={v.get_comments()}|modifier={v.get_modifier()}"
            f"|version={v.get_version()}|date={date}|event={event}"
        )
    if case == "dim_set_floats":
        d = DimensionsType(m)
        d.add_simple_property(DimensionsType.W, 2.5)
        d.add_simple_property(DimensionsType.H, 3.0)
        d.add_simple_property(DimensionsType.UNIT, "inch")
        return f"w={d.get_w()}|h={d.get_h()}|unit={d.get_unit()}"
    if case == "dim_set_nan":
        d = DimensionsType(m)
        d.add_simple_property(DimensionsType.W, math.nan)
        d.add_simple_property(DimensionsType.H, math.inf)
        return f"w={d.get_w()}|h={d.get_h()}"
    if case == "dim_set_zero":
        d = DimensionsType(m)
        d.add_simple_property(DimensionsType.W, 0.0)
        d.add_simple_property(DimensionsType.H, -1.5)
        return f"w={d.get_w()}|h={d.get_h()}"
    if case == "dim_unit_empty":
        d = DimensionsType(m)
        d.add_simple_property(DimensionsType.UNIT, "")
        return f"unit={d.get_unit()}"
    if case == "dim_w_wrong_type":
        d = DimensionsType(m)
        d.add_simple_property(DimensionsType.W, "notanumber")
        return f"w={d.get_w()}"
    if case == "dim_tostring_empty":
        return f"ts={DimensionsType(m).to_string()}"
    if case == "dim_tostring_set":
        d = DimensionsType(m)
        d.add_simple_property(DimensionsType.W, 4.0)
        d.add_simple_property(DimensionsType.H, 5.0)
        d.add_simple_property(DimensionsType.UNIT, "px")
        return f"ts={d.to_string()}"
    if case == "job_set_get":
        j = JobType(m)
        j.set_id("J1")
        j.set_name("nightly")
        j.set_url("http://x/")
        return f"id={j.get_id()}|name={j.get_name()}|url={j.get_url()}"
    if case == "job_ns_prefix":
        j = JobType(m)
        return f"ns={j.get_namespace()}|pfx={j.get_prefix()}"
    if case == "job_field_ns":
        j = JobType(m)
        j.set_id("J1")
        f = j.get_property(JobType.ID)
        fns = None if f is None else f.get_namespace()
        fpfx = None if f is None else f.get_prefix()
        return f"found={f is not None}|fns={fns}|fpfx={fpfx}"
    if case == "job_set_twice":
        j = JobType(m)
        j.set_id("first")
        j.set_id("second")
        return f"count={len(j.get_all_properties())}|id={j.get_id()}"
    if case == "job_order":
        j = JobType(m)
        j.set_url("u")
        j.set_name("n")
        j.set_id("i")
        return f"order={_names(j)}"
    if case == "job_set_null":
        j = JobType(m)
        j.set_id(None)
        return f"id={j.get_id()}"
    if case == "thumb_set_get":
        t = ThumbnailType(m)
        t.set_width(64)
        t.set_height(48)
        t.set_format("JPEG")
        t.set_image("/9j/base64")
        return (
            f"w={t.get_width()}|h={t.get_height()}"
            f"|fmt={t.get_format()}|img={t.get_image()}"
        )
    if case == "thumb_zero":
        t = ThumbnailType(m)
        t.set_width(0)
        t.set_height(-5)
        return f"w={t.get_width()}|h={t.get_height()}"
    if case == "thumb_img_empty":
        t = ThumbnailType(m)
        t.set_image("")
        return f"img={t.get_image()}"
    if case == "thumb_h_wrong_type":
        t = ThumbnailType(m)
        t.add_simple_property(ThumbnailType.HEIGHT, "abc")
        return f"h={t.get_height()}"
    if case == "thumb_order":
        t = ThumbnailType(m)
        t.set_image("img")
        t.set_format("PNG")
        t.set_height(10)
        t.set_width(20)
        return f"order={_names(t)}"
    if case == "layer_set_get":
        layer = LayerType(m)
        layer.set_layer_name("Layer 1")
        layer.set_layer_text("hello")
        return f"name={layer.get_layer_name()}|text={layer.get_layer_text()}"
    if case == "layer_empty_str":
        layer = LayerType(m)
        layer.set_layer_name("")
        return f"name={layer.get_layer_name()}"
    if case == "layer_order":
        layer = LayerType(m)
        layer.set_layer_text("t")
        layer.set_layer_name("n")
        return f"order={_names(layer)}"
    if case == "ref_set_get":
        r = ResourceRefType(m)
        r.set_document_id("uuid:doc")
        r.set_instance_id("uuid:inst")
        r.set_rendition_class("default")
        r.set_version_id("3")
        return (
            f"doc={r.get_document_id()}|inst={r.get_instance_id()}"
            f"|rc={r.get_rendition_class()}|ver={r.get_version_id()}"
        )
    if case == "ref_alt_paths":
        r = ResourceRefType(m)
        r.add_alternate_path("a")
        r.add_alternate_path("b")
        alts = r.get_alternate_paths()
        size = -1 if alts is None else len(alts)
        vals = None if alts is None else ",".join(alts)
        return f"size={size}|vals={vals}"
    if case == "ref_alt_empty":
        r = ResourceRefType(m)
        alt = "list" if r.get_alternate_paths() is not None else None
        return f"alt={alt}"
    if case == "ref_alt_one_empty":
        r = ResourceRefType(m)
        r.add_alternate_path("")
        alts = r.get_alternate_paths()
        size = -1 if alts is None else len(alts)
        v0 = None if not alts else alts[0]
        return f"size={size}|v0={v0}"
    if case == "ref_field_ns":
        r = ResourceRefType(m)
        r.set_document_id("d")
        f = r.get_property(ResourceRefType.DOCUMENT_ID)
        fns = None if f is None else f.get_namespace()
        fpfx = None if f is None else f.get_prefix()
        return f"fns={fns}|fpfx={fpfx}"
    if case == "ref_mask_markers":
        r = ResourceRefType(m)
        r.set_mask_markers("All")
        return f"mm={r.get_mask_markers()}"
    if case == "ver_set_get":
        v = VersionType(m)
        v.set_comments("c")
        v.set_version("2.0")
        v.set_modifier("Bob")
        return (
            f"comments={v.get_comments()}|version={v.get_version()}"
            f"|modifier={v.get_modifier()}"
        )
    if case == "ver_ns_prefix":
        v = VersionType(m)
        return f"ns={v.get_namespace()}|pfx={v.get_prefix()}"
    if case == "ver_order":
        v = VersionType(m)
        v.set_version("v")
        v.set_comments("c")
        v.set_modifier("m")
        return f"order={_names(v)}"
    raise AssertionError(f"unknown case {case}")


@requires_oracle
@pytest.mark.parametrize("case", _CASES, ids=_CASES)
def test_structured_type_matches_xmpbox(case: str) -> None:
    java = _java(case)
    py = _py(case)
    assert py == java, f"structured-type divergence for {case}: java={java} py={py}"
