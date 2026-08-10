#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METADATA = ROOT / "modules/local/rnaseq_qc_plan/resources/usr/bin/validate_metadata.py"
SAMPLE_TABLE = ROOT / "modules/local/import_sample_table/resources/usr/bin/import_build_sample_table.py"
STAR_IMPORT = ROOT / "modules/local/star_import/resources/usr/bin/import_star_counts.py"


def run(program: Path, arguments: list[str], cwd: Path, success: bool, message: str = "") -> None:
    result = subprocess.run([sys.executable, str(program), *arguments], cwd=cwd, text=True, capture_output=True)
    if (result.returncode == 0) != success:
        raise AssertionError(f"unexpected exit for {program.name}: {result.stderr}")
    if message and message not in result.stderr:
        raise AssertionError(f"missing {message!r}: {result.stderr}")


with tempfile.TemporaryDirectory(prefix="helixforge-scientific-review-") as temporary:
    case = Path(temporary)
    metadata = case / "metadata.csv"
    metadata.write_text(
        "dataset,sample_id,run_accession,condition,batch\nD,S1,R1,control,B1\nD,S1,R2,control,B1\n",
        encoding="utf-8",
    )
    run(METADATA, ["--metadata", str(metadata), "--output", "metadata.json"], case, True)
    report = json.loads((case / "metadata.json").read_text())
    assert report["rows"] == 2 and report["biological_samples"] == 1

    duplicate_run = case / "duplicate.csv"
    duplicate_run.write_text(
        "dataset,sample_id,run_accession\nD,S1,R1\nD,S2,R1\n", encoding="utf-8"
    )
    run(METADATA, ["--metadata", str(duplicate_run), "--output", "bad.json"], case, False, "duplicated run_accession")

    source = case / "source"
    source.mkdir()
    (source / "source.json").write_text(json.dumps({
        "provider": "star", "dataset": "D", "sample_id": "S1",
        "source_name": str(source), "compatibility_path": "unused"
    }))
    duplicated_samples = case / "duplicated_samples.csv"
    duplicated_samples.write_text("dataset,sample_id\nD,S1\nD,S1\n", encoding="utf-8")
    run(SAMPLE_TABLE, ["--metadata", str(duplicated_samples), "--provider", "star",
                       "--output", "samples.tsv", str(source)], case, False, "duplicated metadata sample")

    artifact = source / "artifact"
    artifact.write_text("gene:ABC.1\t1\t1\t1\nABC\t2\t2\t2\n", encoding="utf-8")
    star_samples = case / "star_samples.tsv"
    star_samples.write_text(
        "dataset\tsample_id\timport_id\t__source_name\nD\tS1\tD__S1\t" + str(source) + "\n",
        encoding="utf-8",
    )
    common = ["--sample-table", str(star_samples), "--count-column", "unstranded"]
    run(STAR_IMPORT, [*common, "--gene-id-normalization", "preserve"], case, True)
    run(STAR_IMPORT, [*common, "--gene-id-normalization", "legacy"], case, False, "collision")

print("Scientific input validation tests passed")
