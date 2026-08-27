#!/usr/bin/env python3
"""Fail-closed structural validation of the completed biological RC run."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


RC_SHA = "fc38ada8f592bb57a13467965a718ce0df7fb6ce"
REPORT_FIX_SHA = "e913ac6"
RECOVERY_SPEC_SHA = "1692263f71c4f93f7162bd153fa65c8dfa354d40"
RECOVERY_LAUNCHER_SHA = "d0cf0f6bf68304cd5cf590fb913c7cbc2d6e3b17"


def require(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    return path


def rows(path: Path, delimiter: str = "\t") -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def one(candidates: list[Path], label: str) -> Path:
    selected = [path for path in candidates if path.is_file() and path.stat().st_size > 0]
    if len(selected) != 1:
        raise ValueError(f"expected one {label}, found {len(selected)}")
    return selected[0]


def load_json(path: Path) -> dict:
    return json.loads(require(path).read_text(encoding="utf-8"))


def completed_tasks(log_path: Path) -> list[dict[str, str]]:
    """Return unique terminal task events from a Nextflow debug log."""
    pattern = re.compile(
        r"TaskHandler\[jobId: (?P<job_id>[^;]+); id: (?P<task_id>[^;]+); "
        r"name: (?P<name>.*?); status: COMPLETED; exit: (?P<exit>[^;]+);"
    )
    tasks: dict[tuple[str, str, str], dict[str, str]] = {}
    for line in require(log_path).read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(line)
        if match:
            task = match.groupdict()
            tasks[(task["job_id"], task["task_id"], task["name"])] = task
    if not tasks:
        raise ValueError(f"no terminal task events found in {log_path}")
    return list(tasks.values())


def require_processes(tasks: list[dict[str, str]], expected: tuple[str, ...], label: str) -> None:
    successful = [task["name"] for task in tasks if task["exit"] == "0"]
    absent = [process for process in expected if not any(process in name for name in successful)]
    if absent:
        raise ValueError(f"missing successful {label} processes: {absent}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    # The biological run reached DESeq2 under the frozen RC, then exposed a real
    # report ID-policy defect.  The corrected report and the unchanged RC
    # RUN_MANIFEST module were executed as two controlled recoveries.  Keep that
    # provenance explicit instead of forging an uninterrupted execution identity.
    execution_mode = "uninterrupted"
    execution_identity_path = args.case_root / "execution_identity.json"
    report_identity_path = args.case_root / "report-hotfix-recovery/recovery_identity.json"
    terminal_identity_path = args.case_root / "terminal-manifest-recovery/recovery_identity.json"
    if execution_identity_path.is_file():
        identity = load_json(execution_identity_path)
        if identity.get("status") != "complete" or identity.get("rc_sha") != RC_SHA:
            raise ValueError("invalid uninterrupted execution identity")
        if identity.get("nextflow") != "25.10.7" or identity.get("java_major") != 21:
            raise ValueError("incorrect Nextflow/Java runtime identity")
        if identity.get("design") != "~ batch + condition" or identity.get("contrast") != "dexamethasone_vs_untreated":
            raise ValueError("execution identity does not preserve paired design/contrast")
        identities = {"execution": identity}
    else:
        execution_mode = "composite_recovery"
        report_identity = load_json(report_identity_path)
        terminal_identity = load_json(terminal_identity_path)
        if report_identity.get("status") != "complete" or report_identity.get("type") != "report_hotfix_recovery":
            raise ValueError("report recovery identity is not complete")
        if not str(report_identity.get("validated_commit", "")).startswith(REPORT_FIX_SHA):
            raise ValueError("report recovery did not use the validated ID-policy fix")
        if report_identity.get("rc_tag") != "v1.0.0-rc.1":
            raise ValueError("report recovery base RC differs from the frozen release")
        if terminal_identity.get("status") != "complete" or terminal_identity.get("type") != "terminal_manifest_recovery":
            raise ValueError("terminal manifest recovery identity is not complete")
        if terminal_identity.get("run_manifest_code_equal_rc") is not True:
            raise ValueError("RUN_MANIFEST recovery code differs from the RC")
        if terminal_identity.get("recovery_spec_commit") != RECOVERY_SPEC_SHA:
            raise ValueError("unexpected terminal recovery specification")
        if terminal_identity.get("launcher_commit") != RECOVERY_LAUNCHER_SHA:
            raise ValueError("unexpected terminal recovery launcher")
        for current in (report_identity, terminal_identity):
            if current.get("nextflow") != "25.10.7" or current.get("java_major") != 21:
                raise ValueError("recovery used an uncertified Nextflow/Java runtime")
        identities = {"report_recovery": report_identity, "terminal_recovery": terminal_identity}

    metadata = rows(require(args.case_root / "metadata.csv"), delimiter=",")
    if len(metadata) != 8 or len({row["sample_id"] for row in metadata}) != 8:
        raise ValueError("expected eight unique samples")
    if Counter(row["condition"] for row in metadata) != Counter({"untreated": 4, "dexamethasone": 4}):
        raise ValueError("condition balance differs from frozen design")
    donors: defaultdict[str, set[str]] = defaultdict(set)
    for row in metadata:
        donors[row["batch"]].add(row["condition"])
    if len(donors) != 4 or any(values != {"untreated", "dexamethasone"} for values in donors.values()):
        raise ValueError("donor pairing differs from frozen design")

    reference = json.loads(require(args.reference_manifest).read_text(encoding="utf-8"))
    if reference.get("status") != "REFERENCE_READY" or reference.get("release") != "GENCODE_49":
        raise ValueError("invalid frozen reference")
    if reference.get("id_policy", {}).get("ignoreTxVersion") is not False or reference.get("id_policy", {}).get("ignoreAfterBar") is not False:
        raise ValueError("reference ID policy differs from production_v1")

    pipeline_info = args.case_root / "results/pipeline_info"
    for filename in ("execution_timeline.html", "execution_report.html", "pipeline_dag.html"):
        require(pipeline_info / filename)
    science_tasks = completed_tasks(args.case_root / "logs/nextflow.log")
    required_science_processes = (
        "RNASEQ_CONTEXT", "RNASEQ_METADATA", "REFERENCE_BUNDLE", "FASTQC_RAW",
        "TRIM_GALORE", "FASTQC_TRIMMED", "MERGE_FASTQ", "FASTQC_MERGED", "MULTIQC",
        "SALMON_INDEX", "SALMON_QUANT", "TX2GENE_BUILD", "SALMON_IMPORT", "DE_PREFLIGHT",
        "DESEQ2_MODEL", "DESEQ2_CONTRAST", "DE_AGGREGATE",
    )
    require_processes(science_tasks, required_science_processes, "scientific")
    science_failures = [task for task in science_tasks if task["exit"] != "0"]
    if execution_mode == "composite_recovery":
        if len(science_failures) != 1 or "RNASEQ_REPORT_CONTEXT" not in science_failures[0]["name"]:
            raise ValueError(f"unexpected original-run failures: {science_failures}")
        report_tasks = completed_tasks(args.case_root / "report-hotfix-recovery/logs/nextflow.log")
        require_processes(report_tasks, ("RNASEQ_REPORT_CONTEXT", "RNASEQ_GENE_REPORT"), "report recovery")
        if any(task["exit"] != "0" for task in report_tasks):
            raise ValueError("report recovery contains failed tasks")
        terminal_tasks = completed_tasks(args.case_root / "terminal-manifest-recovery/logs/nextflow.log")
        require_processes(terminal_tasks, ("RUN_MANIFEST",), "terminal recovery")
        if any(task["exit"] != "0" for task in terminal_tasks):
            raise ValueError("terminal recovery contains failed tasks")
    else:
        if science_failures:
            raise ValueError(f"non-successful tasks in uninterrupted run: {science_failures[:3]}")
        require_processes(science_tasks, ("RNASEQ_GENE_REPORT", "RUN_MANIFEST"), "terminal")
        report_tasks, terminal_tasks = [], []
    science_names = [task["name"] for task in science_tasks]
    if any("STAR_INDEX" in name or "STAR_ALIGN" in name for name in science_names):
        raise ValueError("experimental STAR provider unexpectedly executed")

    pipeline = args.case_root / "pipeline"
    matrices = {}
    for filename in ("counts_matrix.tsv", "tpm_matrix.tsv", "length_matrix.tsv"):
        path = require(pipeline / f"050-quantification/{filename}")
        matrices[filename] = rows(path)
    require(pipeline / "050-quantification/summarized_experiment.rds")
    sample_ids = [row["sample_id"] for row in metadata]
    quant_samples = rows(require(pipeline / "050-quantification/quant_samples.tsv"))
    if len(quant_samples) != 8 or {row["sample_id"] for row in quant_samples} != set(sample_ids):
        raise ValueError("Import sample table differs from frozen metadata")
    import_ids = [row["import_id"] for row in quant_samples]
    expected_import_ids = {f"{row['dataset']}__{row['sample_id']}" for row in metadata}
    if len(set(import_ids)) != 8 or set(import_ids) != expected_import_ids:
        raise ValueError("Import sample identifiers do not follow the dataset__sample_id contract")
    if any(row.get("quant_exists", "").strip().upper() != "TRUE" for row in quant_samples):
        raise ValueError("Import sample table records missing quantifications")
    salmon = {}
    transcript_universe: set[str] | None = None
    for sample in sample_ids:
        quant = pipeline / f"040-alignment/quants/gse52778_airway/{sample}"
        for relative in ("quant.sf", "cmd_info.json", "lib_format_counts.json", "aux_info/meta_info.json"):
            require(quant / relative)
        meta = json.loads((quant / "aux_info/meta_info.json").read_text(encoding="utf-8"))
        processed, mapped = int(meta["num_processed"]), int(meta["num_mapped"])
        if processed <= 0 or mapped < 0 or mapped > processed:
            raise ValueError(f"invalid Salmon counts for {sample}")
        current = {row["Name"] for row in rows(quant / "quant.sf")}
        if transcript_universe is None:
            transcript_universe = current
        elif current != transcript_universe:
            raise ValueError(f"Salmon transcript universe differs for {sample}")
        salmon[sample] = {"processed": processed, "mapped": mapped, "mapping_rate": mapped / processed}

    tx2gene_rows = rows(require(pipeline / "050-quantification/tx2gene.tsv"))
    tx_to_gene = {row["transcript_id"]: row["gene_id"] for row in tx2gene_rows}
    if len(tx_to_gene) != int(reference["transcripts"]):
        raise ValueError("tx2gene transcript count differs from reference manifest")
    assert transcript_universe is not None
    if not transcript_universe <= tx_to_gene.keys():
        raise ValueError("quantified transcripts are absent from tx2gene")
    estimable_genes = {tx_to_gene[transcript] for transcript in transcript_universe}
    for filename, matrix_rows in matrices.items():
        if {row["gene_id"] for row in matrix_rows} != estimable_genes:
            raise ValueError(f"{filename} gene universe differs from quantified transcripts")
        if set(matrix_rows[0]).difference({"gene_id"}) != set(import_ids):
            raise ValueError(f"{filename} sample columns differ from the Import API contract")

    de_table = one(list((pipeline / "060-deg-analysis").rglob("differential_expression_results.tsv")),
                   "aggregate differential expression table")
    de_rows = rows(de_table)
    if {row["gene_id"] for row in de_rows} != estimable_genes:
        raise ValueError("DE table does not preserve the estimable Import universe")
    report_root = pipeline / "090-search-gene/results"
    report_html = require(report_root / "gene_set_report.html")
    report_manifest = require(report_root / "manifest.json")
    require(report_root / "context.json")
    require(report_root / "sessionInfo.txt")
    require(report_root / "tables/gene_catalog.tsv")
    require(report_root / "tables/expression_long.tsv")
    report_payload = json.loads(report_manifest.read_text(encoding="utf-8"))
    if report_payload.get("status") != "complete":
        raise ValueError("candidate-gene report manifest is not complete")
    if report_payload.get("provider") != "candidate_genes_v1":
        raise ValueError("unexpected candidate-gene report provider")
    if report_payload.get("sample_count") != 8:
        raise ValueError("candidate-gene report does not contain all eight samples")
    report_context = json.loads((report_root / "context.json").read_text(encoding="utf-8"))
    if report_context.get("group_count") != 2 or report_payload.get("query_count") != 9:
        raise ValueError("candidate-gene report does not preserve the frozen two groups and nine queries")
    gene_catalog = rows(report_root / "tables/gene_catalog.tsv")
    if len(gene_catalog) != 9:
        raise ValueError("candidate-gene catalog does not contain the nine frozen queries")
    found_columns = [column for column in gene_catalog[0] if column.lower().startswith("found")]
    if not found_columns or any(
        str(row[column]).strip().lower() not in {"true", "1", "yes"}
        for row in gene_catalog for column in found_columns
    ):
        raise ValueError("one or more candidate-gene queries were not resolved")
    report_plots = [path for path in (report_root / "plots").glob("*.png") if path.stat().st_size > 100]
    if not report_plots:
        raise ValueError("candidate-gene report produced no non-empty scientific plots")

    run_manifests = sorted((args.case_root / "results").rglob("rnaseq_run_manifest.json"))
    if not run_manifests:
        raise ValueError("terminal RNA-seq run manifest is absent")
    payloads = [require(path).read_bytes() for path in run_manifests]
    if any(payload != payloads[0] for payload in payloads[1:]):
        raise ValueError("terminal manifest copies differ")
    terminal = json.loads(payloads[0])
    if terminal.get("status") != "complete":
        raise ValueError("terminal run manifest is not complete")
    if terminal.get("type") != "rnaseq_run_manifest" or terminal.get("schema_version") != "1.0":
        raise ValueError("unexpected terminal run manifest contract")
    if terminal.get("quantification_method") != "salmon":
        raise ValueError("terminal manifest does not declare Salmon")
    if execution_mode == "composite_recovery":
        terminal_run = terminal.get("run", {})
        if not str(terminal_run.get("run_id", "")).startswith("composite-"):
            raise ValueError("terminal manifest omits composite recovery identity")
        if terminal_run.get("git_commit") != RECOVERY_SPEC_SHA:
            raise ValueError("terminal manifest points to an unexpected recovery specification")
        if not str(terminal_run.get("helixforge_version", "")).startswith("1.0.0-rc.1+report-hotfix"):
            raise ValueError("terminal manifest omits the frozen base RC and report hotfix")
        if terminal_run.get("nextflow_version") != "25.10.7" or terminal_run.get("profile") != "slurm":
            raise ValueError("terminal manifest omits the certified Slurm runtime")
    if len(terminal.get("samples", [])) != 8 or len(terminal.get("contrasts", [])) != 1:
        raise ValueError("terminal manifest does not preserve the frozen sample/contrast design")
    if len(terminal.get("artifacts", [])) != 14:
        raise ValueError("terminal manifest does not expose the 14 expected artifacts")
    manifest_validation = load_json(pipeline_info / "integration_api/run_manifest.validation.json")
    if any(manifest_validation.get(key) != "valid" for key in ("schema", "semantic")):
        raise ValueError("terminal manifest schema or semantic validation failed")
    if manifest_validation.get("filesystem") != "tracked_inputs_verified":
        raise ValueError("terminal manifest filesystem validation failed")
    if manifest_validation.get("status") != "complete":
        raise ValueError("terminal manifest validation is incomplete")

    multiqc_findings = []
    multiqc_versions = list((args.case_root / "scratch/gse52778_airway").rglob("multiqc_software_versions.txt"))
    if not multiqc_versions:
        multiqc_findings.append("KNOWN_REPORTING_LIMITATION:MULTIQC_SOFTWARE_TABLE_ABSENT")
    report = {
        "schema_version": "1.0", "status": "pass", "samples": sample_ids,
        "import_sample_ids": import_ids,
        "donors": sorted(donors), "conditions": dict(Counter(row["condition"] for row in metadata)),
        "execution_mode": execution_mode,
        "execution_limitation": (
            "not_one_uninterrupted_top_level_run" if execution_mode == "composite_recovery" else None
        ),
        "identities": identities,
        "task_evidence": {
            "scientific_log": "logs/nextflow.log",
            "scientific_terminal_tasks": len(science_tasks),
            "report_recovery_log": (
                "report-hotfix-recovery/logs/nextflow.log" if report_tasks else None
            ),
            "report_recovery_terminal_tasks": len(report_tasks),
            "terminal_recovery_log": (
                "terminal-manifest-recovery/logs/nextflow.log" if terminal_tasks else None
            ),
            "terminal_recovery_terminal_tasks": len(terminal_tasks),
        },
        "salmon": salmon, "reference_transcripts": int(reference["transcripts"]),
        "indexed_transcripts": len(transcript_universe), "estimable_genes": len(estimable_genes),
        "de_genes": len(de_rows), "de_table": str(de_table.relative_to(args.case_root)),
        "gene_report": str(report_html.relative_to(args.case_root)),
        "gene_report_plots": len(report_plots),
        "gene_report_groups": 2, "gene_report_queries": 9,
        "run_manifests": [str(path.relative_to(args.case_root)) for path in run_manifests],
        "multiqc_findings": multiqc_findings,
        "star": "EXCLUDED_BY_FROZEN_PRODUCTION_PATH",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "pass", "execution_mode": execution_mode,
        "tasks": len(science_tasks) + len(report_tasks) + len(terminal_tasks),
        "samples": len(sample_ids),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
