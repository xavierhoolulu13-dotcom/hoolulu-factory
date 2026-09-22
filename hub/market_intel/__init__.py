"""Market intelligence, offline first.

The hub's default answer comes from a local corpus: it is honest about being a
prior, not a measurement. When an operator turns on a network adapter in
``.env``, live findings are merged in and labelled as such. If an adapter is
configured but unreachable, that becomes a *gap* in the research contract —
never a fabricated finding.
"""

from .corpus import profile_for, DOMAINS  # noqa: F401
from . import adapters  # noqa: F401
from .research import research, format_research  # noqa: F401
