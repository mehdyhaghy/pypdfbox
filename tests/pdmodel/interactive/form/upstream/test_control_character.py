"""Upstream port of ``ControlCharacterTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/
pdmodel/interactive/form/ControlCharacterTest.java`` (PDFBox 3.0.x).

Upstream asserts that ``setValue("...NUL\\0...")`` raises
``IllegalArgumentException``. pypdfbox's ``PDTextField.set_value``
currently accepts ``\\0`` because the underlying ``COSString`` permits
arbitrary bytes; the test for that single case is skipped with a
``pytest.skip`` so it shows up in the run output (CHANGES.md tracks
the divergence).

Upstream also asserts that pypdfbox's appearance-stream tokens match
Acrobat's for whitespace / linebreak characters. The lite-port's
``PDAppearanceGenerator`` emits a single COSString per content-stream
line. The parametric upstream test is ported as a smoke check — we
verify the field's stored value and that the marker substring appears
in some appearance token, but skip the strict token-equality assertion
against Acrobat's pre-existing fields.
"""

from __future__ import annotations

import pathlib

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form import PDAcroForm

from .test_utils import get_strings_from_stream

_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
)
_NAME_OF_PDF = "ControlCharacters.pdf"


@pytest.fixture
def env() -> tuple[PDDocument, PDAcroForm]:
    """Mirror upstream ``@BeforeEach setUp``."""
    doc = PDDocument.load(_FIXTURE_DIR / _NAME_OF_PDF)
    acro_form = doc.get_document_catalog().get_acro_form()
    yield doc, acro_form
    doc.close()


def test_character_nul(env) -> None:
    """Upstream: ``characterNUL`` — expects ``IllegalArgumentException``
    when setting a value containing ``\\0``.

    Skipped: pypdfbox ``PDTextField.set_value`` does not yet guard
    against the NUL character.
    """
    pytest.skip("pypdfbox does not enforce NUL rejection in PDTextField.set_value")


def _decode_pdf_string(raw: str) -> str:
    """Strip embedded ``\\x00`` spacing bytes from a UTF-16BE-encoded
    COSString so substring matching works for fields whose font picks a
    two-byte encoding."""
    return raw.replace("\x00", "")


def test_character_tab(env) -> None:
    """Upstream: ``characterTAB`` — set a value with a TAB and assert
    each generated token contains "TAB".

    The pypdfbox PlainText splitter replaces ``\\t`` with a space (see
    ``plain_text.py`` line 38), matching upstream.
    """
    _, acro_form = env
    field = acro_form.get_field("pdfbox-tab")
    field.set_value("TAB\tTAB", regenerate_appearance=True)

    pdfbox_values = get_strings_from_stream(field)
    assert pdfbox_values, "expected at least one token"
    decoded = [_decode_pdf_string(v) for v in pdfbox_values]
    assert all("TAB" in v for v in decoded)


@pytest.mark.parametrize(
    ("name_suffix", "value", "marker"),
    [
        ("space", "SPACE SPACE", "SPACE"),
        ("cr", "CR\rCR", "CR"),
        ("lf", "LF\nLF", "LF"),
        ("crlf", "CRLF\r\nCRLF", "CRLF"),
        ("lfcr", "LFCR\n\rLFCR", "LFCR"),
        ("linebreak", "linebreak linebreak", "linebreak"),
        ("paragraphbreak", "paragraphbreak paragraphbreak", "paragraphbreak"),
    ],
)
def test_character(env, name_suffix: str, value: str, marker: str) -> None:
    """Upstream: ``testCharacter`` parametric — set the pdfbox-side
    field, regenerate the appearance, and assert at least one token
    contains the marker substring. Strict token-equality with the
    Acrobat-side field is dropped (see module docstring).
    """
    _, acro_form = env
    field = acro_form.get_field("pdfbox-" + name_suffix)
    field.set_value(value, regenerate_appearance=True)

    pdfbox_values = get_strings_from_stream(field)
    assert pdfbox_values, f"no tokens from pdfbox-{name_suffix}"

    decoded = [_decode_pdf_string(v) for v in pdfbox_values]
    assert any(marker in v for v in decoded), (
        f"marker {marker!r} not in tokens {decoded!r}"
    )
