#!/usr/bin/env python3
"""Core tabular engine for the generic integrative RNA-seq + ChIP-seq pipeline."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import glob
import html
import math
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def outdir(*parts: str) -> Path:
    base = Path(env("INTEGRATION_OUTPUT_DIR", env("PROJECT_DIR", ".")))
    path = base.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def norm_path(path: str) -> str:
    cleaned = path.replace("\\", "/")
    match = re.match(r"^([A-Za-z]):/(.*)$", cleaned)
    if match and os.name != "nt":
        drive, rest = match.groups()
        return f"/mnt/{drive.lower()}/{rest}"
    return cleaned


def path_exists(path: str) -> bool:
    return bool(path) and Path(norm_path(path)).is_file() and Path(norm_path(path)).stat().st_size > 0


def open_text(path: str):
    cleaned = norm_path(path)
    if cleaned.endswith(".gz"):
        return gzip.open(cleaned, "rt", encoding="utf-8-sig", newline="")
    return open(cleaned, "r", encoding="utf-8-sig", newline="")


def detect_delimiter(path: str) -> str:
    with open_text(path) as handle:
        first = handle.readline()
    return "\t" if first.count("\t") >= first.count(",") else ","


def read_table(path: str) -> tuple[list[str], list[dict[str, str]]]:
    if not path_exists(path):
        return [], []
    sep = detect_delimiter(path)
    with open_text(path) as handle:
        reader = csv.DictReader(handle, delimiter=sep)
        header = list(reader.fieldnames or [])
        rows = [{k: (v if v is not None else "") for k, v in row.items()} for row in reader]
    return header, rows


def write_table(path: Path, rows: list[dict[str, object]], header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in header})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def first_col(header: list[str], candidates: list[str]) -> str:
    low = {h.lower(): h for h in header}
    for name in candidates:
        if name.lower() in low:
            return low[name.lower()]
    return ""


def as_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() in {"", "NA", "NaN", "nan"}:
            return default
        x = float(value)
        if math.isnan(x) or math.isinf(x):
            return default
        return x
    except (TypeError, ValueError):
        return default


def as_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def is_true(value: object) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def fmt_float(value: object, digits: int = 8) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isnan(number) or math.isinf(number):
        return ""
    return f"{number:.{digits}g}"


def log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_right_tail(overlap: int, selected_size: int, marked_size: int, universe_size: int) -> float:
    if universe_size <= 0 or selected_size <= 0 or marked_size <= 0 or overlap <= 0:
        return 1.0
    selected_size = min(selected_size, universe_size)
    marked_size = min(marked_size, universe_size)
    min_i = max(0, selected_size - (universe_size - marked_size))
    max_i = min(selected_size, marked_size)
    if overlap < min_i:
        overlap = min_i
    if overlap > max_i:
        return 0.0
    log_den = log_choose(universe_size, selected_size)
    terms = [
        log_choose(marked_size, i) + log_choose(universe_size - marked_size, selected_size - i) - log_den
        for i in range(overlap, max_i + 1)
    ]
    terms = [x for x in terms if not math.isinf(x)]
    if not terms:
        return 1.0
    max_log = max(terms)
    prob = math.exp(max_log) * sum(math.exp(x - max_log) for x in terms)
    return max(0.0, min(1.0, prob))


def bh_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    m = len(p_values)
    q_values = [1.0] * m
    prev = 1.0
    ordered = sorted(enumerate(p_values), key=lambda x: x[1])
    for rank, (idx, pval) in reversed(list(enumerate(ordered, start=1))):
        qval = min(prev, pval * m / rank)
        q_values[idx] = max(0.0, min(1.0, qval))
        prev = q_values[idx]
    return q_values


def rank_values(values: list[float]) -> list[float]:
    order = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and order[j + 1][1] == order[i][1]:
            j += 1
        rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k][0]] = rank
        i = j + 1
    return ranks


def pearson_corr(xs: list[float], ys: list[float]):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    ssx = sum(x * x for x in dx)
    ssy = sum(y * y for y in dy)
    if ssx <= 0 or ssy <= 0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / math.sqrt(ssx * ssy)


def spearman_corr(xs: list[float], ys: list[float]):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return pearson_corr(rank_values(xs), rank_values(ys))


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()) or "unknown"


STAGE_ALIASES = {
    "all": "all_stages",
    "allstage": "all_stages",
    "allstages": "all_stages",
    "adult": "adult",
    "adults": "adult",
    "cercaria": "cercariae",
    "cercariae": "cercariae",
    "egg": "eggs",
    "eggs": "eggs",
    "miracidium": "miracidia",
    "miracidia": "miracidia",
    "schistosomulum": "schistosomula",
    "schistosomula": "schistosomula",
    "sporocyst": "sporocysts",
    "sporocysts": "sporocysts",
    "pooled": "all_stages",
}
STAGE_ORDER = ["adult", "eggs", "cercariae", "miracidia", "schistosomula", "sporocysts", "all_stages", "unknown"]
_KNOWN_MARKS_CACHE = None
MARK_ALIASES = [
    (re.compile(r"(^|[^A-Za-z0-9])(?:sm[-_ ]?)?hp1([^A-Za-z0-9]|$)", re.IGNORECASE), "SmHP1"),
    (re.compile(r"(^|[^A-Za-z0-9])smp[-_]?179650([^A-Za-z0-9]|$)", re.IGNORECASE), "SmHP1"),
    (re.compile(r"(^|[^A-Za-z0-9])(?:sm[-_ ]?)?cbx([^A-Za-z0-9]|$)", re.IGNORECASE), "SmHP1"),
]


def glob_existing(pattern: str) -> list[str]:
    if not pattern:
        return []
    return sorted(p for p in glob.glob(norm_path(pattern)) if path_exists(p))


def source_label(path: str) -> str:
    label = re.split(r"[\\/]", str(path))[-1]
    for suffix in [".gz", ".tsv", ".csv", ".txt", ".bed", ".narrowPeak", ".broadPeak"]:
        if label.endswith(suffix):
            label = label[: -len(suffix)]
    for suffix in [".annotated", ".consensus", ".counts"]:
        label = label.replace(suffix, "")
    return label


def canonical_stage(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = re.sub(r"[^a-z0-9]+", " ", text.lower())
    for token in lowered.split():
        if token in STAGE_ALIASES:
            return STAGE_ALIASES[token]
    return ""


def stage_label(value: str) -> str:
    stage = canonical_stage(value)
    if stage:
        return stage
    text = str(value or "").strip()
    if not text or text.lower() in {"na", "n/a", "nan", "none", "null", "not_available"}:
        return "unknown"
    return safe_id(text).lower()


def stage_sort_key(stage: str) -> tuple[int, str]:
    stage = stage_label(stage)
    if stage in STAGE_ORDER:
        return (STAGE_ORDER.index(stage), stage)
    return (len(STAGE_ORDER), stage)


def known_marks() -> list[str]:
    global _KNOWN_MARKS_CACHE
    if _KNOWN_MARKS_CACHE is not None:
        return _KNOWN_MARKS_CACHE
    marks = ["SmHP1", "H3K27ac", "H3K4me3", "H3K27me3", "H3K9me3", "H3K9ac", "ATAC", "unknown_ChIP"]
    marks.extend(load_mark_config().keys() if "load_mark_config" in globals() else [])
    _KNOWN_MARKS_CACHE = sorted({m for m in marks if m and m != "unknown"}, key=len, reverse=True)
    return _KNOWN_MARKS_CACHE


def canonical_mark(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for pattern, mark in MARK_ALIASES:
        if pattern.search(text):
            return mark
    for mark in known_marks():
        if re.search(rf"(^|[^A-Za-z0-9]){re.escape(mark)}([^A-Za-z0-9]|$)", text, flags=re.IGNORECASE):
            return mark
    match = re.search(r"H[234]K[0-9]+(?:me[0-3]|ac)", text, flags=re.IGNORECASE)
    if match:
        raw = match.group(0)
        return raw[:2].upper() + raw[2:]
    if "unknown" in text.lower() and "chip" in text.lower():
        return "unknown_ChIP"
    return ""


def chip_sample_metadata_lookup() -> dict[str, dict[str, str]]:
    header, rows = read_table(env("CHIP_METADATA_FILE"))
    if not header:
        return {}
    sample_col = first_col(header, [env("SAMPLE_ID_COLUMN", "sample_id"), "sample", "run", "accession", "file_prefix"])
    mark_col = first_col(header, [env("MARK_COLUMN", "mark_or_factor"), "mark", "factor"])
    condition_col = first_col(header, [env("CONDITION_COLUMN", "condition"), "stage", "life_stage", "treatment"])
    lookup = {}
    for row in rows:
        keys = []
        if sample_col and row.get(sample_col):
            keys.append(row[sample_col])
        for col in ["run", "Run", "accession", "sample_id", "file_prefix"]:
            if col in row and row[col]:
                keys.append(row[col])
        mark = canonical_mark(row.get(mark_col, "")) if mark_col else ""
        stage = canonical_stage(row.get(condition_col, "")) if condition_col else ""
        for key in keys:
            lookup[str(key)] = {"mark_or_factor": mark, "condition": stage}
    return lookup


def infer_mark_stage(raw_mark: str, raw_stage: str, path: str, metadata_lookup: dict[str, dict[str, str]]) -> tuple[str, str]:
    label = source_label(path)
    meta = {}
    for sample_id, item in metadata_lookup.items():
        if sample_id and sample_id in label:
            meta = item
            break
    mark = canonical_mark(raw_mark) or meta.get("mark_or_factor", "") or canonical_mark(label)
    stage = canonical_stage(raw_stage) or meta.get("condition", "") or canonical_stage(label)
    if not mark:
        clean = re.sub(r"[_-]*(all|peaks?|rep[0-9]+|r[0-9]+)$", "", label, flags=re.IGNORECASE)
        mark = canonical_mark(clean) or "unknown_ChIP"
    return mark, stage or "unknown"


def read_matrix_gene_ids(path: str) -> list[str]:
    header, rows = read_table(path)
    if not header:
        return []
    gene_col = first_col(header, [env("GENE_ID_COLUMN", "gene_id"), "gene", "id", "Geneid"])
    if not gene_col:
        gene_col = header[0]
    return [r.get(gene_col, "") for r in rows if r.get(gene_col, "")]


def read_set_file(path: str) -> set[str]:
    if not path_exists(path):
        return set()
    genes: set[str] = set()
    with open_text(path) as handle:
        for line in handle:
            value = line.strip().split("\t")[0].split(",")[0]
            if value and not value.lower().startswith("gene"):
                genes.add(value)
    return genes


def parse_gtf_attributes(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for item in raw.strip().split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            bits = item.split(None, 1)
            if len(bits) != 2:
                continue
            key, value = bits
        attrs[key.strip()] = value.strip().strip('"')
    return attrs


def parse_annotation_genes(path: str) -> dict[str, dict[str, str]]:
    genes: dict[str, dict[str, str]] = {}
    if not path_exists(path):
        return genes
    with open_text(path) as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue
            chrom, _source, feature, start, end, _score, strand, _phase, raw_attrs = parts[:9]
            if feature.lower() not in {"gene", "mrna", "transcript"}:
                continue
            attrs = parse_gtf_attributes(raw_attrs)
            gene_id = attrs.get("gene_id") or attrs.get("ID") or attrs.get("Name")
            if not gene_id:
                continue
            gene_id = gene_id.replace("gene:", "")
            existing = genes.get(gene_id)
            row = {
                "gene_id": gene_id,
                "gene_name": attrs.get("gene_name") or attrs.get("Name") or gene_id,
                "chromosome": chrom,
                "start": start,
                "end": end,
                "strand": strand,
                "biotype": attrs.get("gene_biotype") or attrs.get("biotype") or attrs.get("gene_type") or "",
            }
            if existing:
                existing["start"] = str(min(as_int(existing.get("start")), as_int(start)))
                existing["end"] = str(max(as_int(existing.get("end")), as_int(end)))
                for key, value in row.items():
                    existing[key] = existing.get(key) or value
            else:
                genes[gene_id] = row
    return genes


def metadata_groups(path: str) -> dict[str, str]:
    header, rows = read_table(path)
    if not header:
        return {}
    sample_col = first_col(
        header,
        [
            env("SAMPLE_ID_COLUMN", "sample_id"),
            "sample_id",
            "sample",
            "Sample",
            "Run",
            "run",
            "accession",
            "file_prefix",
        ],
    )
    group_cols = [c.strip() for c in env("GROUP_COLUMNS", "").split(",") if c.strip()]
    stage_cols = [c.strip() for c in env("RNA_STAGE_COLUMNS", "").split(",") if c.strip()]
    groups = {}
    for row in rows:
        keys = metadata_sample_keys(header, row, sample_col)
        if not keys:
            continue
        stage = row_stage(row, header, stage_cols, group_cols)
        for key in keys:
            for alias in sample_aliases(key):
                groups[alias] = stage
    return groups


def metadata_sample_keys(header: list[str], row: dict[str, str], sample_col: str) -> list[str]:
    candidates = [
        sample_col,
        env("SAMPLE_ID_COLUMN", "sample_id"),
        "sample_id",
        "sample",
        "Sample",
        "sample_name",
        "SampleName",
        "Run",
        "run",
        "accession",
        "run_accession",
        "Run accession",
        "sample_accession",
        "Sample accession",
        "BioSample",
        "biosample",
        "Experiment",
        "experiment",
        "library",
        "library_id",
        "library_name",
        "Library Name",
        "file_prefix",
        "filename",
        "file",
    ]
    lower_to_col = {c.lower(): c for c in header}
    keys: list[str] = []
    for col in candidates:
        actual = col if col in row else lower_to_col.get(str(col).lower(), "")
        value = row.get(actual, "") if actual else ""
        if value:
            keys.append(value)
    for col in header:
        lower = col.lower()
        if any(token in lower for token in ["study", "project", "dataset", "bioproject"]):
            continue
        if any(token in lower for token in ["sample", "run", "accession", "biosample", "experiment", "library", "file_prefix", "filename"]):
            value = row.get(col, "")
            if value:
                keys.append(value)
    seen = set()
    out = []
    for key in keys:
        text = str(key).strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def sample_aliases(value: str) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    raw_items = {text, source_label(text)}
    out: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        variants = {
            item,
            safe_id(item),
            re.sub(r"[_-]R[0-9]+$", "", item, flags=re.IGNORECASE),
            re.sub(r"[_-]rep[0-9]+$", "", item, flags=re.IGNORECASE),
            re.sub(r"[_-](counts|tpm|cpm|quant)$", "", item, flags=re.IGNORECASE),
        }
        if "__" in item:
            variants.add(item.split("__")[-1])
        variants.add(re.sub(r"^[A-Z]{2,}J[EA-Z0-9]+__", "", item))
        for variant in variants:
            variant = str(variant).strip()
            if variant:
                out.add(variant)
    return {x for x in out if x.lower() != "unknown"}


def row_stage(row: dict[str, str], header: list[str], stage_cols: list[str], group_cols: list[str]) -> str:
    lower_to_col = {c.lower(): c for c in header}
    for col in stage_cols + group_cols:
        actual = col if col in row else lower_to_col.get(str(col).lower(), "")
        if actual:
            stage = canonical_stage(row.get(actual, ""))
            if stage:
                return stage
    searchable = [
        c
        for c in header
        if any(token in c.lower() for token in ["stage", "condition", "treatment", "tissue", "source", "title", "description", "characteristic"])
    ]
    for col in searchable:
        stage = canonical_stage(row.get(col, ""))
        if stage:
            return stage
    values = [row.get(c, "") for c in group_cols if row.get(c, "")]
    joined = " | ".join(values)
    return canonical_stage(joined) or "unknown"


def resolve_sample_group(sample: str, groups: dict[str, str]) -> tuple[str, str, str]:
    for alias in sample_aliases(sample):
        if alias in groups:
            return groups[alias], "metadata", alias
    sample_text = str(sample or "")
    for key, group in groups.items():
        if re.match(r"^(PRJ|SRP|ERP|DRP)[A-Z0-9]+$", key, flags=re.IGNORECASE):
            continue
        if len(key) >= 5 and (key in sample_text or sample_text in key):
            return group, "metadata_substring", key
    inferred = canonical_stage(sample_text)
    if inferred:
        return inferred, "sample_name_stage", ""
    return "unknown", "unmapped", ""


def sample_group(sample: str, groups: dict[str, str]) -> str:
    return resolve_sample_group(sample, groups)[0]


def normalize_deg_rows() -> list[dict[str, str]]:
    path = env("RNA_DEG_RESULTS")
    header, rows = read_table(path)
    if not header:
        return []
    gene_col = first_col(header, [env("GENE_ID_COLUMN", "gene_id"), "gene", "id"])
    name_col = first_col(header, [env("GENE_NAME_COLUMN", "gene_name"), "gene", "symbol", "name"])
    contrast_col = first_col(header, [env("CONTRAST_ID_COLUMN", "contrast_id"), "contrast", "comparison"])
    lfc_col = first_col(header, ["log2FoldChange", "log2FC", "logFC", "lfc"])
    padj_col = first_col(header, ["padj", "FDR", "qvalue", "adj.P.Val"])
    pvalue_col = first_col(header, ["pvalue", "P.Value", "p_value"])
    out = []
    for row in rows:
        gene_id = row.get(gene_col, "") if gene_col else ""
        if not gene_id:
            continue
        lfc = as_float(row.get(lfc_col, "0"))
        padj = as_float(row.get(padj_col, "1"), 1.0)
        status = "not_significant"
        if padj <= as_float(env("DEG_PADJ_THRESHOLD", "0.05"), 0.05):
            if lfc >= as_float(env("DEG_LOG2FC_THRESHOLD", "1"), 1.0):
                status = "up"
            elif lfc <= -as_float(env("DEG_LOG2FC_THRESHOLD", "1"), 1.0):
                status = "down"
        item = dict(row)
        item.update(
            {
                "contrast_id": row.get(contrast_col, "") if contrast_col else "default",
                "gene_id": gene_id,
                "gene_name": row.get(name_col, gene_id) if name_col else gene_id,
                "log2FoldChange": f"{lfc:.8g}",
                "pvalue": row.get(pvalue_col, "") if pvalue_col else "",
                "padj": f"{padj:.8g}",
                "deg_status": status,
            }
        )
        out.append(item)
    return out


def load_epigenetic_catalog() -> list[dict[str, str]]:
    out = []
    seen = set()
    for source_label, path in [("primary", env("RNA_GENE_CATALOG")), ("supplemental", env("RNA_GENE_CATALOG_EXTRA"))]:
        header, rows = read_table(path)
        if not header:
            continue
        gene_col = first_col(header, ["matched_gene_id", "gene_id", "query", "id"])
        group_col = first_col(header, ["group", "category", "class"])
        name_col = first_col(header, ["gene_name", "symbol", "name"])
        query_col = first_col(header, ["query", "query_display"])
        for row in rows:
            gid = row.get(gene_col, "") if gene_col else ""
            if not gid:
                continue
            group = row.get(group_col, "epigenetic_machinery") if group_col else "epigenetic_machinery"
            key = (gid, group)
            if key in seen:
                continue
            seen.add(key)
            item = dict(row)
            item["gene_id"] = gid
            item["gene_name"] = row.get(name_col, gid) if name_col else gid
            item["machinery_group"] = group
            item["query_id"] = row.get(query_col, gid) if query_col else gid
            item["catalog_source"] = source_label
            item["catalog_path"] = path
            out.append(item)
    return out


def command_validate(_args: argparse.Namespace) -> None:
    rows = []

    def check_file(label: str, path: str, required: bool = False) -> None:
        ok = path_exists(path)
        status = "ok" if ok else ("error" if required else "warning")
        rows.append({"item": label, "path": path, "status": status, "message": "" if ok else "missing or empty"})

    check_file("RNA counts matrix", env("RNA_COUNTS_MATRIX"), True)
    check_file("RNA normalized matrix", env("RNA_NORMALIZED_MATRIX"), True)
    check_file("RNA DEG results", env("RNA_DEG_RESULTS"), True)
    check_file("RNA metadata", env("RNA_METADATA_FILE"), False)
    check_file("RNA epigenetic machinery catalog", env("RNA_GENE_CATALOG"), False)
    check_file("RNA supplemental epigenetic catalog", env("RNA_GENE_CATALOG_EXTRA"), False)
    check_file("RNA expression by context", env("RNA_EXPRESSION_CONTEXT"), False)
    check_file("RNA WGCNA hits", env("RNA_WGCNA_HITS"), False)
    check_file("RNA Mfuzz hits", env("RNA_MFUZZ_HITS"), False)
    check_file("RNA DTU hits", env("RNA_DTU_HITS"), False)
    check_file("RNA splicing hits", env("RNA_SPLICING_HITS"), False)
    check_file("ChIP metadata", env("CHIP_METADATA_FILE"), False)
    check_file("ChIP differential binding", env("CHIP_DIFF_BINDING_FILE"), False)
    check_file("Genome annotation", env("ANNOTATION_FILE"), False)
    check_file("Functional annotation", env("FUNCTIONAL_ANNOTATION"), False)

    for label, pattern in [
        ("ChIP annotated peaks", env("CHIP_ANNOTATED_PEAKS_GLOB")),
        ("ChIP peak BEDs", env("CHIP_PEAK_BED_GLOB")),
        ("ChIP peak counts", env("CHIP_PEAK_COUNT_GLOB")),
    ]:
        matches = glob_existing(pattern)
        rows.append(
            {
                "item": label,
                "path": pattern,
                "status": "ok" if matches else "warning",
                "message": f"{len(matches)} matching file(s)",
            }
        )

    counts_genes = set(read_matrix_gene_ids(env("RNA_COUNTS_MATRIX")))
    norm_genes = set(read_matrix_gene_ids(env("RNA_NORMALIZED_MATRIX")))
    deg_genes = {r["gene_id"] for r in normalize_deg_rows()}
    if counts_genes and norm_genes:
        overlap = len(counts_genes & norm_genes)
        rows.append({"item": "RNA matrix gene overlap", "path": "", "status": "ok" if overlap else "error", "message": f"{overlap} genes"})
    if deg_genes and norm_genes:
        overlap = len(deg_genes & norm_genes)
        rows.append({"item": "RNA DEG/expression gene overlap", "path": "", "status": "ok" if overlap else "warning", "message": f"{overlap} genes"})

    write_table(outdir("010-input-validation") / "validation_report.tsv", rows, ["item", "path", "status", "message"])
    errors = [r for r in rows if r["status"] == "error"]
    summary = ["# Input validation", "", f"Generated: {dt.datetime.now().isoformat(timespec='seconds')}", ""]
    summary.extend(f"- {r['status'].upper()}: {r['item']} {r['message']}".strip() for r in rows)
    write_text(outdir("010-input-validation") / "validation_report.md", "\n".join(summary) + "\n")
    if errors:
        print("ERROR: required inputs failed validation. See 010-input-validation/validation_report.tsv", file=sys.stderr)
        raise SystemExit(1)


def command_prepare(_args: argparse.Namespace) -> None:
    manifest = []
    for key in [
        "RNA_COUNTS_MATRIX",
        "RNA_NORMALIZED_MATRIX",
        "RNA_DEG_RESULTS",
        "RNA_METADATA_FILE",
        "CHIP_METADATA_FILE",
        "CHIP_DIFF_BINDING_FILE",
        "ANNOTATION_FILE",
        "FUNCTIONAL_ANNOTATION",
        "GENES_OF_INTEREST_FILE",
    ]:
        manifest.append({"input_key": key, "path": env(key), "exists": str(path_exists(env(key)))})
    for key in ["CHIP_ANNOTATED_PEAKS_GLOB", "CHIP_PEAK_BED_GLOB", "CHIP_PEAK_COUNT_GLOB"]:
        matches = glob_existing(env(key))
        manifest.append({"input_key": key, "path": env(key), "exists": str(bool(matches)), "matches": ",".join(matches)})
    write_table(outdir("020-prepared-inputs") / "input_manifest.tsv", manifest, ["input_key", "path", "exists", "matches"])

    deg = normalize_deg_rows()
    deg_header = ["contrast_id", "gene_id", "gene_name", "baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj", "deg_status"]
    extra = sorted({k for r in deg for k in r.keys()} - set(deg_header))
    write_table(outdir("020-prepared-inputs") / "rnaseq_deg_normalized.tsv", deg, deg_header + extra)

    meta_rows = []
    for source, path in [("rna", env("RNA_METADATA_FILE")), ("chip", env("CHIP_METADATA_FILE"))]:
        header, rows = read_table(path)
        for row in rows:
            item = {"assay": source}
            item.update(row)
            meta_rows.append(item)
    header = sorted({k for r in meta_rows for k in r.keys()})
    if "assay" in header:
        header.remove("assay")
        header = ["assay"] + header
    write_table(outdir("020-prepared-inputs") / "metadata_combined.tsv", meta_rows, header or ["assay"])


def command_harmonize(_args: argparse.Namespace) -> None:
    genes = parse_annotation_genes(env("ANNOTATION_FILE"))
    gene_interest = read_set_file(env("GENES_OF_INTEREST_FILE"))
    epigenetic_catalog = load_epigenetic_catalog()
    epigenetic_gene_ids = {r["gene_id"] for r in epigenetic_catalog}
    catalog_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in epigenetic_catalog:
        catalog_by_gene[item["gene_id"]].append(item)
    gene_interest.update(epigenetic_gene_ids)
    deg = normalize_deg_rows()
    deg_by_gene = {r["gene_id"]: r for r in deg}
    functional: dict[str, dict[str, str]] = {}
    f_header, f_rows = read_table(env("FUNCTIONAL_ANNOTATION"))
    f_gene_col = first_col(f_header, ["gene_id", "gene", "id"]) if f_header else ""
    for row in f_rows:
        if f_gene_col and row.get(f_gene_col):
            functional[row[f_gene_col]] = row
    all_gene_ids = set(genes)
    all_gene_ids.update(read_matrix_gene_ids(env("RNA_COUNTS_MATRIX")))
    all_gene_ids.update(read_matrix_gene_ids(env("RNA_NORMALIZED_MATRIX")))
    all_gene_ids.update(deg_by_gene)
    all_gene_ids.update(gene_interest)
    rows = []
    lost = []
    for gid in sorted(all_gene_ids):
        base = genes.get(gid, {"gene_id": gid, "gene_name": gid, "chromosome": "", "start": "", "end": "", "strand": "", "biotype": ""})
        deg_row = deg_by_gene.get(gid, {})
        fn_row = functional.get(gid, {})
        catalog_rows = catalog_by_gene.get(gid, [])
        gene_name = base.get("gene_name") or deg_row.get("gene_name") or gid
        biotype = base.get("biotype") or deg_row.get("biotype") or fn_row.get("biotype", "")
        catalog_description = ""
        for catalog_row in catalog_rows:
            catalog_description = (
                catalog_row.get("functional_annotation")
                or catalog_row.get("description")
                or catalog_row.get("annotation")
                or catalog_row.get("product")
                or catalog_row.get("query_id")
                or ""
            )
            if catalog_description:
                break
        machinery_group = ";".join(sorted({r.get("machinery_group", "") for r in catalog_rows if r.get("machinery_group")}))
        fn_text = fn_row.get("functional_annotation") or fn_row.get("description") or fn_row.get("term") or catalog_description
        row = {
            "gene_id": gid,
            "gene_name": gene_name,
            "chromosome": base.get("chromosome", ""),
            "start": base.get("start", ""),
            "end": base.get("end", ""),
            "strand": base.get("strand", ""),
            "biotype": biotype,
            "functional_annotation": fn_text,
            "is_gene_of_interest": str(gid in gene_interest).lower(),
            "is_epigenetic_machinery": str(gid in epigenetic_gene_ids).lower(),
            "machinery_group": machinery_group,
        }
        if not row["chromosome"]:
            lost.append({"gene_id": gid, "reason": "missing_genomic_annotation"})
        rows.append(row)
    header = [
        "gene_id",
        "gene_name",
        "chromosome",
        "start",
        "end",
        "strand",
        "biotype",
        "functional_annotation",
        "is_gene_of_interest",
        "is_epigenetic_machinery",
        "machinery_group",
    ]
    write_table(outdir("030-id-harmonization") / "gene_master_table.tsv", rows, header)
    write_table(outdir("030-id-harmonization") / "unmapped_genes.tsv", lost, ["gene_id", "reason"])
    catalog_header = ["gene_id", "gene_name", "machinery_group", "query_id"] + [
        h for h in sorted({k for r in epigenetic_catalog for k in r}) if h not in {"gene_id", "gene_name", "machinery_group", "query_id"}
    ]
    write_table(outdir("030-id-harmonization") / "epigenetic_machinery_catalog.tsv", epigenetic_catalog, catalog_header or ["gene_id"])


def load_gene_master() -> dict[str, dict[str, str]]:
    _header, rows = read_table(str(outdir("030-id-harmonization") / "gene_master_table.tsv"))
    return {r["gene_id"]: r for r in rows if r.get("gene_id")}


def annotated_peak_rows() -> list[dict[str, str]]:
    rows = []
    metadata_lookup = chip_sample_metadata_lookup()
    for path in glob_existing(env("CHIP_ANNOTATED_PEAKS_GLOB")):
        header, data = read_table(path)
        if not header:
            continue
        mark_col = first_col(header, [env("MARK_COLUMN", "mark_or_factor"), "mark", "factor"])
        condition_col = first_col(header, [env("CONDITION_COLUMN", "condition"), "stage", "life_stage", "treatment"])
        for idx, row in enumerate(data, start=1):
            gene_col = first_col(header, ["nearest_gene_id", "gene_id", "associated_gene", "target_gene"])
            name_col = first_col(header, ["nearest_gene_name", "gene_name", "gene"])
            class_col = first_col(header, ["genomic_annotation", "annotation", "class", "peak_class"])
            mark, stage = infer_mark_stage(row.get(mark_col, "") if mark_col else "", row.get(condition_col, "") if condition_col else "", path, metadata_lookup)
            peak_id = row.get(first_col(header, ["peak_id", "id", "name"]), "") or f"{source_label(path)}_{idx}"
            rows.append(
                {
                    "peak_id": peak_id,
                    "chrom": row.get(first_col(header, ["chrom", "chr", "seqnames"]), ""),
                    "start": row.get(first_col(header, ["start", "chromStart"]), ""),
                    "end": row.get(first_col(header, ["end", "chromEnd"]), ""),
                    "mark_or_factor": mark,
                    "condition": stage,
                    "associated_gene_id": row.get(gene_col, "") if gene_col else "",
                    "associated_gene_name": row.get(name_col, "") if name_col else "",
                    "distance_to_tss": row.get(first_col(header, ["distance_to_tss", "distanceToTSS", "distance"]), ""),
                    "genomic_annotation": row.get(class_col, "") if class_col else "",
                    "link_mode": "annotated_peak_table",
                    "source_file": norm_path(path),
                }
            )
    return rows


def bed_peak_rows_from_master(gene_master: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    gene_by_chrom: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in gene_master.values():
        if row.get("chromosome") and row.get("start") and row.get("end"):
            gene_by_chrom[row["chromosome"]].append(row)
    rows = []
    window = as_int(env("PEAK_GENE_WINDOW_BP", "5000"), 5000)
    metadata_lookup = chip_sample_metadata_lookup()
    for path in glob_existing(env("CHIP_PEAK_BED_GLOB")):
        mark, stage = infer_mark_stage("", "", path, metadata_lookup)
        with open_text(path) as handle:
            for idx, line in enumerate(handle, start=1):
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                chrom, start, end = parts[0], parts[1], parts[2]
                midpoint = (as_int(start) + as_int(end)) // 2
                best = None
                best_dist = None
                for gene in gene_by_chrom.get(chrom, []):
                    gs, ge = as_int(gene.get("start")), as_int(gene.get("end"))
                    dist = 0 if gs <= midpoint <= ge else min(abs(midpoint - gs), abs(midpoint - ge))
                    if dist <= window and (best_dist is None or dist < best_dist):
                        best, best_dist = gene, dist
                if best:
                    source_name = source_label(path)
                    rows.append(
                        {
                            "peak_id": parts[3] if len(parts) > 3 and parts[3] else f"{source_name}_{idx}",
                            "chrom": chrom,
                            "start": start,
                            "end": end,
                            "mark_or_factor": mark,
                            "condition": stage,
                            "associated_gene_id": best["gene_id"],
                            "associated_gene_name": best.get("gene_name", ""),
                            "distance_to_tss": str(best_dist or 0),
                            "genomic_annotation": "window",
                            "link_mode": "window_based",
                            "source_file": norm_path(path),
                        }
                    )
    return rows


def command_map_peaks(_args: argparse.Namespace) -> None:
    gene_master = load_gene_master()
    rows = annotated_peak_rows()
    if not rows:
        rows = bed_peak_rows_from_master(gene_master)
    for row in rows:
        ann = row.get("genomic_annotation", "").lower()
        row["promoter_flag"] = str("promoter" in ann).lower()
    header = [
        "peak_id",
        "chrom",
        "start",
        "end",
        "mark_or_factor",
        "condition",
        "associated_gene_id",
        "associated_gene_name",
        "distance_to_tss",
        "genomic_annotation",
        "promoter_flag",
        "link_mode",
        "source_file",
    ]
    write_table(outdir("040-peak-gene-mapping") / "peak_to_gene.tsv", rows, header)
    promoter = [r for r in rows if r.get("promoter_flag") == "true"]
    distal = [r for r in rows if r.get("promoter_flag") != "true"]
    write_table(outdir("040-peak-gene-mapping") / "promoter_peak_gene_links.tsv", promoter, header)
    write_table(outdir("040-peak-gene-mapping") / "distal_peak_gene_links.tsv", distal, header)
    summary = []
    by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("associated_gene_id"):
            by_gene[row["associated_gene_id"]].append(row)
    for gid, links in sorted(by_gene.items()):
        anns = [x.get("genomic_annotation", "").lower() for x in links]
        summary.append(
            {
                "gene_id": gid,
                "total_associated_peaks": len(links),
                "promoter_peaks": sum("promoter" in a for a in anns),
                "gene_body_peaks": sum(a in {"gene", "exon", "intron", "gene_body"} for a in anns),
                "distal_peaks": sum("promoter" not in a and a not in {"gene", "exon", "intron", "gene_body"} for a in anns),
                "marks_or_factors": ";".join(sorted({x.get("mark_or_factor", "") for x in links if x.get("mark_or_factor")})),
                "conditions": ";".join(sorted({x.get("condition", "") for x in links if x.get("condition")})),
            }
        )
    write_table(
        outdir("040-peak-gene-mapping") / "gene_to_peak_summary.tsv",
        summary,
        ["gene_id", "total_associated_peaks", "promoter_peaks", "gene_body_peaks", "distal_peaks", "marks_or_factors", "conditions"],
    )


def command_summarize_rna(_args: argparse.Namespace) -> None:
    header, rows = read_table(env("RNA_NORMALIZED_MATRIX"))
    groups = metadata_groups(env("RNA_METADATA_FILE"))
    gene_col = first_col(header, [env("GENE_ID_COLUMN", "gene_id"), "gene", "id"]) if header else ""
    if not gene_col and header:
        gene_col = header[0]
    sample_cols = [h for h in header if h != gene_col]
    deg = normalize_deg_rows()
    by_gene_deg: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in deg:
        by_gene_deg[row["gene_id"]].append(row)
    summaries = []
    context_rows = []
    sample_group_rows = []
    sample_group_cache: dict[str, tuple[str, str, str]] = {}
    for sample in sample_cols:
        group, status, matched_key = resolve_sample_group(sample, groups)
        sample_group_cache[sample] = (group, status, matched_key)
        sample_group_rows.append(
            {
                "sample_id": sample,
                "stage_or_condition": group,
                "mapping_status": status,
                "matched_metadata_key": matched_key,
            }
        )
    for row in rows:
        gid = row.get(gene_col, "")
        if not gid:
            continue
        values_by_group: dict[str, list[float]] = defaultdict(list)
        all_values = []
        for sample in sample_cols:
            value = as_float(row.get(sample, "0"))
            values_by_group[sample_group_cache[sample][0]].append(value)
            all_values.append(value)
        group_means = {g: (sum(v) / len(v) if v else 0.0) for g, v in values_by_group.items()}
        top_group = max(group_means, key=group_means.get) if group_means else ""
        for group, values in sorted(values_by_group.items()):
            mean_value = sum(values) / len(values) if values else 0.0
            context_rows.append(
                {
                    "gene_id": gid,
                    "stage_or_condition": group,
                    "mean_TPM": f"{mean_value:.8g}",
                    "mean_log2TPM": f"{math.log2(mean_value + 1):.8g}",
                    "fraction_expressed": f"{(sum(v > 0 for v in values) / len(values)):.8g}" if values else "0",
                    "n_samples": len(values),
                }
            )
        hits = by_gene_deg.get(gid, [])
        statuses = [h.get("deg_status", "not_significant") for h in hits]
        padjs = [as_float(h.get("padj"), 1.0) for h in hits if h.get("padj")]
        lfcs = [abs(as_float(h.get("log2FoldChange"))) for h in hits]
        max_expr = max(all_values) if all_values else 0.0
        total_expr = sum(all_values) if all_values else 0.0
        summaries.append(
            {
                "gene_id": gid,
                "mean_expression": f"{statistics.mean(all_values):.8g}" if all_values else "0",
                "median_expression": f"{statistics.median(all_values):.8g}" if all_values else "0",
                "max_expression": f"{max_expr:.8g}",
                "min_expression": f"{min(all_values):.8g}" if all_values else "0",
                "context_with_highest_expression": top_group,
                "expression_specificity": f"{(max_expr / total_expr):.8g}" if total_expr else "0",
                "n_deg_records": len(hits),
                "n_significant_contrasts": sum(s in {"up", "down"} for s in statuses),
                "n_up": statuses.count("up"),
                "n_down": statuses.count("down"),
                "max_abs_log2FC": f"{max(lfcs):.8g}" if lfcs else "0",
                "min_padj": f"{min(padjs):.8g}" if padjs else "1",
                "transcriptional_dynamism_score": f"{(math.log2(max_expr + 1) * (max(lfcs) if lfcs else 0)):.8g}",
            }
        )
    sum_header = [
        "gene_id",
        "mean_expression",
        "median_expression",
        "max_expression",
        "min_expression",
        "context_with_highest_expression",
        "expression_specificity",
        "n_deg_records",
        "n_significant_contrasts",
        "n_up",
        "n_down",
        "max_abs_log2FC",
        "min_padj",
        "transcriptional_dynamism_score",
    ]
    write_table(outdir("050-rnaseq-summary") / "rna_gene_summary.tsv", summaries, sum_header)
    write_table(
        outdir("050-rnaseq-summary") / "rna_expression_by_context.tsv",
        context_rows,
        ["gene_id", "stage_or_condition", "mean_TPM", "mean_log2TPM", "fraction_expressed", "n_samples"],
    )
    write_table(
        outdir("050-rnaseq-summary") / "rna_sample_group_mapping.tsv",
        sample_group_rows,
        ["sample_id", "stage_or_condition", "mapping_status", "matched_metadata_key"],
    )
    deg_header = ["contrast_id", "gene_id", "gene_name", "log2FoldChange", "pvalue", "padj", "deg_status"]
    write_table(outdir("050-rnaseq-summary") / "rna_deg_long.tsv", deg, deg_header + sorted({k for r in deg for k in r} - set(deg_header)))


def load_diff_binding() -> list[dict[str, str]]:
    header, rows = read_table(env("CHIP_DIFF_BINDING_FILE"))
    if not header:
        return []
    metadata_lookup = chip_sample_metadata_lookup()
    gene_col = first_col(header, ["gene_id", "nearest_gene_id", "associated_gene_id"])
    peak_col = first_col(header, ["peak_id", "id", "region", "feature_id"])
    mark_col = first_col(header, [env("MARK_COLUMN", "mark_or_factor"), "mark", "factor", "peak_set"])
    lfc_col = first_col(header, ["log2FoldChange", "log2FC", "logFC"])
    padj_col = first_col(header, ["padj", "FDR", "qvalue", "adj.P.Val"])
    out = []
    for row in rows:
        item = dict(row)
        item["gene_id"] = row.get(gene_col, "") if gene_col else ""
        item["peak_id"] = row.get(peak_col, "") if peak_col else ""
        item["mark_or_factor"] = infer_mark_stage(row.get(mark_col, "") if mark_col else "", "", row.get(peak_col, "") if peak_col else "", metadata_lookup)[0]
        item["chip_log2FC"] = row.get(lfc_col, "0") if lfc_col else "0"
        item["chip_padj"] = row.get(padj_col, "1") if padj_col else "1"
        lfc = as_float(item["chip_log2FC"])
        padj = as_float(item["chip_padj"], 1.0)
        status = "not_significant"
        if padj <= as_float(env("DIFF_BINDING_PADJ_THRESHOLD", "0.05"), 0.05):
            if lfc >= as_float(env("DIFF_BINDING_LOG2FC_THRESHOLD", "1"), 1.0):
                status = "gained"
            elif lfc <= -as_float(env("DIFF_BINDING_LOG2FC_THRESHOLD", "1"), 1.0):
                status = "lost"
        item["binding_status"] = status
        out.append(item)
    return out


def command_summarize_chip(_args: argparse.Namespace) -> None:
    _header, links = read_table(str(outdir("040-peak-gene-mapping") / "peak_to_gene.tsv"))
    diff = load_diff_binding()
    diff_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in diff:
        if row.get("gene_id"):
            diff_by_gene[row["gene_id"]].append(row)
    by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in links:
        if row.get("associated_gene_id"):
            by_gene[row["associated_gene_id"]].append(row)
    rows = []
    for gid in sorted(set(by_gene) | set(diff_by_gene)):
        links_g = by_gene.get(gid, [])
        diff_g = diff_by_gene.get(gid, [])
        anns = [x.get("genomic_annotation", "").lower() for x in links_g]
        statuses = [x.get("binding_status", "not_tested") for x in diff_g]
        rows.append(
            {
                "gene_id": gid,
                "total_associated_peaks": len(links_g),
                "promoter_peaks": sum("promoter" in a for a in anns),
                "gene_body_peaks": sum(a in {"gene", "exon", "intron", "gene_body"} for a in anns),
                "distal_peaks": sum("promoter" not in a and a not in {"gene", "exon", "intron", "gene_body"} for a in anns),
                "marks_or_factors": ";".join(sorted({x.get("mark_or_factor", "") for x in links_g + diff_g if x.get("mark_or_factor")})),
                "conditions_with_peak": ";".join(sorted({x.get("condition", "") for x in links_g if x.get("condition")})),
                "n_differential_peaks": sum(s in {"gained", "lost"} for s in statuses),
                "max_abs_chip_log2FC": f"{max([abs(as_float(x.get('chip_log2FC'))) for x in diff_g] or [0]):.8g}",
                "min_chip_padj": f"{min([as_float(x.get('chip_padj'), 1.0) for x in diff_g] or [1]):.8g}",
                "binding_statuses": ";".join(sorted(set(statuses))) if statuses else "not_tested",
            }
        )
    header = [
        "gene_id",
        "total_associated_peaks",
        "promoter_peaks",
        "gene_body_peaks",
        "distal_peaks",
        "marks_or_factors",
        "conditions_with_peak",
        "n_differential_peaks",
        "max_abs_chip_log2FC",
        "min_chip_padj",
        "binding_statuses",
    ]
    write_table(outdir("060-chipseq-summary") / "chip_gene_summary.tsv", rows, header)
    write_table(outdir("060-chipseq-summary") / "chip_differential_long.tsv", diff, sorted({k for r in diff for k in r}) or ["gene_id"])
    mark_stage = chip_metadata_mark_stage_rows()
    write_table(
        outdir("060-chipseq-summary") / "chip_mark_stage_metadata.tsv",
        mark_stage,
        ["mark_or_factor", "stage_or_condition", "n_samples", "replicates", "batches", "sample_ids"],
    )


def load_mark_config() -> dict[str, dict[str, str]]:
    path = Path(env("PROJECT_DIR", ".")) / "config" / "chip_marks_config.tsv"
    header, rows = read_table(str(path))
    return {r.get("mark_or_factor", "unknown"): r for r in rows if r.get("mark_or_factor")}


def chip_metadata_mark_stage_rows() -> list[dict[str, object]]:
    header, rows = read_table(env("CHIP_METADATA_FILE"))
    if not header:
        return []
    mark_col = first_col(header, [env("MARK_COLUMN", "mark_or_factor"), "mark", "factor"])
    condition_col = first_col(header, [env("CONDITION_COLUMN", "condition"), "stage", "life_stage"])
    sample_col = first_col(header, [env("SAMPLE_ID_COLUMN", "sample_id"), "sample"])
    rep_col = first_col(header, ["replicate", "rep", "biological_replicate"])
    batch_col = first_col(header, ["batch"])
    counts: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        mark = canonical_mark(row.get(mark_col, "")) if mark_col else ""
        stage = canonical_stage(row.get(condition_col, "")) if condition_col else ""
        mark = mark or "unknown_ChIP"
        stage = stage or "unknown"
        key = (mark or "unknown", stage or "unknown")
        item = counts.setdefault(
            key,
            {"mark_or_factor": key[0], "stage_or_condition": key[1], "n_samples": 0, "replicates": set(), "batches": set(), "sample_ids": []},
        )
        item["n_samples"] = int(item["n_samples"]) + 1
        if rep_col and row.get(rep_col):
            item["replicates"].add(row[rep_col])
        if batch_col and row.get(batch_col):
            item["batches"].add(row[batch_col])
        if sample_col and row.get(sample_col):
            item["sample_ids"].append(row[sample_col])
    out = []
    for item in counts.values():
        out.append(
            {
                "mark_or_factor": item["mark_or_factor"],
                "stage_or_condition": item["stage_or_condition"],
                "n_samples": item["n_samples"],
                "replicates": ";".join(sorted(item["replicates"])),
                "batches": ";".join(sorted(item["batches"])),
                "sample_ids": ";".join(item["sample_ids"]),
            }
        )
    return sorted(out, key=lambda r: (str(r["stage_or_condition"]), str(r["mark_or_factor"])))


def expression_context_lookup() -> dict[tuple[str, str], dict[str, str]]:
    header, rows = read_table(env("RNA_EXPRESSION_CONTEXT"))
    if not header:
        header, rows = read_table(str(outdir("050-rnaseq-summary") / "rna_expression_by_context.tsv"))
    if not header:
        return {}
    gene_col = first_col(header, ["gene_id", "matched_gene_id", "gene"])
    stage_col = first_col(header, ["stage", "condition", "stage_or_condition", "stage_class", "context"])
    lookup = {}
    for row in rows:
        gid = row.get(gene_col, "") if gene_col else ""
        stage = row.get(stage_col, "") if stage_col else ""
        if gid and stage:
            lookup[(gid, stage.lower())] = row
    return lookup


def supplemental_rna_evidence() -> dict[str, dict[str, str]]:
    specs = [
        ("wgcna", env("RNA_WGCNA_HITS"), ["module_color", "module_label", "is_hub", "kME", "abs_kME"]),
        ("mfuzz", env("RNA_MFUZZ_HITS"), ["cluster", "membership"]),
        ("dtu", env("RNA_DTU_HITS"), ["transcript_id", "variable", "delta_usage", "padj"]),
        ("splicing", env("RNA_SPLICING_HITS"), ["event_type", "splicing_contrast", "FDR", "IncLevelDifference"]),
    ]
    evidence: dict[str, dict[str, str]] = defaultdict(dict)
    for label, path, cols in specs:
        header, rows = read_table(path)
        gene_col = first_col(header, ["gene_id", "matched_gene_id", "gene"]) if header else ""
        if not gene_col:
            continue
        for row in rows:
            gid = row.get(gene_col, "")
            if not gid:
                continue
            evidence[gid][f"{label}_hit"] = "true"
            values = []
            for col in cols:
                if col in row and row[col]:
                    values.append(f"{col}={row[col]}")
            if values:
                prev = evidence[gid].get(f"{label}_summary", "")
                joined = ";".join(values)
                evidence[gid][f"{label}_summary"] = joined if not prev else f"{prev}|{joined}"
    return evidence


def mark_label(value: str) -> str:
    return canonical_mark(value) or str(value or "").strip() or "unknown_ChIP"


def stage_expression_table() -> dict[tuple[str, str], dict[str, str]]:
    header, rows = read_table(str(outdir("050-rnaseq-summary") / "rna_expression_by_context.tsv"))
    if not header:
        header, rows = read_table(env("RNA_EXPRESSION_CONTEXT"))
    if not header:
        return {}
    gene_col = first_col(header, ["gene_id", "matched_gene_id", "gene"])
    stage_col = first_col(header, ["stage_or_condition", "stage", "condition", "stage_class", "context"])
    tpm_col = first_col(header, ["mean_TPM", "mean_tpm", "TPM", "mean_expression"])
    log_col = first_col(header, ["mean_log2TPM", "mean_log2_tpm", "log2TPM"])
    n_col = first_col(header, ["n_samples", "samples", "replicates"])
    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"weighted_tpm": 0.0, "n": 0.0})
    for row in rows:
        gid = row.get(gene_col, "") if gene_col else ""
        stage = stage_label(row.get(stage_col, "")) if stage_col else "unknown"
        if not gid or stage in {"unknown", "all_stages"}:
            continue
        tpm = as_float(row.get(tpm_col, "0") if tpm_col else row.get(log_col, "0"))
        if not tpm_col and log_col:
            tpm = (2**tpm) - 1
        n = max(1.0, as_float(row.get(n_col, "1") if n_col else "1", 1.0))
        grouped[(gid, stage)]["weighted_tpm"] += tpm * n
        grouped[(gid, stage)]["n"] += n
    out = {}
    for key, item in grouped.items():
        n = item["n"]
        mean_tpm = item["weighted_tpm"] / n if n else 0.0
        out[key] = {
            "mean_TPM": fmt_float(mean_tpm),
            "mean_log2TPM": fmt_float(math.log2(mean_tpm + 1)),
            "n_samples": fmt_float(n),
        }
    return out


def assayed_mark_stages(evidence_rows: list[dict[str, str]]) -> dict[str, set[str]]:
    _h, mark_stage_rows = read_table(str(outdir("060-chipseq-summary") / "chip_mark_stage_metadata.tsv"))
    combos: dict[str, set[str]] = defaultdict(set)
    for row in mark_stage_rows:
        mark = mark_label(row.get("mark_or_factor", ""))
        stage = stage_label(row.get("stage_or_condition", ""))
        if stage in {"unknown", "all_stages"}:
            continue
        if as_float(row.get("n_samples", "1"), 1.0) <= 0:
            continue
        combos[mark].add(stage)
    if combos:
        return combos
    for row in evidence_rows:
        mark = mark_label(row.get("mark_or_factor", ""))
        stage = stage_label(row.get("stage_or_condition", ""))
        if stage not in {"unknown", "all_stages"}:
            combos[mark].add(stage)
    return combos


def write_mark_enrichment_tests(scored: list[dict[str, str]], evidence_rows: list[dict[str, str]]) -> None:
    header = [
        "target_set",
        "feature_scope",
        "mark_or_factor",
        "stage_or_condition",
        "universe_genes",
        "target_genes",
        "marked_genes",
        "overlap_genes",
        "expected_overlap",
        "fold_enrichment",
        "odds_ratio",
        "p_value",
        "q_value",
        "top_overlap_genes",
        "overlap_gene_ids",
    ]
    scored_by_gene = {r.get("gene_id", ""): r for r in scored if r.get("gene_id")}
    gene_meta: dict[str, dict[str, str]] = dict(scored_by_gene)
    for row in evidence_rows:
        gid = row.get("gene_id", "")
        if gid and gid not in gene_meta:
            gene_meta[gid] = row
    universe = {gid for gid in gene_meta if gid}
    if not universe:
        write_table(outdir("080-candidate-scoring") / "mark_enrichment_tests.tsv", [], header)
        return

    deg_genes = {
        gid
        for gid, row in gene_meta.items()
        if row.get("representative_deg_status", "") in {"up", "down"}
        or row.get("integrative_class", "").startswith("DEG")
        or as_int(row.get("rna_n_significant_contrasts", "0")) > 0
    }
    machinery_genes = {gid for gid, row in gene_meta.items() if is_true(row.get("is_epigenetic_machinery", "false"))}
    score_by_gene = {gid: as_float(row.get("candidate_score", "0")) for gid, row in gene_meta.items()}

    marked_any: dict[tuple[str, str], set[str]] = defaultdict(set)
    marked_promoter: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in evidence_rows:
        gid = row.get("gene_id", "")
        if not gid:
            continue
        mark = mark_label(row.get("mark_or_factor", ""))
        stage = stage_label(row.get("stage_or_condition", ""))
        if as_int(row.get("n_peaks", "0")) > 0:
            marked_any[(stage, mark)].add(gid)
            marked_any[("all_observed_stages", mark)].add(gid)
        if as_int(row.get("n_promoter_peaks", "0")) > 0:
            marked_promoter[(stage, mark)].add(gid)
            marked_promoter[("all_observed_stages", mark)].add(gid)

    target_sets = [
        ("DEG", deg_genes),
        ("epigenetic_machinery", machinery_genes),
    ]
    feature_sets = [
        ("any_peak", marked_any),
        ("promoter_peak", marked_promoter),
    ]
    out_rows: list[dict[str, object]] = []
    universe_size = len(universe)
    for feature_scope, mark_sets in feature_sets:
        for (stage, mark), marked in sorted(mark_sets.items(), key=lambda x: (stage_sort_key(x[0][0]), x[0][1])):
            marked = marked & universe
            if not marked:
                continue
            for target_name, target in target_sets:
                target = target & universe
                if not target:
                    continue
                overlap_ids = sorted(marked & target, key=lambda gid: (-score_by_gene.get(gid, 0.0), gid))
                a = len(overlap_ids)
                selected_size = len(target)
                marked_size = len(marked)
                expected = selected_size * marked_size / universe_size if universe_size else 0.0
                fold = (a / expected) if expected > 0 else 0.0
                b = selected_size - a
                c = marked_size - a
                d = universe_size - a - b - c
                odds = ((a + 0.5) * (d + 0.5)) / ((b + 0.5) * (c + 0.5)) if universe_size else 0.0
                pval = fisher_right_tail(a, selected_size, marked_size, universe_size)
                top_overlap = []
                for gid in overlap_ids[:20]:
                    row = gene_meta.get(gid, {})
                    label = row.get("gene_name", "")
                    top_overlap.append(f"{gid}({label})" if label and label != gid else gid)
                out_rows.append(
                    {
                        "target_set": target_name,
                        "feature_scope": feature_scope,
                        "mark_or_factor": mark,
                        "stage_or_condition": stage,
                        "universe_genes": universe_size,
                        "target_genes": selected_size,
                        "marked_genes": marked_size,
                        "overlap_genes": a,
                        "expected_overlap": fmt_float(expected),
                        "fold_enrichment": fmt_float(fold),
                        "odds_ratio": fmt_float(odds),
                        "p_value": fmt_float(pval),
                        "q_value": "",
                        "top_overlap_genes": ";".join(top_overlap),
                        "overlap_gene_ids": ";".join(overlap_ids),
                    }
                )
    q_values = bh_adjust([as_float(row.get("p_value", "1"), 1.0) for row in out_rows])
    for row, qval in zip(out_rows, q_values):
        row["q_value"] = fmt_float(qval)
    out_rows.sort(key=lambda r: (as_float(r.get("q_value", "1"), 1.0), as_float(r.get("p_value", "1"), 1.0), str(r.get("target_set")), str(r.get("mark_or_factor"))))
    write_table(outdir("080-candidate-scoring") / "mark_enrichment_tests.tsv", out_rows, header)


def write_gene_mark_stage_correlations(scored: list[dict[str, str]], evidence_rows: list[dict[str, str]]) -> None:
    signal_header = [
        "gene_id",
        "gene_name",
        "is_epigenetic_machinery",
        "machinery_group",
        "functional_annotation",
        "candidate_score",
        "integrative_class",
        "representative_deg_status",
        "wgcna_hit",
        "mfuzz_hit",
        "dtu_hit",
        "splicing_hit",
        "mark_or_factor",
        "stage_or_condition",
        "rna_mean_TPM",
        "rna_mean_log2TPM",
        "n_peaks",
        "n_promoter_peaks",
        "is_mark_assayed_in_stage",
        "signal_source",
    ]
    corr_header = [
        "gene_id",
        "gene_name",
        "is_epigenetic_machinery",
        "machinery_group",
        "functional_annotation",
        "candidate_score",
        "integrative_class",
        "representative_deg_status",
        "wgcna_hit",
        "mfuzz_hit",
        "dtu_hit",
        "splicing_hit",
        "mark_or_factor",
        "n_stage_points",
        "stages",
        "mean_rna_TPM",
        "mean_total_peaks",
        "mean_promoter_peaks",
        "pearson_rna_vs_total_peaks",
        "spearman_rna_vs_total_peaks",
        "pearson_rna_vs_promoter_peaks",
        "spearman_rna_vs_promoter_peaks",
        "max_abs_correlation",
        "best_signal",
        "correlation_direction",
        "correlation_note",
        "stage_values",
    ]

    expr_by_stage = stage_expression_table()
    mark_stages = assayed_mark_stages(evidence_rows)
    gene_meta: dict[str, dict[str, str]] = {r.get("gene_id", ""): r for r in scored if r.get("gene_id")}
    for row in evidence_rows:
        gid = row.get("gene_id", "")
        if gid and gid not in gene_meta:
            gene_meta[gid] = row

    peak_by_key: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"n_peaks": 0, "n_promoter_peaks": 0})
    genes_by_mark: dict[str, set[str]] = defaultdict(set)
    for row in evidence_rows:
        gid = row.get("gene_id", "")
        if not gid:
            continue
        mark = mark_label(row.get("mark_or_factor", ""))
        stage = stage_label(row.get("stage_or_condition", ""))
        if stage in {"unknown", "all_stages"}:
            continue
        key = (gid, mark, stage)
        peak_by_key[key]["n_peaks"] += as_int(row.get("n_peaks", "0"))
        peak_by_key[key]["n_promoter_peaks"] += as_int(row.get("n_promoter_peaks", "0"))
        genes_by_mark[mark].add(gid)

    signal_rows: list[dict[str, object]] = []
    corr_rows: list[dict[str, object]] = []
    for mark, stages in sorted(mark_stages.items()):
        ordered_stages = sorted(stages, key=stage_sort_key)
        for gid in sorted(genes_by_mark.get(mark, set())):
            meta = gene_meta.get(gid, {"gene_id": gid, "gene_name": gid})
            per_stage = []
            for stage in ordered_stages:
                expr = expr_by_stage.get((gid, stage))
                if not expr:
                    continue
                signal = peak_by_key.get((gid, mark, stage), {"n_peaks": 0, "n_promoter_peaks": 0})
                n_peaks = signal["n_peaks"]
                n_promoter = signal["n_promoter_peaks"]
                row = {
                    "gene_id": gid,
                    "gene_name": meta.get("gene_name", gid),
                    "is_epigenetic_machinery": meta.get("is_epigenetic_machinery", "false"),
                    "machinery_group": meta.get("machinery_group", ""),
                    "functional_annotation": meta.get("functional_annotation", ""),
                    "candidate_score": meta.get("candidate_score", ""),
                    "integrative_class": meta.get("integrative_class", ""),
                    "representative_deg_status": meta.get("representative_deg_status", ""),
                    "wgcna_hit": meta.get("wgcna_hit", "false"),
                    "mfuzz_hit": meta.get("mfuzz_hit", "false"),
                    "dtu_hit": meta.get("dtu_hit", "false"),
                    "splicing_hit": meta.get("splicing_hit", "false"),
                    "mark_or_factor": mark,
                    "stage_or_condition": stage,
                    "rna_mean_TPM": expr.get("mean_TPM", "0"),
                    "rna_mean_log2TPM": expr.get("mean_log2TPM", "0"),
                    "n_peaks": n_peaks,
                    "n_promoter_peaks": n_promoter,
                    "is_mark_assayed_in_stage": "true",
                    "signal_source": "observed_peak" if n_peaks > 0 else "assayed_no_linked_peak",
                }
                signal_rows.append(row)
                per_stage.append(row)
            if len(per_stage) < 2:
                continue
            xs = [as_float(r.get("rna_mean_TPM", "0")) for r in per_stage]
            total = [as_float(r.get("n_peaks", "0")) for r in per_stage]
            promoter = [as_float(r.get("n_promoter_peaks", "0")) for r in per_stage]
            stats = {
                "pearson_total_peaks": pearson_corr(xs, total),
                "spearman_total_peaks": spearman_corr(xs, total),
                "pearson_promoter_peaks": pearson_corr(xs, promoter),
                "spearman_promoter_peaks": spearman_corr(xs, promoter),
            }
            valid_stats = {k: v for k, v in stats.items() if v is not None}
            if valid_stats:
                best_key, best_value = max(valid_stats.items(), key=lambda x: abs(x[1]))
                best_signal = best_key
                max_abs = abs(best_value)
                direction = "positive" if best_value > 0 else "negative" if best_value < 0 else "zero"
                note = "low_stage_count" if len(per_stage) < 3 else ""
            else:
                best_signal = ""
                max_abs = None
                direction = ""
                note = "constant_expression_or_chip_signal"
            corr_rows.append(
                {
                    "gene_id": gid,
                    "gene_name": meta.get("gene_name", gid),
                    "is_epigenetic_machinery": meta.get("is_epigenetic_machinery", "false"),
                    "machinery_group": meta.get("machinery_group", ""),
                    "functional_annotation": meta.get("functional_annotation", ""),
                    "candidate_score": meta.get("candidate_score", ""),
                    "integrative_class": meta.get("integrative_class", ""),
                    "representative_deg_status": meta.get("representative_deg_status", ""),
                    "wgcna_hit": meta.get("wgcna_hit", "false"),
                    "mfuzz_hit": meta.get("mfuzz_hit", "false"),
                    "dtu_hit": meta.get("dtu_hit", "false"),
                    "splicing_hit": meta.get("splicing_hit", "false"),
                    "mark_or_factor": mark,
                    "n_stage_points": len(per_stage),
                    "stages": ";".join(str(r["stage_or_condition"]) for r in per_stage),
                    "mean_rna_TPM": fmt_float(statistics.mean(xs)),
                    "mean_total_peaks": fmt_float(statistics.mean(total)),
                    "mean_promoter_peaks": fmt_float(statistics.mean(promoter)),
                    "pearson_rna_vs_total_peaks": fmt_float(stats["pearson_total_peaks"]),
                    "spearman_rna_vs_total_peaks": fmt_float(stats["spearman_total_peaks"]),
                    "pearson_rna_vs_promoter_peaks": fmt_float(stats["pearson_promoter_peaks"]),
                    "spearman_rna_vs_promoter_peaks": fmt_float(stats["spearman_promoter_peaks"]),
                    "max_abs_correlation": fmt_float(max_abs),
                    "best_signal": best_signal,
                    "correlation_direction": direction,
                    "correlation_note": note,
                    "stage_values": ";".join(
                        f"{r['stage_or_condition']}:TPM={r['rna_mean_TPM']},peaks={r['n_peaks']},promoter={r['n_promoter_peaks']}"
                        for r in per_stage
                    ),
                }
            )
    corr_rows.sort(
        key=lambda r: (
            -as_float(r.get("max_abs_correlation", "0")),
            -as_float(r.get("candidate_score", "0")),
            str(r.get("gene_id", "")),
            str(r.get("mark_or_factor", "")),
        )
    )
    write_table(outdir("080-candidate-scoring") / "gene_mark_stage_signal_matrix.tsv", signal_rows, signal_header)
    write_table(outdir("080-candidate-scoring") / "gene_mark_stage_correlations.tsv", corr_rows, corr_header)


def integration_class(deg_status: str, chip: dict[str, str]) -> str:
    total = as_int(chip.get("total_associated_peaks", "0"))
    promoter = as_int(chip.get("promoter_peaks", "0"))
    body = as_int(chip.get("gene_body_peaks", "0"))
    distal = as_int(chip.get("distal_peaks", "0"))
    diff = as_int(chip.get("n_differential_peaks", "0"))
    is_deg = deg_status in {"up", "down"}
    if is_deg and diff:
        return "DEG_with_differential_peak"
    if is_deg and promoter:
        return "DEG_with_promoter_peak"
    if is_deg and body:
        return "DEG_with_gene_body_peak"
    if is_deg and distal:
        return "DEG_with_distal_peak"
    if is_deg:
        return "DEG_only"
    if total:
        return "ChIP_only"
    return "unchanged"


def write_gene_mark_stage_tables(
    gene_master: dict[str, dict[str, str]],
    rna: dict[str, dict[str, str]],
    deg_by_gene: dict[str, list[dict[str, str]]],
    peak_links: list[dict[str, str]],
    chip: dict[str, dict[str, str]],
    rna_evidence: dict[str, dict[str, str]],
) -> None:
    mark_config = load_mark_config()
    expr_context = expression_context_lookup()
    relations = []
    for link in peak_links:
        gid = link.get("associated_gene_id", "")
        if not gid:
            continue
        mark = link.get("mark_or_factor", "") or "unknown"
        stage = link.get("condition", "") or "unknown"
        gene = gene_master.get(gid, {"gene_id": gid, "gene_name": gid})
        expr = expr_context.get((gid, stage.lower()), {})
        deg_hits = deg_by_gene.get(gid, [])
        evidence = rna_evidence.get(gid, {})
        peak_start = link.get("start", "")
        peak_end = link.get("end", "")
        peak_chrom = link.get("chrom", "")
        peak_position = ""
        if peak_chrom and str(peak_start).strip() and str(peak_end).strip():
            peak_position = f"{peak_chrom}:{peak_start}-{peak_end}"
        peak_midpoint = ""
        if str(peak_start).strip() and str(peak_end).strip():
            peak_midpoint = str((as_int(peak_start) + as_int(peak_end)) // 2)
        status = "not_significant"
        if any(d.get("deg_status") == "up" for d in deg_hits):
            status = "up"
        elif any(d.get("deg_status") == "down" for d in deg_hits):
            status = "down"
        mark_row = mark_config.get(mark, mark_config.get("unknown", {}))
        relations.append(
            {
                "gene_id": gid,
                "gene_name": gene.get("gene_name", gid),
                "is_epigenetic_machinery": gene.get("is_epigenetic_machinery", "false"),
                "machinery_group": gene.get("machinery_group", ""),
                "functional_annotation": gene.get("functional_annotation", ""),
                "mark_or_factor": mark,
                "stage_or_condition": stage,
                "regulatory_class": mark_row.get("regulatory_class", "unknown"),
                "expected_effect": mark_row.get("expected_effect", "unknown"),
                "peak_id": link.get("peak_id", ""),
                "peak_chrom": peak_chrom,
                "peak_start": peak_start,
                "peak_end": peak_end,
                "peak_midpoint": peak_midpoint,
                "peak_position": peak_position,
                "peak_location": link.get("genomic_annotation", ""),
                "promoter_flag": link.get("promoter_flag", "false"),
                "distance_to_tss": link.get("distance_to_tss", ""),
                "rna_mean_TPM_in_stage": expr.get("mean_TPM", ""),
                "rna_mean_log2TPM_in_stage": expr.get("mean_log2TPM", ""),
                "rna_fraction_expressed_in_stage": expr.get("fraction_expressed", ""),
                "representative_deg_status": status,
                "max_abs_log2FC": max([as_float(d.get("log2FoldChange")) for d in deg_hits] or [0]),
                "min_padj": min([as_float(d.get("padj"), 1.0) for d in deg_hits] or [1]),
                "wgcna_hit": evidence.get("wgcna_hit", "false"),
                "wgcna_summary": evidence.get("wgcna_summary", ""),
                "mfuzz_hit": evidence.get("mfuzz_hit", "false"),
                "mfuzz_summary": evidence.get("mfuzz_summary", ""),
                "dtu_hit": evidence.get("dtu_hit", "false"),
                "dtu_summary": evidence.get("dtu_summary", ""),
                "splicing_hit": evidence.get("splicing_hit", "false"),
                "splicing_summary": evidence.get("splicing_summary", ""),
                "source_file": link.get("source_file", ""),
            }
        )
    rel_header = [
        "gene_id",
        "gene_name",
        "is_epigenetic_machinery",
        "machinery_group",
        "functional_annotation",
        "mark_or_factor",
        "stage_or_condition",
        "regulatory_class",
        "expected_effect",
        "peak_id",
        "peak_chrom",
        "peak_start",
        "peak_end",
        "peak_midpoint",
        "peak_position",
        "peak_location",
        "promoter_flag",
        "distance_to_tss",
        "rna_mean_TPM_in_stage",
        "rna_mean_log2TPM_in_stage",
        "rna_fraction_expressed_in_stage",
        "representative_deg_status",
        "max_abs_log2FC",
        "min_padj",
        "wgcna_hit",
        "wgcna_summary",
        "mfuzz_hit",
        "mfuzz_summary",
        "dtu_hit",
        "dtu_summary",
        "splicing_hit",
        "splicing_summary",
        "source_file",
    ]
    write_table(outdir("070-integrated-tables") / "gene_mark_stage_links.tsv", relations, rel_header)

    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in relations:
        grouped[(str(row["gene_id"]), str(row["mark_or_factor"]), str(row["stage_or_condition"]))].append(row)
    summary = []
    for (gid, mark, stage), items in sorted(grouped.items()):
        gene = gene_master.get(gid, {"gene_id": gid, "gene_name": gid})
        chip_row = chip.get(gid, {})
        summary.append(
            {
                "gene_id": gid,
                "gene_name": gene.get("gene_name", gid),
                "is_epigenetic_machinery": gene.get("is_epigenetic_machinery", "false"),
                "machinery_group": gene.get("machinery_group", ""),
                "functional_annotation": gene.get("functional_annotation", ""),
                "mark_or_factor": mark,
                "stage_or_condition": stage,
                "n_peaks": len(items),
                "n_promoter_peaks": sum(str(x.get("promoter_flag", "")).lower() == "true" for x in items),
                "peak_locations": ";".join(sorted({str(x.get("peak_location", "")) for x in items if x.get("peak_location")})),
                "regulatory_class": items[0].get("regulatory_class", "unknown"),
                "expected_effect": items[0].get("expected_effect", "unknown"),
                "rna_mean_TPM_in_stage": items[0].get("rna_mean_TPM_in_stage", ""),
                "representative_deg_status": items[0].get("representative_deg_status", ""),
                "gene_total_associated_peaks": chip_row.get("total_associated_peaks", "0"),
                "gene_n_differential_peaks": chip_row.get("n_differential_peaks", "0"),
                "wgcna_hit": items[0].get("wgcna_hit", "false"),
                "mfuzz_hit": items[0].get("mfuzz_hit", "false"),
                "dtu_hit": items[0].get("dtu_hit", "false"),
                "splicing_hit": items[0].get("splicing_hit", "false"),
            }
        )
    sum_header = [
        "gene_id",
        "gene_name",
        "is_epigenetic_machinery",
        "machinery_group",
        "functional_annotation",
        "mark_or_factor",
        "stage_or_condition",
        "n_peaks",
        "n_promoter_peaks",
        "peak_locations",
        "regulatory_class",
        "expected_effect",
        "rna_mean_TPM_in_stage",
        "representative_deg_status",
        "gene_total_associated_peaks",
        "gene_n_differential_peaks",
        "wgcna_hit",
        "mfuzz_hit",
        "dtu_hit",
        "splicing_hit",
    ]
    write_table(outdir("070-integrated-tables") / "gene_mark_stage_summary.tsv", summary, sum_header)

    mark_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in summary:
        mark_groups[str(row["mark_or_factor"])].append(row)
    by_mark = [
        {
            "mark_or_factor": mark,
            "n_linked_genes": len({str(x["gene_id"]) for x in items}),
            "n_epigenetic_machinery_genes": len({str(x["gene_id"]) for x in items if str(x.get("is_epigenetic_machinery", "")).lower() == "true"}),
            "stages_or_conditions": ";".join(sorted({str(x["stage_or_condition"]) for x in items})),
            "n_promoter_gene_links": sum(as_int(x.get("n_promoter_peaks", "0")) > 0 for x in items),
            "n_deg_linked_genes": len({str(x["gene_id"]) for x in items if x.get("representative_deg_status") in {"up", "down"}}),
        }
        for mark, items in sorted(mark_groups.items())
    ]
    write_table(
        outdir("070-integrated-tables") / "mark_to_gene_catalog.tsv",
        by_mark,
        ["mark_or_factor", "n_linked_genes", "n_epigenetic_machinery_genes", "stages_or_conditions", "n_promoter_gene_links", "n_deg_linked_genes"],
    )


def command_integrate(_args: argparse.Namespace) -> None:
    gene_master = load_gene_master()
    _h, rna_rows = read_table(str(outdir("050-rnaseq-summary") / "rna_gene_summary.tsv"))
    _h, deg_rows = read_table(str(outdir("050-rnaseq-summary") / "rna_deg_long.tsv"))
    _h, chip_rows = read_table(str(outdir("060-chipseq-summary") / "chip_gene_summary.tsv"))
    _h, peak_links = read_table(str(outdir("040-peak-gene-mapping") / "peak_to_gene.tsv"))
    rna = {r["gene_id"]: r for r in rna_rows if r.get("gene_id")}
    chip = {r["gene_id"]: r for r in chip_rows if r.get("gene_id")}
    rna_evidence = supplemental_rna_evidence()
    deg_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in deg_rows:
        if row.get("gene_id"):
            deg_by_gene[row["gene_id"]].append(row)
    all_genes = sorted(set(gene_master) | set(rna) | set(chip) | set(deg_by_gene))
    gene_rows = []
    contrast_rows = []
    for gid in all_genes:
        base = dict(gene_master.get(gid, {"gene_id": gid, "gene_name": gid}))
        rna_row = rna.get(gid, {})
        chip_row = chip.get(gid, {})
        deg_hits = deg_by_gene.get(gid, [])
        best_status = "not_significant"
        if any(d.get("deg_status") == "up" for d in deg_hits):
            best_status = "up"
        elif any(d.get("deg_status") == "down" for d in deg_hits):
            best_status = "down"
        base.update({f"rna_{k}": v for k, v in rna_row.items() if k != "gene_id"})
        base.update({f"chip_{k}": v for k, v in chip_row.items() if k != "gene_id"})
        base.update(rna_evidence.get(gid, {}))
        base["representative_deg_status"] = best_status
        base["integrative_class"] = integration_class(best_status, chip_row)
        gene_rows.append(base)
        if deg_hits:
            for d in deg_hits:
                row = dict(base)
                row.update(
                    {
                        "contrast_id": d.get("contrast_id", "default"),
                        "log2FoldChange": d.get("log2FoldChange", "0"),
                        "padj": d.get("padj", "1"),
                        "deg_status": d.get("deg_status", "not_significant"),
                        "integrative_class": integration_class(d.get("deg_status", "not_significant"), chip_row),
                    }
                )
                contrast_rows.append(row)
        else:
            row = dict(base)
            row.update({"contrast_id": "not_tested", "log2FoldChange": "0", "padj": "1", "deg_status": "not_significant"})
            contrast_rows.append(row)
    gene_header = sorted({k for r in gene_rows for k in r})
    for key in ["gene_id", "gene_name", "integrative_class"]:
        if key in gene_header:
            gene_header.remove(key)
    gene_header = ["gene_id", "gene_name", "integrative_class"] + gene_header
    write_table(outdir("070-integrated-tables") / "integrated_gene_table.tsv", gene_rows, gene_header)
    contrast_header = ["contrast_id"] + [h for h in gene_header if h != "contrast_id"]
    for extra in ["log2FoldChange", "padj", "deg_status"]:
        if extra not in contrast_header:
            contrast_header.append(extra)
    write_table(outdir("070-integrated-tables") / "integrated_by_contrast.tsv", contrast_rows, contrast_header)
    counts = [{"integrative_class": k, "n_genes": v} for k, v in sorted(Counter(r["integrative_class"] for r in gene_rows).items())]
    write_table(outdir("070-integrated-tables") / "integrative_class_counts.tsv", counts, ["integrative_class", "n_genes"])
    write_gene_mark_stage_tables(gene_master, rna, deg_by_gene, peak_links, chip, rna_evidence)


def command_score(_args: argparse.Namespace) -> None:
    _h, rows = read_table(str(outdir("070-integrated-tables") / "integrated_gene_table.tsv"))
    scored = []
    for row in rows:
        score = 0.0
        padj = as_float(row.get("rna_min_padj", "1"), 1.0)
        score += min(10.0, -math.log10(max(padj, 1e-300))) if padj < 1 else 0.0
        score += min(5.0, as_float(row.get("rna_max_abs_log2FC", "0")))
        score += 2.0 if as_int(row.get("chip_promoter_peaks", "0")) > 0 else 0.0
        score += 2.0 if as_int(row.get("chip_n_differential_peaks", "0")) > 0 else 0.0
        score += 1.0 if row.get("is_gene_of_interest", "false").lower() == "true" else 0.0
        score += 2.0 if row.get("is_epigenetic_machinery", "false").lower() == "true" else 0.0
        score += min(3.0, as_int(row.get("rna_n_significant_contrasts", "0")) * 0.5)
        score += min(2.0, len([x for x in row.get("chip_marks_or_factors", "").split(";") if x]) * 0.5)
        score += 2.0 if row.get("wgcna_hit", "false").lower() == "true" else 0.0
        score += 1.5 if row.get("mfuzz_hit", "false").lower() == "true" else 0.0
        score += 1.0 if row.get("dtu_hit", "false").lower() == "true" else 0.0
        score += 1.0 if row.get("splicing_hit", "false").lower() == "true" else 0.0
        item = dict(row)
        item["candidate_score"] = f"{score:.4f}"
        item["score_components"] = "deg_significance;rna_log2fc;promoter_peak;differential_peak;gene_interest;epigenetic_machinery;multi_contrast;multi_mark;wgcna;mfuzz;dtu;splicing"
        scored.append(item)
    scored.sort(key=lambda r: as_float(r.get("candidate_score")), reverse=True)
    header = ["candidate_score", "gene_id", "gene_name", "integrative_class", "score_components"] + [
        h for h in sorted({k for r in scored for k in r}) if h not in {"candidate_score", "gene_id", "gene_name", "integrative_class", "score_components"}
    ]
    write_table(outdir("080-candidate-scoring") / "candidate_gene_scores.tsv", scored, header)
    top_n = as_int(env("TOP_CANDIDATES_N", "100"), 100)
    write_table(outdir("080-candidate-scoring") / "top_candidates.tsv", scored[:top_n], header)
    _h, contrast_rows = read_table(str(outdir("070-integrated-tables") / "integrated_by_contrast.tsv"))
    by_contrast = []
    score_by_gene = {r.get("gene_id"): r.get("candidate_score", "0") for r in scored}
    for row in contrast_rows:
        item = dict(row)
        item["candidate_score"] = score_by_gene.get(row.get("gene_id"), "0")
        by_contrast.append(item)
    by_contrast.sort(key=lambda r: (r.get("contrast_id", ""), -as_float(r.get("candidate_score"))))
    write_table(outdir("080-candidate-scoring") / "ranked_candidates_by_contrast.tsv", by_contrast, ["candidate_score"] + [h for h in sorted({k for r in by_contrast for k in r}) if h != "candidate_score"])
    by_mark = []
    for row in scored:
        marks = [m for m in row.get("chip_marks_or_factors", "").split(";") if m] or ["no_chip_mark"]
        for mark in marks:
            item = dict(row)
            item["mark_or_factor"] = mark
            by_mark.append(item)
    write_table(outdir("080-candidate-scoring") / "ranked_candidates_by_mark.tsv", by_mark, ["mark_or_factor"] + header)

    _h, gene_mark_rows = read_table(str(outdir("070-integrated-tables") / "gene_mark_stage_summary.tsv"))
    scored_by_gene = {r.get("gene_id", ""): r for r in scored}
    evidence_rows = []
    for row in gene_mark_rows:
        scored_row = scored_by_gene.get(row.get("gene_id", ""), {})
        item = dict(row)
        for key in [
            "candidate_score",
            "integrative_class",
            "rna_mean_expression",
            "rna_context_with_highest_expression",
            "rna_n_significant_contrasts",
            "rna_max_abs_log2FC",
            "rna_min_padj",
            "chip_marks_or_factors",
            "chip_binding_statuses",
            "wgcna_summary",
            "mfuzz_summary",
            "dtu_summary",
            "splicing_summary",
        ]:
            item[key] = scored_row.get(key, item.get(key, ""))
        evidence_rows.append(item)
    evidence_rows.sort(key=lambda r: (-as_float(r.get("candidate_score")), r.get("stage_or_condition", ""), r.get("mark_or_factor", ""), r.get("gene_id", "")))
    evidence_header = [
        "candidate_score",
        "gene_id",
        "gene_name",
        "is_epigenetic_machinery",
        "machinery_group",
        "functional_annotation",
        "integrative_class",
        "mark_or_factor",
        "stage_or_condition",
        "regulatory_class",
        "expected_effect",
        "n_peaks",
        "n_promoter_peaks",
        "peak_locations",
        "rna_mean_TPM_in_stage",
        "representative_deg_status",
        "rna_n_significant_contrasts",
        "rna_max_abs_log2FC",
        "rna_min_padj",
        "wgcna_hit",
        "wgcna_summary",
        "mfuzz_hit",
        "mfuzz_summary",
        "dtu_hit",
        "dtu_summary",
        "splicing_hit",
        "splicing_summary",
    ]
    write_table(outdir("080-candidate-scoring") / "ranked_gene_mark_stage_evidence.tsv", evidence_rows, evidence_header)

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in evidence_rows:
        grouped[(row.get("stage_or_condition", "unknown"), row.get("mark_or_factor", "unknown"))].append(row)
    comparisons = []
    for (stage, mark), items in sorted(grouped.items()):
        genes = {x.get("gene_id", "") for x in items if x.get("gene_id")}
        comparisons.append(
            {
                "stage_or_condition": stage,
                "mark_or_factor": mark,
                "n_linked_genes": len(genes),
                "n_peak_gene_links": sum(as_int(x.get("n_peaks", "0")) for x in items),
                "n_promoter_linked_genes": len({x.get("gene_id", "") for x in items if as_int(x.get("n_promoter_peaks", "0")) > 0}),
                "n_deg_linked_genes": len({x.get("gene_id", "") for x in items if x.get("representative_deg_status") in {"up", "down"}}),
                "n_epigenetic_machinery_genes": len({x.get("gene_id", "") for x in items if x.get("is_epigenetic_machinery", "").lower() == "true"}),
                "n_wgcna_hits": len({x.get("gene_id", "") for x in items if x.get("wgcna_hit", "").lower() == "true"}),
                "n_mfuzz_hits": len({x.get("gene_id", "") for x in items if x.get("mfuzz_hit", "").lower() == "true"}),
                "n_dtu_hits": len({x.get("gene_id", "") for x in items if x.get("dtu_hit", "").lower() == "true"}),
                "n_splicing_hits": len({x.get("gene_id", "") for x in items if x.get("splicing_hit", "").lower() == "true"}),
                "mean_candidate_score": f"{statistics.mean([as_float(x.get('candidate_score')) for x in items]):.8g}" if items else "0",
                "top_candidate_genes": ";".join([x.get("gene_id", "") for x in sorted(items, key=lambda r: -as_float(r.get("candidate_score")))[:20] if x.get("gene_id")]),
            }
        )
    comparison_header = [
        "stage_or_condition",
        "mark_or_factor",
        "n_linked_genes",
        "n_peak_gene_links",
        "n_promoter_linked_genes",
        "n_deg_linked_genes",
        "n_epigenetic_machinery_genes",
        "n_wgcna_hits",
        "n_mfuzz_hits",
        "n_dtu_hits",
        "n_splicing_hits",
        "mean_candidate_score",
        "top_candidate_genes",
    ]
    write_table(outdir("080-candidate-scoring") / "stage_mark_comparison.tsv", comparisons, comparison_header)

    regulator_rows = [
        r
        for r in scored
        if r.get("is_epigenetic_machinery", "").lower() == "true"
        or r.get("wgcna_hit", "").lower() == "true"
        or r.get("mfuzz_hit", "").lower() == "true"
        or r.get("dtu_hit", "").lower() == "true"
        or r.get("splicing_hit", "").lower() == "true"
    ]
    write_table(outdir("080-candidate-scoring") / "candidate_regulators.tsv", regulator_rows, header)
    write_mark_enrichment_tests(scored, evidence_rows)
    write_gene_mark_stage_correlations(scored, evidence_rows)


def command_visualize(_args: argparse.Namespace) -> None:
    vis_dir = outdir("090-visualizations")
    script = Path(__file__).resolve().parent / "r" / "visualize_integrative.R"
    if not script.is_file():
        raise SystemExit(f"Visualization script not found: {script}")
    rscript = env("RSCRIPT_BIN", "Rscript") or "Rscript"
    subprocess.run(
        [
            rscript,
            str(script),
            "--project-dir",
            str(Path(env("INTEGRATION_OUTPUT_DIR", env("PROJECT_DIR", "."))).resolve()),
            "--outdir",
            str(vis_dir.resolve()),
        ],
        check=True,
    )


def command_functional(_args: argparse.Namespace) -> None:
    _h, top = read_table(str(outdir("080-candidate-scoring") / "top_candidates.tsv"))
    f_header, f_rows = read_table(env("FUNCTIONAL_ANNOTATION"))
    if not f_header:
        write_table(outdir("100-functional-analysis") / "functional_enrichment.tsv", [], ["term", "n_selected", "n_background", "note"])
        write_text(outdir("100-functional-analysis") / "functional_analysis_skipped.txt", "No functional annotation file was configured or found.\n")
        return
    gene_col = first_col(f_header, ["gene_id", "gene", "id"])
    term_col = first_col(f_header, ["term", "go", "GO", "kegg", "pathway", "description", "functional_annotation"])
    selected = {r.get("gene_id", "") for r in top if r.get("gene_id")}
    bg_by_term: dict[str, set[str]] = defaultdict(set)
    sel_by_term: dict[str, set[str]] = defaultdict(set)
    for row in f_rows:
        gid = row.get(gene_col, "") if gene_col else ""
        raw_terms = row.get(term_col, "") if term_col else ""
        for term in re.split(r"[;,|]", raw_terms):
            term = term.strip()
            if not gid or not term:
                continue
            bg_by_term[term].add(gid)
            if gid in selected:
                sel_by_term[term].add(gid)
    rows = [
        {
            "term": term,
            "n_selected": len(sel_by_term.get(term, set())),
            "n_background": len(bg),
            "selected_genes": ";".join(sorted(sel_by_term.get(term, set()))),
            "note": "descriptive_count_offline",
        }
        for term, bg in bg_by_term.items()
        if sel_by_term.get(term)
    ]
    rows.sort(key=lambda r: (-r["n_selected"], r["term"]))
    write_table(outdir("100-functional-analysis") / "functional_enrichment.tsv", rows, ["term", "n_selected", "n_background", "selected_genes", "note"])


def command_report(_args: argparse.Namespace) -> None:
    report_dir = outdir("110-reports")
    _h, classes = read_table(str(outdir("070-integrated-tables") / "integrative_class_counts.tsv"))
    _h, top = read_table(str(outdir("080-candidate-scoring") / "top_candidates.tsv"))
    _h, validation = read_table(str(outdir("010-input-validation") / "validation_report.tsv"))
    _h, mark_stage = read_table(str(outdir("060-chipseq-summary") / "chip_mark_stage_metadata.tsv"))
    _h, gene_mark = read_table(str(outdir("070-integrated-tables") / "gene_mark_stage_summary.tsv"))
    _h, gene_mark_evidence = read_table(str(outdir("080-candidate-scoring") / "ranked_gene_mark_stage_evidence.tsv"))
    _h, stage_mark_comparison = read_table(str(outdir("080-candidate-scoring") / "stage_mark_comparison.tsv"))
    _h, candidate_regulators = read_table(str(outdir("080-candidate-scoring") / "candidate_regulators.tsv"))
    _h, mark_enrichment = read_table(str(outdir("080-candidate-scoring") / "mark_enrichment_tests.tsv"))
    _h, gene_mark_correlations = read_table(str(outdir("080-candidate-scoring") / "gene_mark_stage_correlations.tsv"))
    _h, epi_catalog = read_table(str(outdir("030-id-harmonization") / "epigenetic_machinery_catalog.tsv"))
    _h, figure_manifest = read_table(str(outdir("090-visualizations") / "visualization_manifest.tsv"))
    _h, gene_panels = read_table(str(outdir("090-visualizations") / "gene_panel_index.tsv"))
    n_genes = sum(as_int(r.get("n_genes", "0")) for r in classes)
    generated = dt.datetime.now().isoformat(timespec="seconds")
    md = [
        "# Integrative RNA-seq + ChIP-seq report",
        "",
        f"Generated: {generated}",
        "",
        "## Inputs",
        "",
    ]
    md.extend(f"- {r.get('item')}: {r.get('status')} {r.get('message')}".strip() for r in validation)
    md.extend(
        [
            "",
            "## Summary",
            "",
            f"- Genes in integrated table: {n_genes}",
            f"- Epigenetic machinery genes in catalog: {len(epi_catalog)}",
            f"- ChIP mark/stage metadata combinations: {len(mark_stage)}",
            f"- Gene-mark-stage links from annotated peaks: {len(gene_mark)}",
            f"- Formal mark enrichment tests: {len(mark_enrichment)}",
            f"- Gene-mark RNA/ChIP stage correlations: {len(gene_mark_correlations)}",
            "",
        ]
    )
    md.append("### ChIP marks by stage/condition")
    md.append("")
    if mark_stage:
        for r in mark_stage[:50]:
            md.append(f"- {r.get('stage_or_condition')}: {r.get('mark_or_factor')} ({r.get('n_samples')} sample[s])")
    else:
        md.append("- No ChIP metadata rows were available.")
    md.append("")
    md.append("### Integrative classes")
    md.append("")
    for r in classes:
        md.append(f"- {r.get('integrative_class')}: {r.get('n_genes')}")
    md.extend(["", "### Top candidates", ""])
    for r in top[:20]:
        md.append(f"- {r.get('gene_id')} score={r.get('candidate_score')} class={r.get('integrative_class')}")
    md.extend(
        [
            "",
            "### Gene-mark-stage outputs",
            "",
            "- `070-integrated-tables/gene_mark_stage_links.tsv`: one row per peak-gene-mark-stage association.",
            "- `070-integrated-tables/gene_mark_stage_summary.tsv`: collapsed catalog by gene, mark, and stage.",
            "- `070-integrated-tables/mark_to_gene_catalog.tsv`: marks with linked genes and epigenetic machinery counts.",
            "- `080-candidate-scoring/ranked_gene_mark_stage_evidence.tsv`: ranked gene-mark-stage associations with RNA, WGCNA, Mfuzz, DTU, and splicing evidence.",
            "- `080-candidate-scoring/stage_mark_comparison.tsv`: stage-by-mark comparison table.",
            "- `080-candidate-scoring/candidate_regulators.tsv`: high-priority regulators supported by epigenetic machinery or RNA network/isoform evidence.",
            "- `080-candidate-scoring/mark_enrichment_tests.tsv`: formal mark enrichment tests in DEG and epigenetic machinery gene sets.",
            "- `080-candidate-scoring/gene_mark_stage_correlations.tsv`: stage-by-stage RNA expression versus ChIP evidence correlations by gene and mark.",
            "- `080-candidate-scoring/gene_mark_stage_signal_matrix.tsv`: long RNA/ChIP signal matrix used for the correlations.",
            "- `090-visualizations/gene_panel_index.tsv`: index of gene-specific RNA + ChIP figure panels.",
            "",
            "## Limitations",
            "",
            "- ChIP-seq links are associations between peaks and genes, not proof of causality.",
            "- Concordance depends on mark/factor biology configured in config/chip_marks_config.tsv.",
            "- Offline functional analysis uses supplied annotation only.",
            "",
            "## Key generated files",
            "",
            "- 030-id-harmonization/gene_master_table.tsv",
            "- 040-peak-gene-mapping/peak_to_gene.tsv",
            "- 070-integrated-tables/integrated_gene_table.tsv",
            "- 080-candidate-scoring/candidate_gene_scores.tsv",
            "- 080-candidate-scoring/mark_enrichment_tests.tsv",
            "- 080-candidate-scoring/gene_mark_stage_correlations.tsv",
            "- 090-visualizations/gene_panel_index.tsv",
            "- 090-visualizations/visualization_manifest.tsv",
            "- 100-functional-analysis/functional_enrichment.tsv",
        ]
    )
    md_text = "\n".join(md) + "\n"
    write_text(report_dir / "integrative_report.md", md_text)

    def table_html(rows: list[dict[str, str]], columns: list[str], limit: int = 12) -> str:
        if not rows:
            return "<p class='muted'>No rows available yet.</p>"
        head = "".join(f"<th>{html.escape(col)}</th>" for col in columns)
        body = []
        for row in rows[:limit]:
            body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in columns) + "</tr>")
        more = f"<p class='muted'>Showing {min(limit, len(rows))} of {len(rows)} rows.</p>" if len(rows) > limit else ""
        return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>{more}"

    display_figures = []
    seen_figures = set()
    preferred = {}
    for row in figure_manifest:
        fig = row.get("figure", "")
        if fig.startswith("gene_panels/"):
            continue
        stem = str(Path(fig).with_suffix("")) if fig else ""
        if not stem:
            continue
        if fig.endswith(".png") or (fig.endswith(".svg") and stem not in preferred):
            preferred[stem] = fig
    for fig in preferred.values():
        if fig not in seen_figures:
            seen_figures.add(fig)
            display_figures.append(fig)
    figure_cards = "".join(
        f"<figure><img src='../090-visualizations/{html.escape(fig)}' alt='{html.escape(fig)}'><figcaption>{html.escape(Path(fig).stem.replace('_', ' '))}</figcaption></figure>"
        for fig in display_figures
    )
    if not figure_cards:
        figure_cards = "<p class='muted'>Run the visualize step to populate figure panels.</p>"

    gene_panel_cards = "".join(
        f"<figure><img src='../090-visualizations/{html.escape(row.get('figure_png', ''))}' alt='{html.escape(row.get('gene_id', 'gene panel'))}'><figcaption>{html.escape(row.get('gene_id', ''))} {html.escape(row.get('gene_name', ''))}</figcaption></figure>"
        for row in gene_panels
        if row.get("figure_png")
    )
    if not gene_panel_cards:
        gene_panel_cards = "<p class='muted'>Run the visualize step after scoring to populate gene-specific RNA + ChIP panels.</p>"

    class_items = "".join(
        f"<div class='metric small'><span>{html.escape(r.get('integrative_class', 'unknown'))}</span><strong>{html.escape(str(r.get('n_genes', '0')))}</strong></div>"
        for r in classes
    )
    html_body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Integrative RNA-seq + ChIP-seq Report</title>
  <style>
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: #111827; background: #f8fafc; }}
    header {{ background: #111827; color: white; padding: 28px 36px; }}
    header h1 {{ margin: 0 0 8px; font-size: 28px; }}
    header p {{ margin: 0; color: #cbd5e1; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    section {{ margin: 0 0 26px; }}
    h2 {{ font-size: 20px; margin: 0 0 14px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }}
    .metric, .panel, figure {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05); }}
    .metric span {{ display: block; color: #64748b; font-size: 13px; margin-bottom: 8px; }}
    .metric strong {{ font-size: 28px; }}
    .metric.small strong {{ font-size: 22px; }}
    .figures {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 16px; }}
    figure {{ margin: 0; }}
    figure img {{ width: 100%; height: auto; display: block; }}
    figcaption {{ color: #475569; font-size: 13px; margin-top: 8px; text-transform: capitalize; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid #e5e7eb; border-radius: 8px; background: white; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; white-space: nowrap; }}
    th {{ background: #f1f5f9; font-weight: 700; }}
    .muted {{ color: #64748b; }}
    .status-ok {{ color: #166534; font-weight: 700; }}
    .status-warning {{ color: #92400e; font-weight: 700; }}
    .status-error {{ color: #991b1b; font-weight: 700; }}
    code {{ background: #eef2ff; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <header>
    <h1>Integrative RNA-seq + ChIP-seq Report</h1>
    <p>Generated {html.escape(generated)}. Focus: genes, epigenetic marks, life-cycle stages, and expression evidence.</p>
  </header>
  <main>
    <section class="grid">
      <div class="metric"><span>Integrated genes</span><strong>{n_genes}</strong></div>
      <div class="metric"><span>Epigenetic machinery catalog entries</span><strong>{len(epi_catalog)}</strong></div>
      <div class="metric"><span>ChIP mark/stage combinations</span><strong>{len(mark_stage)}</strong></div>
      <div class="metric"><span>Gene-mark-stage links</span><strong>{len(gene_mark)}</strong></div>
      <div class="metric"><span>Mark enrichment tests</span><strong>{len(mark_enrichment)}</strong></div>
      <div class="metric"><span>RNA/ChIP correlations</span><strong>{len(gene_mark_correlations)}</strong></div>
    </section>
    <section>
      <h2>Figures</h2>
      <div class="figures">{figure_cards}</div>
    </section>
    <section>
      <h2>Integrative Classes</h2>
      <div class="grid">{class_items}</div>
    </section>
    <section>
      <h2>ChIP Marks By Stage</h2>
      {table_html(mark_stage, ["stage_or_condition", "mark_or_factor", "n_samples", "replicates", "batches"], 30)}
    </section>
    <section>
      <h2>Top Candidate Genes</h2>
      {table_html(top, ["candidate_score", "gene_id", "gene_name", "integrative_class", "is_epigenetic_machinery", "machinery_group", "wgcna_hit", "mfuzz_hit", "dtu_hit", "splicing_hit"], 20)}
    </section>
    <section>
      <h2>Candidate Regulators</h2>
      {table_html(candidate_regulators, ["candidate_score", "gene_id", "gene_name", "integrative_class", "is_epigenetic_machinery", "machinery_group", "wgcna_hit", "mfuzz_hit", "dtu_hit", "splicing_hit"], 25)}
    </section>
    <section>
      <h2>Gene-Specific RNA + ChIP Panels</h2>
      <div class="figures">{gene_panel_cards}</div>
      {table_html(gene_panels, ["gene_id", "gene_name", "candidate_score", "integrative_class", "figure_png"], 25)}
    </section>
    <section>
      <h2>Epigenetic Machinery Catalog</h2>
      {table_html(epi_catalog, ["gene_id", "gene_name", "machinery_group", "description", "catalog_source"], 25)}
    </section>
    <section>
      <h2>Stage-Mark Comparisons</h2>
      {table_html(stage_mark_comparison, ["stage_or_condition", "mark_or_factor", "n_linked_genes", "n_deg_linked_genes", "n_epigenetic_machinery_genes", "n_wgcna_hits", "n_mfuzz_hits", "n_dtu_hits", "n_splicing_hits", "mean_candidate_score"], 40)}
    </section>
    <section>
      <h2>Formal Mark Enrichment</h2>
      {table_html(mark_enrichment, ["target_set", "feature_scope", "mark_or_factor", "stage_or_condition", "target_genes", "marked_genes", "overlap_genes", "fold_enrichment", "odds_ratio", "p_value", "q_value", "top_overlap_genes"], 40)}
    </section>
    <section>
      <h2>RNA-ChIP Stage Correlations</h2>
      {table_html(gene_mark_correlations, ["gene_id", "gene_name", "mark_or_factor", "n_stage_points", "max_abs_correlation", "best_signal", "correlation_direction", "candidate_score", "machinery_group", "stage_values"], 40)}
    </section>
    <section>
      <h2>Ranked Gene-Mark-Stage Evidence</h2>
      {table_html(gene_mark_evidence or gene_mark, ["candidate_score", "gene_id", "gene_name", "mark_or_factor", "stage_or_condition", "n_peaks", "n_promoter_peaks", "representative_deg_status", "is_epigenetic_machinery", "machinery_group", "wgcna_hit", "mfuzz_hit", "dtu_hit", "splicing_hit"], 30)}
      <p class="muted">This table is the main answer: each row links one gene to one mark and stage, then adds expression and RNA evidence.</p>
    </section>
    <section>
      <h2>Input Validation</h2>
      {table_html(validation, ["item", "status", "message", "path"], 40)}
    </section>
    <section class="panel">
      <h2>Key Output Files</h2>
      <p><code>070-integrated-tables/gene_mark_stage_summary.tsv</code> answers the central gene-mark-stage question.</p>
      <p><code>080-candidate-scoring/ranked_gene_mark_stage_evidence.tsv</code> ranks those gene-mark-stage associations with RNA, ChIP, WGCNA, Mfuzz, DTU, and splicing evidence.</p>
      <p><code>080-candidate-scoring/stage_mark_comparison.tsv</code> compares marks across life-cycle stages.</p>
      <p><code>080-candidate-scoring/mark_enrichment_tests.tsv</code> tests whether marks are enriched in DEG or epigenetic machinery genes.</p>
      <p><code>080-candidate-scoring/gene_mark_stage_correlations.tsv</code> correlates RNA expression and ChIP evidence across assayed stages for each gene-mark pair.</p>
      <p><code>080-candidate-scoring/candidate_gene_scores.tsv</code> ranks potential regulators of parasite plasticity.</p>
      <p><code>050-rnaseq-summary/rna_sample_group_mapping.tsv</code> diagnoses RNA sample-to-stage mapping for gene panels.</p>
      <p><code>030-id-harmonization/epigenetic_machinery_catalog.tsv</code> consolidates the S. mansoni epigenetic machinery catalog.</p>
    </section>
  </main>
</body>
</html>
"""
    write_text(report_dir / "integrative_report.html", html_body)


COMMANDS = {
    "validate": command_validate,
    "prepare": command_prepare,
    "harmonize": command_harmonize,
    "map-peaks": command_map_peaks,
    "summarize-rna": command_summarize_rna,
    "summarize-chip": command_summarize_chip,
    "integrate": command_integrate,
    "score": command_score,
    "visualize": command_visualize,
    "functional": command_functional,
    "report": command_report,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()
    COMMANDS[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
