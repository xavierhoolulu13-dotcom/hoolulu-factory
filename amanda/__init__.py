"""Amanda — the operator interface to the Hoolulu Factory.

Say a sentence, get a product: researched, scoped, built, tested, packaged,
hosted and then watched. One command, one URL, every step recorded.

    python -m amanda "build me a snake game and host it"
    python -m amanda status
    python -m amanda maintain
"""

from __future__ import annotations

import sys
from pathlib import Path

# Amanda and the hub are sibling packages at the repository root. Running
# `python -m amanda` from anywhere puts the root on the path, so `import hub`
# resolves without the repo having to be pip-installed.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

__version__ = "0.1.0"
