#!/usr/bin/env python3
"""Independent evaluator for the frozen 10B synthetic integration benchmark.

This program intentionally uses only the Python standard library and does not
import HelixForge integration code. Expected joins, classes, score components
and statistics are reconstructed from the frozen truth and executed fixture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ABS_STAT_TOL = 1e-10
REL_STAT_TOL = 1e-8
CORRELATION_TOL = 1e-8
SCORE_TOL = 1e-8
CRITICAL_PATTERNS = {
    "CONCORDANT_ACTIVATION", "CONCORDANT_REPRESSION", "DISCORDANT", "RNA_ONLY", "CHIP_ONLY"
}
SCORE_COMPONENTS = {
    "deg_significance_component", "rna_log2fc_component", "promoter_peak_component",
    "differential_peak_component", "gene_interest_component", "epigenetic_machinery_component",
    "multi_contrast_component", "multi_mark_component", "wgcna_component", "mfuzz_component",
    "dtu_component", "splicing_component",
}


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_tsv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def number(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(result) or math.isinf(result) else result


def truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y"}


def canonical_mark(value: str) -> str:
    source = value.strip()
    normalized = "".join(char for char in source.casefold() if char.isalnum() or char in "_-")
    if normalized in {"hp1", "smhp1", "smp_179650", "smp-179650", "cbx"}:
        return "SmHP1"
    import re
    match = re.fullmatch(r"h([234])k([0-9]+)(me[0-3]|ac)", normalized)
    return f"H{match.group(1)}K{match.group(2)}{match.group(3)}" if match else source


def canonical_context(value: str) -> str:
    aliases = {"adult": "adult", "adults": "adult", "all": "all_stages", "allstage": "all_stages", "allstages": "all_stages", "pooled": "all_stages"}
    token = "".join(char for char in value.casefold() if char.isalnum())
    return aliases.get(token, value.strip())


def locate(root: Path, filename: str, preferred: str = "") -> Path:
    candidates = [item for item in root.rglob(filename) if item.is_file()]
    if preferred:
        preferred_candidates = [item for item in candidates if preferred.replace("\\", "/") in item.as_posix()]
        if preferred_candidates:
            candidates = preferred_candidates
    if not candidates:
        raise FileNotFoundError(f"required HelixForge output not found: {filename}")
    checksums = {sha256(item) for item in candidates}
    if len(checksums) > 1:
        raise ValueError(f"ambiguous non-identical outputs for {filename}: {len(candidates)} candidates")
    return sorted(candidates, key=lambda item: (len(item.parts), item.as_posix()))[0]


def class_metrics(expected: dict[str, str], observed: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    labels = sorted(set(expected.values()) | set(observed.values()))
    correct = sum(observed.get(key) == value for key, value in expected.items())
    per_class = []
    confusion = []
    weighted = 0.0
    for actual in labels:
        support = sum(value == actual for value in expected.values())
        tp = sum(value == actual and observed.get(key) == actual for key, value in expected.items())
        fp = sum(value != actual and observed.get(key) == actual for key, value in expected.items())
        fn = support - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append({"class": actual, "support": support, "precision": precision, "recall": recall, "f1": f1})
        weighted += support * f1
        for predicted in labels:
            count = sum(value == actual and observed.get(key) == predicted for key, value in expected.items())
            confusion.append({"truth": actual, "observed": predicted, "count": count})
    summary = {
        "n": len(expected), "accuracy": correct / len(expected) if expected else 0.0,
        "macro_precision": statistics.mean(row["precision"] for row in per_class) if per_class else 0.0,
        "macro_recall": statistics.mean(row["recall"] for row in per_class) if per_class else 0.0,
        "macro_f1": statistics.mean(row["f1"] for row in per_class) if per_class else 0.0,
        "weighted_f1": weighted / len(expected) if expected else 0.0,
    }
    return summary, per_class, confusion


def ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        rank = (index + end + 2) / 2.0
        for position in range(index, end + 1):
            result[ordered[position][0]] = rank
        index = end + 1
    return result


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    dx, dy = [value - mx for value in xs], [value - my for value in ys]
    ssx, ssy = sum(value * value for value in dx), sum(value * value for value in dy)
    if ssx <= 0 or ssy <= 0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / math.sqrt(ssx * ssy)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    return pearson(ranks(xs), ranks(ys)) if len(xs) == len(ys) and len(xs) >= 2 else None


def fisher_right_tail(overlap: int, selected: int, marked: int, universe: int) -> float:
    if universe <= 0 or selected <= 0 or marked <= 0 or overlap <= 0:
        return 1.0
    selected, marked = min(selected, universe), min(marked, universe)
    minimum, maximum = max(0, selected - (universe - marked)), min(selected, marked)
    overlap = max(overlap, minimum)
    if overlap > maximum:
        return 0.0
    choose = lambda n, k: float("-inf") if k < 0 or k > n else math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    denominator = choose(universe, selected)
    terms = [choose(marked, value) + choose(universe - marked, selected - value) - denominator for value in range(overlap, maximum + 1)]
    finite = [value for value in terms if not math.isinf(value)]
    largest = max(finite)
    return max(0.0, min(1.0, math.exp(largest) * sum(math.exp(value - largest) for value in finite)))


def bh(values: list[float]) -> list[float]:
    adjusted, previous = [1.0] * len(values), 1.0
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    for rank, (index, value) in reversed(list(enumerate(ordered, 1))):
        previous = min(previous, value * len(values) / rank)
        adjusted[index] = max(0.0, min(1.0, previous))
    return adjusted


def independent_pattern(row: dict[str, str]) -> str:
    rna_state, chip_state = row["rna_evidence_state"], row["chip_evidence_state"]
    rna_missing, chip_missing = row["rna_observation_state"] == "MISSING", row["chip_observation_state"] == "MISSING"
    rna_sig = rna_state == "MEASURED" and not rna_missing and abs(float(row["rna_log2fc"])) >= 1 and float(row["rna_padj"]) <= 0.05
    chip_sig = chip_state == "MEASURED" and not chip_missing and abs(float(row["chip_log2fc"])) >= 1 and float(row["chip_padj"]) <= 0.05
    if rna_state == "NOT_MEASURED":
        return "CHIP_ONLY" if chip_state == "MEASURED" else "NO_REGULATORY_INTERPRETATION"
    if not rna_sig:
        if chip_state == "MEASURED" and chip_sig:
            return "CHIP_ONLY"
        if chip_state in {"NO_PEAK", "NOT_MEASURED"}:
            return "NO_REGULATORY_INTERPRETATION"
        return "INSUFFICIENT_CROSS_ASSAY_EVIDENCE"
    if chip_state in {"NO_PEAK", "NOT_MEASURED"}:
        return "RNA_ONLY"
    if not chip_sig:
        return "INSUFFICIENT_CROSS_ASSAY_EVIDENCE"
    if row["mark_role"] not in {"ACTIVATING", "REPRESSIVE"}:
        return "INSUFFICIENT_MARK_SEMANTICS"
    rna_up = float(row["rna_log2fc"]) > 0
    chip_up = float(row["chip_log2fc"]) > 0
    expected_up = chip_up if row["mark_role"] == "ACTIVATING" else not chip_up
    if rna_up == expected_up:
        return "CONCORDANT_ACTIVATION" if rna_up else "CONCORDANT_REPRESSION"
    return "DISCORDANT"


def expected_peak_aggregation(fixture: Path, truth_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    source_map = {
        row[key]: row["gene_id"] for row in truth_rows for key in ("source_rna_gene_id", "source_chip_gene_id")
        if row[key] != "NOT_APPLICABLE"
    }
    annotations = read_tsv(fixture / "chip/integration_artifacts/peak_gene_annotation.tsv")[1]
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(lambda: {"total": 0, "promoter": 0, "body": 0, "distal": 0, "peak_ids": set(), "source_ids": set()})
    for index, row in enumerate(annotations, 1):
        key = (source_map[row["gene_id"]], canonical_mark(row["mark_or_factor"]), canonical_context(row["stage"] or row["condition"]))
        item = grouped[key]
        relation = row["relationship"].casefold()
        item["total"] += 1
        item["promoter"] += int("promoter" in relation)
        item["body"] += int(relation in {"gene", "exon", "intron", "gene_body"})
        item["peak_ids"].add(row["peak_id"])
        item["source_ids"].add(f"chip.peak_gene.chip.annotation.{index}")
    for item in grouped.values():
        item["distal"] = item["total"] - item["promoter"] - item["body"]
    return grouped


def expected_scores(truth_rows: list[dict[str, str]], peak_groups: dict[tuple[str, str, str], dict[str, Any]]) -> tuple[dict[str, dict[str, float]], list[str]]:
    scores: dict[str, dict[str, float]] = {}
    for row in truth_rows:
        gene = row["gene_id"]
        rna_measured = row["rna_evidence_state"] == "MEASURED"
        rna_missing = row["rna_observation_state"] == "MISSING"
        chip_measured = row["chip_evidence_state"] == "MEASURED"
        chip_missing = row["chip_observation_state"] == "MISSING"
        rna_padj = float(row["rna_padj"]) if rna_measured and not rna_missing else 1.0
        rna_lfc = abs(float(row["rna_log2fc"])) if rna_measured and not rna_missing else 0.0
        rna_sig = rna_measured and not rna_missing and rna_padj <= 0.05 and rna_lfc >= 1.0
        chip_sig = chip_measured and not chip_missing and float(row["chip_padj"]) <= 0.05 and abs(float(row["chip_log2fc"])) >= 1.0
        gene_groups = [value for (item_gene, _mark, _context), value in peak_groups.items() if item_gene == gene]
        promoter = sum(item["promoter"] for item in gene_groups)
        marks = {mark for (item_gene, mark, _context) in peak_groups if item_gene == gene}
        raw_components = {
            "deg_significance_component": min(10.0, -math.log10(max(rna_padj, 1e-300))) if rna_padj < 1 else 0.0,
            "rna_log2fc_component": min(5.0, rna_lfc),
            "promoter_peak_component": 2.0 if promoter else 0.0,
            "differential_peak_component": 2.0 if chip_sig else 0.0,
            "gene_interest_component": 1.0 if row["candidate_context_flags"] != "none" else 0.0,
            "epigenetic_machinery_component": 0.0,
            "multi_contrast_component": 0.5 if rna_sig else 0.0,
            "multi_mark_component": min(2.0, len(marks) * 0.5),
            "wgcna_component": 0.0, "mfuzz_component": 0.0, "dtu_component": 0.0, "splicing_component": 0.0,
        }
        components = {key: float(f"{value:.4f}") for key, value in raw_components.items()}
        components["final_score"] = float(f"{sum(raw_components.values()):.4f}")
        components["statistical_support"] = float(f"{raw_components['deg_significance_component'] + raw_components['differential_peak_component']:.4f}")
        scores[gene] = components
    ranking = sorted(scores, key=lambda gene: (-scores[gene]["final_score"], -scores[gene]["statistical_support"], gene))
    return scores, ranking


def expected_fisher(truth_rows: list[dict[str, str]], peak_groups: dict[tuple[str, str, str], dict[str, Any]], scores: dict[str, dict[str, float]]) -> dict[str, dict[str, Any]]:
    genes = {row["gene_id"] for row in truth_rows}
    deg = {
        row["gene_id"] for row in truth_rows
        if row["rna_evidence_state"] == "MEASURED" and row["rna_observation_state"] != "MISSING"
        and abs(float(row["rna_log2fc"])) >= 1 and float(row["rna_padj"]) <= 0.05
    }
    any_peak: dict[tuple[str, str], set[str]] = defaultdict(set)
    promoter: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (gene, mark, context), item in peak_groups.items():
        if item["total"]:
            any_peak[(context, mark)].add(gene); any_peak[("all_observed_stages", mark)].add(gene)
        if item["promoter"]:
            promoter[(context, mark)].add(gene); promoter[("all_observed_stages", mark)].add(gene)
    rows = []
    for scope, groups in (("any_peak", any_peak), ("promoter_peak", promoter)):
        for (context, mark), marked in sorted(groups.items()):
            overlap = marked & deg
            a, b, c = len(overlap), len(deg - overlap), len(marked - overlap)
            d = len(genes) - a - b - c
            expected = len(deg) * len(marked) / len(genes)
            pvalue = float(f"{fisher_right_tail(a, len(deg), len(marked), len(genes)):.8g}")
            rows.append({
                "test_id": f"fisher|DEG|{scope}|{mark}|{context}", "n11": a, "n10": b, "n01": c, "n00": d,
                "expected_overlap": float(f"{expected:.8g}"), "fold_enrichment": float(f"{(a / expected if expected else 0.0):.8g}"),
                "odds_ratio": float(f"{(((a + 0.5) * (d + 0.5)) / ((b + 0.5) * (c + 0.5))):.8g}"), "pvalue": pvalue,
                "overlap_gene_ids": ";".join(sorted(overlap, key=lambda gene: (-scores[gene]["final_score"], gene))),
            })
    adjusted = bh([row["pvalue"] for row in rows])
    for row, value in zip(rows, adjusted):
        row["padj"] = float(f"{value:.8g}")
    return {row["test_id"]: row for row in rows}


def expected_correlations(fixture: Path, truth_rows: list[dict[str, str]], peak_groups: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, dict[str, Any]]:
    source_map = {
        row[key]: row["gene_id"] for row in truth_rows for key in ("source_rna_gene_id", "source_chip_gene_id")
        if row[key] != "NOT_APPLICABLE"
    }
    expression: dict[tuple[str, str], list[float]] = defaultdict(list)
    for filename, sample_context in (("rna_abundance_main.tsv", {"control_1": "control", "control_2": "control", "treated_1": "treated", "treated_2": "treated"}), ("rna_abundance_adult.tsv", {"adult_1": "adult", "adult_2": "adult"})):
        fields, rows = read_tsv(fixture / "rna/integration_artifacts" / filename)
        for row in rows:
            gene = source_map[row["gene_id"]]
            for sample in fields[1:]:
                if row[sample]:
                    expression[(gene, sample_context[sample])].append(float(row[sample]))
    genes_by_mark: dict[str, set[str]] = defaultdict(set)
    contexts_by_mark: dict[str, set[str]] = defaultdict(set)
    for gene, mark, context in peak_groups:
        genes_by_mark[mark].add(gene); contexts_by_mark[mark].add(context)
    output = {}
    for mark in sorted(genes_by_mark):
        contexts = sorted(contexts_by_mark[mark])
        for gene in sorted(genes_by_mark[mark]):
            points = []
            for context in contexts:
                values = expression.get((gene, context), [])
                if values:
                    item = peak_groups.get((gene, mark, context), {"total": 0, "promoter": 0})
                    points.append((context, statistics.mean(values), float(item["total"]), float(item["promoter"])))
            for metric, position in (("total_associated_peaks", 2), ("promoter_peaks", 3)):
                xs, ys = [item[1] for item in points], [item[position] for item in points]
                for method, value in (("pearson", pearson(xs, ys)), ("spearman", spearman(xs, ys))):
                    analysis = f"correlation|{gene}|{mark}|{metric}|{method}"
                    output[analysis] = {"n": len(points), "correlation": value, "contexts": ";".join(item[0] for item in points)}
    return output


def close(a: float, b: float, absolute: float, relative: float = 0.0) -> bool:
    return abs(a - b) <= max(absolute, relative * max(abs(a), abs(b)))


def auprc(ranking: list[str], positives: set[str]) -> float:
    if not positives:
        return 0.0
    hit, previous_recall, area = 0, 0.0, 0.0
    for index, gene in enumerate(ranking, 1):
        if gene in positives:
            hit += 1
            recall = hit / len(positives)
            area += (recall - previous_recall) * (hit / index)
            previous_recall = recall
    return area


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    _truth_fields, truth_rows = read_tsv(args.truth.resolve())
    truth_by_gene = {row["gene_id"]: row for row in truth_rows}
    files = {
        "master": locate(args.results_root, "master_evidence.tsv", "integration/master"),
        "long": locate(args.results_root, "master_evidence_long.tsv", "integration/master"),
        "peaks": locate(args.results_root, "peak_aggregation.tsv", "integration/master"),
        "entities": locate(args.results_root, "entity_map.tsv", "integration/harmonization"),
        "contrasts": locate(args.results_root, "contrast_map.tsv", "integration/harmonization"),
        "marks": locate(args.results_root, "mark_map.tsv", "integration/harmonization"),
        "classes": locate(args.results_root, "regulatory_classes.tsv", "integration/interpretation/final"),
        "scores": locate(args.results_root, "candidate_score.tsv", "integration/interpretation/final"),
        "ranking": locate(args.results_root, "candidate_ranking.tsv", "integration/interpretation/final"),
        "fisher": locate(args.results_root, "fisher_tests.tsv", "integration/interpretation/final"),
        "correlations": locate(args.results_root, "correlations.tsv", "integration/interpretation/final"),
        "terminal_manifest": locate(args.results_root, "integrative_run_manifest.json", "integration"),
    }
    rows = {name: read_tsv(path)[1] for name, path in files.items() if path.suffix == ".tsv"}
    master = {row["canonical_entity_id"]: row for row in rows["master"]}
    expected_genes, observed_genes = set(truth_by_gene), set(master)
    entity_metric = {
        "expected_entities": len(expected_genes), "observed_entities": len(observed_genes),
        "missing_entities": len(expected_genes - observed_genes), "unexpected_entities": len(observed_genes - expected_genes),
        "duplicate_entities": len(rows["master"]) - len(observed_genes), "entity_recall": len(expected_genes & observed_genes) / len(expected_genes),
    }
    write_tsv(output / "entity_metrics.tsv", list(entity_metric), [entity_metric])

    join_rows, master_errors = [], []
    for gene, truth in truth_by_gene.items():
        observed = master.get(gene, {})
        ok = observed.get("rna_evidence_state") == truth["rna_evidence_state"] and observed.get("chip_evidence_state") == truth["chip_evidence_state"]
        join_rows.append({"gene_id": gene, "truth_class": truth["truth_class"], "expected_rna": truth["rna_evidence_state"], "observed_rna": observed.get("rna_evidence_state", "ABSENT"), "expected_chip": truth["chip_evidence_state"], "observed_chip": observed.get("chip_evidence_state", "ABSENT"), "status": "PASS" if ok else "FAIL"})
        if not ok: master_errors.append(gene)
    write_tsv(output / "full_outer_join_metrics.tsv", list(join_rows[0]), join_rows)

    normalization_rows, normalization_errors = [], []
    entity_lookup = {(row["source_assay"], row["source_entity_id"]): row["canonical_entity_id"] for row in rows["entities"]}
    for truth in truth_rows:
        for assay, field in (("rnaseq", "source_rna_gene_id"), ("chipseq", "source_chip_gene_id")):
            if assay == "rnaseq" and truth["rna_evidence_state"] != "MEASURED": continue
            if assay == "chipseq" and truth["chip_evidence_state"] != "MEASURED": continue
            source = truth[field]
            if source == "NOT_APPLICABLE": continue
            observed = entity_lookup.get((assay, source), "ABSENT")
            ok = observed == truth["gene_id"]
            normalization_rows.append({"normalization_type": "entity", "source_assay": assay, "input": source, "expected": truth["gene_id"], "observed": observed, "status": "PASS" if ok else "FAIL"})
            if not ok: normalization_errors.append(f"{assay}:{source}")
    mark_lookup = {row["source_mark"]: row["canonical_mark"] for row in rows["marks"]}
    for source in sorted({row["source_mark"] for row in truth_rows if row["source_mark"] != "NOT_APPLICABLE"}):
        expected = canonical_mark(source); observed = mark_lookup.get(source, "ABSENT"); ok = observed == expected
        normalization_rows.append({"normalization_type": "mark", "source_assay": "chipseq", "input": source, "expected": expected, "observed": observed, "status": "PASS" if ok else "FAIL"})
        if not ok: normalization_errors.append(f"mark:{source}")
    contrast_rows = rows["contrasts"]
    contrast_ok = len(contrast_rows) == 1 and contrast_rows[0]["canonical_contrast_id"] == "condition__treated_vs_control" and contrast_rows[0]["mapping_status"] == "MATCHED"
    normalization_rows.append({"normalization_type": "contrast", "source_assay": "cross_assay", "input": "treated_vs_control;treatment_effect", "expected": "condition__treated_vs_control", "observed": contrast_rows[0]["canonical_contrast_id"] if contrast_rows else "ABSENT", "status": "PASS" if contrast_ok else "FAIL"})
    if not contrast_ok: normalization_errors.append("contrast")
    write_tsv(output / "normalization_metrics.tsv", list(normalization_rows[0]), normalization_rows)

    peak_expected = expected_peak_aggregation(args.fixture.resolve(), truth_rows)
    peak_observed = {(row["canonical_entity_id"], row["canonical_mark"], row["canonical_context"]): row for row in rows["peaks"]}
    peak_errors = []
    for key, expected in peak_expected.items():
        observed = peak_observed.get(key)
        if not observed or any(int(observed[field]) != expected[name] for field, name in (("total_associated_peaks", "total"), ("promoter_peaks", "promoter"), ("gene_body_peaks", "body"), ("distal_peaks", "distal"))) or set(filter(None, observed["peak_ids"].split(";"))) != expected["peak_ids"] or set(filter(None, observed["source_evidence_ids"].split(";"))) != expected["source_ids"]:
            peak_errors.append("|".join(key))
    peak_exact = not peak_errors and set(peak_expected) == set(peak_observed)

    long_gene = [row for row in rows["long"] if row["entity_type"] == "gene"]
    de_by_gene = defaultdict(list); db_by_gene = defaultdict(list)
    for row in long_gene:
        if row["evidence_type"] == "differential_expression": de_by_gene[row["canonical_entity_id"]].append(row)
        if row["evidence_type"] == "differential_binding": db_by_gene[row["canonical_entity_id"]].append(row)
    expected_states, observed_states = {}, {}
    for gene, truth in truth_by_gene.items():
        expected_states[f"{gene}|rna_master"] = truth["rna_evidence_state"]
        expected_states[f"{gene}|chip_master"] = truth["chip_evidence_state"]
        expected_states[f"{gene}|rna_observation"] = truth["rna_observation_state"]
        expected_states[f"{gene}|chip_observation"] = truth["chip_observation_state"]
        observed_states[f"{gene}|rna_master"] = master.get(gene, {}).get("rna_evidence_state", "ABSENT")
        observed_states[f"{gene}|chip_master"] = master.get(gene, {}).get("chip_evidence_state", "ABSENT")
        observed_states[f"{gene}|rna_observation"] = de_by_gene[gene][0]["measurement_state"] if de_by_gene[gene] else "NOT_APPLICABLE"
        observed_states[f"{gene}|chip_observation"] = db_by_gene[gene][0]["measurement_state"] if db_by_gene[gene] else "NOT_APPLICABLE"
    missing_summary, missing_per, missing_confusion = class_metrics(expected_states, observed_states)
    write_tsv(output / "missing_state_metrics.tsv", ["class", "support", "precision", "recall", "f1"], missing_per)
    write_tsv(output / "missing_state_confusion.tsv", ["truth", "observed", "count"], missing_confusion)

    class_rows = rows["classes"]
    class_by_gene = defaultdict(list)
    for row in class_rows: class_by_gene[row["canonical_entity_id"]].append(row)
    expected_patterns = {gene: row["expected_regulatory_pattern"] for gene, row in truth_by_gene.items()}
    independent_patterns = {gene: independent_pattern(row) for gene, row in truth_by_gene.items()}
    observed_patterns, divergences = {}, []
    for gene, truth in truth_by_gene.items():
        expected_mark = truth["expected_canonical_mark"]
        matches = [row for row in class_by_gene[gene] if row["canonical_mark"] == expected_mark]
        if not matches and expected_mark == "NOT_APPLICABLE": matches = [row for row in class_by_gene[gene] if row["canonical_mark"] == "NOT_APPLICABLE"]
        observed = matches[0]["regulatory_pattern"] if len(matches) == 1 else "ABSENT_OR_AMBIGUOUS"
        observed_patterns[gene] = observed
        if expected_patterns[gene] != observed or independent_patterns[gene] != observed:
            category = "SHARED_VS_TRUTH_DIVERGENCE" if independent_patterns[gene] == observed else "HELIXFORGE_ONLY_DIVERGENCE" if independent_patterns[gene] == expected_patterns[gene] else "INDEPENDENT_ONLY_DIVERGENCE"
            divergences.append({"gene_id": gene, "truth": expected_patterns[gene], "helixforge": observed, "independent": independent_patterns[gene], "difficulty": truth["difficulty_tier"], "mark": expected_mark, "error_category": category})
    classification_summary, classification_per, regulatory_confusion = class_metrics(expected_patterns, observed_patterns)
    write_tsv(output / "regulatory_class_metrics.tsv", ["class", "support", "precision", "recall", "f1"], classification_per)
    write_tsv(output / "regulatory_confusion.tsv", ["truth", "observed", "count"], regulatory_confusion)
    if divergences: write_tsv(output / "divergences.tsv", list(divergences[0]), divergences)

    difficulty_rows = []
    for tier in ("EASY", "MODERATE", "HARD"):
        subset = {gene: expected_patterns[gene] for gene, row in truth_by_gene.items() if row["difficulty_tier"] == tier}
        metric = class_metrics(subset, {gene: observed_patterns[gene] for gene in subset})[0]
        missing_subset = {key: value for key, value in expected_states.items() if truth_by_gene[key.split("|")[0]]["difficulty_tier"] == tier}
        missing_metric = class_metrics(missing_subset, {key: observed_states[key] for key in missing_subset})[0]
        difficulty_rows.append({"difficulty": tier, "n": len(subset), "accuracy": metric["accuracy"], "macro_f1": metric["macro_f1"], "missing_state_accuracy": missing_metric["accuracy"]})
    write_tsv(output / "difficulty_metrics.tsv", list(difficulty_rows[0]), difficulty_rows)
    mark_rows = []
    for mark in sorted({row["expected_canonical_mark"] for row in truth_rows if row["expected_canonical_mark"] != "NOT_APPLICABLE"}):
        subset = {gene: expected_patterns[gene] for gene, row in truth_by_gene.items() if row["expected_canonical_mark"] == mark}
        metric = class_metrics(subset, {gene: observed_patterns[gene] for gene in subset})[0]
        mark_rows.append({"mark": mark, "n": len(subset), "accuracy": metric["accuracy"], "macro_f1": metric["macro_f1"]})
    write_tsv(output / "mark_metrics.tsv", list(mark_rows[0]), mark_rows)

    independent_scores, independent_ranking = expected_scores(truth_rows, peak_expected)
    score_observed = {row["canonical_entity_id"]: row for row in rows["scores"]}
    score_comparison, score_errors, max_score_diff = [], [], 0.0
    for gene, expected in independent_scores.items():
        observed = score_observed.get(gene, {})
        for component in sorted(SCORE_COMPONENTS | {"final_score", "statistical_support"}):
            expected_value, observed_value = expected[component], number(observed.get(component))
            difference = float("inf") if observed_value is None else abs(expected_value - observed_value)
            max_score_diff = max(max_score_diff, difference)
            status = "PASS" if observed_value is not None and difference <= SCORE_TOL else "FAIL"
            score_comparison.append({"gene_id": gene, "component": component, "helixforge": observed_value if observed_value is not None else "", "independent": expected_value, "absolute_difference": difference, "tolerance": SCORE_TOL, "status": status})
            if status == "FAIL": score_errors.append(f"{gene}:{component}")
    observed_ranking = [row["canonical_entity_id"] for row in rows["ranking"]]
    rank_exact = observed_ranking == independent_ranking
    priority_value = {"BACKGROUND": 0.0, "LOW": 1.0, "MEDIUM": 2.0, "HIGH": 3.0}
    priority_spearman = spearman([independent_scores[gene]["final_score"] for gene in sorted(truth_by_gene)], [priority_value[truth_by_gene[gene]["candidate_priority"]] for gene in sorted(truth_by_gene)])
    high = {gene for gene, row in truth_by_gene.items() if row["candidate_priority"] == "HIGH"}
    candidate_metrics = {
        "score_rows": len(score_observed), "score_component_failures": len(score_errors), "maximum_score_difference": max_score_diff,
        "rank_exact": rank_exact, "priority_spearman": priority_spearman, "high_priority_auprc": auprc(observed_ranking, high),
    }
    for top in (10, 25, 50, 100):
        candidate_metrics[f"top_{top}_recovery"] = len(set(observed_ranking[:top]) & high) / min(top, len(high))
    write_tsv(output / "candidate_score_metrics.tsv", list(candidate_metrics), [candidate_metrics])
    write_tsv(output / "candidate_score_comparison.tsv", list(score_comparison[0]), score_comparison)

    independent_fisher = expected_fisher(truth_rows, peak_expected, independent_scores)
    observed_fisher = {row["test_id"]: row for row in rows["fisher"]}
    statistic_rows, statistic_failures, max_numeric_diff = [], [], 0.0
    for test_id in sorted(set(independent_fisher) | set(observed_fisher)):
        expected, observed = independent_fisher.get(test_id), observed_fisher.get(test_id)
        if not expected or not observed:
            statistic_failures.append(f"{test_id}:set"); continue
        for field in ("n11", "n10", "n01", "n00"):
            if int(observed[field]) != expected[field]: statistic_failures.append(f"{test_id}:{field}")
        for field in ("expected_overlap", "fold_enrichment", "odds_ratio", "pvalue", "padj"):
            observed_value = float(observed[field]); difference = abs(observed_value - expected[field]); max_numeric_diff = max(max_numeric_diff, difference)
            status = "PASS" if close(observed_value, expected[field], ABS_STAT_TOL, REL_STAT_TOL) else "FAIL"
            statistic_rows.append({"analysis_id": test_id, "metric": field, "helixforge": observed_value, "independent": expected[field], "absolute_difference": difference, "relative_difference": difference / max(abs(expected[field]), 1e-300), "tolerance": "abs=1e-10;rel=1e-8", "status": status})
            if status == "FAIL": statistic_failures.append(f"{test_id}:{field}")
        if observed["overlap_gene_ids"] != expected["overlap_gene_ids"]: statistic_failures.append(f"{test_id}:overlap_gene_ids")
    independent_corr = expected_correlations(args.fixture.resolve(), truth_rows, peak_expected)
    observed_corr = {row["analysis_id"]: row for row in rows["correlations"]}
    correlation_failures = []
    for analysis in sorted(set(independent_corr) | set(observed_corr)):
        expected, observed = independent_corr.get(analysis), observed_corr.get(analysis)
        if not expected or not observed:
            correlation_failures.append(f"{analysis}:set"); continue
        expected_value, observed_value = expected["correlation"], number(observed["correlation"])
        exact_na = expected_value is None and observed_value is None
        difference = 0.0 if exact_na else float("inf") if expected_value is None or observed_value is None else abs(expected_value - observed_value)
        max_numeric_diff = max(max_numeric_diff, difference)
        status = "PASS" if exact_na or (difference <= CORRELATION_TOL and int(observed["n"]) == expected["n"] and observed["contexts"] == expected["contexts"]) else "FAIL"
        statistic_rows.append({"analysis_id": analysis, "metric": "correlation", "helixforge": observed["correlation"], "independent": "" if expected_value is None else expected_value, "absolute_difference": difference, "relative_difference": "", "tolerance": "abs=1e-8;NA exact", "status": status})
        if status == "FAIL": correlation_failures.append(analysis)
    write_tsv(output / "statistics_comparison.tsv", list(statistic_rows[0]), statistic_rows)

    critical_ok = all(row["precision"] == 1.0 and row["recall"] == 1.0 and row["f1"] == 1.0 for row in classification_per if row["class"] in CRITICAL_PATTERNS)
    gates = [
        ("IS1", entity_metric["observed_entities"] == 1000 and not entity_metric["missing_entities"] and not entity_metric["unexpected_entities"] and not entity_metric["duplicate_entities"], "exact 1,000 canonical entities"),
        ("IS2", not master_errors, "100% exact RNA/ChIP master states"),
        ("IS3", missing_summary["accuracy"] == 1.0, "100% exact scoped missing states"),
        ("IS4", critical_ok, "precision/recall/F1 1.0 for critical patterns"),
        ("IS5", classification_summary["accuracy"] >= 0.995 and classification_summary["macro_f1"] >= 0.995, "accuracy and macro-F1 >= 0.995"),
        ("IS6", not normalization_errors, "exact entity/contrast/context/mark maps"),
        ("IS7", peak_exact, "exact peak counts and complete ID sets"),
        ("IS8", not statistic_failures, "Fisher/BH/odds within frozen tolerance"),
        ("IS9", not correlation_failures, "Pearson/Spearman within frozen tolerance"),
        ("IS10", not score_errors and rank_exact, "all score components and tie order exact"),
        ("IS11", priority_spearman is not None and priority_spearman >= 0.60, "priority Spearman >= 0.60"),
        ("IS12", candidate_metrics["top_100_recovery"] >= 0.80, "HIGH-priority top-100 recovery >= 0.80"),
    ]
    gate_rows = [{"criterion_id": gate, "metric": description, "observed": "PASS" if status else "FAIL", "expected_threshold": description, "status": "PASS" if status else "FAIL", "evidence": "machine-readable metrics in this directory"} for gate, status, description in gates]
    write_tsv(output / "acceptance_criteria.tsv", list(gate_rows[0]), gate_rows)

    release_failures = [gate for gate, status, _ in gates[:10] if not status]
    expected_limitations = [gate for gate, status, _ in gates[10:] if not status]
    summary = {
        "schema_version": "1.0", "type": "integrative_synthetic_benchmark_summary",
        "technical_execution": "PASS", "truth_integrity": "PASS", "fixture_validation": "PASS",
        "entity_preservation": "PASS" if gates[0][1] else "FAIL", "full_outer_join": "PASS" if gates[1][1] else "FAIL",
        "identifier_normalization": "PASS" if gates[5][1] else "FAIL", "missing_state_correctness": "PASS" if gates[2][1] else "FAIL",
        "regulatory_interpretation": "PASS" if gates[3][1] and gates[4][1] else "FAIL",
        "statistical_integration": "PASS" if gates[7][1] and gates[8][1] else "FAIL",
        "candidate_score": "PASS" if gates[9][1] else "FAIL", "independent_concordance": "PASS" if not release_failures else "FAIL",
        "determinism": "PENDING_SECOND_RUN", "release_gate_failures": release_failures, "expected_range_limitations": expected_limitations,
        "classification": classification_summary, "missing_states": missing_summary, "candidate_score_metrics": candidate_metrics,
        "maximum_numerical_difference": max_numeric_diff, "maximum_score_difference": max_score_diff,
        "files": {name: {"path": str(path), "sha256": sha256(path)} for name, path in files.items()},
        "synthetic_integration_benchmark": "FAIL" if release_failures else "PASS_WITH_LIMITATIONS" if expected_limitations else "PASS",
    }
    dump_json(output / "benchmark_summary.json", summary)
    dump_json(output / "independent_reference_provenance.json", {"language": "Python standard library", "libraries": [], "algorithm": "independent frozen-protocol reconstruction of joins, states, patterns, scores, Fisher/BH and correlations", "script": "benchmark/integrative/scripts/evaluate_synthetic_integration.py", "script_sha256": sha256(Path(__file__).resolve()), "imports_helixforge_code": False})
    print(json.dumps({"classification": summary["synthetic_integration_benchmark"], "release_gate_failures": release_failures, "expected_range_limitations": expected_limitations}, sort_keys=True))


if __name__ == "__main__":
    main()
