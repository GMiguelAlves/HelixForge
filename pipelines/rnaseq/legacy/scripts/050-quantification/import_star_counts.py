#!/usr/bin/env python3
"""
Import STAR GeneCounts files into pipeline-wide gene matrices.

STAR writes one ReadsPerGene.out.tab per sample when run with:

    --quantMode GeneCounts

The columns are gene_id, unstranded counts, stranded-forward counts and
stranded-reverse counts. This script selects one configured count column,
combines samples into a count matrix, and writes a CPM matrix for exploratory
reports.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


COUNT_COLUMNS = {
    "unstranded": "unstranded",
    "2": "unstranded",
    "stranded_forward": "stranded_forward",
    "3": "stranded_forward",
    "stranded_reverse": "stranded_reverse",
    "4": "stranded_reverse",
}


def read_metadata(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=None, engine="python", dtype=str, keep_default_na=False)


def read_star_counts(path: Path, count_column: str) -> pd.Series:
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=["gene_id", "unstranded", "stranded_forward", "stranded_reverse"],
        dtype={"gene_id": str},
    )
    df = df.loc[~df["gene_id"].str.startswith("N_")].copy()
    df["gene_id"] = df["gene_id"].str.replace(r"^gene:", "", regex=True)
    df["gene_id"] = df["gene_id"].str.replace(r"\.[0-9]+$", "", regex=True)
    df[count_column] = pd.to_numeric(df[count_column], errors="coerce").fillna(0).astype(int)
    return df.set_index("gene_id")[count_column]


def make_sample_table(metadata: pd.DataFrame, project: str, quant_root: Path) -> pd.DataFrame:
    required = {"dataset", "sample_id"}
    missing = sorted(required - set(metadata.columns))
    if missing:
        raise ValueError("metadata missing required columns: " + ", ".join(missing))

    sample_meta = metadata.loc[metadata["sample_id"].astype(str) != ""].copy()
    sample_meta = sample_meta.drop_duplicates(["dataset", "sample_id"])
    if project:
        sample_meta = sample_meta.loc[sample_meta["dataset"] == project].copy()
    if sample_meta.empty:
        suffix = f" for {project}" if project else ""
        raise ValueError(f"no samples found in metadata{suffix}")

    sample_meta = sample_meta.sort_values(["dataset", "sample_id"]).reset_index(drop=True)
    sample_meta["import_id"] = sample_meta.apply(
        lambda row: row["sample_id"] if project else f"{row['dataset']}__{row['sample_id']}",
        axis=1,
    )
    if sample_meta["import_id"].duplicated().any():
        duplicated = sample_meta.loc[sample_meta["import_id"].duplicated(), "import_id"].unique()
        raise ValueError("duplicated import_id values: " + ", ".join(duplicated[:20]))

    sample_meta["quant_file"] = sample_meta.apply(
        lambda row: str(quant_root / row["dataset"] / row["sample_id"] / "ReadsPerGene.out.tab"),
        axis=1,
    )
    sample_meta["quant_exists"] = sample_meta["quant_file"].map(lambda path: Path(path).is_file())
    return sample_meta


def write_matrix(matrix: pd.DataFrame, path: Path) -> None:
    out = matrix.reset_index().rename(columns={"index": "gene_id"})
    out.to_csv(path, sep="\t", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--quant-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--project", default="")
    parser.add_argument("--counts-name", default="")
    parser.add_argument("--expression-name", default="")
    parser.add_argument("--sample-table-name", default="")
    parser.add_argument("--count-column", default="unstranded")
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    count_column = COUNT_COLUMNS.get(args.count_column)
    if count_column is None:
        allowed = ", ".join(sorted(COUNT_COLUMNS))
        raise SystemExit(f"[ERRO] Invalid --count-column '{args.count_column}'. Use one of: {allowed}")

    counts_name = args.counts_name or (
        "counts_matrix.tsv" if args.project == "" else f"{args.project}_counts_matrix.tsv"
    )
    expression_name = args.expression_name or (
        "star_cpm_matrix.tsv" if args.project == "" else f"{args.project}_star_cpm_matrix.tsv"
    )
    sample_table_name = args.sample_table_name or (
        "quant_samples.tsv" if args.project == "" else f"{args.project}_quant_samples.tsv"
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata = read_metadata(args.metadata)
    sample_meta = make_sample_table(metadata, args.project, args.quant_root)

    missing = sample_meta.loc[~sample_meta["quant_exists"]]
    if not missing.empty and not args.allow_missing:
        examples = ", ".join(missing["sample_id"].head(20).tolist())
        raise SystemExit(
            f"[ERRO] ReadsPerGene.out.tab missing for {len(missing)} samples, e.g. {examples}\n"
            "Use --allow-missing only if you want to import the available subset."
        )
    if not missing.empty:
        print(f"[WARN] Ignoring {len(missing)} samples without STAR counts.")
        sample_meta = sample_meta.loc[sample_meta["quant_exists"]].copy()
    if sample_meta.empty:
        raise SystemExit("[ERRO] No STAR count files available to import.")

    series_by_sample = []
    for row in sample_meta.itertuples(index=False):
        counts = read_star_counts(Path(row.quant_file), count_column)
        counts.name = row.import_id
        series_by_sample.append(counts)

    counts_matrix = pd.concat(series_by_sample, axis=1).fillna(0).astype(int)
    library_sizes = counts_matrix.sum(axis=0)
    zero_libraries = library_sizes[library_sizes == 0].index.tolist()
    if zero_libraries:
        raise SystemExit("[ERRO] STAR count libraries with zero total reads: " + ", ".join(zero_libraries[:20]))
    cpm_matrix = counts_matrix.div(library_sizes, axis=1) * 1_000_000

    sample_meta["quant_method"] = "star"
    sample_meta["expression_unit"] = "CPM"
    sample_meta["star_count_column"] = count_column

    counts_out = args.output_dir / counts_name
    expression_out = args.output_dir / expression_name
    sample_table_out = args.output_dir / sample_table_name

    write_matrix(counts_matrix, counts_out)
    write_matrix(cpm_matrix, expression_out)
    sample_meta.to_csv(sample_table_out, sep="\t", index=False)

    print(f"[OK] Counts: {counts_out}")
    print(f"[OK] CPM: {expression_out}")
    print(f"[OK] Sample table: {sample_table_out}")


if __name__ == "__main__":
    main()
