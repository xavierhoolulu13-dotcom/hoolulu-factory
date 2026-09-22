"""Commercial reasoning: is this worth building, and will anyone pay?"""

from .productizer import (  # noqa: F401
    build_spec, parse_request, slugify, format_spec,
)
from .gap_engine import analyze, format_gaps  # noqa: F401
from . import evidence  # noqa: F401
