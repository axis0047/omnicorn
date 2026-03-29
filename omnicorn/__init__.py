"""
Omnicorn - Erlang/OTP Distributed Application Server

A production-grade, distributed Python application server powered by Erlang/OTP.
"""

__version__ = "1.0.0.dev0"
__author__ = "axis0047"
__email__ = "origin@axis.codes"

# Cache API
from .cache import delete, get, incr, set
from .orchestrator.activities import activity, defer_activity
from .orchestrator.context import Context

# Workflow orchestration
from .orchestrator.sagas import orchestrator, start_workflow

# Fault tolerance
from .supervision import let_it_crash

__all__ = [
    # Version
    "__version__",
    # Cache
    "get",
    "set",
    "delete",
    "incr",
    # Workflow orchestration
    "orchestrator",
    "start_workflow",
    "activity",
    "defer_activity",
    "Context",
    # Fault tolerance
    "let_it_crash",
]
