#!/usr/bin/env bash
#
# Tests for scripts/check-gemini-extension.sh, the sync-gemini-extension job in
# publish-release.yml, and the GEMINI.md / README facts of the Gemini CLI
# extension. Plain Bash; run from anywhere: bash tests/check-gemini-extension.test.sh

set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
check="$root/scripts/check-gemini-extension.sh"
release_wf="$root/.github/workflows/publish-release.yml"
validate_wf="$root/.github/workflows/validate-gemini-extension.yml"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

failures=0
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; failures=$((failures + 1)); }

# run <args...>: runs the check script; sets rc, out, err
run() {
  out="$(bash "$check" "$@" 2>"$tmp/err")"
  rc=$?
  err="$(cat "$tmp/err")"
}

# expect <desc> <rc> <stderr-substring|-> -- args...
expect() {
  local desc="$1" want_rc="$2" want_err="$3"
  shift 4
  run "$@"
  if [[ "$rc" -ne "$want_rc" ]]; then
    fail "$desc (exit $rc, want $want_rc; stderr: $err)"
  elif [[ "$want_err" != "-" && "$err" != *"$want_err"* ]]; then
    fail "$desc (stderr lacks '$want_err': $err)"
  elif [[ "$want_rc" -eq 0 && "$out" != "ok: "* ]]; then
    fail "$desc (stdout lacks 'ok: ': $out)"
  else
    pass "$desc"
  fi
}

# fixture <name> <jq-filter>: the committed manifest transformed by the filter,
# in its own directory next to a GEMINI.md.
fixture() {
  mkdir -p "$tmp/$1"
  cp "$root/GEMINI.md" "$tmp/$1/GEMINI.md"
  jq --indent 2 "$2" "$root/gemini-extension.json" >"$tmp/$1/gemini-extension.json"
  echo "$tmp/$1/gemini-extension.json"
}

# --- Scenario 1: the committed manifest ------------------------------------
expect "committed manifest is valid" 0 - -- "$root/gemini-extension.json"
if [[ "$(jq -c '[.name, .description, .mcpServers.goodsender.httpUrl, .contextFileName, (keys|sort)]' "$root/gemini-extension.json")" \
  == '["goodsender","Publish blog posts, send newsletters and emails from Gemini CLI, Claude, Codex and ChatGPT.","https://mcp.goodsender.com/","GEMINI.md",["contextFileName","description","mcpServers","name","version"]]' ]]; then
  pass "committed manifest has exactly the five expected keys and values"
else
  fail "committed manifest content"
fi
if jq --indent 2 . "$root/gemini-extension.json" | cmp -s - "$root/gemini-extension.json"; then
  pass "committed manifest is jq --indent 2 formatted"
else
  fail "committed manifest is not jq --indent 2 formatted"
fi

# --- Scenario 2: release tag match / mismatch ------------------------------
v="$(jq -r .version "$root/gemini-extension.json")"
expect "tag v$v matches" 0 - -- "$root/gemini-extension.json" "v$v"
expect "bare tag $v matches" 0 - -- "$root/gemini-extension.json" "$v"
expect "tag v99.0.0 mismatches" 1 "version-tag" -- "$root/gemini-extension.json" v99.0.0
if [[ "$err" == *"99.0.0"* && "$err" == *"$v"* ]]; then
  pass "mismatch error names both versions"
else
  fail "mismatch error names both versions ($err)"
fi

# --- Scenario 3: each invalid class ----------------------------------------
expect "name with uppercase" 1 "name:" -- "$(fixture upper '.name = "GoodSender"')"
expect "name with underscore" 1 "name:" -- "$(fixture under '.name = "good_sender"')"
expect "name with space" 1 "name:" -- "$(fixture space '.name = "good sender"')"
expect "version not semver" 1 "version:" -- "$(fixture semver '.version = "0.9"')"
expect "prerelease version ok" 0 - -- "$(fixture pre '.version = "1.0.0-rc1+build.5"')"
expect "httpUrl not https" 1 "mcpServers.goodsender.https" -- "$(fixture http '.mcpServers.goodsender.httpUrl = "http://mcp.goodsender.com/"')"
expect "url not https" 1 "mcpServers.goodsender.https" -- "$(fixture sse '.mcpServers.goodsender = {url: "http://x.example/sse"}')"
expect "trust key in server" 1 "mcpServers.goodsender.trust" -- "$(fixture trust '.mcpServers.goodsender.trust = true')"
expect "missing context file" 1 "contextFileName:" -- "$(fixture ctx '.contextFileName = "MISSING.md"')"
expect "undocumented top-level key" 1 "keys:" -- "$(fixture keys '.homepage = "https://goodsender.com"')"
expect "missing name" 1 "name:" -- "$(fixture noname 'del(.name)')"
expect "missing version" 1 "version:" -- "$(fixture noversion 'del(.version)')"
expect "missing description" 1 "description:" -- "$(fixture nodesc 'del(.description)')"
expect "empty mcpServers" 1 "mcpServers:" -- "$(fixture nosrv '.mcpServers = {}')"
mkdir -p "$tmp/badjson" && echo '{"name":' >"$tmp/badjson/gemini-extension.json"
expect "invalid JSON" 1 "json:" -- "$tmp/badjson/gemini-extension.json"

three="$(fixture three '.name = "Bad_Name" | .mcpServers.goodsender.trust = true | .extra = 1')"
run "$three"
lines="$(printf '%s\n' "$err" | grep -c .)"
if [[ "$rc" -eq 1 && "$lines" -eq 3 && "$err" == *"name:"* && "$err" == *".trust"* && "$err" == *"keys:"* ]]; then
  pass "three faults reported as three stderr lines"
else
  fail "three faults (exit $rc, $lines lines: $err)"
fi

# --- usage errors ------------------------------------------------------------
expect "no arguments is a usage error" 2 "usage" --
expect "--write without a tag is a usage error" 2 "usage" -- --write "$root/gemini-extension.json"
expect "missing file" 2 "cannot read" -- "$tmp/nope.json"
PATH="$tmp/empty-path" "$BASH" "$check" "$root/gemini-extension.json" 2>"$tmp/err"
rc=$?
if [[ "$rc" -eq 2 ]] && grep -q "jq is required" "$tmp/err"; then pass "missing jq exits 2"; else fail "missing jq (exit $rc)"; fi

# --- Scenario 4: --write stamps and is idempotent ---------------------------
w="$(fixture write '.')"
expect "--write v1.2.3 succeeds" 0 - -- --write "$w" v1.2.3
if [[ "$(jq -r .version "$w")" == "1.2.3" ]]; then pass "--write stamped 1.2.3"; else fail "--write stamped 1.2.3"; fi
if jq --indent 2 . "$w" | cmp -s - "$w"; then pass "--write output is jq --indent 2 formatted"; else fail "--write formatting"; fi
cp "$w" "$tmp/write.before"
expect "--write v1.2.3 again succeeds" 0 - -- --write "$w" v1.2.3
if cmp -s "$w" "$tmp/write.before"; then pass "second --write is byte-identical"; else fail "second --write changed the file"; fi
if [[ -z "$(find "$tmp/write" -name 'gemini-extension.json.*')" ]]; then pass "--write leaves no temp file"; else fail "--write left a temp file"; fi

# --- Scenario 5: release workflow job ---------------------------------------
job="$(awk '/^  sync-gemini-extension:/{f=1; print; next} f && /^  [A-Za-z0-9_-]+:/{f=0} f' "$release_wf")"
if [[ -n "$job" ]]; then pass "publish-release.yml has sync-gemini-extension"; else fail "publish-release.yml lacks sync-gemini-extension"; fi
for needle in "needs: publish-container" "if: needs.publish-container.outputs.stage == 'prod'" \
  "contents: write" "ref: main" "check-gemini-extension.sh --write gemini-extension.json" "git push origin HEAD:main"; do
  if [[ "$job" == *"$needle"* ]]; then pass "sync job: $needle"; else fail "sync job lacks: $needle"; fi
done
if grep -A3 '^permissions:' "$release_wf" | grep -q 'contents: read'; then
  pass "workflow-level permissions stay contents: read"
else
  fail "workflow-level permissions changed"
fi

if command -v ruby >/dev/null 2>&1; then
  for wf in "$release_wf" "$validate_wf"; do
    if ruby -ryaml -e 'YAML.load_file(ARGV[0])' "$wf" 2>"$tmp/yaml"; then
      pass "YAML parses: ${wf#"$root"/}"
    else
      fail "YAML parse: ${wf#"$root"/} ($(cat "$tmp/yaml"))"
    fi
  done
else
  echo "WARN ruby not found; skipped YAML parse of the workflows"
fi

# --- Scenarios 7-8: docs ------------------------------------------------------
if [[ -f "$root/GEMINI.md" && "$(wc -l <"$root/GEMINI.md")" -le 40 ]]; then
  pass "GEMINI.md exists and is at most 40 lines"
else
  fail "GEMINI.md missing or longer than 40 lines"
fi
for needle in confirm_action publish_post broadcast_post reannounce_post enqueue_ send_ delete_ draft; do
  if grep -q -- "$needle" "$root/GEMINI.md"; then pass "GEMINI.md mentions $needle"; else fail "GEMINI.md lacks $needle"; fi
done
for needle in '### Gemini CLI' 'gemini extensions install https://github.com/good-sender/mcp' '/mcp auth goodsender' 'Antigravity CLI'; do
  if grep -qF -- "$needle" "$root/README.md"; then pass "README has: $needle"; else fail "README lacks: $needle"; fi
done

echo
if [[ "$failures" -gt 0 ]]; then
  echo "$failures check(s) failed"
  exit 1
fi
echo "all checks passed"
