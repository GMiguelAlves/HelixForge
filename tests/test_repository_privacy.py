#!/usr/bin/env python3

"""Repository-level safeguards against publishing personal runtime paths."""

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLASH = bytes((47,))
HOME_PREFIX = SLASH + b"home" + SLASH
SCRATCH_PREFIX = SLASH + b"scratch" + SLASH
ALLOWED_HOME_COMPONENTS = {b"CLUSTER_USER"}
ALLOWED_SCRATCH_COMPONENTS = {b"HELIXFORGE_WORKSPACE", b"my_user"}
PLACEHOLDER_PREFIXES = (b"$", b"{", b"<", b"[", b"(")
WINDOWS_USER_HOME = re.compile(
    rb"[A-Za-z]:[\\/]+Users[\\/]+(?!LOCAL_USER(?:[\\/]|$))[^\\/\s\"']+",
    re.IGNORECASE,
)


def tracked_files():
    output = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files", "-z"],
        cwd=ROOT,
    )
    for raw_path in output.split(b"\0"):
        if raw_path:
            yield ROOT / raw_path.decode("utf-8", errors="surrogateescape")


def path_components_after(data, prefix):
    start = 0
    while True:
        position = data.find(prefix, start)
        if position < 0:
            return
        component_start = position + len(prefix)
        component_end = component_start
        while component_end < len(data):
            if data[component_end] in b"/\\\r\n\t \"'`":
                break
            component_end += 1
        yield data[component_start:component_end]
        start = component_start


class RepositoryPrivacyTest(unittest.TestCase):
    def test_tracked_files_do_not_expose_personal_runtime_paths(self):
        violations = []

        for path in tracked_files():
            data = path.read_bytes()
            relative_path = path.relative_to(ROOT).as_posix()

            if WINDOWS_USER_HOME.search(data):
                violations.append(f"{relative_path}: personal Windows home")

            for component in path_components_after(data, HOME_PREFIX):
                if (
                    component
                    and component not in ALLOWED_HOME_COMPONENTS
                    and not component.startswith(PLACEHOLDER_PREFIXES)
                    and b"@" in component
                ):
                    violations.append(f"{relative_path}: personal cluster home")

            for component in path_components_after(data, SCRATCH_PREFIX):
                if (
                    component
                    and component not in ALLOWED_SCRATCH_COMPONENTS
                    and not component.startswith(PLACEHOLDER_PREFIXES)
                ):
                    violations.append(f"{relative_path}: unredacted scratch workspace")

        self.assertEqual(
            [],
            violations,
            "Tracked files contain personal runtime paths:\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
