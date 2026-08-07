#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a DEG analysis plan for raw/corrected matrices.")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--quantification-dir", required=True)
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--projects", default="auto", help="Comma-separated projects or auto.")
    parser.add_argument("--include-all", action="store_true")
    parser.add_argument("--include-corrected", action="store_true")
    parser.add_argument("--test-variables", default="condition,stage,sex,tissue,infection_mode")
    parser.add_argument("--design-covariates", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-missing", action="store_true")
    return parser.parse_args()


def metadata_projects(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        projects = sorted({row["dataset"] for row in reader if row.get("dataset")})
    return projects


def add_row(rows, args, scope, project, correction, counts, samples, output_dir):
    counts_path = Path(counts)
    samples_path = Path(samples)
    if not args.allow_missing and (not counts_path.exists() or not samples_path.exists()):
        return
    analysis_id = f"{scope}_{correction}" if scope == "all_projects" else f"{project}_{correction}"
    rows.append(
        {
            "analysis_id": analysis_id,
            "scope": scope,
            "project": project,
            "correction": correction,
            "counts": str(counts_path),
            "samples": str(samples_path),
            "output_dir": str(Path(output_dir)),
            "test_variables": args.test_variables,
            "design_covariates": args.design_covariates,
        }
    )


def main():
    args = parse_args()
    qdir = Path(args.quantification_dir)
    bdir = Path(args.batch_dir)
    out_root = Path(args.output_root)

    if args.projects == "auto":
        projects = metadata_projects(args.metadata)
    else:
        projects = [p.strip() for p in args.projects.split(",") if p.strip()]

    rows = []
    for project in projects:
        add_row(
            rows,
            args,
            "project",
            project,
            "raw",
            qdir / f"{project}_counts_matrix.tsv",
            qdir / f"{project}_quant_samples.tsv",
            out_root / project / "raw",
        )
        if args.include_corrected:
            add_row(
                rows,
                args,
                "project",
                project,
                "batch_corrected",
                bdir / project / "counts_batch_corrected.tsv",
                bdir / project / "batch_correction_samples.tsv",
                out_root / project / "batch_corrected",
            )

    if args.include_all:
        add_row(
            rows,
            args,
            "all_projects",
            "all_projects",
            "raw",
            qdir / "counts_matrix.tsv",
            qdir / "quant_samples.tsv",
            out_root / "all_projects" / "raw",
        )
        if args.include_corrected:
            add_row(
                rows,
                args,
                "all_projects",
                "all_projects",
                "batch_corrected",
                bdir / "all_projects" / "counts_batch_corrected.tsv",
                bdir / "all_projects" / "batch_correction_samples.tsv",
                out_root / "all_projects" / "batch_corrected",
            )

    if not rows:
        raise SystemExit("[ERRO] Nenhuma analise entrou no plano. Verifique arquivos ou use --allow-missing.")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Plano DEG: {args.output}")
    print(f"[OK] Analises: {len(rows)}")


if __name__ == "__main__":
    main()
