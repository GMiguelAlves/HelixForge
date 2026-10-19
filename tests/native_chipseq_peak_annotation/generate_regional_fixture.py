#!/usr/bin/env python3
"""Small interval fixture: full envelopes, a one-base core and a one-base gap."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def dump(path, document):
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(root):
    root.mkdir(parents=True, exist_ok=True)
    reference = root / "reference.fa"
    reference.write_text(">chrStub\n" + "ACGT" * 250 + "\n", encoding="utf-8")
    # All coordinates below are zero-based half-open; GTF conversion is explicit.
    genes = [(120, 180, "left_tail"), (400, 450, "right_tail"),
             (500, 501, "gap_gene"), (550, 560, "single_library")]
    (root / "annotation.gtf").write_text("".join(
        f'chrStub\tfixture\tgene\t{start+1}\t{end}\t.\t+\t.\tgene_id "{name}";\n'
        for start, end, name in genes), encoding="utf-8")
    dump(root / "reference_manifest.json", {
        "schema_version": "1.0", "type": "reference_bundle", "id": "fixture.reference",
        "genome_id": "fixture_v1", "build": "fixture_v1", "organism": "fixture",
        "artifacts": {"reference": {"available": True, "path": reference.name, "sha256": digest(reference)}},
        "status": "complete",
    })
    records, directories, manifests, qcs = [], [], [], []
    for index, intervals in enumerate(([(100, 300), (501, 601)], [(299, 500)]), 1):
        identifier = f"ip{index}"
        directory = root / f"{identifier}.peak_calling"
        directory.mkdir(exist_ok=True)
        peak = directory / "peaks.broadPeak"
        peak.write_text("".join(f"chrStub\t{a}\t{b}\t{identifier}.{j}\t100\t.\t2\t3\t4\n"
                                 for j, (a, b) in enumerate(intervals, 1)), encoding="utf-8")
        row = dict(group_id="fixture.catalog", peak_id=identifier, peak_directory=directory.name,
                   record_id=f"r{index}", sample_id=f"s{index}", dataset="fixture",
                   experiment_id="fixture.H3K27me3", condition="fixture", target="H3K27me3",
                   genome_id="fixture_v1", peak_type="broad", caller="macs3", caller_version="3.0.4",
                   biological_replicate=str(index), technical_replicate="1")
        manifest = directory / "manifest.json"
        qc = directory / "qc.json"
        dump(manifest, dict(row, schema_version="1.0", type="peak_calling", id=identifier,
                            artifacts={"peaks": {"available": True, "path": peak.name, "sha256": digest(peak)}}, status="complete"))
        dump(qc, dict(row, type="peak_qc_frip", id=identifier))
        records.append(row); directories.append(str(directory)); manifests.append(str(manifest)); qcs.append(str(qc))
    path = ROOT / "modules/local/consensus_context/resources/usr/bin/validate_consensus_context.py"
    spec = importlib.util.spec_from_file_location("fixture_consensus_context", path)
    context = importlib.util.module_from_spec(spec); spec.loader.exec_module(context)
    request = context.build_request(records, directories, manifests, qcs,
        dict(strategy="regional_catalog", min_replicates=2, replicate_mode="biological", replicate_policy="require_premerged"))
    dump(root / "request.json", request)
    return request


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True, type=Path)
    generate(parser.parse_args().outdir.resolve())
