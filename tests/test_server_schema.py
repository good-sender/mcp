"""Validate checked-in and release-rendered metadata against the registry schema."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.request import urlopen

from jsonschema import Draft7Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_URL = (
    "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
)


class ServerSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print(f"Loading registry schema: {SCHEMA_URL}", flush=True)
        with urlopen(SCHEMA_URL, timeout=30) as response:
            schema = json.load(response)
        Draft7Validator.check_schema(schema)
        cls.validator = Draft7Validator(schema, format_checker=FormatChecker())
        cls.server = json.loads((ROOT / "server.json").read_text())

        # Exercise the release generator without overwriting checked-in metadata
        # or downloading a release asset: only its hash is needed for validation.
        cls.bundle = b"schema-validation fixture\n"
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "goodsender.mcpb"
            rendered = Path(directory) / "server.json"
            bundle.write_bytes(cls.bundle)
            subprocess.run(
                ["bash", str(ROOT / "scripts/gen-server-json.sh"), str(bundle), "v1.2.3"],
                cwd=ROOT,
                env={
                    **os.environ,
                    "TEMPLATE": str(ROOT / "server.template.json"),
                    "OUT": str(rendered),
                },
                check=True,
                timeout=30,
            )
            cls.rendered_text = rendered.read_text()
            cls.template = json.loads(cls.rendered_text)

    def test_server_matches_registry_schema(self):
        self.assertEqual(self.server["$schema"], SCHEMA_URL)
        self.validator.validate(self.server)

    def test_rendered_template_matches_registry_schema(self):
        self.assertEqual(self.template["$schema"], SCHEMA_URL)
        self.validator.validate(self.template)

    def test_template_release_placeholders_are_substituted(self):
        self.assertNotRegex(self.rendered_text, r"__[A-Z_]+__")
        self.assertEqual(self.template["version"], "1.2.3")
        mcpb = next(p for p in self.template["packages"] if p["registryType"] == "mcpb")
        self.assertEqual(mcpb["version"], "1.2.3")
        self.assertEqual(
            mcpb["identifier"],
            "https://github.com/good-sender/mcp/releases/download/v1.2.3/goodsender.mcpb",
        )
        self.assertEqual(mcpb["fileSha256"], hashlib.sha256(self.bundle).hexdigest())

    def test_invalid_icons_are_rejected_in_both_documents(self):
        documents = (("server.json", self.server), ("server.template.json", self.template))
        invalid_fields = (
            ("mimeType", "text/plain"),
            ("sizes", ["512"]),
            ("src", "not a URI"),
        )
        for name, document in documents:
            for field, value in invalid_fields:
                with self.subTest(document=name, field=field):
                    invalid = copy.deepcopy(document)
                    invalid["icons"][0][field] = value
                    with self.assertRaises(ValidationError):
                        self.validator.validate(invalid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
