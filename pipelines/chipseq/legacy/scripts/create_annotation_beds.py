#!/usr/bin/env python3
import argparse
import gzip
import os
import re
import sys


def open_text(path):
    return gzip.open(path, "rt") if path.endswith(".gz") else open(path, "r", encoding="utf-8")


def parse_attrs(attr_text):
    attrs = {}
    if "=" in attr_text and ";" in attr_text:
        for part in attr_text.strip().split(";"):
            if not part.strip() or "=" not in part:
                continue
            key, value = part.split("=", 1)
            attrs[key.strip()] = value.strip()
    else:
        for key, value in re.findall(r'(\S+)\s+"([^"]+)"', attr_text):
            attrs[key] = value
    return attrs


def attr_gene_id(attrs):
    for key in ("gene_id", "gene", "ID", "Name", "locus_tag", "Parent"):
        if key in attrs and attrs[key]:
            value = attrs[key]
            if key == "Parent":
                value = value.split(",")[0]
            return value.replace("gene:", "")
    return "unknown_gene"


def write_bed(rows, path):
    with open(path, "w", encoding="utf-8") as handle:
        for row in sorted(rows, key=lambda x: (x[0], x[1], x[2], x[3])):
            handle.write("\t".join(map(str, row)) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Create gene, exon, intron, promoter, and downstream BED files")
    parser.add_argument("--annotation", required=True)
    parser.add_argument("--chrom-sizes", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--promoter-upstream", type=int, required=True)
    parser.add_argument("--promoter-downstream", type=int, required=True)
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    chrom_sizes = {}
    with open(args.chrom_sizes, encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 2:
                chrom_sizes[fields[0]] = int(fields[1])

    genes = {}
    exons_by_gene = {}
    annotation_chroms = set()

    with open_text(args.annotation) as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9:
                continue
            chrom, _, feature, start, end, _, strand, _, attr_text = fields
            start0 = int(start) - 1
            end1 = int(end)
            attrs = parse_attrs(attr_text)
            gene_id = attr_gene_id(attrs)
            annotation_chroms.add(chrom)

            if feature.lower() in {"gene", "transcript", "mrna"}:
                if gene_id not in genes:
                    genes[gene_id] = [chrom, start0, end1, gene_id, ".", strand]
                else:
                    genes[gene_id][1] = min(genes[gene_id][1], start0)
                    genes[gene_id][2] = max(genes[gene_id][2], end1)
            elif feature.lower() == "exon":
                exons_by_gene.setdefault(gene_id, []).append([chrom, start0, end1, gene_id, ".", strand])

    if not genes:
        for gene_id, exons in exons_by_gene.items():
            chrom = exons[0][0]
            strand = exons[0][5]
            genes[gene_id] = [chrom, min(e[1] for e in exons), max(e[2] for e in exons), gene_id, ".", strand]

    if not genes:
        print("ERROR: no gene or exon features were parsed from annotation", file=sys.stderr)
        sys.exit(1)

    genome_chroms = set(chrom_sizes)
    overlap = annotation_chroms & genome_chroms
    if not overlap:
        print("ERROR: no chromosome names overlap between annotation and FASTA index", file=sys.stderr)
        sys.exit(1)

    missing = sorted(annotation_chroms - genome_chroms)
    if missing:
        print("WARNING: annotation contains chromosomes absent from FASTA index: " + ",".join(missing[:20]), file=sys.stderr)

    gene_rows = list(genes.values())
    exon_rows = [row for rows in exons_by_gene.values() for row in rows if row[0] in chrom_sizes]
    promoter_rows = []
    downstream_rows = []
    intron_rows = []

    for gene_id, gene in genes.items():
        chrom, start, end, _, score, strand = gene
        if chrom not in chrom_sizes:
            continue
        chrom_len = chrom_sizes[chrom]
        if strand == "-":
            prom_start = max(0, end - args.promoter_downstream)
            prom_end = min(chrom_len, end + args.promoter_upstream)
            down_start = max(0, start - args.promoter_upstream)
            down_end = min(chrom_len, start + args.promoter_downstream)
        else:
            prom_start = max(0, start - args.promoter_upstream)
            prom_end = min(chrom_len, start + args.promoter_downstream)
            down_start = max(0, end - args.promoter_downstream)
            down_end = min(chrom_len, end + args.promoter_upstream)
        if prom_end > prom_start:
            promoter_rows.append([chrom, prom_start, prom_end, gene_id, score, strand])
        if down_end > down_start:
            downstream_rows.append([chrom, down_start, down_end, gene_id, score, strand])

        exons = sorted([e for e in exons_by_gene.get(gene_id, []) if e[0] == chrom], key=lambda e: (e[1], e[2]))
        cursor = start
        for exon in exons:
            if exon[1] > cursor:
                intron_rows.append([chrom, cursor, exon[1], gene_id, score, strand])
            cursor = max(cursor, exon[2])
        if exons and cursor < end:
            intron_rows.append([chrom, cursor, end, gene_id, score, strand])

    write_bed([g for g in gene_rows if g[0] in chrom_sizes], os.path.join(args.outdir, "genes.bed"))
    write_bed(exon_rows, os.path.join(args.outdir, "exons.bed"))
    write_bed(intron_rows, os.path.join(args.outdir, "introns.bed"))
    write_bed(promoter_rows, os.path.join(args.outdir, "promoters.bed"))
    write_bed(downstream_rows, os.path.join(args.outdir, "downstream.bed"))
    with open(os.path.join(args.outdir, "annotation_chromosomes.txt"), "w", encoding="utf-8") as handle:
        for chrom in sorted(annotation_chroms):
            handle.write(chrom + "\n")


if __name__ == "__main__":
    main()
