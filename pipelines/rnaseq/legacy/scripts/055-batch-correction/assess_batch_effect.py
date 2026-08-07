#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Assess batch effect strength before and optionally after correction."
    )
    parser.add_argument("--counts", required=True, help="Raw counts matrix TSV from step 050.")
    parser.add_argument("--samples", required=True, help="Sample table TSV from step 050.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--batch-column", default="dataset", help="Sample table column used as batch.")
    parser.add_argument("--corrected-counts", default="", help="Optional corrected counts matrix TSV from step 055.")
    parser.add_argument(
        "--covariates",
        default="",
        help="Comma-separated biological covariates to evaluate alongside batch.",
    )
    parser.add_argument("--top-variable-genes", type=int, default=5000)
    parser.add_argument("--min-total-count", type=int, default=10)
    parser.add_argument("--n-pcs", type=int, default=10)
    parser.add_argument("--permutations", type=int, default=199)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--report-name", default="batch_effect_assessment.json")
    parser.add_argument("--metrics-name", default="batch_effect_metrics.tsv")
    parser.add_argument("--pc-scores-name", default="batch_effect_pc_scores.tsv")
    parser.add_argument("--plot-name", default="batch_effect_pca.png")
    return parser.parse_args()


def read_matrix(path):
    df = pd.read_csv(path, sep="\t")
    if df.shape[1] < 2:
        raise ValueError(f"Counts matrix has fewer than two columns: {path}")
    gene_col = df.columns[0]
    counts = df.set_index(gene_col)
    counts.index.name = "gene_id"
    counts = counts.apply(pd.to_numeric, errors="coerce")
    if counts.isna().any().any():
        bad = int(counts.isna().sum().sum())
        raise ValueError(f"Counts matrix contains {bad} non-numeric values.")
    return counts.round().clip(lower=0).astype(int)


def read_samples(path):
    samples = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    if "import_id" not in samples.columns:
        if "sample_id" in samples.columns:
            samples["import_id"] = samples["sample_id"]
        else:
            raise ValueError("Sample table must contain import_id or sample_id.")
    if {"dataset", "sample_id"}.issubset(samples.columns):
        samples["import_id_combined"] = samples["dataset"] + "__" + samples["sample_id"]
    return samples


def align_inputs(counts, samples):
    if not set(counts.columns).issubset(set(samples["import_id"])) and "import_id_combined" in samples.columns:
        if set(counts.columns).issubset(set(samples["import_id_combined"])):
            samples = samples.copy()
            samples["import_id"] = samples["import_id_combined"]
    samples = samples[samples["import_id"].isin(counts.columns)].copy()
    missing_meta = sorted(set(counts.columns) - set(samples["import_id"]))
    if missing_meta:
        raise ValueError("Counts columns without sample metadata: " + ", ".join(missing_meta[:20]))
    duplicated = samples["import_id"][samples["import_id"].duplicated()].unique()
    if len(duplicated) > 0:
        raise ValueError("Duplicated import_id in sample table: " + ", ".join(duplicated[:20]))
    samples = samples.set_index("import_id").loc[list(counts.columns)].reset_index()
    return counts.loc[:, list(samples["import_id"])], samples


def select_gene_index(counts, min_total_count, top_variable_genes):
    counts = counts.loc[counts.sum(axis=1) >= min_total_count]
    if counts.empty:
        raise ValueError("No genes left after min-total-count filtering.")
    library_sizes = counts.sum(axis=0)
    if (library_sizes <= 0).any():
        bad = list(library_sizes[library_sizes <= 0].index)
        raise ValueError("Samples with zero library size: " + ", ".join(bad[:20]))
    cpm = counts.div(library_sizes, axis=1) * 1_000_000
    log_cpm = np.log2(cpm + 1.0)
    if top_variable_genes > 0 and log_cpm.shape[0] > top_variable_genes:
        variances = log_cpm.var(axis=1)
        return list(variances.sort_values(ascending=False).head(top_variable_genes).index)
    return list(log_cpm.index)


def prepare_expression(counts, gene_index):
    missing = [gene for gene in gene_index if gene not in counts.index]
    if missing:
        raise ValueError("Corrected matrix is missing genes used for assessment: " + ", ".join(missing[:20]))
    counts = counts.loc[gene_index]
    library_sizes = counts.sum(axis=0)
    if (library_sizes <= 0).any():
        bad = list(library_sizes[library_sizes <= 0].index)
        raise ValueError("Samples with zero library size: " + ", ".join(bad[:20]))
    cpm = counts.div(library_sizes, axis=1) * 1_000_000
    log_cpm = np.log2(cpm + 1.0)
    return log_cpm


def pca(matrix, n_pcs):
    x = matrix.T.to_numpy(dtype=float)
    x = x - x.mean(axis=0)
    _, s, vt = np.linalg.svd(x, full_matrices=False)
    n = min(n_pcs, vt.shape[0], x.shape[0])
    coords = x @ vt[:n].T
    denom = float(np.sum(s**2))
    variance = (s[:n] ** 2 / denom) if denom > 0 else np.zeros(n)
    pc_names = [f"PC{i + 1}" for i in range(n)]
    scores = pd.DataFrame(coords, index=matrix.columns, columns=pc_names)
    if "PC2" not in scores.columns:
        scores["PC2"] = 0.0
        variance = np.pad(variance, (0, 1), constant_values=0.0)
    return scores, variance


def categorical_eta2(values, groups):
    values = np.asarray(values, dtype=float)
    groups = np.asarray(groups, dtype=str)
    overall = values.mean()
    ss_total = float(np.sum((values - overall) ** 2))
    if ss_total <= 0:
        return 0.0
    ss_between = 0.0
    for level in np.unique(groups):
        y = values[groups == level]
        ss_between += len(y) * float((y.mean() - overall) ** 2)
    return ss_between / ss_total


def pc_association(scores, variance, groups, permutations, rng):
    groups = np.asarray(groups, dtype=str)
    rows = []
    for i, pc in enumerate(scores.columns):
        observed = categorical_eta2(scores[pc].to_numpy(), groups)
        pvalue = np.nan
        if permutations > 0 and len(np.unique(groups)) > 1:
            permuted = 0
            for _ in range(permutations):
                shuffled = rng.permutation(groups)
                if categorical_eta2(scores[pc].to_numpy(), shuffled) >= observed:
                    permuted += 1
            pvalue = (permuted + 1) / (permutations + 1)
        rows.append(
            {
                "pc": pc,
                "variance_fraction": float(variance[i]),
                "eta2": float(observed),
                "pvalue": None if np.isnan(pvalue) else float(pvalue),
            }
        )
    return rows


def multivariate_r2(matrix, groups):
    x = matrix.T.to_numpy(dtype=float)
    groups = np.asarray(groups, dtype=str)
    overall = x.mean(axis=0)
    ss_total = float(np.sum((x - overall) ** 2))
    levels = np.unique(groups)
    if ss_total <= 0 or len(levels) < 2:
        return {"r2": 0.0, "pseudo_f": 0.0}
    ss_between = 0.0
    for level in levels:
        subset = x[groups == level]
        ss_between += subset.shape[0] * float(np.sum((subset.mean(axis=0) - overall) ** 2))
    ss_within = ss_total - ss_between
    df_between = len(levels) - 1
    df_within = x.shape[0] - len(levels)
    pseudo_f = np.inf if ss_within <= 0 else (ss_between / df_between) / (ss_within / max(df_within, 1))
    return {"r2": float(ss_between / ss_total), "pseudo_f": float(pseudo_f)}


def multivariate_permutation_pvalue(matrix, groups, observed_f, permutations, rng):
    if permutations <= 0 or len(np.unique(groups)) < 2:
        return None
    hits = 0
    groups = np.asarray(groups, dtype=str)
    for _ in range(permutations):
        shuffled = rng.permutation(groups)
        if multivariate_r2(matrix, shuffled)["pseudo_f"] >= observed_f:
            hits += 1
    return float((hits + 1) / (permutations + 1))


def evaluate_dataset(label, counts, samples, variables, args, rng, gene_index):
    expr = prepare_expression(counts, gene_index)
    scores, variance = pca(expr, args.n_pcs)
    score_out = scores.reset_index().rename(columns={"index": "import_id"})
    score_out.insert(0, "matrix", label)

    metric_rows = []
    summary = {"n_genes_used": int(expr.shape[0]), "n_samples": int(expr.shape[1]), "variables": {}}
    for variable in variables:
        if variable not in samples.columns:
            raise ValueError(f"Variable not found in sample table: {variable}")
        groups = samples[variable].astype(str).replace("", np.nan)
        if groups.isna().any():
            raise ValueError(f"Variable contains missing values: {variable}")
        groups = groups.to_numpy()
        pc_rows = pc_association(scores, variance, groups, args.permutations, rng)
        weighted_pc_eta2 = float(sum(row["eta2"] * row["variance_fraction"] for row in pc_rows))
        mv = multivariate_r2(expr, groups)
        mv_p = multivariate_permutation_pvalue(expr, groups, mv["pseudo_f"], args.permutations, rng)

        for row in pc_rows:
            metric_rows.append(
                {
                    "matrix": label,
                    "variable": variable,
                    "metric": "pc_eta2",
                    "component": row["pc"],
                    "value": row["eta2"],
                    "variance_fraction": row["variance_fraction"],
                    "pvalue": row["pvalue"],
                }
            )
        metric_rows.extend(
            [
                {
                    "matrix": label,
                    "variable": variable,
                    "metric": "weighted_pc_eta2",
                    "component": "PCs",
                    "value": weighted_pc_eta2,
                    "variance_fraction": float(np.sum(variance)),
                    "pvalue": None,
                },
                {
                    "matrix": label,
                    "variable": variable,
                    "metric": "multivariate_r2",
                    "component": "logCPM",
                    "value": mv["r2"],
                    "variance_fraction": None,
                    "pvalue": mv_p,
                },
                {
                    "matrix": label,
                    "variable": variable,
                    "metric": "multivariate_pseudo_f",
                    "component": "logCPM",
                    "value": mv["pseudo_f"],
                    "variance_fraction": None,
                    "pvalue": mv_p,
                },
            ]
        )
        summary["variables"][variable] = {
            "levels": sorted(pd.unique(groups)),
            "weighted_pc_eta2": weighted_pc_eta2,
            "multivariate_r2": mv["r2"],
            "multivariate_pvalue": mv_p,
        }
    return score_out, metric_rows, summary


def interpret(raw_summary, corrected_summary, batch_column):
    raw = raw_summary["variables"][batch_column]
    r2 = raw["multivariate_r2"]
    p = raw["multivariate_pvalue"]
    weighted = raw["weighted_pc_eta2"]
    evidence = "fraco/ausente"
    if r2 >= 0.10 or weighted >= 0.10 or (p is not None and p <= 0.05):
        evidence = "moderado/forte"
    elif r2 >= 0.05 or weighted >= 0.05:
        evidence = "possivel"

    result = {
        "raw_batch_evidence": evidence,
        "raw_batch_multivariate_r2": r2,
        "raw_batch_weighted_pc_eta2": weighted,
        "raw_batch_pvalue": p,
    }
    if corrected_summary is not None:
        corrected = corrected_summary["variables"][batch_column]
        corrected_r2 = corrected["multivariate_r2"]
        reduction = None if r2 == 0 else (r2 - corrected_r2) / r2
        status = "nao_avaliado"
        if reduction is not None:
            if reduction >= 0.5 and corrected_r2 < 0.05:
                status = "correcao_eficiente"
            elif reduction > 0:
                status = "correcao_parcial"
            else:
                status = "sem_melhoria_clara"
        result.update(
            {
                "corrected_batch_multivariate_r2": corrected_r2,
                "batch_r2_reduction_fraction": reduction,
                "correction_status": status,
            }
        )
    return result


def plot_pca(scores_df, samples, batch_column, output_path):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    matrices = list(scores_df["matrix"].drop_duplicates())
    fig, axes = plt.subplots(1, len(matrices), figsize=(6 * len(matrices), 5), squeeze=False, constrained_layout=True)
    color_values = samples.set_index("import_id")[batch_column].astype(str)
    levels = sorted(color_values.unique())
    color_map = {level: plt.cm.tab20(i % 20) for i, level in enumerate(levels)}

    for ax, label in zip(axes[0], matrices):
        part = scores_df[scores_df["matrix"] == label].copy()
        colors = [color_map[color_values.loc[sid]] for sid in part["import_id"]]
        ax.scatter(part["PC1"], part.get("PC2", 0.0), s=34, alpha=0.85, c=colors)
        ax.set_title(label)
        ax.set_xlabel("PC1")
        ax.set_ylabel("PC2")
        ax.grid(alpha=0.2)

    handles = [
        plt.Line2D([0], [0], marker="o", color="w", label=level, markerfacecolor=color_map[level], markersize=8)
        for level in levels
    ]
    axes[0, -1].legend(handles=handles, title=batch_column, bbox_to_anchor=(1.04, 1), loc="upper left", fontsize=8)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    raw_counts = read_matrix(args.counts)
    samples = read_samples(args.samples)
    raw_counts, samples = align_inputs(raw_counts, samples)
    gene_index = select_gene_index(raw_counts, args.min_total_count, args.top_variable_genes)

    variables = [args.batch_column] + [c.strip() for c in args.covariates.split(",") if c.strip()]
    variables = list(dict.fromkeys(variables))
    if args.batch_column not in samples.columns:
        raise ValueError(f"Batch column not found in sample table: {args.batch_column}")

    all_scores = []
    all_metrics = []
    raw_scores, raw_metrics, raw_summary = evaluate_dataset("raw", raw_counts, samples, variables, args, rng, gene_index)
    all_scores.append(raw_scores)
    all_metrics.extend(raw_metrics)

    corrected_summary = None
    if args.corrected_counts:
        corrected_counts = read_matrix(args.corrected_counts)
        missing_cols = sorted(set(raw_counts.columns) - set(corrected_counts.columns))
        if missing_cols:
            raise ValueError("Corrected matrix is missing samples: " + ", ".join(missing_cols[:20]))
        corrected_counts = corrected_counts.loc[:, list(raw_counts.columns)]
        corrected_scores, corrected_metrics, corrected_summary = evaluate_dataset(
            "corrected", corrected_counts, samples, variables, args, rng, gene_index
        )
        all_scores.append(corrected_scores)
        all_metrics.extend(corrected_metrics)

    scores_df = pd.concat(all_scores, ignore_index=True)
    metrics_df = pd.DataFrame(all_metrics)

    scores_out = output_dir / args.pc_scores_name
    metrics_out = output_dir / args.metrics_name
    report_out = output_dir / args.report_name
    plot_out = output_dir / args.plot_name

    scores_df.to_csv(scores_out, sep="\t", index=False)
    metrics_df.to_csv(metrics_out, sep="\t", index=False)
    plot_written = plot_pca(scores_df, samples, args.batch_column, plot_out)

    report = {
        "counts": str(Path(args.counts).resolve()),
        "samples": str(Path(args.samples).resolve()),
        "corrected_counts": str(Path(args.corrected_counts).resolve()) if args.corrected_counts else None,
        "batch_column": args.batch_column,
        "covariates": [v for v in variables if v != args.batch_column],
        "top_variable_genes": args.top_variable_genes,
        "min_total_count": args.min_total_count,
        "n_pcs": args.n_pcs,
        "permutations": args.permutations,
        "raw": raw_summary,
        "corrected": corrected_summary,
        "interpretation": interpret(raw_summary, corrected_summary, args.batch_column),
        "outputs": {
            "metrics": str(metrics_out),
            "pc_scores": str(scores_out),
            "pca_plot": str(plot_out) if plot_written else None,
        },
    }
    if not plot_written:
        report["pca_warning"] = "matplotlib unavailable; PCA plot was not generated."
    report_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[OK] Metricas: {metrics_out}")
    print(f"[OK] PC scores: {scores_out}")
    if plot_written:
        print(f"[OK] PCA: {plot_out}")
    else:
        print("[WARN] PCA nao gerado: matplotlib indisponivel.")
    print(f"[OK] Relatorio: {report_out}")


if __name__ == "__main__":
    main()
