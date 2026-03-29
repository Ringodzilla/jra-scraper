import json
import tempfile
import unittest
from pathlib import Path

try:
    from scripts.run_pipeline import load_race_configs
    HAS_RUN_PIPELINE = True
except ModuleNotFoundError:
    HAS_RUN_PIPELINE = False


@unittest.skipUnless(HAS_RUN_PIPELINE, "run_pipeline dependencies are not installed")
class TestPipelineEntrypoints(unittest.TestCase):
    def test_load_race_configs_requires_keys(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "races.json"
            p.write_text(json.dumps([{"race_name": "x"}], ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_race_configs(p)


if __name__ == "__main__":
    unittest.main()
