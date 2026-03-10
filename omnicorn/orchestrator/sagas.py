import sys
import traceback

import erlpack

from .context import Context

ORCHESTRATOR_REGISTRY = {}


def orchestrator(name: str):
    """Registers a stateful workflow backed by Erlang Actors."""

    def decorator(func):
        ORCHESTRATOR_REGISTRY[name.encode("utf-8")] = func
        return func

    return decorator


async def execute_workflow_step(msg: dict, transport):
    """Called by worker.py when an Erlang Actor resumes a saga."""
    payload = msg.get(b"payload", {})
    w_name = payload.get(b"name")
    w_id = payload.get(b"workflow_id")
    step = payload.get(b"step")
    data = erlpack.unpack(payload.get(b"data", b"")) if payload.get(b"data") else {}

    func = ORCHESTRATOR_REGISTRY.get(w_name)
    if not func:
        return await transport.send(
            {
                b"type": b"workflow_error",
                b"workflow_id": w_id,
                b"error": b"Saga Not Found",
            }
        )

    ctx = Context(w_id, step, data)
    try:
        # Execute the python function. It MUST return ctx.checkpoint()
        cmd = await func(ctx)
        await transport.send(cmd)
    except Exception as e:
        sys.stderr.write(f"Workflow {w_name} Error: {traceback.format_exc()}\n")
        await transport.send(
            {
                b"type": b"workflow_error",
                b"workflow_id": w_id,
                b"error": str(e).encode("utf-8"),
            }
        )
