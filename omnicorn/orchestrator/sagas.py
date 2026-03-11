import sys
import traceback

from .context import Context

ORCHESTRATOR_REGISTRY = {}


def orchestrator(name: str):
    """Registers a stateful workflow backed by Erlang Actors."""

    def decorator(func):
        ORCHESTRATOR_REGISTRY[name.encode("utf-8")] = func
        return func

    return decorator


async def start_workflow(name: str, workflow_id: str, init_data: dict = None):
    """Triggers an Erlang Workflow Actor from Python."""
    from ..cache import _rpc_call

    return await _rpc_call(
        b"workflow_start",
        {
            b"name": name.encode("utf-8"),
            b"workflow_id": workflow_id.encode("utf-8"),
            b"data": init_data or {},  # REMOVED double-packing!
        },
    )


async def execute_workflow_step(msg: dict, transport):
    """Called by worker.py when an Erlang Actor resumes a saga."""
    payload = msg.get(b"payload", {})
    w_name = payload.get(b"name")
    w_id = payload.get(b"workflow_id")
    step = payload.get(b"step")

    # Data is already natively unpacked by the Transport boundary!
    data = payload.get(b"data", {})

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
        safe_name = (
            w_name.decode("utf-8", "ignore")
            if isinstance(w_name, bytes)
            else str(w_name)
        )
        sys.stderr.write(f"Workflow {safe_name} Error: {traceback.format_exc()}\n")
        await transport.send(
            {
                b"type": b"workflow_error",
                b"workflow_id": w_id,
                b"error": str(e).encode("utf-8"),
            }
        )
