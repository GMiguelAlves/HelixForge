#!/usr/bin/env python3

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/native_de"
PROGRAM = ROOT / "modules/local/de_preflight/resources/usr/bin/de_preflight.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(name: str, mutate, expected_success: bool, expected_text: str = "", manifest_mutate=None) -> None:
    with tempfile.TemporaryDirectory(prefix=f"helixforge-de-{name}-") as temporary:
        case = Path(temporary)
        counts = case / "counts.tsv"
        samples = case / "samples.tsv"
        spec = case / "spec.json"
        counts.write_bytes((FIXTURE / "counts_matrix.tsv").read_bytes())
        samples.write_bytes((FIXTURE / "quant_samples.tsv").read_bytes())
        spec.write_bytes((FIXTURE / "analysis_spec.json").read_bytes())
        mutate(counts, samples, spec)
        manifest = {
            "type": "import",
            "provider": "salmon",
            "parameters": {"countsFromAbundance": "lengthScaledTPM", "libraryProtocol": "full_length"},
            "artifacts": {
                "counts": {"available": True, "sha256": digest(counts)},
                "metadata": {"available": True, "sha256": digest(samples)},
            },
        }
        if manifest_mutate:
            manifest_mutate(manifest)
        manifest_path = case / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        output = case / "output"
        result = subprocess.run([
            sys.executable, str(PROGRAM), "--manifest", str(manifest_path),
            "--counts", str(counts), "--samples", str(samples),
            "--spec", str(spec), "--output-dir", str(output),
        ], text=True, capture_output=True)
        if (result.returncode == 0) != expected_success:
            raise AssertionError(f"{name}: unexpected exit {result.returncode}: {result.stderr}")
        if expected_text and expected_text not in result.stderr:
            raise AssertionError(f"{name}: missing {expected_text!r}: {result.stderr}")


def no_change(*_args):
    return None


def duplicate_sample(_counts, samples, _spec):
    rows = samples.read_text().splitlines()
    samples.write_text("\n".join(rows + [rows[1]]) + "\n")


def invalid_level(_counts, _samples, spec):
    document = json.loads(spec.read_text())
    document["contrasts"][0]["numerator"] = "absent"
    spec.write_text(json.dumps(document))


def lrt(_counts, _samples, spec):
    document = json.loads(spec.read_text())
    document["test"] = "lrt"
    spec.write_text(json.dumps(document))


def missing_design(_counts, _samples, spec):
    document = json.loads(spec.read_text())
    document["design"]["variable"] = "missing_field"
    document["design"]["formula"] = "~ batch + missing_field"
    spec.write_text(json.dumps(document))


def missing_contrasts(_counts, _samples, spec):
    document = json.loads(spec.read_text())
    document["contrasts"] = []
    spec.write_text(json.dumps(document))


def missing_factor_value(_counts, samples, _spec):
    rows = list(csv.reader(samples.read_text().splitlines(), delimiter="\t"))
    condition = rows[0].index("condition")
    rows[1][condition] = ""
    samples.write_text("\n".join("\t".join(row) for row in rows) + "\n")


def negative_count(counts, _samples, _spec):
    rows = list(csv.reader(counts.read_text().splitlines(), delimiter="\t"))
    rows[1][1] = "-1"
    counts.write_text("\n".join("\t".join(row) for row in rows) + "\n")


def original_full_length_counts(manifest):
    manifest["parameters"]["countsFromAbundance"] = "no"


run_case("valid", no_change, True)
run_case("duplicate-sample", duplicate_sample, False, "duplicated import_id")
run_case("invalid-level", invalid_level, False, "unavailable levels")
run_case("unsupported-lrt", lrt, False, "provider=deseq2 and test=wald only")
run_case("missing-design", missing_design, False, "design fields missing")
run_case("missing-contrasts", missing_contrasts, False, "at least one explicit contrast")
run_case("missing-factor-value", missing_factor_value, False, "missing design values")
run_case("negative-count", negative_count, False, "negative count")
run_case("invalid-salmon-mode", no_change, False, "requires full_length", original_full_length_counts)
print("Native DE preflight tests passed")
