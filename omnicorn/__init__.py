__version__ = "1.2.0"

# 1. The Bridge-ETS Cache
from .cache import get, set, delete, incr

# 2. The Task Broker (ETS + Mnesia)
from .tasks import task

# 3. Fault Tolerance & Supervision
from .supervision import let_it_crash
