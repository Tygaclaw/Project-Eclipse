from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ENV = (
    "PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
    "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR",
)


class PortableImportBootstrapTests(unittest.TestCase):
    def test_tests_import_eclipse_without_pythonpath(self) -> None:
        # Reproduce the controller's allowlisted environment, which deliberately
        # omits PYTHONPATH. The shared test bootstrap must still locate src/.
        env = {key: os.environ[key] for key in ALLOWED_ENV if key in os.environ}
        env["CI"] = "true"
        result = subprocess.run(
            [
                sys.executable, "-m", "unittest", "discover", "-s", "tests",
                "-p", "test_hardware.py", "-v",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            (result.stdout or "")[-2000:] + (result.stderr or "")[-2000:],
        )
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertIn("Ran ", result.stderr)
        self.assertIn("OK", result.stderr)


if __name__ == "__main__":
    unittest.main()