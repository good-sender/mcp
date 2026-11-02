"""Tests for the OpenAI plugin package generator (scripts/openai-plugin/build.py).

Hermetic: they build from a temporary copy of openai-plugin/ against the
tools/list fixture in tests/fixtures/openai-plugin/tools.json (a trimmed copy
of a released server's listing). The Actions workflow builds the real package
from the released binary.
"""

import contextlib
import io
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "openai-plugin"))

import build  # noqa: E402

FIXTURE_TOOLS = ROOT / "tests" / "fixtures" / "openai-plugin" / "tools.json"
AGENT_PLUGIN_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def png(width, height, padding=0):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b"".join(b"\x00" + b"\x00" * 4 * width for _ in range(height)))
    extra = chunk(b"tEXt", b"pad\x00" + b"x" * padding) if padding else b""
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + extra + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


class PackageTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.source = self.tmp / "openai-plugin"
        shutil.copytree(ROOT / "openai-plugin", self.source)
        self.tools = self.tmp / "tools.json"
        shutil.copy(FIXTURE_TOOLS, self.tools)
        self.out = self.tmp / "dist"

    def run_build(self, *extra, tools=True):
        args = ["--version", "v1.2.3", "--source", str(self.source), "--out-dir", str(self.out)]
        if tools:
            args += ["--tools", str(self.tools)]
        stderr, stdout = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
            code = build.main(args + list(extra))
        return code, stderr.getvalue()

    def edit_json(self, path, mutate):
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data, indent=2))

    def edit_interface(self, mutate):
        self.edit_json(self.source / "plugin.template.json",
                       lambda m: mutate(m["extensions"]["com.openai"]["interface"]))

    def assertRejected(self, needle):
        code, stderr = self.run_build()
        self.assertEqual(code, 1, stderr)
        self.assertIn(needle, stderr)
        self.assertFalse((self.out / "goodsender-openai-plugin-1.2.3.zip").exists())


class ValidPackageTests(PackageTestCase):
    def test_builds_the_zip_with_the_expected_layout(self):
        code, stderr = self.run_build()
        self.assertEqual(code, 0, stderr)
        archive = self.out / "goodsender-openai-plugin-1.2.3.zip"
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(sorted(z.namelist()), [
                "assets/composer-icon-dark.png", "assets/composer-icon.png",
                "assets/logo-dark.png", "assets/logo.png", "mcp.json",
                "plugin.json", "skills/get-started/SKILL.md",
            ])
            manifest = json.loads(z.read("plugin.json"))
        self.assertEqual(manifest["version"], "1.2.3")
        self.assertNotIn("__VERSION__", json.dumps(manifest))
        openai = manifest["extensions"]["com.openai"]
        self.assertEqual(len(openai["review"]["test_cases"]["positive"]), 5)
        self.assertEqual(len(openai["review"]["test_cases"]["negative"]), 3)
        self.assertIn("1.2.3", openai["publication"]["release_notes"])
        self.assertNotIn("demo_recording_url", openai["review"])

    def test_packaged_icons_include_square_pngs_for_both_themes(self):
        code, stderr = self.run_build()
        self.assertEqual(code, 0, stderr)
        with zipfile.ZipFile(self.out / "goodsender-openai-plugin-1.2.3.zip") as archive:
            ui = json.loads(archive.read("plugin.json"))["extensions"]["com.openai"]["interface"]
            for key in ("logo", "composerIcon", "logoDark", "composerIconDark"):
                with self.subTest(icon=key):
                    path = ui[key]
                    self.assertTrue(path.endswith(".png"))
                    data = archive.read(path.removeprefix("./"))
                    self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                    width, height = struct.unpack(">II", data[16:24])
                    self.assertEqual(width, height)
                    self.assertGreaterEqual(width, 48)
                    self.assertLessEqual(width, 4096)
                    self.assertLessEqual(len(data), 5 * 1024 * 1024)

    def test_generated_table_records_tools_and_outcomes_for_every_case(self):
        code, stderr = self.run_build()
        self.assertEqual(code, 0, stderr)
        cases = json.loads((self.out / "plugin.json").read_text())["extensions"]["com.openai"]["review"]["test_cases"]
        md = (self.out / "TEST_CASES.md").read_text()
        self.assertIn("| # | Prompt | Tools triggered | Expected behavior |", md)
        self.assertIn("| # | Prompt | Tools triggered | Why the app must not act | Expected behavior |", md)
        for kind, prefix in (("positive", "P"), ("negative", "N")):
            rows = [line.split(" | ") for line in md.splitlines() if line.startswith(f"| {prefix}")]
            self.assertEqual(len(rows), len(cases[kind]))
            for row, case in zip(rows, cases[kind]):
                self.assertEqual(row[1], case["prompt"])
                self.assertEqual(row[2], f"`{case['tools_triggered']}`")
                self.assertEqual(row[-1], case["expected_behavior"] + " |")
        self.assertEqual([case["tools_triggered"] for case in cases["negative"]],
                         ["none", "send_consentless_email", "none"])

    def test_zip_is_deterministic(self):
        self.assertEqual(self.run_build()[0], 0)
        first = (self.out / "goodsender-openai-plugin-1.2.3.zip").read_bytes()
        self.assertEqual(self.run_build()[0], 0)
        self.assertEqual(first, (self.out / "goodsender-openai-plugin-1.2.3.zip").read_bytes())

    def test_annotations_cover_every_tool_with_three_justifications(self):
        self.assertEqual(self.run_build()[0], 0)
        tools = json.loads(self.tools.read_text())["tools"]
        doc = json.loads((self.out / "annotations.json").read_text())
        self.assertEqual([r["name"] for r in doc["tools"]], sorted(t["name"] for t in tools))
        by_name = {r["name"]: r for r in doc["tools"]}
        for tool in tools:
            row = by_name[tool["name"]]
            for hint in build.HINTS:
                self.assertIs(row[hint], tool["annotations"][hint])
                self.assertTrue(row["justification"][hint])
        self.assertEqual(by_name["publish_post"]["justification"]["destructiveHint"][:30],
                         "Makes the post public and deli")
        md = (self.out / "ANNOTATIONS.md").read_text()
        self.assertIn(f"({len(tools)} tools)", md)
        self.assertIn("`list_posts` | true | false | false |", md)

    def test_demo_url_is_stamped_when_given(self):
        code, stderr = self.run_build("--demo-recording-url", "https://example.com/demo")
        self.assertEqual(code, 0, stderr)
        manifest = json.loads((self.out / "plugin.json").read_text())
        self.assertEqual(manifest["extensions"]["com.openai"]["review"]["demo_recording_url"],
                         "https://example.com/demo")

    def test_builds_without_tools_but_skips_annotations(self):
        code, stderr = self.run_build(tools=False)
        self.assertEqual(code, 0, stderr)
        self.assertIn("no --tools given", stderr)
        self.assertFalse((self.out / "ANNOTATIONS.md").exists())

    def test_manifest_matches_the_agent_plugins_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema not installed")
        from urllib.request import urlopen
        with urlopen(AGENT_PLUGIN_SCHEMA_URL, timeout=30) as response:
            schema = json.load(response)
        self.assertEqual(self.run_build()[0], 0)
        Draft202012Validator(schema).validate(json.loads((self.out / "plugin.json").read_text()))


class RejectedPackageTests(PackageTestCase):
    def test_short_description_over_30_chars(self):
        self.edit_interface(lambda ui: ui.update(shortDescription="x" * 31))
        self.assertRejected("interface.shortDescription: is 31 characters; the limit is 30")

    def test_display_name_on_two_lines(self):
        self.edit_interface(lambda ui: ui.update(displayName="Good\nSender"))
        self.assertRejected("interface.displayName: must fit on one line")

    def test_long_description_over_4000_chars(self):
        self.edit_interface(lambda ui: ui.update(longDescription="x" * 4001))
        self.assertRejected("interface.longDescription: is 4001 characters")

    def test_developer_name_over_80_chars(self):
        self.edit_interface(lambda ui: ui.update(developerName="x" * 81))
        self.assertRejected("interface.developerName: is 81 characters")

    def test_unknown_category(self):
        self.edit_interface(lambda ui: ui.update(category="Marketing"))
        self.assertRejected("interface.category: must be one of")

    def test_non_https_support_url(self):
        self.edit_interface(lambda ui: ui.update(supportURL="mailto:support@goodsender.com"))
        self.assertRejected("interface.supportURL: must be an HTTPS URL")

    def test_missing_terms_url(self):
        self.edit_interface(lambda ui: ui.pop("termsOfServiceURL"))
        self.assertRejected("interface.termsOfServiceURL: is required")

    def test_four_default_prompts(self):
        self.edit_interface(lambda ui: ui.update(defaultPrompt=["a", "b", "c", "d"]))
        self.assertRejected("interface.defaultPrompt: must hold at most three prompts")

    def test_default_prompt_over_128_chars(self):
        self.edit_interface(lambda ui: ui.update(defaultPrompt=["x" * 129]))
        self.assertRejected("interface.defaultPrompt[0]: is 129 characters")

    def test_duplicate_default_prompts(self):
        self.edit_interface(lambda ui: ui.update(defaultPrompt=["List posts.", "list  POSTS."]))
        self.assertRejected("duplicates another starter prompt")

    def test_low_contrast_brand_color(self):
        self.edit_interface(lambda ui: ui.update(brandColor="#EEEEEE"))
        self.assertRejected("interface.brandColor: needs at least 2:1 contrast")

    def test_missing_logo(self):
        self.edit_interface(lambda ui: ui.pop("logo"))
        self.assertRejected("interface.logo: is required")

    def test_logo_path_without_dot_slash(self):
        self.edit_interface(lambda ui: ui.update(logo="assets/logo.png"))
        self.assertRejected("interface.logo: must be a ./-relative path")

    def test_non_square_logo(self):
        (self.source / "assets" / "logo.png").write_bytes(png(512, 256))
        self.assertRejected("must be square (got 512x256)")

    def test_too_small_logo(self):
        (self.source / "assets" / "logo.png").write_bytes(png(32, 32))
        self.assertRejected("must be at least 48x48")

    def test_logo_over_5_mib(self):
        (self.source / "assets" / "logo.png").write_bytes(png(64, 64, padding=5 * 1024 * 1024))
        self.assertRejected("the limit is 5 MiB")

    def test_png_content_with_svg_extension(self):
        self.edit_interface(lambda ui: ui.update(composerIcon="./assets/composer-icon.svg"))
        (self.source / "assets" / "composer-icon.svg").write_bytes(png(64, 64))
        self.assertRejected("SVG is not valid UTF-8 XML")

    def test_non_square_svg(self):
        self.edit_interface(lambda ui: ui.update(composerIcon="./assets/composer-icon.svg"))
        (self.source / "assets" / "composer-icon.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"/>')
        self.assertRejected("SVG dimensions must be square")

    def test_every_icon_requires_png(self):
        for key in ("logo", "composerIcon", "logoDark", "composerIconDark"):
            with self.subTest(icon=key):
                self.edit_interface(lambda ui: ui.update({key: "./assets/composer-icon.svg"}))
                self.assertRejected(f"interface.{key}: must use a PNG")

    def test_both_dark_icons_are_required(self):
        for key in ("logoDark", "composerIconDark"):
            with self.subTest(icon=key):
                self.edit_interface(lambda ui: ui.pop(key))
                self.assertRejected(f"interface.{key}: is required")

    def test_four_positive_cases(self):
        self.edit_json(self.source / "test-cases.json", lambda c: c["positive"].pop())
        self.assertRejected("review.test_cases.positive: must hold exactly 5 cases (got 4)")

    def test_four_negative_cases(self):
        self.edit_json(self.source / "test-cases.json",
                       lambda c: c["negative"].append({"description": "d", "prompt": "another"}))
        self.assertRejected("review.test_cases.negative: must hold exactly 3 cases (got 4)")

    def test_positive_case_without_expected_behavior(self):
        self.edit_json(self.source / "test-cases.json", lambda c: c["positive"][0].pop("expected_behavior"))
        self.assertRejected("review.test_cases.positive[0].expected_behavior: is required")

    def test_negative_case_requires_tool_expectation_and_outcome(self):
        for key in ("tools_triggered", "expected_behavior"):
            with self.subTest(field=key):
                self.edit_json(self.source / "test-cases.json", lambda c: c["negative"][0].pop(key))
                self.assertRejected(f"review.test_cases.negative[0].{key}: is required")

    def test_negative_case_with_empty_tool_expectation(self):
        self.edit_json(self.source / "test-cases.json", lambda c: c["negative"][0].update(tools_triggered=""))
        self.assertRejected("review.test_cases.negative[0].tools_triggered: must not be empty")

    def test_negative_case_names_a_tool_the_server_lacks(self):
        self.edit_json(self.source / "test-cases.json",
                       lambda c: c["negative"][1].update(tools_triggered="send_consentless_email, no_such_tool"))
        self.assertRejected("review.test_cases.negative[1].tools_triggered: names 'no_such_tool'")

    def test_none_cannot_be_combined_with_a_tool(self):
        self.edit_json(self.source / "test-cases.json",
                       lambda c: c["negative"][1].update(tools_triggered="none, send_consentless_email"))
        self.assertRejected("names 'none', which the released server does not list")

    def test_unknown_test_case_field(self):
        self.edit_json(self.source / "test-cases.json", lambda c: c["negative"][0].update(test_credentials="x"))
        self.assertRejected("has unsupported field 'test_credentials'")

    def test_test_case_names_a_tool_the_server_lacks(self):
        self.edit_json(self.source / "test-cases.json",
                       lambda c: c["positive"][0].update(tools_triggered="get_blog, no_such_tool"))
        self.assertRejected("names 'no_such_tool', which the released server does not list")

    def test_tool_without_explicit_hint(self):
        self.edit_json(self.tools, lambda d: d["tools"][0]["annotations"].pop("openWorldHint"))
        self.assertRejected("must set openWorldHint to an explicit boolean")

    def test_override_written_for_another_hint_value(self):
        def flip(doc):
            tool = next(t for t in doc["tools"] if t["name"] == "upload_post_image")
            tool["annotations"]["openWorldHint"] = False
        self.edit_json(self.tools, flip)
        self.assertRejected("upload_post_image.openWorldHint: wording was written for True")

    def test_override_for_a_removed_tool(self):
        self.edit_json(self.source / "annotation-overrides.json",
                       lambda o: o["tools"].update(retired_tool={"readOnlyHint": {"when": True, "text": "x"}}))
        self.assertRejected("retired_tool: no such tool in the released server")

    def test_client_secret_in_mcp_json(self):
        self.edit_json(self.source / "mcp.json", lambda m: m["mcpServers"]["goodsender"]["extensions"]
                       ["com.openai"]["auth"]["client"].update(clientSecret="s"))
        self.assertRejected("must not contain")

    def test_server_headers_in_mcp_json(self):
        self.edit_json(self.source / "mcp.json",
                       lambda m: m["mcpServers"]["goodsender"].update(headers={"Authorization": "x"}))
        self.assertRejected("must be empty: public submission rejects server headers")

    def test_empty_release_notes(self):
        (self.source / "release-notes.md").write_text("   \n")
        self.assertRejected("publication.release_notes: must not be empty")

    def test_invalid_version(self):
        code, stderr = self.run_build()
        self.assertEqual(code, 0, stderr)
        stderr_io = io.StringIO()
        with contextlib.redirect_stderr(stderr_io), contextlib.redirect_stdout(io.StringIO()):
            code = build.main(["--version", "latest", "--source", str(self.source),
                               "--out-dir", str(self.out), "--check-only"])
        self.assertEqual(code, 1)
        self.assertIn("must be a semantic version", stderr_io.getvalue())

    def test_skill_without_description(self):
        (self.source / "skills" / "get-started" / "SKILL.md").write_text("---\nname: get-started\n---\n\nBody.\n")
        self.assertRejected("SKILL.md description: is required")


if __name__ == "__main__":
    unittest.main()
