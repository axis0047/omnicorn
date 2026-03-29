def _decode_bytes(obj):
    """Recursively converts ETF bytes back to Python strings."""
    if isinstance(obj, bytes):
        return obj.decode("utf-8")
    elif isinstance(obj, dict):
        return {_decode_bytes(k): _decode_bytes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_decode_bytes(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(_decode_bytes(x) for x in obj)
    return obj


class Context:
    def __init__(self, workflow_id, step, state_data):
        self.workflow_id = _decode_bytes(workflow_id)
        self.step = _decode_bytes(step)

        # 🔥 FIX: Decode ETF dictionaries so users can use string keys
        self.data = _decode_bytes(state_data) if state_data else {}

    # 🔥 FIX: Added days/seconds support to match your Markdown spec
    def checkpoint(
        self,
        next_step: str,
        sleep_ms: int = 0,
        sleep_seconds: int = 0,
        sleep_days: int = 0,
    ):
        total_sleep_ms = sleep_ms + (sleep_seconds * 1000) + (sleep_days * 86400000)

        return {
            b"type": b"workflow_checkpoint",
            b"workflow_id": self.workflow_id.encode("utf-8")
            if isinstance(self.workflow_id, str)
            else self.workflow_id,
            b"next_step": next_step.encode("utf-8")
            if isinstance(next_step, str)
            else next_step,
            b"sleep_ms": total_sleep_ms,
            b"data": self.data,
        }

    def finish(self):
        return self.checkpoint("__finished__")
