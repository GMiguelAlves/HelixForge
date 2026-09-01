import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
BENCHMARK = ROOT / "benchmark" / "integrative"


class ReentryBenchmarkDesignTests(unittest.TestCase):
    def test_frozen_route_definition(self):
        config = json.loads((BENCHMARK / "configs" / "reentry_comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(config["route_a"], "direct_terminal_manifests")
        self.assertEqual(config["route_b"], "relocated_manifest_relative_reentry")
        self.assertTrue(config["deterministic_tsv_sha256_identity"])

    def test_all_frozen_ir_gates_are_implemented(self):
        source = (BENCHMARK / "scripts" / "compare_reentry_routes.py").read_text(encoding="utf-8")
        for gate in ("IR1", "IR2", "IR3", "IR4"):
            self.assertIn(f'"criterion_id": "{gate}"', source)

    def test_reentry_uses_independent_nextflow_state(self):
        source = (BENCHMARK / "scripts" / "run_reentry_benchmark_slurm.sh").read_text(encoding="utf-8")
        self.assertIn('NXF_HOME="$nxf_home/route-$route"', source)
        self.assertIn('NXF_CACHE_DIR="$cache/route-$route"', source)
        self.assertIn('rm -rf -- "$work/route-a" "$cache/route-a" "$nxf_home/route-a"', source)


if __name__ == "__main__":
    unittest.main()
