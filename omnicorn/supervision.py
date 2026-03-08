import os
import sys
import traceback
import functools

def let_it_crash(exceptions=(Exception,), log=True):
    """
    The Erlang Fault-Tolerance Wrapper.
    If the wrapped function encounters an unrecoverable state (like a broken TCP socket),
    it logs the error and immediately kills the Python OS process (os._exit(1)).

    The Omnicorn Erlang Supervisor will detect the port closure in microseconds
    and instantly respawn a fresh, clean worker with re-initialized connections.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log:
                    sys.stderr.write(f"\n💥 [Omnicorn Supervision] {func.__name__} encountered unrecoverable error: {e}\n")
                    sys.stderr.write(f"🛡️  Triggering OS Process Death. Erlang Supervisor will respawn instantly.\n")
                    traceback.print_exc(file=sys.stderr)

                # Force an abrupt exit. This bypasses Python's graceful shutdown,
                # releasing corrupted sockets and memory instantly to the OS.
                os._exit(1)
        return wrapper
    return decorator
