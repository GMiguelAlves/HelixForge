#!/usr/bin/env python3
"""Validate the real reduced IDR provider execution."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


EXPECTED_DIGEST = "sha256:d6fb2a7eb69bb236278562d08fcd0b62bfbe2e887d330111c6aea1e42cb26caa"


def require(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise AssertionError(f"missing or empty artifact: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifests = sorted(root.glob("results/chipseq/consensus/*/*.idr_result/manifest.json"))
    if len(manifests) != 1:
        raise AssertionError(f"expected one IDR manifest, found {len(manifests)}")
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["type"] == manifest["strategy"] == manifest["provider"] == "idr"
    assert manifest["provider_version"] == "2.0.4.2"
    assert manifest["status"] == "complete"
    assert manifest["parameters"]["rank_metric"] == "signal_value"
    assert float(manifest["parameters"]["idr_threshold"]) == 0.05
    assert len(manifest["replicates"]) == 2
    assert manifest["statistics"]["consolidated_peaks"] > 0

    checked = {}
    for role in ("consolidated_peaks", "consolidated_bed", "idr_output", "replicate_evidence", "statistics"):
        artifact = manifest["artifacts"][role]
        assert artifact["available"] is True
        path = require(manifest_path.parent / artifact["path"])
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        assert observed == artifact["sha256"]
        checked[role] = observed

    with require(manifest_path.parent / "consolidated_peaks.tsv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == manifest["statistics"]["consolidated_peaks"]
    assert all(0.0 <= float(row["global_idr"]) <= 0.05 for row in rows)

    digest_text = require(root / "image_digest.txt").read_text(encoding="utf-8").strip()
    assert EXPECTED_DIGEST in digest_text
    certification = {
        "schema_version": "1.0",
        "type": "idr_container_certification",
        "provider": "idr",
        "provider_version": "2.0.4.2",
        "image_digest": EXPECTED_DIGEST,
        "consolidated_peaks": len(rows),
        "artifacts": checked,
        "status": "pass",
    }
    (root / "certification.json").write_text(
        json.dumps(certification, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
