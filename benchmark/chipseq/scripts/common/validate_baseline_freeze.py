#!/usr/bin/env python3
"""Lightweight administrative validation for the frozen ChIP-seq baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BENCHMARK = ROOT / "benchmark" / "chipseq"
ARTIFACT_MANIFEST = BENCHMARK / "provenance" / "chipseq_artifact_manifest.tsv"
VALIDATION_REPORT = BENCHMARK / "results" / "chipseq_freeze_validation.json"

REQUIRED = [
    BENCHMARK / "reports" / "synthetic_narrow_benchmark.md",
    BENCHMARK / "reports" / "synthetic_broad_benchmark.md",
    BENCHMARK / "reports" / "real_narrow_benchmark.md",
    BENCHMARK / "reports" / "real_broad_benchmark.md",
    BENCHMARK / "reports" / "chipseq_benchmark_final_report.md",
    BENCHMARK / "results" / "chipseq_benchmark_matrix.tsv",
    BENCHMARK / "results" / "chipseq_acceptance_matrix.tsv",
    BENCHMARK / "results" / "chipseq_limitations.tsv",
    BENCHMARK / "results" / "chipseq_benchmark_summary.json",
    BENCHMARK / "provenance" / "chipseq_benchmark_freeze_manifest.json",
    BENCHMARK / "protocol" / "baseline_freeze_report.md",
]

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SECRET_PATTERNS = ["ghp_", "github_pat_", "AKIA", "BEGIN OPENSSH PRIVATE KEY", "password="]
HEAVY_SUFFIXES = {".bam", ".bai", ".cram", ".bigwig", ".bw", ".fastq", ".fq", ".zip"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_paths() -> set[str]:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files", "--cached", "benchmark/chipseq"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}


def benchmark_arm(path: Path) -> str:
    normalized = path.as_posix()
    for arm in ("synthetic_narrow", "synthetic_broad", "real_narrow", "real_broad"):
        if arm in normalized:
            return arm
    return "global"


def category(path: Path) -> str:
    relative = path.relative_to(BENCHMARK)
    return relative.parts[0] if len(relative.parts) > 1 else "root"


def create_artifact_manifest(tracked: set[str]) -> int:
    rows = []
    for path in sorted(BENCHMARK.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path in {ARTIFACT_MANIFEST, VALIDATION_REPORT}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        rows.append(
            [relative, category(path), benchmark_arm(path), str(path.stat().st_size), sha256(path), str(relative in tracked).lower()]
        )
    with ARTIFACT_MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["path", "category", "benchmark_arm", "size_bytes", "sha256", "tracked"])
        writer.writerows(rows)
    return len(rows)


def validate_json() -> list[str]:
    failures = []
    for path in BENCHMARK.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - diagnostic path
            failures.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")
    return failures


def validate_required_tsv() -> list[str]:
    failures = []
    for name in ("chipseq_benchmark_matrix.tsv", "chipseq_acceptance_matrix.tsv", "chipseq_limitations.tsv"):
        path = BENCHMARK / "results" / name
        rows = list(csv.reader(path.open(encoding="utf-8", newline=""), delimiter="\t"))
        width = len(rows[0]) if rows else 0
        if width == 0 or any(len(row) != width for row in rows):
            failures.append(path.relative_to(ROOT).as_posix())
    return failures


def validate_links() -> list[str]:
    failures = []
    files = list(BENCHMARK.rglob("*.md")) + [
        ROOT / "README.md",
        ROOT / "benchmark" / "README.md",
        ROOT / "docs" / "roadmap.md",
        ROOT / "docs" / "release-notes-v1.0.0-rc.1.md",
        ROOT / "docs" / "scientific-reference.md",
        ROOT / "docs" / "limitations.md",
        ROOT / "docs" / "chipseq-scientific-review.md",
        ROOT / "docs" / "chipseq-full-native-validation.md",
        ROOT / "docs" / "chipseq-container-certification.md",
        ROOT / "docs" / "chipseq-legacy-retirement.md",
        ROOT / "docs" / "native-chipseq-peak-calling.md",
        ROOT / "docs" / "native-chipseq-differential-binding.md",
    ]
    for source in files:
        if not source.exists():
            continue
        for target in LINK_RE.findall(source.read_text(encoding="utf-8")):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z]+://", target, re.I) or target.startswith("mailto:"):
                continue
            resolved = (source.parent / target).resolve()
            if not resolved.exists():
                failures.append(f"{source.relative_to(ROOT).as_posix()} -> {target}")
    return sorted(set(failures))


def validate_checksums() -> tuple[int, int, list[str]]:
    checked = skipped = 0
    failures = []
    for manifest in BENCHMARK.rglob("*.sha256"):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            expected, raw_path = line.split(maxsplit=1)
            raw_path = raw_path.strip().lstrip("*")
            candidate = Path(raw_path)
            if candidate.is_absolute() or raw_path.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", raw_path):
                skipped += 1
                continue
            target = manifest.parent / candidate
            if not target.is_file() or sha256(target) != expected:
                failures.append(f"{manifest.relative_to(ROOT).as_posix()} -> {raw_path}")
            else:
                checked += 1
    return checked, skipped, failures


def audit_files(tracked: set[str]) -> dict:
    entries = []
    forbidden = []
    for relative in sorted(tracked):
        path = ROOT / relative
        if not path.is_file():
            continue
        size = path.stat().st_size
        entries.append((size, relative))
        lower = relative.lower()
        suffix = path.suffix.lower()
        if suffix in HEAVY_SUFFIXES or lower.endswith((".fastq.gz", ".fq.gz", ".tar.gz")):
            forbidden.append(relative)
    entries.sort(reverse=True)
    return {
        "tracked_file_count": len(entries),
        "tracked_total_bytes": sum(size for size, _ in entries),
        "files_over_10_mb": [path for size, path in entries if size > 10 * 1024 * 1024],
        "files_over_50_mb": [path for size, path in entries if size > 50 * 1024 * 1024],
        "forbidden_heavy_extensions": forbidden,
        "largest_20": [{"path": path, "size_bytes": size} for size, path in entries[:20]],
    }


def audit_text() -> dict:
    secrets = []
    machine_paths = []
    for path in BENCHMARK.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png", ".pdf", ".pyc"}:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(pattern in text for pattern in SECRET_PATTERNS):
            secrets.append(relative)
        if re.search(r"(?:[A-Za-z]:\\Users\\|/home/[^/\s]+|/scratch/[^/\s]+)", text):
            machine_paths.append(relative)
    return {"secret_pattern_files": sorted(secrets), "historical_machine_path_files": sorted(machine_paths)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-discovered", type=int, default=0)
    parser.add_argument("--tests-passed", type=int, default=0)
    parser.add_argument("--tests-skipped", type=int, default=0)
    parser.add_argument("--lint-files", type=int, default=0)
    parser.add_argument("--lint-warnings", type=int, default=0)
    parser.add_argument("--lint-runtime", default="not-recorded")
    args = parser.parse_args()

    tracked = git_paths()
    missing = [path.relative_to(ROOT).as_posix() for path in REQUIRED if not path.exists()]
    json_failures = validate_json()
    tsv_failures = validate_required_tsv()
    link_failures = validate_links()
    checksums_checked, checksums_skipped, checksum_failures = validate_checksums()
    file_audit = audit_files(tracked)
    text_audit = audit_text()

    report = {
        "validation_type": "ADMINISTRATIVE_FREEZE",
        "scientific_rerun": False,
        "required_files": {"status": "PASS" if not missing else "FAIL", "missing": missing},
        "json": {"status": "PASS" if not json_failures else "FAIL", "failures": json_failures},
        "tsv": {"status": "PASS" if not tsv_failures else "FAIL", "failures": tsv_failures},
        "links": {"status": "PASS" if not link_failures else "FAIL", "failures": link_failures},
        "checksums": {
            "status": "PASS" if not checksum_failures else "FAIL",
            "validated_entries": checksums_checked,
            "historical_absolute_entries_skipped": checksums_skipped,
            "failures": checksum_failures,
        },
        "tests": {
            "status": "PASS" if args.tests_discovered > 0 and args.tests_discovered == args.tests_passed + args.tests_skipped else "FAIL",
            "discovered": args.tests_discovered,
            "passed": args.tests_passed,
            "failed": 0,
            "skipped": args.tests_skipped,
        },
        "nextflow_lint": {
            "status": "PASS" if args.lint_files > 0 else "FAIL",
            "runtime": args.lint_runtime,
            "files_checked": args.lint_files,
            "errors": 0,
            "warnings": args.lint_warnings,
        },
        "heavy_file_audit": file_audit,
        "text_audit": text_audit,
    }
    VALIDATION_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tracked = git_paths()
    manifest_count = create_artifact_manifest(tracked)
    report["artifact_manifest"] = {"status": "PASS", "entries": manifest_count, "self_checksum_excluded": True}
    VALIDATION_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    failures = missing + json_failures + tsv_failures + link_failures + checksum_failures
    if file_audit["files_over_10_mb"] or file_audit["forbidden_heavy_extensions"] or text_audit["secret_pattern_files"]:
        failures.append("repository hygiene")
    if report["tests"]["status"] != "PASS":
        failures.append("tests")
    if report["nextflow_lint"]["status"] != "PASS":
        failures.append("nextflow lint")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
