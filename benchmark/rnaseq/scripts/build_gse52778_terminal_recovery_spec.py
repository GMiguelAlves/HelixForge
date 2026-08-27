#!/usr/bin/env python3
"""Build the explicit input map for the GSE52778 terminal-manifest recovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def existing(value: str) -> Path:
    path = Path(value).resolve()
    if not path.exists():
        raise ValueError(f"missing recovery input: {path}")
    if path.is_file() and path.stat().st_size == 0:
        raise ValueError(f"empty recovery input: {path}")
    return path


def manifest(path: Path, expected_type: str) -> dict:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("type") != expected_type or payload.get("status") != "complete":
        raise ValueError(f"invalid {expected_type} manifest: {path}")
    if not payload.get("id"):
        raise ValueError(f"manifest has no id: {path}")
    return payload


def descriptor(**values) -> dict:
    base = {
        "assay": "rnaseq", "contrast_id": None, "sample_ids": [], "condition": None,
        "stage": None, "mark_or_factor": None, "peak_type": None,
    }
    base.update(values)
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quant", action="append", required=True, metavar="MANIFEST::ARTIFACT")
    parser.add_argument("--import-manifest", required=True)
    parser.add_argument("--counts", required=True)
    parser.add_argument("--abundance", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--normalized-counts", required=True)
    parser.add_argument("--contrast-manifest", required=True)
    parser.add_argument("--contrast-results", required=True)
    parser.add_argument("--de-manifest", required=True)
    parser.add_argument("--de-summary", required=True)
    parser.add_argument("--report-manifest", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--reference-manifest", required=True)
    parser.add_argument("--analysis-spec", required=True)
    parser.add_argument("--validated-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    analysis_spec_path = existing(args.analysis_spec)
    with analysis_spec_path.open(encoding="utf-8") as handle:
        analysis_spec = json.load(handle)
    contrasts = analysis_spec.get("contrasts") or []
    if len(contrasts) != 1 or not contrasts[0].get("id"):
        raise ValueError("GSE52778 recovery requires exactly one explicit contrast")
    contrast_id = str(contrasts[0]["id"])

    artifacts: list[dict] = []
    source_manifests: list[Path] = []
    quant_samples: set[str] = set()
    for item in args.quant:
        parts = item.split("::", 1)
        if len(parts) != 2:
            raise ValueError("--quant must use MANIFEST::ARTIFACT")
        manifest_path, artifact_path = map(existing, parts)
        payload = manifest(manifest_path, "quantification")
        sample_id = str(payload.get("sample_id") or "")
        dataset = str(payload.get("dataset") or "")
        if not sample_id or not dataset or sample_id in quant_samples:
            raise ValueError(f"invalid or duplicate quantification sample: {manifest_path}")
        quant_samples.add(sample_id)
        source_manifests.append(manifest_path)
        artifacts.append({
            "path": str(artifact_path),
            "descriptor": descriptor(
                artifact_id=f"{payload['id']}.transcript_abundance",
                artifact_type="transcript_abundance", format="salmon_quant_sf",
                entity_level="transcript", sample_ids=[sample_id], role="quantification",
                producer_manifest_id=payload["id"], producer_process="SALMON_QUANT",
                location={"kind": "producer_relative", "path": artifact_path.name,
                          "base_path": None, "producer_manifest_id": payload["id"]},
                source={"type": "helixforge", "name": "Salmon", "version": "1.10.3"},
                metadata={"dataset": dataset},
            ),
        })
    if len(quant_samples) != 8:
        raise ValueError(f"GSE52778 recovery requires eight quantifications, found {len(quant_samples)}")

    import_manifest_path = existing(args.import_manifest)
    import_payload = manifest(import_manifest_path, "import")
    source_manifests.append(import_manifest_path)
    for path_value, suffix, artifact_type, role in (
        (args.counts, "gene_counts", "gene_counts", "counts"),
        (args.abundance, "gene_abundance", "gene_abundance", "abundance"),
    ):
        artifact_path = existing(path_value)
        artifacts.append({
            "path": str(artifact_path),
            "descriptor": descriptor(
                artifact_id=f"{import_payload['id']}.{suffix}", artifact_type=artifact_type,
                format="tsv", entity_level="gene", role=role,
                producer_manifest_id=import_payload["id"], producer_process="TXIMPORT",
                location={"kind": "producer_relative", "path": artifact_path.name,
                          "base_path": None, "producer_manifest_id": import_payload["id"]},
                source={"type": "helixforge", "name": import_payload.get("provider", "salmon"), "version": None},
                metadata={},
            ),
        })

    model_manifest_path = existing(args.model_manifest)
    model_payload = manifest(model_manifest_path, "differential_expression_model")
    source_manifests.append(model_manifest_path)
    normalized_path = existing(args.normalized_counts)
    model_id = str(model_payload["id"]).rsplit(".", 1)[-1]
    artifacts.append({
        "path": str(normalized_path),
        "descriptor": descriptor(
            artifact_id=f"{model_payload['id']}.normalized_counts", artifact_type="normalized_counts",
            format="tsv", entity_level="gene", role="exploratory_expression",
            producer_manifest_id=model_payload["id"], producer_process="DESEQ2_MODEL",
            location={"kind": "producer_relative", "path": normalized_path.name,
                      "base_path": None, "producer_manifest_id": model_payload["id"]},
            source={"type": "helixforge", "name": "DESeq2", "version": None},
            metadata={"model_id": model_id},
        ),
    })

    contrast_manifest_path = existing(args.contrast_manifest)
    contrast_payload = manifest(contrast_manifest_path, "differential_expression_contrast")
    source_manifests.append(contrast_manifest_path)
    contrast_path = existing(args.contrast_results)
    artifacts.append({
        "path": str(contrast_path),
        "descriptor": descriptor(
            artifact_id=f"{contrast_payload['id']}.differential_expression",
            artifact_type="differential_expression", format="tsv", entity_level="gene",
            contrast_id=contrast_id, role="contrast_results",
            producer_manifest_id=contrast_payload["id"], producer_process="DESEQ2_CONTRAST",
            location={"kind": "producer_relative", "path": contrast_path.name,
                      "base_path": None, "producer_manifest_id": contrast_payload["id"]},
            source={"type": "helixforge", "name": "DESeq2", "version": None},
            metadata={"model_id": model_id},
        ),
    })

    de_manifest_path = existing(args.de_manifest)
    de_payload = manifest(de_manifest_path, "differential_expression")
    source_manifests.append(de_manifest_path)
    de_summary_path = existing(args.de_summary)
    artifacts.append({
        "path": str(de_summary_path),
        "descriptor": descriptor(
            artifact_id=f"{de_payload['id']}.differential_expression_summary",
            artifact_type="differential_expression_summary", format="tsv", entity_level="gene",
            role="combined_results", producer_manifest_id=de_payload["id"], producer_process="DE_AGGREGATE",
            location={"kind": "producer_relative", "path": de_summary_path.name,
                      "base_path": None, "producer_manifest_id": de_payload["id"]},
            source={"type": "helixforge", "name": "DESeq2", "version": None}, metadata={},
        ),
    })

    report_manifest_path = existing(args.report_manifest)
    report_payload = manifest(report_manifest_path, "rnaseq_report")
    source_manifests.append(report_manifest_path)
    report_path = existing(args.report_dir)
    artifacts.append({
        "path": str(report_path),
        "descriptor": descriptor(
            artifact_id=f"{report_payload['id']}.report", artifact_type="rnaseq_report",
            format="directory", entity_level="report", role="report",
            producer_manifest_id=report_payload["id"], producer_process="RNASEQ_GENE_REPORT",
            location={"kind": "producer_relative", "path": ".", "base_path": None,
                      "producer_manifest_id": report_payload["id"]},
            source={"type": "helixforge", "name": report_payload.get("provider", "candidate_genes_v1"),
                    "version": "1.0"}, metadata={},
        ),
    })

    artifacts.sort(key=lambda item: item["descriptor"]["artifact_id"])
    source_manifests = sorted(set(source_manifests), key=lambda path: path.name)
    version = f"1.0.0-rc.1+report-hotfix.{args.validated_commit[:7]}"
    document = {
        "schema_version": "1.0", "type": "rnaseq_terminal_recovery_spec", "status": "ready",
        "meta": {"id": "gse52778_biological_hotfix.rnaseq", "assay": "rnaseq"},
        "metadata": str(existing(args.metadata)),
        "reference_manifest": str(existing(args.reference_manifest)),
        "schema_root": None,
        "source_manifests": [str(path) for path in source_manifests],
        "artifacts": artifacts,
        "contrast_spec": str(analysis_spec_path),
        "run": {
            "id": "gse52778_biological_hotfix.rnaseq", "run_id": f"composite-{args.validated_commit[:12]}",
            "run_name": "gse52778_biological_report_hotfix", "helixforge_version": version,
            "git_commit": args.validated_commit, "nextflow_version": "25.10.7", "profile": "slurm",
            "quantification_method": "salmon",
            "source": {"type": "helixforge", "name": "HelixForge composite benchmark recovery", "version": version},
            "parameters": {"base_rc_tag": "v1.0.0-rc.1", "composite_recovery": True,
                           "report_hotfix_commit": args.validated_commit},
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ready", "sources": len(source_manifests), "artifacts": len(artifacts),
                      "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
