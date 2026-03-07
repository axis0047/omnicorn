import functools

# Global registry for functions that can be called via RPC
RPC_REGISTRY = {}

def supervised_task(name=None):
    """
    Decorator to register a function for RPC calls from Erlang.
    """
    def decorator(func):
        key = name or func.__name__
        RPC_REGISTRY[key] = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

def get_task(name):
    return RPC_REGISTRY.get(name)
