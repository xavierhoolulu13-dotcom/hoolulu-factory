"""The offline brain.

``provider`` talks to llama.cpp's OpenAI-compatible endpoint.
``runtime`` knows how to find the binary and the model files.
``bridge`` decides, per call, whether the model answers or the deterministic
fallback does — and always records which one it was.
"""

from .provider import (  # noqa: F401
    OfflineModelUnavailable,
    health,
    complete,
    json_complete,
)
from . import runtime  # noqa: F401
from .bridge import think_json, status_line, provenance, available  # noqa: F401
