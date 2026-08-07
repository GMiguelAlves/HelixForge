#!/usr/bin/env python3

import argparse
import importlib.metadata
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Apply pyComBat/ComBat-Seq batch correction to gene-level RNA-seq counts."
    )
    parser.add_argument("--counts", required=True, help="Gene-level counts matrix TSV from step 050.")
    parser.add_argument("--samples", required=True, help="Sample table TSV from step 050.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--batch-column", default="dataset", help="Sample table column used as batch.")
    parser.add_argument(
        "--covariates",
        default="",
        help="Comma-separated categorical covariates to preserve, e.g. life_stage,tissue,sex.",
    )
    parser.add_argument("--output-name", default="counts_batch_corrected.tsv")
    parser.add_argument("--report-name", default="batch_correction_report.json")
    parser.add_argument("--pca-name", default="batch_pca_before_after.png")
    parser.add_argument("--ref-batch", default=None, help="Optional reference batch for pycombat_seq.")
    parser.add_argument("--shrink", action="store_true", help="Enable shrinkage in pycombat_seq.")
    parser.add_argument("--shrink-disp", action="store_true", help="Enable dispersion shrinkage in pycombat_seq.")
    parser.add_argument("--gene-subset-n", type=int, default=None, help="Gene subset size when shrink=True.")
    parser.add_argument(
        "--allow-confounded",
        action="store_true",
        help="Do not fail when a covariate is perfectly nested in the batch column.",
    )
    parser.add_argument(
        "--skip-if-single-batch",
        action="store_true",
        help="Write an unchanged copy if the batch column has fewer than two levels.",
    )
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


def build_covar_model(samples, covariates):
    covariates = [c.strip() for c in covariates.split(",") if c.strip()]
    if not covariates:
        return None, []
    missing = [c for c in covariates if c not in samples.columns]
    if missing:
        raise ValueError("Missing covariate columns: " + ", ".join(missing))
    covar_df = samples[covariates].replace("", np.nan)
    if covar_df.isna().any().any():
        bad_cols = list(covar_df.columns[covar_df.isna().any()])
        raise ValueError("Covariates contain missing values: " + ", ".join(bad_cols))
    return covar_df.astype(str), covariates


def summarize_confounding(samples, batch_column, covariates):
    warnings = []
    crosstabs = {}
    for cov in covariates:
        tab = pd.crosstab(samples[batch_column], samples[cov])
        crosstabs[cov] = tab.to_dict()
        batch_to_cov = tab.gt(0).sum(axis=1)
        cov_to_batch = tab.gt(0).sum(axis=0)
        if (batch_to_cov <= 1).all() or (cov_to_batch <= 1).all():
            warnings.append(f"Covariavel '{cov}' parece fortemente confundida/nested com batch '{batch_column}'.")
    return warnings, crosstabs


def write_counts(df, path):
    out = df.copy()
    out.index.name = "gene_id"
    out.reset_index().to_csv(path, sep="\t", index=False)


def plot_pca(raw_counts, corrected_counts, samples, batch_column, output_path):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    def pca_coords(matrix):
        log_counts = np.log2(matrix.to_numpy(dtype=float) + 1.0).T
        centered = log_counts - log_counts.mean(axis=0)
        _, s, vt = np.linalg.svd(centered, full_matrices=False)
        coords = centered @ vt[:2].T
        if coords.shape[1] < 2:
            coords = np.pad(coords, ((0, 0), (0, 2 - coords.shape[1])), constant_values=0.0)
        denom = np.sum(s**2)
        var = (s[:2] ** 2 / denom * 100) if denom > 0 else np.array([0.0])
        if len(var) < 2:
            var = np.pad(var, (0, 2 - len(var)), constant_values=0.0)
        return coords, var

    raw_coords, raw_var = pca_coords(raw_counts)
    corr_coords, corr_var = pca_coords(corrected_counts)
    batches = samples[batch_column].astype(str).to_numpy()
    levels = sorted(pd.unique(batches))
    color_map = {level: plt.cm.tab20(i % 20) for i, level in enumerate(levels)}

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, coords, var, title in [
        (axes[0], raw_coords, raw_var, "Antes"),
        (axes[1], corr_coords, corr_var, "Depois"),
    ]:
        for level in levels:
            mask = batches == level
            ax.scatter(coords[mask, 0], coords[mask, 1], label=level, s=34, alpha=0.85, color=color_map[level])
        ax.set_title(title)
        ax.set_xlabel(f"PC1 ({var[0]:.1f}%)")
        ax.set_ylabel(f"PC2 ({var[1]:.1f}%)")
        ax.grid(alpha=0.2)
    axes[1].legend(title=batch_column, bbox_to_anchor=(1.04, 1), loc="upper left", fontsize=8)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return True


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    counts = read_matrix(args.counts)
    samples = read_samples(args.samples)
    counts, samples = align_inputs(counts, samples)

    if args.batch_column not in samples.columns:
        raise ValueError(f"Batch column not found in sample table: {args.batch_column}")

    batch = samples[args.batch_column].astype(str).replace("", np.nan)
    if batch.isna().any():
        raise ValueError(f"Batch column contains missing values: {args.batch_column}")
    batch_levels = sorted(batch.unique())

    covar_mod, covariates = build_covar_model(samples, args.covariates)
    confounding_warnings, crosstabs = summarize_confounding(samples, args.batch_column, covariates)
    if confounding_warnings and not args.allow_confounded:
        raise ValueError(
            "Potencial confundimento batch/biologia detectado:\n- "
            + "\n- ".join(confounding_warnings)
            + "\nUse --allow-confounded apenas se isso for intencional."
        )

    corrected_path = output_dir / args.output_name
    pca_path = output_dir / args.pca_name
    report_path = output_dir / args.report_name

    report = {
        "method": "inmoose.pycombat.pycombat_seq",
        "counts": str(Path(args.counts).resolve()),
        "samples": str(Path(args.samples).resolve()),
        "batch_column": args.batch_column,
        "batch_levels": batch_levels,
        "n_genes": int(counts.shape[0]),
        "n_samples": int(counts.shape[1]),
        "covariates": covariates,
        "confounding_warnings": confounding_warnings,
        "crosstabs": crosstabs,
    }

    if len(batch_levels) < 2:
        if not args.skip_if_single_batch:
            raise ValueError(
                f"Batch column '{args.batch_column}' has fewer than two levels. "
                "Use --skip-if-single-batch to write an unchanged copy."
            )
        corrected = counts.copy()
        report["status"] = "skipped_single_batch"
    else:
        try:
            from inmoose.pycombat import pycombat_seq
        except ImportError as exc:
            raise ImportError(
                "Could not import inmoose.pycombat.pycombat_seq. "
                "Create/activate envs/batch-correction.yml or install inmoose."
            ) from exc

        report["inmoose_version"] = importlib.metadata.version("inmoose")
        corrected = pycombat_seq(
            counts,
            list(batch),
            covar_mod=covar_mod,
            shrink=args.shrink,
            shrink_disp=args.shrink_disp,
            gene_subset_n=args.gene_subset_n,
            ref_batch=args.ref_batch,
        )
        corrected = pd.DataFrame(corrected, index=counts.index, columns=counts.columns)
        corrected = corrected.round().clip(lower=0).astype(int)
        report["status"] = "corrected"

    write_counts(corrected, corrected_path)
    pca_written = plot_pca(counts, corrected, samples, args.batch_column, pca_path)
    samples.to_csv(output_dir / "batch_correction_samples.tsv", sep="\t", index=False)

    report["outputs"] = {
        "corrected_counts": str(corrected_path),
        "pca": str(pca_path) if pca_written else None,
        "sample_table": str(output_dir / "batch_correction_samples.tsv"),
    }
    if not pca_written:
        report["pca_warning"] = "matplotlib unavailable; PCA plot was not generated."
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[OK] Counts corrigidos: {corrected_path}")
    if pca_written:
        print(f"[OK] PCA antes/depois: {pca_path}")
    else:
        print("[WARN] PCA antes/depois nao gerado: matplotlib indisponivel.")
    print(f"[OK] Relatorio: {report_path}")


if __name__ == "__main__":
    main()
