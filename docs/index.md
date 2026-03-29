# Omnicorn Documentation

Welcome to the Omnicorn documentation.

## Getting Started

### Installation

```bash
# Prerequisites
# - Python 3.9+
# - Erlang/OTP 25+
# - rebar3 3.20+

# Install from source
git clone https://github.com/axis0047/omnicorn.git
cd omnicorn
pip install -e .
```

### Quick Start

1. **Create an application** (`app.py`):

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

2. **Create a config** (`omnicorn.yaml`):

```yaml
server:
  port: 8080

workers:
  count: 4
  timeout: 30000

upstream:
  app_path: "app:app"
  mode: "auto"
```

3. **Run the server**:

```bash
omnicorn app:app --config omnicorn.yaml
```

## Core Concepts

### Architecture

Omnicorn uses a hybrid Python-Erlang architecture:

- **Erlang/OTP** handles HTTP server, process supervision, and distributed state
- **Python workers** run your WSGI/ASGI applications
- **Unix Domain Sockets** provide fast IPC between Erlang and Python
- **Erlang Term Format (ETF)** enables efficient serialization

### Components

| Component                 | Description                      |
| ------------------------- | -------------------------------- |
| **Cowboy**                | Erlang HTTP/WebSocket server     |
| **Worker Pool**           | Dynamic Python worker management |
| **ETS Cache**             | In-memory distributed caching    |
| **Workflow Orchestrator** | Stateful workflow execution      |
| **Activity Queue**        | Background task processing       |

## API Reference

### Cache API

```python
from omnicorn import cache

# Set a value
await cache.set("key", "value")

# Set with TTL (1 hour)
await cache.set("key", "value", ttl_ms=3600000)

# Get a value
value = await cache.get("key")

# Delete a value
await cache.delete("key")

# Atomic increment
count = await cache.incr("counter")
```

### Workflow Orchestration

```python
from omnicorn import orchestrator, activity, defer_activity, start_workflow

# Define an activity
@activity(name="send_email", retries=3)
async def send_email(to, subject, body):
    # Send email logic
    pass

# Define a workflow
@orchestrator(name="user_onboarding")
async def onboarding_workflow(ctx):
    if ctx.step == "welcome":
        await defer_activity("send_email",
                           to=ctx.data["email"],
                           subject="Welcome!")
        return ctx.checkpoint("setup", sleep_days=1)
    elif ctx.step == "setup":
        return ctx.finish()

# Start a workflow
await start_workflow("user_onboarding", "user_123",
                    {"email": "user@example.com"})
```

### Context API

```python
from omnicorn import Context

# Create context (usually done internally)
ctx = Context(workflow_id, step, data)

# Checkpoint to next step
return ctx.checkpoint("next_step", sleep_ms=1000)

# Checkpoint with sleep variants
return ctx.checkpoint("next_step", sleep_seconds=5)
return ctx.checkpoint("next_step", sleep_days=1)

# Finish workflow
return ctx.finish()
```

### Fault Tolerance

```python
from omnicorn import let_it_crash

@let_it_crash()
def critical_operation():
    # If this raises an exception, the process will be restarted
    pass
```

## Configuration

### Basic Configuration

```yaml
server:
  port: 8080
  socket: "127.0.0.1:8080"

workers:
  count: 4
  timeout: 30000

upstream:
  app_path: "myapp:app"
  mode: "auto"
```

### Cache Configuration

```yaml
cache:
  max_entries: 10000
  default_ttl_ms: 3600000
```

### Orchestrator Configuration

```yaml
orchestrator:
  max_concurrent_workflows: 100
  activity_retry_count: 3
  activity_retry_delay_ms: 5000
```

### Logging Configuration

```yaml
logging:
  level: "info" # debug, info, warning, error
  format: "text" # text or json
```

## Examples

See the `examples/` directory for complete examples:

- `fastapi_app.py` - FastAPI application
- `flask_app.py` - Flask application
- `workflow_example.py` - Workflow orchestration
- `activity_example.py` - Background activities

## Testing

```bash
# Run all tests
./scripts/test.sh

# Python tests only
pytest tests/ -v --cov=omnicorn

# Erlang tests only
cd omnicorn/erl_src && rebar3 eunit
```

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup and guidelines.

## Troubleshooting

### Common Issues

**Erlang backend not found**

```bash
./scripts/build.sh
```

**Port already in use**

```bash
# Change port in config or use --port option
omnicorn app:app --port 8081
```

**Worker timeout**

```yaml
# Increase timeout in config
workers:
  timeout: 60000 # 60 seconds
```

## Support

- **GitHub Issues**: [Report bugs](https://github.com/axis0047/omnicorn/issues)
- **Discussions**: [Ask questions](https://github.com/axis0047/omnicorn/discussions)
