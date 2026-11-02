#!/usr/bin/env python3
"""Build and validate the GoodSender OpenAI Plugin Directory package.

Usage:
  build.py --version <v1.2.3|1.2.3> [--tools <tools.json>] [--out-dir dist]
           [--release-notes-file <file>] [--demo-recording-url <https-url>]
           [--source openai-plugin] [--check-only]

Reads the package sources in openai-plugin/ (manifest template, mcp.json,
skills, icons, test cases, release notes, annotation wording overrides),
stamps the version, validates everything against the OpenAI submission rules
(https://developers.openai.com/plugins/deploy/submission and
.../submission-errors), and writes to --out-dir:

  goodsender-openai-plugin-<version>.zip   the package to upload
  plugin.json                              the stamped manifest (for review)
  TEST_CASES.md                            the review test cases, readable
  ANNOTATIONS.md, annotations.json         per-tool hint justifications,
                                           generated from --tools (the
                                           released server's tools/list)

--tools is the output of list_tools.py. Without it the package is still
validated and built, but no annotation justifications are generated and the
test cases' tool names are not checked against the server.

Every problem is reported before exiting non-zero. Standard library only.
"""

import argparse
import json
import os
import re
import struct
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PREFIX = "goodsender-openai-plugin"
AGENT_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AGENT_MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
CATEGORIES = {
    "Productivity", "Creativity", "Developer Tools", "Business & Operations",
    "Data & Analytics", "Communication", "Education & Research", "Security",
    "Finance", "Healthcare", "Travel", "Entertainment", "Other",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MIN_ICON_PX, MAX_ICON_PX = 48, 4096
POSITIVE_CASES, NEGATIVE_CASES = 5, 3
CASE_KEYS = {"description", "prompt", "tools_triggered", "expected_behavior",
             "file_attachment_urls", "expected_output_url"}
FORBIDDEN_KEYS = {"test_credentials", "reviewer_instructions", "clientSecret"}
HINTS = ("readOnlyHint", "destructiveHint", "openWorldHint")
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
NAME = re.compile(r"^(?!.*--)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)

# Generic justification wording, keyed by hint and value. A tool's own wording
# in openai-plugin/annotation-overrides.json replaces the generic text.
GENERIC_JUSTIFICATION = {
    ("readOnlyHint", True): "Only reads data; it creates, changes, sends and publishes nothing.",
    ("readOnlyHint", False): "Writes data: it creates, changes, sends or publishes something.",
    ("destructiveHint", False, "read"): "A read-only tool cannot delete, overwrite, publish or send anything.",
    ("destructiveHint", False, "write"): "An additive write: it adds data without deleting or overwriting anything, and publishes and sends nothing.",
    ("destructiveHint", True): "Its effect deletes or overwrites existing data, changes the live site, or publishes or sends something that cannot be recalled.",
    ("openWorldHint", False, "read"): "It reads only the user's private GoodSender workspace or static documentation.",
    ("openWorldHint", False, "write"): "Its effect stays inside the user's private GoodSender workspace.",
    ("openWorldHint", True): "Its effect reaches the public internet or a third party (the public blog, an email inbox, a social network or DNS).",
}


class Problems(list):
    def add(self, where, message):
        self.append(f"{where}: {message}")


# ---------------------------------------------------------------- text rules

def _bad_chars(text, allow_newlines):
    for ch in text:
        if ch in "\n" and allow_newlines:
            continue
        if ch in "  ":
            return True
        if unicodedata.category(ch) in ("Cc", "Cf"):
            return True
    return False


def check_text(problems, where, value, limit, *, required=True, single_line=True):
    if value is None:
        if required:
            problems.add(where, "is required")
        return
    if not isinstance(value, str):
        problems.add(where, "must be a string")
        return
    if not value.strip():
        problems.add(where, "must not be empty or whitespace only")
        return
    if len(value) > limit:
        problems.add(where, f"is {len(value)} characters; the limit is {limit}")
    if single_line and ("\n" in value or "\r" in value):
        problems.add(where, "must fit on one line")
    if _bad_chars(value, allow_newlines=not single_line):
        problems.add(where, "contains control or invisible formatting characters")


def check_https_url(problems, where, value, limit, *, required=True):
    if value is None:
        if required:
            problems.add(where, "is required")
        return
    if not isinstance(value, str) or not value:
        problems.add(where, "must be a non-empty string")
        return
    if len(value) > limit:
        problems.add(where, f"is {len(value)} characters; the limit is {limit}")
    parts = urlsplit(value)
    if parts.scheme != "https":
        problems.add(where, f"must be an HTTPS URL (got {value!r})")
    if not parts.hostname:
        problems.add(where, f"must include a host (got {value!r})")
    if parts.username is not None or parts.password is not None:
        problems.add(where, "must not embed credentials")
    if any(c.isspace() for c in value) or _bad_chars(value, allow_newlines=False):
        problems.add(where, "contains whitespace or control characters")


def _luminance(hex_color):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def find_forbidden_keys(node, path="$"):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                found.append(f"{path}.{key}")
            found.extend(find_forbidden_keys(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found.extend(find_forbidden_keys(value, f"{path}[{i}]"))
    return found


# -------------------------------------------------------------------- images

def image_size(data, suffix):
    """Return (width, height) of a PNG/JPEG/WebP/SVG image, or raise ValueError."""
    if suffix == ".svg":
        return _svg_size(data)
    if suffix == ".png":
        if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ValueError("not a PNG file (extension and content differ)")
        return struct.unpack(">II", data[16:24])
    if suffix in (".jpg", ".jpeg"):
        if data[:2] != b"\xff\xd8":
            raise ValueError("not a JPEG file (extension and content differ)")
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return width, height
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
        raise ValueError("JPEG has no frame header")
    if suffix == ".webp":
        if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            raise ValueError("not a WebP file (extension and content differ)")
        chunk = data[12:16]
        if chunk == b"VP8X":
            w = int.from_bytes(data[24:27], "little") + 1
            h = int.from_bytes(data[27:30], "little") + 1
            return w, h
        if chunk == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        raise ValueError("unrecognised WebP chunk")
    raise ValueError("unsupported image format; use .png, .jpg, .jpeg, .webp or .svg")


def _number(value, what):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"SVG {what} must be numeric without units (got {value!r})")
    if not number > 0 or number == float("inf"):
        raise ValueError(f"SVG {what} must be positive")
    return number


def _svg_size(data):
    try:
        root = ET.fromstring(data.decode("utf-8"))
    except (UnicodeDecodeError, ET.ParseError) as error:
        raise ValueError(f"SVG is not valid UTF-8 XML: {error}")
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("SVG root element must be <svg>")
    sizes = []
    view_box = root.get("viewBox")
    if view_box is not None:
        fields = view_box.replace(",", " ").split()
        if len(fields) != 4:
            raise ValueError("SVG viewBox must have four numbers")
        sizes.append((_number(fields[2], "viewBox width"), _number(fields[3], "viewBox height")))
    if root.get("width") is not None or root.get("height") is not None:
        sizes.append((_number(root.get("width"), "width"), _number(root.get("height"), "height")))
    if not sizes:
        raise ValueError("SVG must define a numeric viewBox or numeric width and height")
    for w, h in sizes:
        if w != h:
            raise ValueError(f"SVG dimensions must be square (got {w:g}x{h:g})")
    return min(sizes)


def check_icon(problems, source, where, rel_path, *, required):
    if rel_path is None:
        if required:
            problems.add(where, "is required")
        return None
    if not isinstance(rel_path, str) or not rel_path.startswith("./"):
        problems.add(where, f"must be a ./-relative path (got {rel_path!r})")
        return None
    relative = rel_path[2:]
    if not relative or ".." in Path(relative).parts or "\\" in relative:
        problems.add(where, f"must stay inside the package (got {rel_path!r})")
        return None
    path = source / relative
    if not path.is_file():
        problems.add(where, f"references a missing file {rel_path}")
        return None
    data = path.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        problems.add(where, f"{rel_path} is {len(data)} bytes; the limit is 5 MiB")
    try:
        width, height = image_size(data, path.suffix.lower())
    except ValueError as error:
        problems.add(where, f"{rel_path}: {error}")
        return relative
    if width != height:
        problems.add(where, f"{rel_path} must be square (got {width:g}x{height:g})")
    if min(width, height) < MIN_ICON_PX:
        problems.add(where, f"{rel_path} must be at least {MIN_ICON_PX}x{MIN_ICON_PX} (got {width:g}x{height:g})")
    if path.suffix.lower() != ".svg" and max(width, height) > MAX_ICON_PX:
        problems.add(where, f"{rel_path} must be at most {MAX_ICON_PX}x{MAX_ICON_PX} (got {width}x{height})")
    return relative


# -------------------------------------------------------------------- skills

def parse_skill(text):
    """Return (frontmatter dict of simple `key: value` lines, body) or raise ValueError."""
    if not text.startswith("---\n"):
        raise ValueError("must start with YAML front matter between --- lines")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("YAML front matter is not closed with ---")
    meta = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line or line.startswith((" ", "\t")):
            raise ValueError(f"front matter supports only `key: value` lines (got {line!r})")
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[end + 4:].lstrip("-").strip()


def check_skills(problems, source, plugin_name):
    skills_dir = source / "skills"
    files = []
    if not skills_dir.is_dir():
        problems.add("skills/", "the package needs at least one skill (archive_plugin_files_missing)")
        return files
    names = set()
    for entry in sorted(skills_dir.iterdir()):
        where = f"skills/{entry.name}"
        if entry.is_symlink() or not entry.is_dir() or entry.name.startswith("."):
            problems.add(where, "each skill must be a real, non-hidden directory containing SKILL.md")
            continue
        manifest = entry / "SKILL.md"
        if not manifest.is_file():
            problems.add(where, "is missing SKILL.md")
            continue
        try:
            meta, body = parse_skill(manifest.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            problems.add(f"{where}/SKILL.md", str(error))
            continue
        check_text(problems, f"{where}/SKILL.md name", meta.get("name"), 64)
        check_text(problems, f"{where}/SKILL.md description", meta.get("description"), 1024)
        if not body:
            problems.add(f"{where}/SKILL.md", "instructions must not be empty")
        name = meta.get("name", "")
        if name in names:
            problems.add(f"{where}/SKILL.md", f"duplicate skill name {name!r}")
        names.add(name)
        if len(f"{plugin_name}:{name}") > 64:
            problems.add(f"{where}/SKILL.md", "plugin-name:skill-name must be 64 characters or fewer")
        for path in sorted(entry.rglob("*")):
            if path.is_file():
                files.append(path.relative_to(source).as_posix())
    if not names:
        problems.add("skills/", "the package needs at least one skill")
    return files


# --------------------------------------------------------------- manifest

def stamp_manifest(source, version, release_notes, demo_url):
    template = (source / "plugin.template.json").read_text(encoding="utf-8")
    manifest = json.loads(template.replace("__VERSION__", version))
    openai = manifest.setdefault("extensions", {}).setdefault("com.openai", {})
    cases = json.loads((source / "test-cases.json").read_text(encoding="utf-8"))
    review = openai.setdefault("review", {})
    review["test_cases"] = {"positive": cases.get("positive"), "negative": cases.get("negative")}
    if demo_url:
        review["demo_recording_url"] = demo_url
    publication = openai.setdefault("publication", {})
    publication["release_notes"] = release_notes.replace("__VERSION__", version).strip()
    return manifest


def check_manifest(problems, manifest, source):
    if manifest.get("$schema") != AGENT_PLUGIN_SCHEMA:
        problems.add("plugin.json $schema", f"must be {AGENT_PLUGIN_SCHEMA}")
    name = manifest.get("name")
    if not isinstance(name, str) or len(name) > 64 or not NAME.match(name):
        problems.add("plugin.json name", "must be 1-64 lowercase letters, digits and single hyphens")
    version = manifest.get("version")
    if not isinstance(version, str) or len(version) > 64 or not SEMVER.match(version):
        problems.add("plugin.json version", f"must be a semantic version (got {version!r})")
    check_text(problems, "plugin.json description", manifest.get("description"), 4000, single_line=False)
    author = manifest.get("author") or {}
    check_text(problems, "plugin.json author.name", author.get("name"), 120)
    check_text(problems, "plugin.json author.email", author.get("email"), 320, required=False)
    check_https_url(problems, "plugin.json author.url", author.get("url"), 2048, required=False)
    check_https_url(problems, "plugin.json homepage", manifest.get("homepage"), 2048, required=False)
    for key in ("skills", "mcpServers", "apps", "hooks"):
        if key in manifest:
            problems.add(f"plugin.json {key}", "is not used by portable packages; remove it")
    for path in find_forbidden_keys(manifest):
        problems.add("plugin.json", f"must not contain {path} (secrets and reviewer access go in the dashboard)")

    openai = (manifest.get("extensions") or {}).get("com.openai") or {}
    for key in ("apps", "hooks"):
        if key in openai:
            problems.add(f"extensions.com.openai.{key}", "packages with app references or hooks cannot be submitted")
    ui = openai.get("interface") or {}
    where = "interface."
    check_text(problems, where + "displayName", ui.get("displayName"), 30)
    check_text(problems, where + "shortDescription", ui.get("shortDescription"), 30)
    check_text(problems, where + "longDescription", ui.get("longDescription"), 4000, single_line=False)
    check_text(problems, where + "developerName", ui.get("developerName"), 80)
    if ui.get("category") not in CATEGORIES:
        problems.add(where + "category", f"must be one of {sorted(CATEGORIES)} (got {ui.get('category')!r})")
    capabilities = ui.get("capabilities", [])
    if not isinstance(capabilities, list) or len(capabilities) > 20:
        problems.add(where + "capabilities", "must be a list of at most 20 entries")
    else:
        for i, capability in enumerate(capabilities):
            check_text(problems, f"{where}capabilities[{i}]", capability, 120)
    for key in ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL"):
        check_https_url(problems, where + key, ui.get(key), 1024)
    prompts = ui.get("defaultPrompt", [])
    prompts = [prompts] if isinstance(prompts, str) else prompts
    if not isinstance(prompts, list) or len(prompts) > 3:
        problems.add(where + "defaultPrompt", "must hold at most three prompts")
    else:
        seen = set()
        for i, prompt in enumerate(prompts):
            check_text(problems, f"{where}defaultPrompt[{i}]", prompt, 128)
            if isinstance(prompt, str):
                if "@" in prompt:
                    problems.add(f"{where}defaultPrompt[{i}]", "must not contain an @mention")
                key = " ".join(unicodedata.normalize("NFKC", prompt).casefold().split())
                if key in seen:
                    problems.add(f"{where}defaultPrompt[{i}]", "duplicates another starter prompt")
                seen.add(key)
    for key, background in (("brandColor", "#FFFFFF"), ("brandColorDark", "#212121")):
        color = ui.get(key)
        if color is None:
            continue
        if not isinstance(color, str) or not HEX_COLOR.match(color):
            problems.add(where + key, f"must be #RRGGBB (got {color!r})")
        elif contrast(color, background) < 2:
            problems.add(where + key, f"needs at least 2:1 contrast against {background} "
                                      f"(got {contrast(color, background):.2f}:1)")
    if ui.get("screenshots"):
        problems.add(where + "screenshots", "are allowed only for MCP servers with custom UI; remove them")
    assets = []
    for key, required in (("logo", True), ("composerIcon", True), ("logoDark", False), ("composerIconDark", False)):
        relative = check_icon(problems, source, where + key, ui.get(key), required=required)
        if relative:
            assets.append(relative)

    onboarding = openai.get("onboardingSkill")
    if onboarding is not None:
        if not (isinstance(onboarding, str) and onboarding.startswith("./skills/")
                and onboarding.endswith("/SKILL.md") and (source / onboarding[2:]).is_file()):
            problems.add("extensions.com.openai.onboardingSkill", f"must point to an included skill (got {onboarding!r})")

    review = openai.get("review") or {}
    if "demo_recording_url" in review:
        check_https_url(problems, "review.demo_recording_url", review["demo_recording_url"], 2048)
    check_test_cases(problems, (review.get("test_cases") or {}))
    notes = (openai.get("publication") or {}).get("release_notes")
    check_text(problems, "publication.release_notes", notes, 4000, single_line=False)
    return assets


def check_test_cases(problems, cases):
    for kind, count, required in (
        ("positive", POSITIVE_CASES, ("description", "prompt", "tools_triggered", "expected_behavior")),
        ("negative", NEGATIVE_CASES, ("description", "prompt")),
    ):
        items = cases.get(kind)
        where = f"review.test_cases.{kind}"
        if not isinstance(items, list) or len(items) != count:
            problems.add(where, f"must hold exactly {count} cases (got {len(items) if isinstance(items, list) else items!r})")
            continue
        prompts = set()
        for i, case in enumerate(items):
            here = f"{where}[{i}]"
            if not isinstance(case, dict):
                problems.add(here, "must be an object")
                continue
            for key in sorted(set(case) - CASE_KEYS):
                problems.add(here, f"has unsupported field {key!r}")
            for key in required:
                check_text(problems, f"{here}.{key}", case.get(key), 4000, single_line=False)
            for key in set(CASE_KEYS) - set(required) - {"file_attachment_urls", "expected_output_url"}:
                if key in case:
                    check_text(problems, f"{here}.{key}", case.get(key), 4000, single_line=False)
            if "expected_output_url" in case:
                check_https_url(problems, f"{here}.expected_output_url", case["expected_output_url"], 2048)
            for j, url in enumerate(case.get("file_attachment_urls") or []):
                check_https_url(problems, f"{here}.file_attachment_urls[{j}]", url, 2048)
            prompt = case.get("prompt")
            if prompt in prompts:
                problems.add(here, "duplicates another prompt")
            prompts.add(prompt)


def check_mcp(problems, source):
    try:
        config = json.loads((source / "mcp.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        problems.add("mcp.json", f"must be readable JSON ({error})")
        return
    if config.get("$schema") != AGENT_MCP_SCHEMA:
        problems.add("mcp.json $schema", f"must be {AGENT_MCP_SCHEMA}")
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or len(servers) != 1:
        problems.add("mcp.json mcpServers", "must declare exactly one server (plugin-level test cases need one)")
        return
    for name, server in servers.items():
        where = f"mcp.json mcpServers.{name}"
        if not isinstance(server, dict):
            problems.add(where, "must be an object")
            continue
        if server.get("type") != "streamable-http":
            problems.add(where + ".type", "must be streamable-http for a remote submission")
        check_https_url(problems, where + ".url", server.get("url"), 2048)
        if server.get("headers"):
            problems.add(where + ".headers", "must be empty: public submission rejects server headers")
        auth = (((server.get("extensions") or {}).get("com.openai") or {}).get("auth")) or {}
        if auth.get("type") not in ("oauth", "mixed", "none"):
            problems.add(where + " auth.type", "must be oauth, mixed or none (the portal has no API-key flow)")
        client = auth.get("client") or {}
        if client.get("mode") in ("dcr", "cimd") and "clientId" in client:
            problems.add(where + " auth.client", "must not carry clientId in dcr or cimd mode")
    for path in find_forbidden_keys(config):
        problems.add("mcp.json", f"must not contain {path}")


# ------------------------------------------------------------- annotations

def generate_annotations(problems, tools_doc, overrides_doc):
    tools = sorted(tools_doc.get("tools") or [], key=lambda t: t.get("name", ""))
    if not tools:
        problems.add("tools", "the tools listing is empty")
        return []
    overrides = (overrides_doc or {}).get("tools") or {}
    by_name = {t.get("name"): t for t in tools}
    for name, hints in overrides.items():
        if name not in by_name:
            problems.add("annotation-overrides.json", f"{name}: no such tool in the released server")
            continue
        for hint, wording in hints.items():
            if hint not in HINTS:
                problems.add("annotation-overrides.json", f"{name}.{hint}: unknown hint")
                continue
            actual = (by_name[name].get("annotations") or {}).get(hint)
            if not isinstance(wording, dict) or wording.get("when") is not actual:
                problems.add("annotation-overrides.json",
                             f"{name}.{hint}: wording was written for {wording.get('when') if isinstance(wording, dict) else wording!r} "
                             f"but the server reports {actual!r}; update or remove it")
            elif not isinstance(wording.get("text"), str) or not wording["text"].strip():
                problems.add("annotation-overrides.json", f"{name}.{hint}: text must be non-empty")

    rows = []
    for tool in tools:
        name = tool.get("name")
        annotations = tool.get("annotations") or {}
        missing = [h for h in HINTS if not isinstance(annotations.get(h), bool)]
        if missing:
            problems.add(f"tool {name}", f"must set {', '.join(missing)} to an explicit boolean")
            continue
        if annotations["readOnlyHint"] and annotations["destructiveHint"]:
            problems.add(f"tool {name}", "cannot be both read-only and destructive")
        justification = {}
        for hint in HINTS:
            value = annotations[hint]
            custom = (overrides.get(name) or {}).get(hint)
            if isinstance(custom, dict) and custom.get("when") is value and custom.get("text"):
                text = custom["text"].strip()
            elif hint in ("destructiveHint", "openWorldHint") and not value:
                text = GENERIC_JUSTIFICATION[(hint, False, "read" if annotations["readOnlyHint"] else "write")]
            else:
                text = GENERIC_JUSTIFICATION[(hint, value)]
            justification[hint] = text
        rows.append({
            "name": name,
            "title": tool.get("title") or (annotations.get("title") or ""),
            "readOnlyHint": annotations["readOnlyHint"],
            "destructiveHint": annotations["destructiveHint"],
            "openWorldHint": annotations["openWorldHint"],
            "idempotentHint": annotations.get("idempotentHint"),
            "justification": justification,
        })
    return rows


def render_annotations_md(rows, server, version):
    lines = [
        f"# GoodSender MCP tool annotations ({len(rows)} tools)",
        "",
        f"Generated by `scripts/openai-plugin/build.py` from the `tools/list` of the released "
        f"server {server.get('name', 'GoodSender')} {server.get('version', '?')} (package {version}). "
        "Do not edit by hand: change the hints in good-sender/goodsender-mcp-go, or the wording in "
        "`openai-plugin/annotation-overrides.json`, and rebuild.",
        "",
        "| Tool | readOnly | destructive | openWorld | Justification |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        j = row["justification"]
        text = (f"**readOnly={str(row['readOnlyHint']).lower()}:** {j['readOnlyHint']} "
                f"**destructive={str(row['destructiveHint']).lower()}:** {j['destructiveHint']} "
                f"**openWorld={str(row['openWorldHint']).lower()}:** {j['openWorldHint']}")
        lines.append(f"| `{row['name']}` | {str(row['readOnlyHint']).lower()} | "
                     f"{str(row['destructiveHint']).lower()} | {str(row['openWorldHint']).lower()} | "
                     f"{text.replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def check_tools_triggered(problems, cases, tool_names):
    for i, case in enumerate(cases.get("positive") or []):
        if not isinstance(case, dict) or not isinstance(case.get("tools_triggered"), str):
            continue
        for tool in (t.strip() for t in case["tools_triggered"].split(",")):
            if tool and tool not in tool_names:
                problems.add(f"review.test_cases.positive[{i}].tools_triggered",
                             f"names {tool!r}, which the released server does not list")


def render_test_cases_md(cases, version):
    lines = [f"# GoodSender OpenAI review test cases (package {version})", "",
             "Generated from `openai-plugin/test-cases.json`; the same cases ship in the package "
             "manifest under `extensions.com.openai.review.test_cases`.", "",
             "## Positive", "", "| # | Prompt | Tools triggered | Expected behavior |", "|---|---|---|---|"]
    for i, case in enumerate(cases["positive"], 1):
        lines.append(f"| P{i} | {case['prompt']} | `{case['tools_triggered']}` | {case['expected_behavior']} |")
    lines += ["", "## Negative", "", "| # | Prompt | Why the app must not act | Expected behavior |", "|---|---|---|---|"]
    for i, case in enumerate(cases["negative"], 1):
        lines.append(f"| N{i} | {case['prompt']} | {case['description']} | {case.get('expected_behavior', '')} |")
    return "\n".join(line.replace("\n", " ") for line in lines) + "\n"


# -------------------------------------------------------------------- zip

def write_zip(path, entries):
    """entries: list of (archive name, bytes). Deterministic: sorted, fixed time."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def check_zip(problems, path):
    if path.stat().st_size > 100 * 1000 * 1000:
        problems.add(path.name, "the compressed ZIP must be 100 MB or less")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not names:
            problems.add(path.name, "is empty")
        if len(names) > 5000:
            problems.add(path.name, "must hold at most 5,000 entries")
        folded = set()
        for name in names:
            segments = name.split("/")
            if (name != name.strip() or "\\" in name or name.startswith("/") or "" in segments
                    or ".." in segments or len(segments) > 20):
                problems.add(path.name, f"entry {name!r} has an unsupported path")
            key = unicodedata.normalize("NFC", name).casefold()
            if key in folded:
                problems.add(path.name, f"entry {name!r} collides with another after normalization")
            folded.add(key)
        for required in ("plugin.json", "mcp.json"):
            if required not in names:
                problems.add(path.name, f"is missing {required} at the archive root")
        if archive.testzip() is not None:
            problems.add(path.name, "is corrupt")


# ------------------------------------------------------------------- main

def build(args):
    source = Path(args.source).resolve()
    version = args.version[1:] if args.version.startswith("v") else args.version
    problems = Problems()

    notes_path = Path(args.release_notes_file) if args.release_notes_file else source / "release-notes.md"
    release_notes = notes_path.read_text(encoding="utf-8")
    manifest = stamp_manifest(source, version, release_notes, args.demo_recording_url)
    assets = check_manifest(problems, manifest, source)
    check_mcp(problems, source)
    skill_files = check_skills(problems, source, manifest.get("name", ""))

    cases = manifest["extensions"]["com.openai"]["review"]["test_cases"]
    rows, server = [], {}
    if args.tools:
        tools_doc = json.loads(Path(args.tools).read_text(encoding="utf-8"))
        server = tools_doc.get("serverInfo") or {}
        overrides_path = source / "annotation-overrides.json"
        overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
        rows = generate_annotations(problems, tools_doc, overrides)
        check_tools_triggered(problems, cases, {t.get("name") for t in tools_doc.get("tools") or []})
    else:
        print("build: no --tools given; annotation justifications are not generated "
              "and test-case tool names are not checked", file=sys.stderr)

    if problems:
        print(f"build: {len(problems)} problem(s) in the OpenAI plugin package:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if args.check_only:
        print(f"build: package {version} is valid")
        return 0

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    entries = [("plugin.json", manifest_bytes), ("mcp.json", (source / "mcp.json").read_bytes())]
    entries += [(rel, (source / rel).read_bytes()) for rel in sorted(set(assets))]
    entries += [(rel, (source / rel).read_bytes()) for rel in skill_files]
    zip_path = out / f"{PACKAGE_PREFIX}-{version}.zip"
    write_zip(zip_path, entries)
    check_zip(problems, zip_path)
    (out / "plugin.json").write_bytes(manifest_bytes)
    (out / "TEST_CASES.md").write_text(render_test_cases_md(cases, version), encoding="utf-8")
    if rows:
        (out / "ANNOTATIONS.md").write_text(render_annotations_md(rows, server, version), encoding="utf-8")
        (out / "annotations.json").write_text(json.dumps(
            {"server": server, "package_version": version, "tools": rows}, indent=2) + "\n", encoding="utf-8")
    if problems:
        print("build: the written ZIP failed its own checks:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"build: wrote {zip_path} ({len(entries)} files"
          + (f", {len(rows)} tool justifications" if rows else "") + ")")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--version", required=True, help="release tag or version, e.g. v1.2.3")
    parser.add_argument("--tools", help="tools/list JSON written by list_tools.py")
    parser.add_argument("--out-dir", default="dist/openai-plugin")
    parser.add_argument("--source", default=str(ROOT / "openai-plugin"))
    parser.add_argument("--release-notes-file", help="defaults to <source>/release-notes.md")
    parser.add_argument("--demo-recording-url", default=os.environ.get("OPENAI_PLUGIN_DEMO_URL") or None)
    parser.add_argument("--check-only", action="store_true", help="validate without writing files")
    return build(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
