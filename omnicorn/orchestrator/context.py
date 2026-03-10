class Context:
    """Deterministic snapshot passed to workflow functions from Erlang."""

    def __init__(self, workflow_id, step, state_data):
        self.workflow_id = workflow_id
        self.step = step.decode("utf-8") if isinstance(step, bytes) else step
        self.data = state_data if state_data else {}

    def checkpoint(self, next_step: str, sleep_ms: int = 0):
        """Instructs Erlang to snapshot Mnesia state and optionally hibernate."""
        return {
            b"type": b"workflow_checkpoint",
            b"workflow_id": self.workflow_id,
            b"next_step": next_step.encode("utf-8"),
            b"sleep_ms": sleep_ms,
            b"data": self.data,
        }

    def finish(self):
        return self.checkpoint("__finished__", 0)
