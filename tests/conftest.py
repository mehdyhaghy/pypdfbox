"""Top-level pytest configuration for pypdfbox.

Houses the cross-cutting hooks that need to apply to every test
module:

* a custom ``serial`` marker for tests that must not run alongside
  other Tk-using tests (we don't enforce serialization here -- pytest
  has no built-in worker pool -- but the marker lets users select /
  deselect easily, e.g. ``pytest -m 'not serial'``);
* an opt-out for Tk-based tests via the ``PYPDFBOX_SKIP_TK`` env var.
  Setting ``PYPDFBOX_SKIP_TK=1`` makes every ``tk_root`` fixture
  (defined across the debugger subpackage conftests) skip the test.
  This is useful for headless CI and for running multiple ``pytest``
  invocations concurrently from independent shells on macOS, where
  two processes contending for the same WindowServer connection can
  push one of them into a fatal NSAlert modal loop (observed during
  waves 1300-1302).

The actual ``tk_root`` fixtures live under ``tests/debugger/*/conftest.py``;
this module only provides the global skip hook and marker registration.
"""

from __future__ import annotations

import os
import pathlib

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "serial: test must not run concurrently with other Tk tests "
        "(advisory; use ``pytest -m 'not serial'`` to deselect).",
    )
    config.addinivalue_line(
        "markers",
        "live_oracle: test shells out to Java PDFBox via "
        "``tests/oracle/harness.py``. Applied automatically (see "
        "``pytest_collection_modifyitems`` below) and deselected by "
        "default in ``pyproject.toml``; run with ``pytest -m live_oracle``.",
    )


# Auto-marking the live-differential tests
# ---------------------------------------
# ~44 hand-written test modules embed a live differential against
# ``archive/oracle/jars/pdfbox-app-*.jar``. They are NOT under a
# ``*/oracle/*`` path, so the ``--ignore-glob='*/oracle/*'`` filter never
# excluded them, and each one pays JVM start-up -- which is what turned the
# "fast" suite into a multi-minute, CPU-saturating run.
#
# Detection is by module source rather than by a decorator because the
# modules reach the harness through several idioms (``requires_oracle``,
# a bare ``run_probe``, a try/except import fallback). One substring check
# per file, cached, catches all of them and cannot drift out of sync with
# a decorator someone forgets to apply.
_ORACLE_HARNESS_IMPORT = "oracle.harness"
_uses_live_oracle: dict[str, bool] = {}


def _module_uses_live_oracle(path: pathlib.Path) -> bool:
    key = str(path)
    cached = _uses_live_oracle.get(key)
    if cached is None:
        try:
            cached = _ORACLE_HARNESS_IMPORT in path.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - unreadable/synthetic module
            cached = False
        _uses_live_oracle[key] = cached
    return cached


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = getattr(item, "path", None)
        if path is not None and _module_uses_live_oracle(path):
            item.add_marker(pytest.mark.live_oracle)


@pytest.fixture(autouse=True, scope="session")
def _pypdfbox_skip_tk_env_var() -> None:
    """No-op session fixture; exists only to centralise the env-var
    contract documented at the top of this module. Actual skipping is
    performed in the per-subpackage ``tk_root`` fixtures, which call
    :func:`should_skip_tk` (re-exported below).
    """
    return None


def should_skip_tk() -> bool:
    """Return ``True`` if the caller should skip Tk-based tests.

    Triggered by ``PYPDFBOX_SKIP_TK=1`` in the environment. Used by
    ``tk_root`` fixtures throughout ``tests/debugger/`` so callers can
    opt out of Tk-heavy tests without editing every conftest.
    """
    return os.environ.get("PYPDFBOX_SKIP_TK", "") == "1"
