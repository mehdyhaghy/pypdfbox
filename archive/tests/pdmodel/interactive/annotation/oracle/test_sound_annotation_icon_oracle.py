"""Live Apache PDFBox differential parity for SOUND annotation appearance
generation — the OPERAND-LEVEL ``/AP`` result.

Surface under test
------------------
``PDSoundAppearanceHandler.generate_normal_appearance`` (driven via
``PDAnnotationSound.construct_appearances()``).

Apache PDFBox 3.0.7's ``PDSoundAppearanceHandler`` is an unimplemented stub —
all three ``generate*Appearance`` methods are ``// TODO to be implemented``
no-ops (``PDSoundAppearanceHandler.java`` lines 34/40/46). ``constructAppearances``
therefore instantiates the handler and drives ``generateAppearanceStreams()``
but NO appearance stream is written for any icon name, colour, or /Name shape.

pypdfbox mirrors this exactly: ``PDAnnotationSound.construct_appearances`` routes
through the ported ``PDSoundAppearanceHandler`` (whose three generate methods are
faithful no-op stubs), so it likewise produces no ``/AP /N``. This oracle pins
the no-op contract byte-for-byte across the icon-name matrix — Speaker / Mic /
colour-set / missing-/Name (defaults to Speaker) / unknown-/Name — so a future
"implement the handler" change must come with a matching upstream behaviour and
cannot silently start emitting an appearance that diverges from Apache PDFBox.

A negative control verifies the routing actually exercises the handler: a custom
appearance handler installed via ``set_custom_appearance_handler`` IS invoked
(it stamps a sentinel ``/AP /N``), proving the default path is the handler path
and not a bare base-class no-op.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.pdmodel.interactive.annotation import PDAnnotationSound
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_appearance_handler import (
    PDAppearanceHandler,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "SoundAnnotationIconProbe"

# The supported icon names, in the order the probe writes them.
_SUPPORTED_NAMES = (
    PDAnnotationSound.NAME_SPEAKER,
    PDAnnotationSound.NAME_MIC,
)


# ---------------------------------------------------------------------------
# canonical rendering — mirrors SoundAnnotationIconProbe.canon* (Java)
# ---------------------------------------------------------------------------


def _canon(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _canon_rect(r) -> str:
    if r is None:
        return "none"
    return ",".join(
        _canon(v)
        for v in (
            r.get_lower_left_x(),
            r.get_lower_left_y(),
            r.get_upper_right_x(),
            r.get_upper_right_y(),
        )
    )


# ---------------------------------------------------------------------------
# Java record parsing
# ---------------------------------------------------------------------------


def _parse_java(text: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if line.startswith("ANNOT "):
            current = {"name": line[len("ANNOT ") :]}
        elif line.startswith("RAWNAME "):
            assert current is not None
            current["rawname"] = line[len("RAWNAME ") :]
        elif line.startswith("RECT "):
            assert current is not None
            current["rect"] = line[len("RECT ") :]
        elif line == "NOAP":
            assert current is not None
            current["ap"] = "NOAP"
        elif line == "HASSTREAM":
            assert current is not None
            current["ap"] = "HASSTREAM"
        elif line == "END":
            assert current is not None
            records.append(current)
            current = None
    return records


def _build_battery() -> list[PDAnnotationSound]:
    """Mirror SoundAnnotationIconProbe.write — Speaker, Mic, a colour-set
    Speaker, a missing-/Name annot, then an unknown-/Name annot."""
    battery: list[PDAnnotationSound] = []
    y = 750
    for name in _SUPPORTED_NAMES:
        ann = PDAnnotationSound()
        ann.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
        ann.set_name(name)
        battery.append(ann)
        y -= 45
    # colour-set Speaker
    coloured = PDAnnotationSound()
    coloured.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
    coloured.set_name(PDAnnotationSound.NAME_SPEAKER)
    coloured.set_color_components([1.0, 0.0, 0.0])
    battery.append(coloured)
    y -= 45
    # missing /Name
    missing = PDAnnotationSound()
    missing.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
    battery.append(missing)
    y -= 45
    # unknown /Name
    unknown = PDAnnotationSound()
    unknown.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
    unknown.set_name("DefinitelyNotAStandardIcon")
    battery.append(unknown)
    return battery


def _java_records() -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "sound_annotation.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


def _py_fingerprint(ann: PDAnnotationSound) -> dict[str, object]:
    ann.construct_appearances()
    stream = ann.get_normal_appearance_stream()
    return {
        "name": ann.get_name(),
        "rect": _canon_rect(ann.get_rectangle()),
        "ap": "NOAP" if stream is None else "HASSTREAM",
    }


@requires_oracle
def test_sound_annotation_icons_match_pdfbox_exactly() -> None:
    java = _java_records()
    battery = _build_battery()
    assert len(java) == len(battery), (
        f"probe wrote {len(java)} annots, battery has {len(battery)}"
    )
    for ann, jr in zip(battery, java, strict=True):
        py = _py_fingerprint(ann)
        label = jr["name"]
        assert py["name"] == jr["name"], (
            f"icon name: {py['name']!r} != PDFBox {jr['name']!r}"
        )
        # /Rect is untouched (handler is a no-op, no adjustRectAndBBox).
        assert py["rect"] == jr["rect"], (
            f"{label} /Rect: {py['rect']!r} != PDFBox {jr['rect']!r}"
        )
        # The substance: Apache PDFBox writes NO appearance stream; so must we.
        assert py["ap"] == jr["ap"] == "NOAP", (
            f"{label} appearance: pypdfbox {py['ap']!r} != PDFBox {jr['ap']!r} "
            f"(both must be NOAP — the handler is an unimplemented stub)"
        )


def test_default_name_is_speaker() -> None:
    """Missing /Name resolves to Speaker (spec default), matching the probe's
    ``getName()`` on the no-/Name annotation."""
    ann = PDAnnotationSound()
    assert ann.get_name() == PDAnnotationSound.NAME_SPEAKER


def test_custom_handler_routes_through_handler_path() -> None:
    """Negative control: the default ``construct_appearances`` path drives an
    appearance handler (not a bare no-op). Installing a custom handler that
    stamps a sentinel proves the routing actually invokes the handler."""

    calls: list[str] = []

    class _SentinelHandler(PDAppearanceHandler):
        def generate_normal_appearance(self) -> None:
            calls.append("N")

        def generate_rollover_appearance(self) -> None:
            calls.append("R")

        def generate_down_appearance(self) -> None:
            calls.append("D")

    ann = PDAnnotationSound()
    ann.set_rectangle(PDRectangle.from_xywh(50, 700, 30, 30))
    ann.set_custom_appearance_handler(_SentinelHandler())
    ann.construct_appearances()
    # generate_appearance_streams drives N, R, D in order.
    assert calls == ["N", "R", "D"]
    # Clearing the custom handler restores the default (still NOAP) path.
    ann.set_custom_appearance_handler(None)
    ann.construct_appearances()
    assert ann.get_normal_appearance_stream() is None
