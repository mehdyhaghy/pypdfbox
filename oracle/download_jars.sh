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
SHA256="bf70b90aca964bda6f1438d7b87d6f99cfaa9912ba6fcebc0541d9d90ee5ef54"
URL="https://repo1.maven.org/maven2/org/apache/pdfbox/pdfbox-app/${VERSION}/pdfbox-app-${VERSION}.jar"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/jars"
JAR="${DIR}/pdfbox-app-${VERSION}.jar"
mkdir -p "${DIR}"

if [ -f "${JAR}" ]; then
  echo "already present: ${JAR}"
else
  echo "downloading ${URL}"
  curl -sSL -o "${JAR}" "${URL}"
fi

# Integrity check (portable: prefer shasum, fall back to sha256sum).
if command -v shasum >/dev/null 2>&1; then
  GOT="$(shasum -a 256 "${JAR}" | cut -d' ' -f1)"
else
  GOT="$(sha256sum "${JAR}" | cut -d' ' -f1)"
fi
if [ "${GOT}" != "${SHA256}" ]; then
  echo "CHECKSUM MISMATCH for ${JAR}" >&2
  echo "  expected ${SHA256}" >&2
  echo "  got      ${GOT}" >&2
  exit 1
fi
echo "ok: ${JAR} (sha256 verified)"
