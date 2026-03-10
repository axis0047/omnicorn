import asyncio
import sys
import traceback

import erlpack

from ..cache import _rpc_call

ACTIVITY_REGISTRY = {}


def activity(name=None, retries=3):
    """Registers a stateless background activity."""

    def decorator(func):
        n = (name or func.__name__).encode("utf-8")
        ACTIVITY_REGISTRY[n] = {"func": func, "retries": retries}
        return func

    return decorator


async def defer_activity(name: str, *args, **kwargs):
    """Enqueues an activity to the Erlang Mnesia Task Broker."""
    return await _rpc_call(
        b"activity_enqueue",
        {
            b"name": name.encode("utf-8"),
            b"args": erlpack.pack(args),
            b"kwargs": erlpack.pack(kwargs),
        },
    )


async def execute_activity(msg: dict, transport):
    payload = msg.get(b"payload", {})
    a_name = payload.get(b"name")
    a_id = payload.get(b"activity_id")

    args = erlpack.unpack(payload.get(b"args")) if b"args" in payload else ()
    kwargs = erlpack.unpack(payload.get(b"kwargs")) if b"kwargs" in payload else {}

    record = ACTIVITY_REGISTRY.get(a_name)
    if record:
        try:
            if asyncio.iscoroutinefunction(record["func"]):
                await record["func"](*args, **kwargs)
            else:
                await asyncio.to_thread(record["func"], *args, **kwargs)
            await transport.send({b"type": b"activity_ack", b"activity_id": a_id})
        except Exception as e:
            await transport.send(
                {
                    b"type": b"activity_fail",
                    b"activity_id": a_id,
                    b"error": str(e).encode("utf-8"),
                }
            )
