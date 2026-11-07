"""Run the test suite and annotate failures for the GitHub Actions UI.

The normal unittest output remains available in the job log. The extra
``::error`` lines make the failing test ID visible even when the raw Windows
job log is not accessible to the person reviewing the run.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


class AnnotatingResult(unittest.TextTestResult):
    def _annotate(self, kind: str, test: unittest.TestCase, err: tuple) -> None:
        trace = "".join(traceback.format_exception(*err)).strip()
        detail = trace.splitlines()[-1] if trace else kind
        print(
            f"::error title={_escape(test.id())}::{_escape(f'{test.id()}: {detail[:900]}')}",
            flush=True,
        )

    def addFailure(self, test: unittest.TestCase, err: tuple) -> None:
        super().addFailure(test, err)
        self._annotate("failure", test, err)

    def addError(self, test: unittest.TestCase, err: tuple) -> None:
        super().addError(test, err)
        self._annotate("error", test, err)


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    runner = unittest.TextTestRunner(verbosity=2, resultclass=AnnotatingResult)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
