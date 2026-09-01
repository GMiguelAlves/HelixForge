#!/usr/bin/env python3
"""Finalize compact 10C provenance, checksums and audit package."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--audit-archive", type=Path, required=True)
    args = parser.parse_args()
    execution = args.execution_root.resolve()
    repo = args.repo_root.resolve()
    output = args.output_dir.resolve()
    report = args.report.resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary = json.loads((output / "benchmark_summary.json").read_text(encoding="utf-8"))
    provenance = {
        "schema_version": "1.0", "type": "integrative_reentry_execution_provenance",
        "scientific_target": summary["scientific_target"], "integration_workflow": summary["integration_workflow"],
        "baseline_10b_commit": summary["baseline_10b_commit"],
        "benchmark_execution_commit": (execution / "repository_commit.txt").read_text(encoding="utf-8").strip(),
        "route_a": {"mode": "direct_terminal_manifests", "command_record": "commands.txt"},
        "route_b": {"mode": "relocated_manifest_relative_reentry", "command_record": "commands.txt"},
        "nextflow": "25.10.7", "comparison_script": "benchmark/integrative/scripts/compare_reentry_routes.py",
        "comparison_script_sha256": sha256(repo / "benchmark/integrative/scripts/compare_reentry_routes.py"),
        "config": "benchmark/integrative/configs/reentry_slurm.config",
        "config_sha256": sha256(repo / "benchmark/integrative/configs/reentry_slurm.config"),
        "classification": summary["reentry_equivalence_benchmark"], "readiness": summary["readiness"],
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "audit_archive.json").unlink(missing_ok=True)
    targets = sorted(path for path in output.iterdir() if path.is_file() and path.name not in {"SHA256SUMS", "audit_archive.json"}) + [report]
    (output / "SHA256SUMS").write_text("\n".join(f"{sha256(path)}  {path.name}" for path in targets) + "\n", encoding="utf-8")

    args.audit_archive.parent.mkdir(parents=True, exist_ok=True)
    readme = """# Auditoria do benchmark integrativo de reentrada\n\nEste pacote preserva os manifests, comandos, configurações, métricas, tabelas científicas centrais, logs, traces, checksums e o relatório da comparação entre a rota direta e a reentrada relocada por manifest. Workdirs, caches, dados redundantes e estado oculto do Nextflow não foram incluídos.\n"""
    with zipfile.ZipFile(args.audit_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("README.md", readme)
        for path in sorted(output.iterdir()):
            if path.is_file():
                archive.write(path, f"metrics/{path.name}")
        archive.write(report, f"report/{report.name}")
        for path in (
            repo / "benchmark/integrative/configs/reentry_comparison.json",
            repo / "benchmark/integrative/configs/reentry_slurm.config",
            repo / "benchmark/integrative/protocol/benchmark_protocol.md",
            repo / "benchmark/integrative/protocol/interpretation_criteria.md",
        ):
            archive.write(path, f"frozen/{path.name}")
        for path in (
            execution / "commands.txt", execution / "environment.txt", execution / "repository_commit.txt",
            execution / "repository_status.txt", execution / "setup/setup_summary.json",
            execution / "setup/manifest_validation.tsv", execution / "setup/input_artifact_identity.tsv",
        ):
            archive.write(path, f"execution/{path.name}")
        for route in ("a", "b"):
            bundle = execution / ("direct_bundle" if route == "a" else "relocated_bundle")
            archive.write(bundle / "rna/rnaseq_run_manifest.json", f"manifests/route-{route}/rnaseq_run_manifest.json")
            archive.write(bundle / "chip/chipseq_run_manifest.json", f"manifests/route-{route}/chipseq_run_manifest.json")
            archive.write(execution / f"logs/route-{route}.trace.tsv", f"execution/logs/route-{route}.trace.tsv")
            archive.write(execution / f"logs/route-{route}.nextflow.log", f"execution/logs/route-{route}.nextflow.log")
            result = execution / f"results/route-{route}"
            for name in ("master_evidence.tsv", "master_evidence_long.tsv", "regulatory_classes.tsv", "candidate_score.tsv", "candidate_ranking.tsv", "fisher_tests.tsv", "correlations.tsv", "gene_sets.tsv", "candidate_explorer.tsv", "integrative_run_manifest.json"):
                candidates = sorted(result.rglob(name), key=lambda item: (len(item.parts), item.as_posix()))
                if candidates:
                    archive.write(candidates[0], f"scientific/route-{route}/{name}")
    archive_info = {"archive": args.audit_archive.name, "size_bytes": args.audit_archive.stat().st_size, "sha256": sha256(args.audit_archive), "location_class": "user_home_audit"}
    (output / "audit_archive.json").write_text(json.dumps(archive_info, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"classification": summary["reentry_equivalence_benchmark"], "readiness": summary["readiness"], "archive": archive_info}, sort_keys=True))


if __name__ == "__main__":
    main()
