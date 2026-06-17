#!/usr/bin/env bash
# Download the Apache PDFBox standalone "app" jar used as a LIVE differential
# oracle for behavioural parity tests. The jar is Apache-2.0 (verified: it
# bundles pdfbox + fontbox + xmpbox + pdfbox-io + commons-logging + tools, all
# Apache-2.0). It is a TEST-ONLY oracle tool — never a runtime dependency, never
# added to pyproject.toml — analogous to the qpdf CLI we already shell out to.
#
# The jar is gitignored (oracle/jars/). Run this once on a machine that has
# Java; the behavioural differential tests skip automatically when it is absent.
set -euo pipefail

VERSION="3.0.7"   # pinned: PDFBox 3.0.x latest stable (matches PROVENANCE baseline)

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/jars"
mkdir -p "${DIR}"

# Each oracle jar: "<maven-artifact> <sha256>". The standalone app jar bundles
# pdfbox + fontbox + pdfbox-io + commons-logging + tools; xmpbox ships as a
# SEPARATE Maven artifact (NOT bundled in pdfbox-app), so probes that import
# org.apache.xmpbox need it on the classpath too — tests/oracle/harness.py
# globs every jar in this dir onto the classpath.
ARTIFACTS=(
  "pdfbox-app bf70b90aca964bda6f1438d7b87d6f99cfaa9912ba6fcebc0541d9d90ee5ef54"
  "xmpbox a5307d87764103e6194bbfb800a8f79acbad2df32d59dabca2252abf923c401a"
)

for entry in "${ARTIFACTS[@]}"; do
  artifact="${entry%% *}"
  sha256="${entry##* }"
  jar="${DIR}/${artifact}-${VERSION}.jar"
  url="https://repo1.maven.org/maven2/org/apache/pdfbox/${artifact}/${VERSION}/${artifact}-${VERSION}.jar"
  if [ -f "${jar}" ]; then
    echo "already present: ${jar}"
  else
    echo "downloading ${url}"
    curl -sSL -o "${jar}" "${url}"
  fi
  if command -v shasum >/dev/null 2>&1; then
    got="$(shasum -a 256 "${jar}" | cut -d' ' -f1)"
  else
    got="$(sha256sum "${jar}" | cut -d' ' -f1)"
  fi
  if [ "${got}" != "${sha256}" ]; then
    echo "CHECKSUM MISMATCH for ${jar}" >&2
    echo "  expected ${sha256}" >&2
    echo "  got      ${got}" >&2
    exit 1
  fi
  echo "ok: ${jar} (sha256 verified)"
done
