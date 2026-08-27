#!/usr/bin/env python3
"""Archive compact provenance for superseded Stage 9B.1 attempts."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import zipfile


EXPECTED_SCRATCH = Path("/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825")
EXPECTED_AUDIT = Path("/home/ra236875@bio.ib.unicamp.br/helixforge-rnaseq-benchmark-audits/20260825-9b1")
FAILED_CASES = (
    "synthetic-primary",
    "synthetic-primary-run1",
    "synthetic-primary-run2",
    "synthetic-clean-repeat",
)
ROOT = "helixforge-rnaseq-stage9b1-failed-attempts"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def selected_files(scratch: Path):
    for path in sorted((scratch / "logs").rglob("*")):
        if path.is_file():
            yield path, Path("slurm_logs", path.relative_to(scratch / "logs"))
    for case_name in FAILED_CASES:
        case = scratch / "cases" / case_name
        for filename in ("pipeline_config.sh", "analysis_spec.json", "execution_identity.json"):
            path = case / filename
            if path.is_file():
                yield path, Path("cases", case_name, filename)
        for subdir in ("logs", "results/pipeline_info"):
            source_dir = case / subdir
            if source_dir.is_dir():
                for path in sorted(source_dir.rglob("*")):
                    if path.is_file() and path.stat().st_size < 10_000_000:
                        yield path, Path("cases", case_name, subdir, path.relative_to(source_dir))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scratch", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--name", default="helixforge-rnaseq-stage9b1-failed-attempts-20260826.zip")
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("failure-provenance packaging must execute inside a Slurm job")
    if args.scratch.resolve() != EXPECTED_SCRATCH:
        raise SystemExit("unexpected scratch root")
    args.audit.mkdir(parents=True, exist_ok=True)
    if args.audit.resolve() != EXPECTED_AUDIT:
        raise SystemExit("unexpected audit root")

    archive_path = args.audit / args.name
    checksum_path = Path(str(archive_path) + ".sha256")
    if archive_path.exists() or checksum_path.exists():
        raise SystemExit("refusing to overwrite an existing audit artifact")

    readme = (
        "# Tentativas supersedidas do benchmark RNA-seq\n\n"
        "Este ZIP preserva somente configurações, logs e relatórios pequenos das "
        "tentativas interrompidas ou substituídas na Etapa 9B.1. Os diretórios work "
        "e cópias pesadas de FASTQ não foram incluídos. As causas e resoluções estão "
        "documentadas em 9b1_protocol_discrepancies.md no pacote principal.\n\n"
        "Sujeito científico: HelixForge v1.0.0-rc.1, commit "
        "fc38ada8f592bb57a13467965a718ce0df7fb6ce.\n"
    ).encode()
    manifest = [(sha256_bytes(readme), "README_PT.md")]
    files = list(selected_files(args.scratch))
    for source, relative in files:
        manifest.append((sha256_bytes(source.read_bytes()), relative.as_posix()))
    manifest_text = "".join(f"{digest}  {relative}\n" for digest, relative in manifest).encode()

    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(f"{ROOT}/README_PT.md", readme)
        for source, relative in files:
            archive.write(source, f"{ROOT}/{relative.as_posix()}")
        archive.writestr(f"{ROOT}/MANIFEST_SHA256.txt", manifest_text)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():
            raise SystemExit("created ZIP failed integrity verification")

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path.write_text(f"{digest}  {archive_path}\n", encoding="utf-8")
    print(f"{digest}  {archive_path}")


if __name__ == "__main__":
    main()
