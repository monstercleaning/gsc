import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
CATALOG = ROOT / "canonical_artifacts.json"


class TestCanonicalArtifactsSchemaV2(unittest.TestCase):
    def test_schema_v2_shape_and_required_fields(self):
        obj = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(obj.get("schema_version"), 2)

        artifacts = obj.get("artifacts")
        self.assertIsInstance(artifacts, dict)
        self.assertEqual(set(artifacts.keys()), {"late_time", "submission", "referee_pack", "toe_bundle"})

        re_sha = re.compile(r"^[0-9a-f]{64}$")
        for key in ("late_time", "submission", "referee_pack", "toe_bundle"):
            rec = artifacts[key]
            self.assertIsInstance(rec, dict, msg=key)
            for f in ("type", "tier", "tag", "release_url", "asset", "sha256"):
                self.assertTrue(str(rec.get(f, "")).strip(), msg=f"{key}.{f} is empty")
            self.assertRegex(str(rec["sha256"]).lower(), re_sha, msg=f"{key}.sha256")


if __name__ == "__main__":
    unittest.main()
