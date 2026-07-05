"""Live-oracle differential for the popup + markup-reply wiring surface.

Wave 1598, agent A. Runs ``PopupReplyWiringProbe`` (Apache PDFBox 3.0.7)
and diffs every ``CASE <name> <value>`` line against the identical
projection computed from pypdfbox by
``test_popup_reply_wiring_fuzz_wave1598.build_python_cases``.

Also cross-checks the probe output against the pinned ``EXPECTED`` table in
the sibling module so a jar upgrade that shifts upstream behaviour is
flagged even before the pypdfbox side diverges.
"""

from __future__ import annotations

import pytest

from tests.oracle.harness import requires_oracle, run_probe_text
from tests.pdmodel.interactive.annotation.test_popup_reply_wiring_fuzz_wave1598 import (
    EXPECTED,
    build_python_cases,
)

pytestmark = requires_oracle


def _parse_cases(output: str) -> dict[str, str]:
    cases: dict[str, str] = {}
    for line in output.splitlines():
        if not line.startswith("CASE "):
            continue
        # "CASE <name> <value-possibly-with-spaces>"
        rest = line[len("CASE ") :]
        name, _, value = rest.partition(" ")
        cases[name] = value
    return cases


@pytest.fixture(scope="module")
def java_cases() -> dict[str, str]:
    return _parse_cases(run_probe_text("PopupReplyWiringProbe"))


@pytest.fixture(scope="module")
def python_cases() -> dict[str, str]:
    return build_python_cases()


def test_probe_output_matches_pinned_table(java_cases: dict[str, str]) -> None:
    assert java_cases == EXPECTED


@pytest.mark.parametrize("name", sorted(EXPECTED), ids=sorted(EXPECTED))
def test_pypdfbox_matches_live_pdfbox(
    name: str, java_cases: dict[str, str], python_cases: dict[str, str]
) -> None:
    assert python_cases[name] == java_cases[name]
