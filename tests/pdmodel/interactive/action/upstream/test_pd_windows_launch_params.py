"""Ported upstream tests for ``PDWindowsLaunchParams``.

No upstream JUnit test for ``PDWindowsLaunchParams`` exists in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/action/`` on the
PDFBox 3.0 branch (as of the snapshot consulted while porting this module).
The only upstream test in that package is ``PDActionURITest.java``.

Hand-written coverage lives in
``tests/pdmodel/interactive/action/test_pd_windows_launch_params.py``.
"""

from __future__ import annotations

import pytest

pytest.skip(
    "No upstream JUnit test for PDWindowsLaunchParams in pdfbox 3.0; "
    "see hand-written tests in test_pd_windows_launch_params.py.",
    allow_module_level=True,
)
