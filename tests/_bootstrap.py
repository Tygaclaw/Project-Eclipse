"""Make the ``src`` layout importable when tests run without ``PYTHONPATH``.

CI normally sets ``PYTHONPATH=src``. The autonomous controller's child
environment is an allowlist that intentionally does not inherit an arbitrary
``PYTHONPATH``, so the portable suite must still locate ``eclipse`` when it is
invoked directly. Importing this module adds the repository's ``src``
directory to ``sys.path`` exactly once.
"""

from __future__ import annotations

from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))