"""Wave 1351 coverage-boost tests for :class:`LucenePDFDocument`.

Targets the URL-style branch inside :meth:`create_uid` (lines 131-132)
- exercised when ``time`` is omitted *and* ``file_or_url`` is not a
``str``/``Path`` (mirrors upstream's ``createUID(URL u)`` overload
where the timestamp defaults to ``0``).
"""

from __future__ import annotations

from pypdfbox.examples.lucene.lucene_pdf_document import LucenePDFDocument


class _UrlLike:
    """Stand-in for a ``java.net.URL`` - has a ``__str__`` but is
    neither ``str`` nor ``pathlib.Path``."""

    def __init__(self, value: str) -> None:
        self._value = value

    def __str__(self) -> str:
        return self._value


def test_create_uid_url_like_without_time_defaults_to_epoch() -> None:
    """Non-string-non-Path ``file_or_url`` with ``time=None`` triggers
    the URL-like branch: ``time`` is forced to ``0`` and ``str()`` is
    used to derive the key (lines 131-132)."""
    url = _UrlLike("https://example.com/foo.pdf")
    uid = LucenePDFDocument.create_uid(url)  # type: ignore[arg-type]
    # ``time=0`` → epoch timestamp formatting.
    assert uid.endswith("19700101000000")
    # The URL string survives into the UID (modulo separator
    # substitution, which leaves the ``https://`` scheme intact since
    # ``:`` is not ``os.sep[0]``).
    assert "example.com" in uid
