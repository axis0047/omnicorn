import functools
import os
import sys
import traceback


def let_it_crash(exceptions=(Exception,), log=True):
    """Forces an OS exit on unrecoverable errors, relying on Erlang to respawn."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log:
                    sys.stderr.write(
                        f"\n💥[Omnicorn] {func.__name__} fatal error: {e}\n"
                    )
                    sys.stderr.write(
                        f"🛡️ Triggering OS Process Death. Omnicorn will respawn process instantly.\n"
                    )
                    traceback.print_exc(file=sys.stderr)
                os._exit(1)

        return wrapper

    return decorator
