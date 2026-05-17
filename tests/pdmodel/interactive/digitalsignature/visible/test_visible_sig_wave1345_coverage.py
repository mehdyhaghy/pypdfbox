"""Wave 1345 coverage-boost for the visible-signature value objects.

Two narrow gaps left over from earlier waves:

* :class:`PDFTemplateStructure` — 7 getter methods (the corresponding
  setters are exercised in wave 1281, but the getters had no
  ``get -> setter -> get`` round-trip).
* :class:`PDVisibleSigProperties.build_signature` — the orchestration
  path that wires a :class:`PDVisibleSigBuilder` + a
  :class:`PDFTemplateCreator` and stashes the produced binary stream
  via :meth:`set_visible_signature`. Pre-1345 the only existing tests
  hit the fluent setters.

The ``build_signature`` test installs a stub
:class:`PDFTemplateCreator` (via :func:`monkeypatch.setattr`) that
returns a sentinel ``io.BytesIO`` without driving the real
:class:`PDVisibleSigBuilder` pipeline — which would otherwise need a
fully-formed :class:`PDDocument` to operate on.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.visible import (
    pdf_template_creator as _pdf_template_creator_module,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_properties import (
    PDVisibleSigProperties,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pdf_template_structure import (
    PDFTemplateStructure,
)

# ---------------------------------------------------------------------------
# PDFTemplateStructure — round-trip getter coverage
# ---------------------------------------------------------------------------


def test_acro_form_dictionary_round_trip() -> None:
    s = PDFTemplateStructure()
    marker = object()
    s.set_acro_form_dictionary(marker)
    assert s.get_acro_form_dictionary() is marker


def test_appearance_dictionary_round_trip() -> None:
    s = PDFTemplateStructure()
    marker = object()
    s.set_appearance_dictionary(marker)
    assert s.get_appearance_dictionary() is marker


def test_image_form_round_trip() -> None:
    s = PDFTemplateStructure()
    marker = object()
    s.set_image_form(marker)
    assert s.get_image_form() is marker


def test_image_form_name_round_trip() -> None:
    s = PDFTemplateStructure()
    marker = object()
    s.set_image_form_name(marker)
    assert s.get_image_form_name() is marker


def test_image_name_round_trip() -> None:
    s = PDFTemplateStructure()
    marker = object()
    s.set_image_name(marker)
    assert s.get_image_name() is marker


def test_acro_form_fields_round_trip() -> None:
    s = PDFTemplateStructure()
    marker = object()
    s.set_acro_form_fields(marker)
    assert s.get_acro_form_fields() is marker


def test_widget_dictionary_round_trip() -> None:
    s = PDFTemplateStructure()
    marker = object()
    s.set_widget_dictionary(marker)
    assert s.get_widget_dictionary() is marker


# ---------------------------------------------------------------------------
# PDVisibleSigProperties.build_signature
# ---------------------------------------------------------------------------


class _StubTemplateCreator:
    """Drop-in for :class:`PDFTemplateCreator` — captures the designer
    argument so the test can assert ``build_signature`` wired the call
    correctly, and returns a sentinel stream."""

    last_designer: object = None
    sentinel_stream: io.BytesIO = io.BytesIO(b"visible-signature-bytes")

    def __init__(self, builder: object) -> None:
        self.builder = builder

    def build_pdf(self, properties: object) -> io.BytesIO:
        _StubTemplateCreator.last_designer = properties
        return _StubTemplateCreator.sentinel_stream


def test_build_signature_invokes_creator_and_stores_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        _pdf_template_creator_module,
        "PDFTemplateCreator",
        _StubTemplateCreator,
    )

    designer = object()  # opaque — the stub just records it
    props = PDVisibleSigProperties()
    props.set_pd_visible_signature(designer)  # type: ignore[arg-type]

    assert props.get_visible_signature() is None
    props.build_signature()

    assert _StubTemplateCreator.last_designer is designer
    assert props.get_visible_signature() is _StubTemplateCreator.sentinel_stream
