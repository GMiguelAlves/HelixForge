#!/usr/bin/env python3

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from baseline_support import (
    BASE_DIR,
    COMMANDS,
    FIXTURE_DIR,
    GOLDEN_DIR,
    iter_expected_outputs,
    normalized_text,
    sha256,
)
from run_baseline import REPO_ROOT, run


def command_output(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, cwd=REPO_ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        return f"unavailable: {error}"


def main() -> int:
    actual = BASE_DIR / "actual"
    run(actual)
    if GOLDEN_DIR.exists():
        shutil.rmtree(GOLDEN_DIR)
    for group, relative in iter_expected_outputs():
        source = actual / relative
        if not source.is_file():
            raise SystemExit(f"Missing expected legacy output: {source}")
        target = GOLDEN_DIR / group / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(normalized_text(source, actual), encoding="utf-8", newline="\n")

    input_checksums = {
        str(path.relative_to(FIXTURE_DIR)).replace("\\", "/"): sha256(path)
        for path in sorted((FIXTURE_DIR / "inputs").rglob("*"))
        if path.is_file()
    }
    output_checksums = {
        str(path.relative_to(GOLDEN_DIR)).replace("\\", "/"): sha256(path)
        for path in sorted(GOLDEN_DIR.rglob("*"))
        if path.is_file()
    }
    safe_repository = REPO_ROOT.as_posix()
    manifest = {
        "schema_version": "1.0",
        "type": "legacy_integrative_baseline",
        "id": "integrative.legacy.characterization.v1",
        "status": "complete",
        "repository_commit": command_output(["git", "-c", f"safe.directory={safe_repository}", "rev-parse", "HEAD"]),
        "legacy_source_commit": command_output(
            ["git", "-c", f"safe.directory={safe_repository}", "log", "-1", "--format=%H", "--", "pipelines/integrative/legacy"]
        ),
        "commands": COMMANDS,
        "visualization": {
            "executed": False,
            "reason": "R is present but ggplot2 is unavailable; no dependency chain was installed.",
            "equivalence": "VISUAL_NOT_REGRESSION_CRITICAL",
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "r": command_output(["Rscript", "-e", "cat(R.version.string)"]),
            "ggplot2": command_output(["Rscript", "-e", "cat(as.character(packageVersion('ggplot2')))"]),
        },
        "parameters": {
            "DEG_PADJ_THRESHOLD": 0.05,
            "DEG_LOG2FC_THRESHOLD": 1,
            "DIFF_BINDING_PADJ_THRESHOLD": 0.05,
            "DIFF_BINDING_LOG2FC_THRESHOLD": 1,
            "PEAK_GENE_WINDOW_BP": 5000,
            "PROMOTER_UPSTREAM_BP": 2000,
            "PROMOTER_DOWNSTREAM_BP": 500,
            "TOP_CANDIDATES_N": 4,
        },
        "input_checksums": input_checksums,
        "golden_checksums": output_checksums,
    }
    (BASE_DIR / "baseline_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checksum_lines = [f"{digest}  {path}" for path, digest in sorted(output_checksums.items())]
    (BASE_DIR / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(output_checksums)} golden artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
