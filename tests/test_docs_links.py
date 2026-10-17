"""Documentation checks must inspect real targets even below runner/work."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('check_docs', ROOT / 'bin/check_docs.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class DocumentationLinksTest(unittest.TestCase):
    def test_assay_overviews_are_linked_symmetrically(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        index = (ROOT / 'docs/index.md').read_text(encoding='utf-8')
        for assay in ('rnaseq', 'chipseq'):
            page = ROOT / f'docs/api/{assay}-api.md'
            self.assertTrue(page.is_file(), assay)
            self.assertIn(f'](docs/api/{assay}-api.md)', readme)
            self.assertIn(f'](api/{assay}-api.md)', index)
            architecture = (ROOT / f'docs/architecture/{assay}-architecture.md').read_text(encoding='utf-8')
            self.assertIn(f'](../api/{assay}-api.md)', architecture)

    def test_overviews_link_to_each_other_and_shared_alignment(self):
        for assay, other in (('rnaseq', 'chipseq'), ('chipseq', 'rnaseq')):
            content = (ROOT / f'docs/api/{assay}-api.md').read_text(encoding='utf-8')
            self.assertIn(f']({other}-api.md)', content)
            self.assertIn('](alignment_api.md)', content)

    def test_checkout_below_work_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'work' / 'checkout'
            (root / 'docs').mkdir(parents=True)
            (root / 'README.md').write_text('[Guide](docs/guide.md)\n')
            (root / 'docs/guide.md').write_text('# Guide\n')
            checked, failures = CHECK.check_links(root)
            self.assertEqual(1, checked)
            self.assertEqual([], failures)

    def test_missing_target_is_reported_below_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'work' / 'checkout'
            root.mkdir(parents=True)
            (root / 'README.md').write_text('[Missing](docs/missing.md)\n')
            checked, failures = CHECK.check_links(root)
            self.assertEqual(1, checked)
            self.assertEqual(['README.md:1: docs/missing.md -> missing'], failures)

    def test_generated_directories_inside_checkout_are_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'README.md').write_text('[Self](README.md)\n')
            for name in ('work', 'results', '.codex_tmp', '.codex_worktrees', 'node_modules'):
                (root / name).mkdir()
                (root / name / 'generated.md').write_text('[Missing](missing.md)\n')
            self.assertEqual((1, []), CHECK.check_links(root))

    def test_zero_checked_links_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'README.md').write_text('[External](https://example.org)\n')
            checked, failures = CHECK.check_links(root)
            self.assertEqual(0, checked)
            self.assertIn('No local Markdown links were checked', failures)
