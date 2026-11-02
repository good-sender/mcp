#!/usr/bin/env bash
#
# Validate gemini-extension.json against the Gemini CLI extensions gallery rules
# (https://geminicli.com/docs/extensions/reference/ and /releasing/), and
# optionally stamp a release version into it.
#
# Usage:
#   ./check-gemini-extension.sh [--write] <manifest> [<release-tag>]
#
#   <release-tag>  v-prefixed or bare; when given, .version must equal it (sans v).
#   --write        requires <release-tag>; sets .version to it first, rewriting
#                  the file only when the value differs (byte-identical otherwise).
#
# Exit codes: 0 all rules passed · 1 one or more rules failed (every failure is
# printed to stderr, one line each) · 2 usage error, unreadable file, jq missing.
#
# Used by .github/workflows/publish-release.yml (sync-gemini-extension, prod
# releases) and .github/workflows/validate-gemini-extension.yml (PRs).

set -euo pipefail

usage() {
  echo "usage: check-gemini-extension.sh [--write] <manifest> [<release-tag>]" >&2
  exit 2
}

write=0
if [[ "${1:-}" == "--write" ]]; then
  write=1
  shift
fi
[[ $# -ge 1 && $# -le 2 ]] || usage
manifest="$1"
tag="${2:-}"
[[ "$write" -eq 0 || -n "$tag" ]] || usage

command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 2; }
[[ -f "$manifest" && -r "$manifest" ]] || { echo "cannot read $manifest" >&2; exit 2; }

if ! jq -e . "$manifest" >/dev/null 2>&1; then
  echo "json: $manifest is not valid JSON" >&2
  exit 1
fi

want="${tag#v}"
if [[ "$write" -eq 1 && "$(jq -r '.version // empty' "$manifest")" != "$want" ]]; then
  tmp="$(mktemp "${manifest}.XXXXXX")"
  jq --indent 2 --arg v "$want" '.version = $v' "$manifest" >"$tmp"
  mv "$tmp" "$manifest"
fi

errors=()
fail() { errors+=("$1"); }
q() { jq -r "$1" "$manifest"; }

semver='^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$'
allowed='["name","version","description","mcpServers","contextFileName","excludeTools","settings","migratedTo","plan","themes"]'

name="$(q 'if (.name|type) == "string" then .name else "" end')"
[[ "$name" =~ ^[a-z0-9-]+$ ]] \
  || fail "name: must be a string of lowercase letters, digits and dashes (got '$(q '.name')')"

version="$(q 'if (.version|type) == "string" then .version else "" end')"
[[ "$version" =~ $semver ]] \
  || fail "version: must be MAJOR.MINOR.PATCH[-prerelease][+build] (got '$(q '.version')')"

if [[ -n "$tag" && "$version" != "$want" ]]; then
  fail "version-tag: manifest version ${version:-<none>} does not match release tag ${tag} (${want})"
fi

[[ "$(q '(.description|type) == "string" and (.description|length) > 0')" == "true" ]] \
  || fail "description: must be a non-empty string"

if [[ "$(q '(.mcpServers|type) == "object" and (.mcpServers|length) > 0')" != "true" ]]; then
  fail "mcpServers: must be an object with at least one server"
else
  while IFS= read -r key; do
    fail "mcpServers.${key}.https: httpUrl/url must start with https://"
  done < <(q '.mcpServers | to_entries[]
    | select([.value.httpUrl?, .value.url?] | map(select(. != null))
             | any(type != "string" or (startswith("https://") | not)))
    | .key')
  while IFS= read -r key; do
    fail "mcpServers.${key}.trust: 'trust' is not supported in extensions"
  done < <(q '.mcpServers | to_entries[] | select(.value | type == "object" and has("trust")) | .key')
fi

if [[ "$(q 'has("contextFileName")')" == "true" ]]; then
  ctx="$(q 'if (.contextFileName|type) == "string" then .contextFileName else "" end')"
  if [[ -z "$ctx" || ! -f "$(dirname "$manifest")/$ctx" ]]; then
    fail "contextFileName: '$(q '.contextFileName')' does not exist next to $manifest"
  fi
fi

extra="$(jq -r --argjson ok "$allowed" '(keys - $ok) | join(", ")' "$manifest")"
[[ -z "$extra" ]] || fail "keys: undocumented top-level key(s): $extra"

if [[ ${#errors[@]} -gt 0 ]]; then
  printf '%s\n' "${errors[@]}" >&2
  exit 1
fi
echo "ok: $manifest ($name $version)"
