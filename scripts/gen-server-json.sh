#!/usr/bin/env bash
#
# Generate server.json from server.template.json, auto-computing the
# MCPB SHA-256. Run this from your release CI (or locally) so fileSha256
# is never hand-maintained.
#
# Usage:
#   ./gen-server-json.sh <path-to.mcpb> <release-tag>
#
# Example:
#   ./gen-server-json.sh goodsender.mcpb v0.2.1
#
# Env overrides:
#   TEMPLATE  (default: server.template.json)
#   OUT       (default: server.json)

set -euo pipefail

MCPB_PATH="${1:?usage: gen-server-json.sh <path-to.mcpb> <release-tag>}"
RELEASE_TAG="${2:?usage: gen-server-json.sh <path-to.mcpb> <release-tag>}"
TEMPLATE="${TEMPLATE:-server.template.json}"
OUT="${OUT:-server.json}"

# Version = release tag without a leading "v" (v0.2.1 -> 0.2.1)
VERSION="${RELEASE_TAG#v}"

# Compute SHA-256 (prefer sha256sum, fall back to openssl)
if command -v sha256sum >/dev/null 2>&1; then
  SHA="$(sha256sum "$MCPB_PATH" | awk '{print $1}')"
else
  SHA="$(openssl dgst -sha256 "$MCPB_PATH" | awk '{print $NF}')"
fi

sed -e "s|__VERSION__|${VERSION}|g" \
    -e "s|__RELEASE_TAG__|${RELEASE_TAG}|g" \
    -e "s|__MCPB_SHA256__|${SHA}|g" \
    "$TEMPLATE" > "$OUT"

echo "Wrote ${OUT}"
echo "  version : ${VERSION}"
echo "  tag     : ${RELEASE_TAG}"
echo "  sha256  : ${SHA}"
