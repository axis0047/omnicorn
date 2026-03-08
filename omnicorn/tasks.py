import asyncio
import erlpack
from .cache import _rpc_call

# Global registry of background tasks
TASK_REGISTRY = {}

class Task:
    def __init__(self, func, name, persistent, retries):
        self.func = func
        self.name = name
        self.persistent = persistent
        self.retries = retries
        TASK_REGISTRY[name] = self

    async def defer(self, *args, **kwargs):
        """Pushes the task into the Erlang VM (Mnesia or ETS)."""
        payload = {
            b'name': self.name.encode('utf-8'),
            b'args': erlpack.pack(args),
            b'kwargs': erlpack.pack(kwargs),
            b'persistent': self.persistent,
            b'retries': self.retries
        }
        # We reuse the ultra-fast UDS RPC channel
        return await _rpc_call(b'task_enqueue', payload)

def task(name=None, persistent=False, retries=3):
    """
    Decorator to register a background task.
    If persistent=True, Erlang writes it to disk (Mnesia) to survive server crashes.
    """
    def decorator(func):
        t_name = name or func.__name__
        return Task(func, t_name, persistent, retries)
    return decorator
