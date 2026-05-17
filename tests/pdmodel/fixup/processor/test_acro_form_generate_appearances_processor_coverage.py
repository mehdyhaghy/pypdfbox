"""Hand-written coverage tests for
``AcroFormGenerateAppearancesProcessor``.

Drives the previously-uncovered branches in
``pypdfbox/pdmodel/fixup/processor/acro_form_generate_appearances_processor.py``:

* the early-return when the catalog has no ``get_acro_form``.
* the early-return when ``get_acro_form`` returns ``None``.
* the ``TypeError`` fallback when ``get_acro_form`` doesn't take a fixup
  argument.
* the happy path where ``refresh_appearances`` + ``set_need_appearances``
  are both invoked.
* the ``except (OSError, ValueError)`` handler around the refresh call.
* the ``getattr(..., None)`` guards when the acro form is missing one
  of those two methods.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from pypdfbox.pdmodel.fixup.processor.acro_form_generate_appearances_processor import (
    AcroFormGenerateAppearancesProcessor,
)


# ----------------------------------------------------------------------
# Lightweight stand-ins
# ----------------------------------------------------------------------


class _AcroFormStub:
    def __init__(
        self,
        *,
        raise_in_refresh: type[Exception] | None = None,
        no_refresh: bool = False,
        no_set_need: bool = False,
    ) -> None:
        self.refresh_calls = 0
        self.set_need_calls: list[bool] = []
        self._raise_in_refresh = raise_in_refresh
        if no_refresh:
            # Drop the attribute so ``getattr(..., None)`` returns None.
            self._suppress_refresh = True
        else:
            self._suppress_refresh = False
        if no_set_need:
            self._suppress_set_need = True
        else:
            self._suppress_set_need = False

    def refresh_appearances(self) -> None:
        if self._suppress_refresh:
            raise AttributeError("synthetic")
        self.refresh_calls += 1
        if self._raise_in_refresh is not None:
            raise self._raise_in_refresh("synthetic refresh failure")

    def set_need_appearances(self, flag: bool) -> None:
        if self._suppress_set_need:
            raise AttributeError("synthetic")
        self.set_need_calls.append(flag)


class _AcroFormNoRefresh:
    """AcroForm-like object missing ``refresh_appearances``."""

    def __init__(self) -> None:
        self.set_need_calls: list[bool] = []

    def set_need_appearances(self, flag: bool) -> None:
        self.set_need_calls.append(flag)


class _AcroFormNoSetNeed:
    """AcroForm-like object missing ``set_need_appearances``."""

    def __init__(self) -> None:
        self.refresh_calls = 0

    def refresh_appearances(self) -> None:
        self.refresh_calls += 1


class _StubCatalog:
    def __init__(self, acro_form: object | None) -> None:
        self._acro_form = acro_form

    def get_acro_form(self, _fixup: object | None = None) -> object | None:
        return self._acro_form


class _StrictCatalog:
    """Catalog whose ``get_acro_form`` takes no args — drives the
    TypeError branch."""

    def __init__(self, acro_form: object | None) -> None:
        self._acro_form = acro_form

    def get_acro_form(self) -> object | None:
        return self._acro_form


class _NoAcroFormCatalog:
    """Catalog without a ``get_acro_form`` method at all."""


class _StubDoc:
    def __init__(self, catalog: object) -> None:
        self._catalog = catalog

    def get_document_catalog(self) -> object:
        return self._catalog


# ----------------------------------------------------------------------
# process(): early-return guards
# ----------------------------------------------------------------------


def test_process_catalog_without_get_acro_form_is_noop() -> None:
    """``getattr(catalog, "get_acro_form", None) is None`` short-circuits."""
    doc = _StubDoc(_NoAcroFormCatalog())
    AcroFormGenerateAppearancesProcessor(doc).process()  # no raise


def test_process_acro_form_none_is_noop() -> None:
    doc = _StubDoc(_StubCatalog(None))
    AcroFormGenerateAppearancesProcessor(doc).process()  # no raise


def test_process_typeerror_fallback_uses_no_arg_get_acro_form() -> None:
    """``get_acro_form(None)`` raises TypeError → falls through to the
    parameterless form."""
    acro = _AcroFormStub()
    doc = _StubDoc(_StrictCatalog(acro))
    AcroFormGenerateAppearancesProcessor(doc).process()
    assert acro.refresh_calls == 1
    assert acro.set_need_calls == [False]


# ----------------------------------------------------------------------
# process(): happy path
# ----------------------------------------------------------------------


def test_process_happy_path_calls_refresh_and_set_need_false() -> None:
    acro = _AcroFormStub()
    doc = _StubDoc(_StubCatalog(acro))
    AcroFormGenerateAppearancesProcessor(doc).process()
    assert acro.refresh_calls == 1
    assert acro.set_need_calls == [False]


def test_process_missing_refresh_method_only_calls_set_need() -> None:
    """``getattr(..., "refresh_appearances", None) is None`` skips refresh
    but still flips ``set_need_appearances``."""
    acro = _AcroFormNoRefresh()
    doc = _StubDoc(_StubCatalog(acro))
    AcroFormGenerateAppearancesProcessor(doc).process()
    assert acro.set_need_calls == [False]


def test_process_missing_set_need_method_only_calls_refresh() -> None:
    acro = _AcroFormNoSetNeed()
    doc = _StubDoc(_StubCatalog(acro))
    AcroFormGenerateAppearancesProcessor(doc).process()
    assert acro.refresh_calls == 1


# ----------------------------------------------------------------------
# process(): error handling on refresh
# ----------------------------------------------------------------------


@pytest.mark.parametrize("exc_type", [OSError, ValueError])
def test_process_swallows_refresh_errors(
    exc_type: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An ``OSError`` / ``ValueError`` raised by ``refresh_appearances``
    is logged at DEBUG and swallowed."""
    acro = _AcroFormStub(raise_in_refresh=exc_type)
    doc = _StubDoc(_StubCatalog(acro))
    with caplog.at_level(
        logging.DEBUG,
        logger="pypdfbox.pdmodel.fixup.processor.acro_form_generate_appearances_processor",
    ):
        AcroFormGenerateAppearancesProcessor(doc).process()  # no raise
    # The DEBUG log line was emitted at least once for the failure path.
    assert any(
        "couldn't generate appearance stream" in rec.getMessage()
        for rec in caplog.records
    )


def test_process_does_not_swallow_unexpected_exceptions() -> None:
    """Exceptions *other than* OSError / ValueError must propagate."""
    acro = _AcroFormStub(raise_in_refresh=RuntimeError)
    doc = _StubDoc(_StubCatalog(acro))
    with pytest.raises(RuntimeError):
        AcroFormGenerateAppearancesProcessor(doc).process()


__all__: list[Any] = []
