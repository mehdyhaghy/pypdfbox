"""Wave 271 — pdmodel/interactive/annotation/PDAnnotationFileAttachment
parity gaps.

Round-out cold gaps:

* ``has_file`` / ``clear_file`` predicate + clear pair around ``/FS``
* ``has_attachment_name`` / ``clear_attachment_name`` predicate + clear
  pair around ``/Name`` (distinct from spec-default fallback)
* ``is_default_attachment_name`` — predicate for resolved-default icon
* ``is_known_attachment_name`` — predicate for one of the four spec
  constants (Table 184)
* ``get_custom_appearance_handler`` — Pythonic getter to mirror the
  squiggly/strikeout pattern (Wave 269/270)
"""

from __future__ import annotations

from dataclasses import dataclass

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.common.filespecification import PDSimpleFileSpecification
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
    PDAnnotationFileAttachment,
)

# ---------- /FS predicate + clear ----------


def test_has_file_default_false_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    assert ann.has_file() is False


def test_has_file_true_after_set_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    fs = PDSimpleFileSpecification()
    fs.set_file("attached.pdf")
    ann.set_file(fs)

    assert ann.has_file() is True


def test_clear_file_removes_entry_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    fs = PDSimpleFileSpecification()
    fs.set_file("foo.bin")
    ann.set_file(fs)

    ann.clear_file()

    assert ann.has_file() is False
    assert ann.get_file() is None
    assert (
        ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FS"))
        is None
    )


def test_clear_file_idempotent_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    ann.clear_file()
    ann.clear_file()
    assert ann.has_file() is False


def test_clear_file_preserves_attachment_name_wave271() -> None:
    """Clearing /FS must not touch /Name."""
    ann = PDAnnotationFileAttachment()
    fs = PDSimpleFileSpecification()
    fs.set_file("foo.pdf")
    ann.set_file(fs)
    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_TAG)

    ann.clear_file()

    assert ann.has_file() is False
    assert ann.get_attachment_name() == "Tag"


# ---------- /Name predicate + clear ----------


def test_has_attachment_name_default_false_wave271() -> None:
    """Predicate reflects raw /Name presence — the spec-default ``"PushPin"``
    surfaces via :meth:`get_attachment_name` even when /Name is absent."""
    ann = PDAnnotationFileAttachment()
    assert ann.has_attachment_name() is False
    assert ann.get_attachment_name() == "PushPin"


def test_has_attachment_name_true_after_set_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP)
    assert ann.has_attachment_name() is True


def test_has_attachment_name_true_for_explicit_default_wave271() -> None:
    """An explicit ``/Name /PushPin`` is "set" — distinct from absent."""
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN)
    assert ann.has_attachment_name() is True


def test_clear_attachment_name_removes_entry_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name("Tag")

    ann.clear_attachment_name()

    assert ann.has_attachment_name() is False
    # Spec-default fallback surfaces.
    assert ann.get_attachment_name() == "PushPin"
    assert (
        ann.get_cos_object().get_name(COSName.get_pdf_name("Name")) is None
    )


def test_clear_attachment_name_idempotent_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    ann.clear_attachment_name()
    ann.clear_attachment_name()
    assert ann.has_attachment_name() is False


# ---------- is_default_attachment_name ----------


def test_is_default_attachment_name_when_unset_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    assert ann.is_default_attachment_name() is True


def test_is_default_attachment_name_when_explicitly_push_pin_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN)
    assert ann.is_default_attachment_name() is True


def test_is_default_attachment_name_false_for_other_constants_wave271() -> None:
    for name in (
        PDAnnotationFileAttachment.ATTACHMENT_NAME_GRAPH,
        PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP,
        PDAnnotationFileAttachment.ATTACHMENT_NAME_TAG,
    ):
        ann = PDAnnotationFileAttachment()
        ann.set_attachment_name(name)
        assert ann.is_default_attachment_name() is False, name


# ---------- is_known_attachment_name ----------


def test_is_known_attachment_name_default_wave271() -> None:
    """Default unset → resolves to ``PushPin`` → known."""
    ann = PDAnnotationFileAttachment()
    assert ann.is_known_attachment_name() is True


def test_is_known_attachment_name_for_each_spec_constant_wave271() -> None:
    for name in (
        PDAnnotationFileAttachment.ATTACHMENT_NAME_GRAPH,
        PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP,
        PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN,
        PDAnnotationFileAttachment.ATTACHMENT_NAME_TAG,
    ):
        ann = PDAnnotationFileAttachment()
        ann.set_attachment_name(name)
        assert ann.is_known_attachment_name() is True, name


def test_is_known_attachment_name_false_for_vendor_extension_wave271() -> None:
    """Vendor-extension icon name (not in Table 184) — predicate False."""
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name("MyCustomIcon")
    assert ann.is_known_attachment_name() is False
    # Existing icon predicates also stay disjoint for the unknown name.
    assert ann.is_push_pin() is False
    assert ann.is_paperclip() is False
    assert ann.is_graph() is False
    assert ann.is_tag() is False


# ---------- get_custom_appearance_handler ----------


@dataclass
class _RecordingAppearanceHandler:
    normal: int = 0
    rollover: int = 0
    down: int = 0

    def generate_normal_appearance(self) -> None:
        self.normal += 1

    def generate_rollover_appearance(self) -> None:
        self.rollover += 1

    def generate_down_appearance(self) -> None:
        self.down += 1

    def generate_appearance_streams(self) -> None:
        self.generate_normal_appearance()
        self.generate_rollover_appearance()
        self.generate_down_appearance()


def test_default_custom_appearance_handler_is_none_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    assert ann.get_custom_appearance_handler() is None


def test_set_custom_appearance_handler_round_trips_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    handler = _RecordingAppearanceHandler()

    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]

    assert ann.get_custom_appearance_handler() is handler


def test_set_custom_appearance_handler_none_clears_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    handler = _RecordingAppearanceHandler()
    ann.set_custom_appearance_handler(handler)  # type: ignore[arg-type]

    ann.set_custom_appearance_handler(None)

    assert ann.get_custom_appearance_handler() is None


def test_handler_replacement_uses_latest_wave271() -> None:
    ann = PDAnnotationFileAttachment()
    first = _RecordingAppearanceHandler()
    second = _RecordingAppearanceHandler()

    ann.set_custom_appearance_handler(first)  # type: ignore[arg-type]
    ann.set_custom_appearance_handler(second)  # type: ignore[arg-type]

    assert ann.get_custom_appearance_handler() is second
    ann.construct_appearances()
    assert first.normal == 0
    assert second.normal == 1
