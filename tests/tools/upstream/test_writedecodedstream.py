"""Upstream-parity placeholder for ``WriteDecodedDoc``.

Apache PDFBox 3.0/trunk ships no dedicated unit test for
``org.apache.pdfbox.tools.WriteDecodedDoc`` — the tool's coverage at
upstream is implicit (see ``PDFBoxHeadlessTest`` which exercises every
CLI tool against the regression-test corpus). Until our parity harness
imports that integration suite, this file is intentionally empty so the
upstream-test directory layout still reflects "we looked, there was
nothing to port".

When a Java-side ``WriteDecodedDocTest`` does land upstream, port it
here following the conventions in ``CLAUDE.md`` §"Test Porting
Conventions".
"""
from __future__ import annotations
