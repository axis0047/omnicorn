# Omnicorn

## 🗿🌽 ඔම්නිකෝර්න් - The Universal Corn That Controls Everything

**A production-grade, distributed Python application server powered by Erlang/OTP**

---

## 🚀 Features

- **WSGI + ASGI Support** - Run Flask, Django, FastAPI, and any Python web framework
- **Erlang/OTP Reliability** - Fault-tolerant supervision trees and process isolation
- **Distributed Cache** - High-performance ETS-backed caching with TTL support
- **Workflow Orchestration** - Temporal-like durable workflows with state persistence
- **Background Activities** - Retryable background tasks with dead-letter queue
- **WebSocket Support** - Full-duplex real-time communication
- **Multi-Node Clustering** - Experimental distributed deployment (v1.0+)

---

## ⚡ Quick Start

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

### Basic Usage

**1. Create a FastAPI app (`app.py`):**

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello from Omnicorn!"}
```

**2. Create a config file (`omnicorn.yaml`):**

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

**3. Run the server:**

```bash
omnicorn app:app --config omnicorn.yaml
```

---

## 📚 Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) - Development setup and contribution guidelines
- [ROADMAP.md](ROADMAP.md) - Development roadmap and planned features
- [CHANGELOG.md](CHANGELOG.md) - Version history

---

## 🏗️ Architecture

Omnicorn uses a hybrid Python-Erlang architecture:

```
Client Requests → Cowboy (Erlang) → Worker Pool → Python Workers (WSGI/ASGI)
                       ↓
                ETS Cache + Mnesia (State Persistence)
                       ↓
                Workflow Orchestrator (gen_statem)
```

### Core Components

| Component   | Technology                | Purpose                          |
| ----------- | ------------------------- | -------------------------------- |
| Web Server  | Cowboy (Erlang)           | HTTP/WebSocket handling          |
| Worker Pool | gen_server                | Dynamic Python worker management |
| Cache       | ETS tables                | In-memory distributed caching    |
| Workflows   | gen_statem                | Stateful orchestration           |
| Activities  | Mnesia + gen_server       | Background task queue            |
| IPC         | Unix Domain Sockets + ETF | Python↔Erlang communication      |

---

## 🎯 Use Cases

### 1. Drop-in Replacement for Gunicorn/uWSGI

```bash
# Instead of gunicorn
gunicorn myapp:app

# Use omnicorn
omnicorn myapp:app
```

### 2. Distributed Workflow Orchestration

```python
from omnicorn import orchestrator, activity, defer_activity

@activity(name="send_email")
async def send_email(to, subject, body):
    pass

@orchestrator(name="user_onboarding")
async def onboarding_workflow(ctx):
    if ctx.step == "welcome":
        await defer_activity("send_email",
                           to=ctx.data["email"],
                           subject="Welcome!")
        return ctx.checkpoint("setup", sleep_days=1)
    elif ctx.step == "setup":
        return ctx.finish()
```

### 3. High-Performance Caching

```python
from omnicorn import cache

await cache.set("user:123", {"name": "John"})
user = await cache.get("user:123")

# With TTL
await cache.set("session:abc", data, ttl_ms=3600000)
```

---

## 🔧 Configuration

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

cache:
  max_entries: 10000
  default_ttl_ms: 3600000

logging:
  level: "info"
  format: "text"
```

---

## 🧪 Testing

```bash
# Run all tests
./scripts/test.sh

# Python tests only
pytest tests/ -v --cov=omnicorn

# Erlang tests only
cd omnicorn/erl_src && rebar3 eunit
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

### Quick Start

```bash
git clone https://github.com/axis0047/omnicorn.git
cd omnicorn
pip install -e ".[dev]"
./scripts/build.sh
./scripts/test.sh
```

### Branch Strategy

- `release/stable` - Production releases
- `dev/stable` - Current release integration
- `dev/stable-phase-X` - Feature development

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
