# omnicorn
*One corn to rule them all,  
One corn to find them all,  
One corn to bring them all  
and in the darkness bind them  
In the land of Scale  
where the chaos lie...*
### 🗿🌽 ඔම්නිකෝර්න් - සියල්ල පාලනය කරන තනි ඉරිඟුව
(Don't ask me to change this. I won't)

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
## Notice

This project has a lot of AI generated code, I am currently reading and documenting them my self, latter part of this README.md is also AI generated. How I built this was incrementally improving my minimal implementation of this idea with AI. So my original code is basically now extinct from current version, like some old wood from Thesius's ship. I myself dislike the idea of using AI to create project beyond some minimal prototype, but given the limited time and limites skills, I used AI till this stage. It's better to have working slop instead of having non functional elegance. But before stable release, I will read and review every line, unit and will risk my projects to test this. Writting AI code is pretty frtustating BTW. But AI writes better code than me. damn shame

Even this is created to solve real pain point I encounter at my job, I consider this as a learning proejct basically. What is to learn from an AI generated project. basically I learnt nothing. I guess that how 2026 works. 

---

<b>Omnicorn is the lord of *corn</b>

Omnicorn is an experimental(not very, a lot of people have probably done this, but i couldn't find anything like this) Python ASGI/WSGI webserver + toolkit that is written in erlang. The idea is treating each ASGI or WSGI worker as an erlang processes and supervising and managing them with OTP functionalities and tools. What this is trying to solve is unplanned chaos that a system encounters when coupled with large scale complex systems. Existing servers like Gunicorn, Uvicorn or uWSGI or even Hypercone is built for the performance and handling known runtime errors and scenarios, with try except or in similar manner. But in my opinion and experience they lack the stability when it comes to the issues that originated from chaos and randomness of large scale or high throughput systems. For example droping tcp connections or app fully crashing on unexpected high load or unplanned network latency that makes tasks to run out of sync and enter into a crashloop.

On the other hand, Erlang/OTP is built exactly for handling those chaotic scenarios and be highly available and massively scalable.As they say, every cloud service is a bad and incomplete implementation of Erlang/OTP. Erlang/OTP is that good.Python may never achieve that level of scalability, but trying to borrow that super powers from erlang/OTP is an endeavour worth taking.

This current implementation (dev/stable branch, currently default branch, will be changed in feature) is the a feature-full, yet unstable implementation of the previously discussed concept. This currently has WSGI and ASGI support (support that is enough to run an app).
Websocket support, Basic idempotency caching, Background tasks, and task recovery (task storages to recover tasks, both volatile and persistent tasks). On top of those features, omnicorn tries to utilise Erlang/OTP supervision for instant recovery and high availability. (same as server support, these features are just still unstable and not fully tested) I tested this mainly with flask and fastapi it and worked okay. Please refer the below guide for installation and usage. 

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
