"""Shared fixtures for streampane.tooltip tests.

The tooltip subsystem is pure logic (operator-row -> structured
payload), so no Tk display is required. The fixture below mirrors the
pattern used by other debugger test subpackages so a future widget
test can be added without restructuring.
"""

from __future__ import annotations
