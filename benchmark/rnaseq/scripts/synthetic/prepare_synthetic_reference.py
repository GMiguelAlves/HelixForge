#!/usr/bin/env python3
"""Build the frozen 2,400-transcript synthetic reference from GENCODE FASTA."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fasta_records(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="ascii") as handle:
        header = None
        chunks: list[str] = []
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(chunks).upper()
                header, chunks = line[1:], []
            elif header is None:
                raise ValueError("sequence encountered before first FASTA header")
            else:
                chunks.append(line)
        if header is not None:
            yield header, "".join(chunks).upper()


def file_entry(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-fasta", required=True, type=Path)
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    design = json.loads(args.design.read_text(encoding="utf-8"))
    selection = design["selection"]
    seed = int(selection["seed"])
    minimum = int(selection["eligible_transcript_length_min"])
    maximum = int(selection["eligible_transcript_length_max"])
    per_count = {int(key): int(value) for key, value in selection["genes_per_transcript_count"].items()}

    if not args.source_fasta.is_file():
        raise FileNotFoundError(args.source_fasta)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)

    by_gene: dict[str, list[tuple[str, str]]] = defaultdict(list)
    seen_transcripts: set[str] = set()
    source_records = 0
    for header, sequence in fasta_records(args.source_fasta):
        source_records += 1
        fields = header.split("|")
        if len(fields) < 2:
            raise ValueError(f"GENCODE header lacks transcript/gene fields: {header[:120]}")
        transcript_id, gene_id = fields[0], fields[1]
        if transcript_id in seen_transcripts:
            raise ValueError(f"duplicate transcript ID: {transcript_id}")
        seen_transcripts.add(transcript_id)
        if minimum <= len(sequence) <= maximum and set(sequence) <= set("ACGT"):
            by_gene[gene_id].append((transcript_id, sequence))

    selected: list[tuple[str, str, str]] = []
    stratum_counts: dict[str, int] = {}
    for transcript_count, required_genes in sorted(per_count.items()):
        candidates = [gene for gene, records in by_gene.items() if len(records) == transcript_count]
        candidates.sort(key=lambda gene: (hashlib.sha256(f"{seed}:{gene}".encode()).hexdigest(), gene))
        if len(candidates) < required_genes:
            raise ValueError(
                f"stratum {transcript_count} has {len(candidates)} eligible genes; {required_genes} required"
            )
        genes = candidates[:required_genes]
        stratum_counts[str(transcript_count)] = len(genes)
        for gene in genes:
            for transcript, sequence in sorted(by_gene[gene]):
                selected.append((gene, transcript, sequence))

    selected.sort(key=lambda item: (item[0], item[1]))
    if len({item[0] for item in selected}) != int(selection["genes"]):
        raise ValueError("selected gene count does not match design")
    if len(selected) != int(selection["expected_transcripts"]):
        raise ValueError("selected transcript count does not match design")

    transcriptome = output / "transcriptome.fa"
    genome = output / "synthetic_genome.fa"
    annotation = output / "annotation.gtf"
    mapping = output / "transcript_to_gene.tsv"
    selected_table = output / "selected_transcripts.tsv"
    selected_genes = output / "selected_genes.tsv"

    with transcriptome.open("w", encoding="ascii", newline="\n") as tx_fasta, \
         genome.open("w", encoding="ascii", newline="\n") as genome_fasta, \
         annotation.open("w", encoding="utf-8", newline="\n") as gtf, \
         mapping.open("w", encoding="utf-8", newline="") as map_handle, \
         selected_table.open("w", encoding="utf-8", newline="") as table_handle:
        map_writer = csv.writer(map_handle, delimiter="\t", lineterminator="\n")
        table_writer = csv.writer(table_handle, delimiter="\t", lineterminator="\n")
        map_writer.writerow(["transcript_id", "gene_id"])
        table_writer.writerow(["gene_id", "transcript_id", "length", "sha256"])
        for gene, transcript, sequence in selected:
            tx_fasta.write(f">{transcript}\n{sequence}\n")
            genome_fasta.write(f">{transcript}\n{sequence}\n")
            attrs = f'gene_id "{gene}"; transcript_id "{transcript}"; gene_name "{gene}";'
            gtf.write(f"{transcript}\tHelixForgeBenchmark\ttranscript\t1\t{len(sequence)}\t.\t+\t.\t{attrs}\n")
            gtf.write(f"{transcript}\tHelixForgeBenchmark\texon\t1\t{len(sequence)}\t.\t+\t.\t{attrs} exon_number \"1\";\n")
            map_writer.writerow([transcript, gene])
            table_writer.writerow([gene, transcript, len(sequence), hashlib.sha256(sequence.encode()).hexdigest()])

    gene_rows = []
    effect_seed = int(design["differential_expression"]["selection_seed"])
    for gene in sorted({item[0] for item in selected}):
        gene_rows.append((
            gene,
            len(by_gene[gene]),
            hashlib.sha256(f"{effect_seed}:{gene}".encode()).hexdigest(),
        ))
    gene_rows.sort(key=lambda item: (item[2], item[0]))
    with selected_genes.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene_id", "transcript_count", "de_assignment_sha256", "de_assignment_rank"])
        for rank, (gene, count, digest) in enumerate(gene_rows, start=1):
            writer.writerow([gene, count, digest, rank])

    manifest = {
        "schema_version": "1.0",
        "reference_id": "polyester-ground-truth-v1-reference",
        "source": {
            "path": str(args.source_fasta.resolve()),
            "bytes": args.source_fasta.stat().st_size,
            "sha256": sha256(args.source_fasta),
            "records": source_records,
        },
        "design_sha256": sha256(args.design),
        "selection_seed": seed,
        "genes": len({item[0] for item in selected}),
        "transcripts": len(selected),
        "strata": stratum_counts,
        "files": {
            path.name: file_entry(path, output)
            for path in (transcriptome, genome, annotation, mapping, selected_table, selected_genes)
        },
    }
    manifest_path = output / "reference_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "valid", "genes": manifest["genes"], "transcripts": manifest["transcripts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
