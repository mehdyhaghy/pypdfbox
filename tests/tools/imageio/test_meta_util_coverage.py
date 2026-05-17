"""Coverage-boost tests for ``pypdfbox.tools.imageio.meta_util``.

Targets the active ``debug_log_metadata`` branches: the duck-typed
``to_xml`` path, the ``str(metadata)`` fallback, the exception-swallow
path, and the static-only constructor guard.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.tools.imageio.meta_util import MetaUtil

# ---------- Static-only ctor & constants ---------------------------------


def test_constants_are_published_at_class_level() -> None:
    assert MetaUtil.SUN_TIFF_FORMAT == "com_sun_media_imageio_plugins_tiff_image_1.0"
    assert MetaUtil.JPEG_NATIVE_FORMAT == "javax_imageio_jpeg_image_1.0"
    assert MetaUtil.STANDARD_METADATA_FORMAT == "javax_imageio_1.0"


def test_constructor_raises_type_error() -> None:
    with pytest.raises(TypeError, match="static-only"):
        MetaUtil()


# ---------- debug_log_metadata: disabled-debug short-circuit -------------


def test_debug_log_metadata_short_circuits_when_debug_disabled(caplog) -> None:
    # Default level (WARNING) -> debug is disabled, function must return
    # immediately without touching the metadata at all. We assert the
    # metadata's ``to_xml`` is not called.

    class _SpyMeta:
        def __init__(self) -> None:
            self.calls = 0

        def to_xml(self, fmt: str) -> str:
            self.calls += 1
            return "<root/>"

    meta = _SpyMeta()
    with caplog.at_level(logging.WARNING, logger="pypdfbox.tools.imageio.meta_util"):
        MetaUtil.debug_log_metadata(meta, MetaUtil.STANDARD_METADATA_FORMAT)
    assert meta.calls == 0


# ---------- debug_log_metadata: happy path with to_xml ------------------


def test_debug_log_metadata_pretty_prints_metadata_via_to_xml(caplog) -> None:
    class _Meta:
        def to_xml(self, fmt: str) -> str:
            assert fmt == MetaUtil.SUN_TIFF_FORMAT
            return "<root><child a='1'/></root>"

    with caplog.at_level(logging.DEBUG, logger="pypdfbox.tools.imageio.meta_util"):
        MetaUtil.debug_log_metadata(_Meta(), MetaUtil.SUN_TIFF_FORMAT)

    records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert records, "Expected at least one DEBUG record"
    msg = records[-1].getMessage()
    assert "root" in msg
    assert "child" in msg


# ---------- debug_log_metadata: str fallback when no to_xml -------------


def test_debug_log_metadata_falls_back_to_str_when_no_to_xml(caplog) -> None:
    class _PlainMeta:
        def __str__(self) -> str:
            return "<plain/>"

    with caplog.at_level(logging.DEBUG, logger="pypdfbox.tools.imageio.meta_util"):
        MetaUtil.debug_log_metadata(
            _PlainMeta(), MetaUtil.STANDARD_METADATA_FORMAT
        )

    debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("plain" in r.getMessage() for r in debug_records)


# ---------- debug_log_metadata: exception-swallow path ------------------


def test_debug_log_metadata_logs_error_on_invalid_xml(caplog) -> None:
    """Malformed XML triggers ``parseString``'s exception, which is
    captured by the broad ``except`` and logged as an ERROR instead of
    propagating.
    """

    class _BadMeta:
        def to_xml(self, fmt: str) -> str:
            return "not well-formed xml"

    with caplog.at_level(logging.DEBUG, logger="pypdfbox.tools.imageio.meta_util"):
        # Must not raise.
        MetaUtil.debug_log_metadata(_BadMeta(), MetaUtil.JPEG_NATIVE_FORMAT)

    err_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert err_records, "Expected ERROR record on malformed XML"


def test_debug_log_metadata_logs_error_when_to_xml_raises(caplog) -> None:
    class _Boom:
        def to_xml(self, fmt: str) -> str:
            raise RuntimeError("blast")

    with caplog.at_level(logging.DEBUG, logger="pypdfbox.tools.imageio.meta_util"):
        MetaUtil.debug_log_metadata(_Boom(), MetaUtil.STANDARD_METADATA_FORMAT)

    err_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert err_records
