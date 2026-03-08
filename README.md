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

<b>Omnicorn is the lord of *corn</b>

Omnicorn is an experimental(not very, a lot of people have probably done this, but i couldn't find anything like this) Python ASGI/WSGI webserver + toolkit that is written in erlang. The idea is treating each ASGI or WSGI worker as an erlang processes and supervising and managing them with OTP functionalities and tools. What this is trying to solve is unplanned chaos that a system encounters when coupled with large scale complex systems. Existing servers like Gunicorn, Uvicorn or uWSGI or even Hypercone is built for the performance and handling known runtime errors and scenarios, with try except or in similar manner. But in my opinion and experience they lack the stability when it comes to the issues that originated from chaos and randomness of large scale or high throughput systems. For example droping tcp connections or app fully crashing on unexpected high load or unplanned network latency that makes tasks to run out of sync and enter into a crashloop.

On the other hand, Erlang/OTP is built exactly for handling those chaotic scenarios and be highly available and massively scalable.As they say, every cloud service is a bad and incomplete implementation of Erlang/OTP. Erlang/OTP is that good.Python may never achieve that level of scalability, but trying to borrow that super powers from erlang/OTP is an endeavour worth taking.

This current implementation (release/dev branch, currently default branch, may change in feature) is the very minimum basic proof of concept implementation of the previously discussed concept. This currently has WSGI and ASGI support (support that is enough to run an app).
Websocket support, Basic idempotency caching, Background tasks, and task recovery (task storages to recover tasks, both volatile and persistent tasks). On top of those features, omnicorn tries to utilise Erlang/OTP supervision for instant recovery and high availability. (same as server support, these features are just barely working) I tested this mainly with flask and fastapi it and worked okay. Please refer the below guide for installation and usage. 

Also note that this is very unstable and has almost zero test coverage and has AI slop too.

---

## Installation
- Clone this repository
- You need Python3, Erlang and rebar3 to build this from source.
```bash
sudo apt update && sudo apt install python3 erlang rebar3 python3-pip
```
- Inside the repository run this command to build the wheel
```bash
pip install .
```
- Omnicorn should build now, and you may build this inside your projects venv for ease, I haven't test other scenarios much. Standard pip ways should work.

## How to run a server with this
- This currently offers a minimal config system using a yaml file, please refer following format. You may add this inside your project root.
```yaml
server:
  port: 9090
  host: "0.0.0.0"

workers:
  count: 8  #Worker thread count, will run 2*cpu_count otherwise
  max_restarts: 5000  # Allow 5000 crashes
  restart_period: 60  # per minute
  timeout: 10000  # Waits 10 seconds before killing and respawning the thread

upstream:
  app_path: "your_app:app" #Same as other servers
  mode: "auto"  #wsgi, asgi or auto
```
- Run the app with following command, omnicorn.yaml is your yaml config file
```bash
omnicorn --config omnicorn.yaml
```

- This currently has few wrappers. View __init__.py for them. (let_it_crash and task)

- Also note that the execution time maybe higher than other servers, for me it didn't show any noticable differences (for now)

edit - I tested and this is a little faster than gunicorn, i guess it is mainly due to not having serialization load.

---

## What is on the way
- Stable release
- All other regular python webserver functionalities (dev server, hot reload)
- Cache system and background workers system utilizing erlang/OTP ETS and process handling features. (currently has basic implementations, will work on them, need to learn more)
- Toolkit for orchestration (set of decorators) that wraps python functions to supervise and manage them with OTP tools (basic implementation done, barely works)
- Supervision tree hierachy resolver (So Python developer can use decorators where he need, and not think about that he wrapped outer function with totaly opposite behaviour.)
- Runtime code changes (Does anyone need that for Python?)
- Intelligent (Not LLM) supervision based on situated AI and free energy principle (or something more suitable and in-between). (This is a real experimental end goal, most probably wont make upto here.)

---
