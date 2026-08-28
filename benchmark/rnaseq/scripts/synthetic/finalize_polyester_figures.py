#!/usr/bin/env python3
"""Write checksums and provenance for rendered Polyester benchmark figures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("figure finalization must execute inside a Slurm job")
    expected = [args.output_dir / f"figure_{number}_{name}.{extension}"
                for number, name in (
                    (1, "gene_abundance"),
                    (2, "transcript_quantification"),
                    (3, "log2fc_recovery"),
                    (4, "precision_recall"),
                    (5, "reproducibility"),
                    (6, "performance"),
                ) for extension in ("png", "pdf")]
    missing = [str(path) for path in expected if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise SystemExit("missing rendered figures: " + ", ".join(missing))
    manifest = {
        "schema_version": "1.0",
        "status": "pass",
        "subject": {"tag": "v1.0.0-rc.1", "commit": "fc38ada8f592bb57a13467965a718ce0df7fb6ce"},
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "files": [{"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)} for path in expected],
    }
    (args.output_dir / "figures_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "pass", "files": len(expected)}))


if __name__ == "__main__":
    main()
