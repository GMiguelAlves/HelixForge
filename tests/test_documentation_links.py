"""Keep the repository documentation navigable after file moves."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^\s)]+)")


class DocumentationLinks(unittest.TestCase):
    def test_local_markdown_links_exist(self) -> None:
        pages = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
        missing: list[str] = []
        for page in pages:
            text = page.read_text(encoding="utf-8")
            for raw in LINK.findall(text):
                if raw.startswith(("http:", "https:", "mailto:", "data:", "#", "/", "<")):
                    continue
                path = unquote(raw.split("#", 1)[0].split("?", 1)[0])
                if not path:
                    continue
                target = (page.parent / path).resolve()
                if not target.is_relative_to(ROOT) or not target.exists():
                    missing.append(f"{page.relative_to(ROOT)} -> {raw}")
        self.assertEqual([], missing)

    def test_index_reaches_every_document(self) -> None:
        index = ROOT / "docs/index.md"
        linked = {
            (index.parent / unquote(raw.split("#", 1)[0])).resolve()
            for raw in LINK.findall(index.read_text(encoding="utf-8"))
            if not raw.startswith(("http:", "https:", "mailto:", "data:", "#", "/", "<"))
        }
        documents = set((ROOT / "docs").rglob("*.md")) - {index}
        self.assertEqual(documents, linked)


if __name__ == "__main__":
    unittest.main()
