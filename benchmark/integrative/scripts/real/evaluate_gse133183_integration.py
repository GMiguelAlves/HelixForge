#!/usr/bin/env python3
"""Evaluate the frozen GSE133183 real-integration criteria."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable


EXAMPLE_SYMBOLS = ("FGF18", "UBTD2", "FBXW11", "IGF2", "HBB", "HBZ", "HBE1")
CONCORDANT = {"CONCORDANT_ACTIVATION", "CONCORDANT_REPRESSION"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle, delimiter="\t")


def optional_float(value: str | None) -> float | None:
    if value in {None, "", "NA", "NaN", "nan", "null"}:
        return None
    return float(value)


def write_tsv(path: Path, columns: list[str], values: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def selected_gene_ids(annotation: Path) -> dict[str, str]:
    wanted = set(EXAMPLE_SYMBOLS)
    found: dict[str, str] = {}
    pattern = re.compile(r'(gene_id|gene_name) "([^"]+)"')
    with annotation.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#") or "\tgene\t" not in line:
                continue
            attrs = dict(pattern.findall(line.rsplit("\t", 1)[-1]))
            symbol, gene_id = attrs.get("gene_name"), attrs.get("gene_id")
            if symbol in wanted and gene_id:
                found.setdefault(symbol, gene_id)
                if len(found) == len(wanted):
                    break
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    job_id = os.environ.get("SLURM_JOB_ID")
    if not job_id:
        raise SystemExit("real integration evaluation must execute inside a Slurm job")
    root = args.results_dir.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)

    paths = {
        "terminal": root / "integrative_run_manifest.json",
        "input": root / "010-input-validation/integrative_inputs/input_validation.json",
        "rna_evidence": root / "evidence/rnaseq/rnaseq_evidence/evidence_manifest.json",
        "chip_evidence": root / "evidence/chipseq/chipseq_evidence/evidence_manifest.json",
        "harmonization": root / "harmonization/harmonized_evidence/harmonization_manifest.json",
        "integration": root / "master/integrated_evidence/integration_manifest.json",
        "interpretation": root / "interpretation/final/interpretation/interpretation_manifest.json",
        "functional": root / "080-functional-analysis/functional_analysis/functional_manifest.json",
        "visualization": root / "090-visualization/integrative_visualization/visualization_manifest.json",
        "report_manifest": root / "100-report/integrative_report/report_manifest.json",
        "report_html": root / "100-report/integrative_report/integrative_report.html",
        "master": root / "master/integrated_evidence/master_evidence.tsv",
        "db": root / "evidence/chipseq/chipseq_evidence/differential_binding.tsv",
        "classes": root / "interpretation/final/interpretation/regulatory_classes.tsv",
        "fisher": root / "interpretation/final/interpretation/fisher_tests.tsv",
        "ranking": root / "interpretation/final/interpretation/candidate_ranking.tsv",
    }
    missing = [name for name, path in paths.items() if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise ValueError("missing required outputs: " + ", ".join(missing))

    documents = {name: load_json(path) for name, path in paths.items() if path.suffix == ".json"}
    complete_status = {"complete", "complete_empty", "valid", "PASS"}
    component_status = {name: str(document.get("status")) for name, document in documents.items()}
    ib1 = "PASS" if component_status["input"] in complete_status else "FAIL"
    required_components = ("terminal", "rna_evidence", "chip_evidence", "harmonization", "integration",
                           "interpretation", "functional", "visualization", "report_manifest")
    ib2 = "PASS" if all(component_status[name] in complete_status for name in required_components) else "FAIL"

    master_states: dict[str, Counter[str]] = {"rna": Counter(), "chip": Counter()}
    master_count = 0
    master_ids: set[str] = set()
    state_error = False
    for row in rows(paths["master"]):
        master_count += 1
        gene = row.get("canonical_entity_id", "")
        rna_state, chip_state = row.get("rna_evidence_state", ""), row.get("chip_evidence_state", "")
        if not gene or gene in master_ids or not rna_state or not chip_state:
            state_error = True
        master_ids.add(gene)
        master_states["rna"][rna_state] += 1
        master_states["chip"][chip_state] += 1
    declared_master = int(documents["integration"].get("record_counts", {}).get("canonical_genes", -1))
    ib3 = "PASS" if not state_error and master_count == declared_master == len(master_ids) else "FAIL"

    db_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows(paths["db"]):
        mark = row.get("mark_or_factor", "")
        effect, padj = optional_float(row.get("log2_fold_change")), optional_float(row.get("padj"))
        db_counts[mark]["total"] += 1
        if effect is not None and padj is not None and padj <= 0.05 and abs(effect) >= 1.0:
            db_counts[mark]["significant"] += 1
            db_counts[mark]["decreased" if effect < 0 else "increased"] += 1
    me3 = db_counts["H3K27me3"]
    ib4 = "PASS" if me3["significant"] > 0 and me3["decreased"] > me3["increased"] else "FAIL"

    fisher_rows = list(rows(paths["fisher"]))
    directional_tests = [row for row in fisher_rows if row.get("target_set") in CONCORDANT]
    if directional_tests:
        ib5 = "PASS" if all((optional_float(row.get("odds_ratio")) or 0.0) > 1.0 for row in directional_tests) else "FAIL"
    else:
        ib5 = "NOT_EVALUABLE"

    ranking = list(rows(paths["ranking"]))
    rank_by_gene = {row["canonical_entity_id"]: row for row in ranking}
    top20 = ranking[:20]
    class_counts: Counter[str] = Counter()
    class_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    directional_ranked: dict[str, list[dict[str, str]]] = {key: [] for key in sorted(CONCORDANT)}
    for row in rows(paths["classes"]):
        pattern = row.get("regulatory_pattern", "")
        class_counts[pattern] += 1
        gene = row.get("canonical_entity_id", "")
        if gene in rank_by_gene and pattern in CONCORDANT and len(directional_ranked[pattern]) < 10:
            merged = dict(rank_by_gene[gene])
            merged.update({"regulatory_pattern": pattern, "canonical_mark": row.get("canonical_mark", "")})
            directional_ranked[pattern].append(merged)
        class_by_gene[gene].append(row)

    symbols = selected_gene_ids(args.annotation)
    examples = []
    for symbol in EXAMPLE_SYMBOLS:
        gene_id = symbols.get(symbol, "")
        ranked = rank_by_gene.get(gene_id, {})
        observed = class_by_gene.get(gene_id, [])
        examples.append({
            "symbol": symbol, "canonical_entity_id": gene_id,
            "evaluation_state": "MEASURED" if observed else "NOT_EVALUABLE",
            "rank": ranked.get("rank", ""), "final_score": ranked.get("final_score", ""),
            "regulatory_patterns": ";".join(sorted({item.get("regulatory_pattern", "") for item in observed if item.get("regulatory_pattern")})),
            "marks": ";".join(sorted({item.get("canonical_mark", "") for item in observed if item.get("canonical_mark")})),
        })
    ib6 = "PASS" if len(examples) == len(EXAMPLE_SYMBOLS) else "FAIL"
    ib7 = "PASS" if len(top20) == 20 else "FAIL"

    functional = documents["functional"]
    selection = functional.get("selection", {})
    methods = functional.get("methods", {})
    ib8 = ("PASS" if selection.get("background") and "Benjamini-Hochberg" in methods.get("multiple_testing", "")
           and functional.get("annotation", {}).get("checksum", {}).get("value") else "INCOMPLETE")

    criteria = [
        {"criterion": "IB1", "type": "RELEASE_GATE", "status": ib1, "metric": "contract/reference compatibility"},
        {"criterion": "IB2", "type": "RELEASE_GATE", "status": ib2, "metric": "technical completion"},
        {"criterion": "IB3", "type": "SANITY_CHECK", "status": ib3, "metric": "entity/state accounting"},
        {"criterion": "IB4", "type": "EXPECTED_RANGE", "status": ib4, "metric": "H3K27me3 depletion direction"},
        {"criterion": "IB5", "type": "EXPECTED_RANGE", "status": ib5, "metric": "directional enrichment"},
        {"criterion": "IB6", "type": "DESCRIPTIVE", "status": ib6, "metric": "preregistered examples"},
        {"criterion": "IB7", "type": "DESCRIPTIVE", "status": ib7, "metric": "candidate review inventories"},
        {"criterion": "IB8", "type": "DESCRIPTIVE", "status": ib8, "metric": "functional analysis provenance"},
    ]
    gates_failed = any(item["status"] == "FAIL" for item in criteria if item["type"] in {"RELEASE_GATE", "SANITY_CHECK"})
    limitations = [item["criterion"] for item in criteria if item["status"] not in {"PASS"}]
    classification = "FAIL" if gates_failed else "PASS_WITH_LIMITATIONS" if limitations else "PASS"

    write_tsv(out / "acceptance_results.tsv", ["criterion", "type", "status", "metric"], criteria)
    write_tsv(out / "top20_candidates.tsv", list(top20[0]) if top20 else ["rank"], top20)
    directional_values = [row for pattern in sorted(directional_ranked) for row in directional_ranked[pattern]]
    directional_columns = list(directional_values[0]) if directional_values else ["regulatory_pattern"]
    write_tsv(out / "directional_candidates.tsv", directional_columns, directional_values)
    write_tsv(out / "preregistered_examples.tsv",
              ["symbol", "canonical_entity_id", "evaluation_state", "rank", "final_score", "regulatory_patterns", "marks"], examples)

    performance = []
    for row in rows(args.trace):
        performance.append({key: row.get(key, "") for key in ("task_id", "native_id", "name", "status", "duration", "realtime", "%cpu", "peak_rss", "peak_vmem")})
    write_tsv(out / "performance.tsv", ["task_id", "native_id", "name", "status", "duration", "realtime", "%cpu", "peak_rss", "peak_vmem"], performance)

    summary = {
        "benchmark": "GSE133183 real biological integration", "status": classification,
        "criteria": {item["criterion"]: item["status"] for item in criteria}, "limitations": limitations,
        "master_genes": master_count, "master_state_counts": {key: dict(value) for key, value in master_states.items()},
        "differential_binding": {key: dict(value) for key, value in db_counts.items()},
        "regulatory_pattern_counts": dict(class_counts), "fisher_tests": len(fisher_rows),
        "directional_fisher_tests": len(directional_tests), "top20_candidates": len(top20),
        "functional_status": functional.get("status"), "functional_record_counts": functional.get("record_counts"),
        "terminal_manifest_sha256": sha256(paths["terminal"]), "report_html_sha256": sha256(paths["report_html"]),
        "git_commit": args.git_commit, "slurm_job_id": job_id,
    }
    (out / "benchmark_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = [
        "# GSE133183 real biological integration", "", f"**Classification:** `{classification}`", "",
        "## Frozen criteria", "", "| Criterion | Type | Status | Metric |", "|---|---|---|---|",
    ]
    report.extend(f"| {item['criterion']} | {item['type']} | {item['status']} | {item['metric']} |" for item in criteria)
    report.extend([
        "", "## Principal observations", "",
        f"- Canonical genes: {master_count:,}.",
        f"- Significant H3K27me3 regions: {me3['significant']:,}; decreased: {me3['decreased']:,}; increased: {me3['increased']:,}.",
        f"- Significant H3K27ac regions: {db_counts['H3K27ac']['significant']:,}; decreased: {db_counts['H3K27ac']['decreased']:,}; increased: {db_counts['H3K27ac']['increased']:,}.",
        f"- Directional Fisher tests available: {len(directional_tests)}.",
        f"- Functional-analysis status: `{functional.get('status')}` with {functional.get('record_counts', {}).get('tests', 0)} formal tests.",
        "", "## Interpretation", "",
        "Technical and contract gates are evaluated independently from expected biological ranges and descriptive outputs.",
        "`NOT_EVALUABLE` does not invent evidence and is retained as a documented limitation.",
    ])
    (out / "real_biological_integration_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    checksum_files = sorted(path for path in out.iterdir() if path.name != "SHA256SUMS")
    (out / "SHA256SUMS").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in checksum_files), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if classification != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
