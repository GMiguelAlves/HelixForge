#!/usr/bin/env python3
"""Fail when a repository Markdown link points to a missing local target."""

from __future__ import annotations

import re
import os
import sys
from pathlib import Path
from urllib.parse import unquote


LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SCHEMES = ("http://", "https://", "mailto:", "ftp://", "data:")


def local_target(document: Path, raw: str, root: Path) -> Path | None:
    value = raw.strip().split(maxsplit=1)[0].strip("<>")
    if not value or value.startswith("#") or value.startswith(SCHEMES):
        return None
    value = unquote(value.split("#", 1)[0].split("?", 1)[0])
    if not value or "{" in value or "}" in value:
        return None
    return (root / value.lstrip("/")) if value.startswith("/") else (document.parent / value)


def check_links(root: Path) -> tuple[int, list[str]]:
    failures: list[str] = []
    checked = 0
    documents = []
    ignored = {".git", ".nextflow", "work", "results", "node_modules",
               ".codex_tmp", ".codex_worktrees", ".venv", "venv"}
    # Only prune directories inside the checkout, never its absolute ancestors.
    for directory, children, filenames in os.walk(root):
        children[:] = sorted(child for child in children if child not in ignored)
        documents.extend(Path(directory) / name for name in filenames if name.endswith('.md'))
    for document in sorted(documents):
        text = document.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for raw in LINK.findall(line):
                target = local_target(document, raw, root)
                if target is None:
                    continue
                checked += 1
                if not target.exists():
                    failures.append(f"{document.relative_to(root)}:{line_number}: {raw} -> missing")
    if checked == 0:
        failures.append('No local Markdown links were checked')
    return checked, failures


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    checked, failures = check_links(root)
    if failures:
        print("Broken local Markdown links:")
        print("\n".join(failures))
        return 1
    print(f"Documentation links OK ({checked} local links checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
