"""``Version`` class port — prints the pypdfbox / pdfbox version string.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/Version.java
    (lines 34-87)

Module is named ``version_tool`` to avoid colliding with the existing
``pypdfbox/tools/version.py`` argparse subcommand.
"""
from __future__ import annotations

import sys

import pypdfbox


class Version:
    def __init__(self) -> None:
        self.spec_qualified_name: str = "pypdfbox"

    def get_version(self) -> list[str]:
        """Mirror of upstream ``Version.getVersion()`` — returns a list to
        match the Java ``String[]`` signature."""
        version = getattr(pypdfbox, "__version__", None)
        if version is not None:
            return [f"{self.spec_qualified_name} [{version}]"]
        return ["unknown"]

    def call(self) -> int:
        sys.stdout.write(self.get_version()[0] + "\n")
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        return Version().call()


if __name__ == "__main__":
    sys.exit(Version.main(sys.argv[1:]))
