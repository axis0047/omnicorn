# omnicorn
*One corn to rule them all,*
*One corn to find them all,*
*One corn to bring them all*
*and in the darkness bind them*
*In the land of scalaability*
*where the chaos lie...*
### 🗿🌽 ඔම්නිකෝර්න් - සියලු දේ පාලනය කලහැකි තනි ඉරිඟුව
---
Omnicorn is a experimental(not very, a lot of people have probably done this, but i couldn't find anything like this) Python ASGI/WSGI webserver + toolkit that is written in erlang. The idea is treating each ASGI or WSGI worker as an erlang processes and supervising and managing them with OTP functionalities and tools. What this is trying to solve is unplanned chaos that a system encounters when coupled with large scale complex systems. Existing servers like Gunicorn, Uvicorn or uWSGI or even Hypercone is built for the performance and handling known runtime or production errors, with try except or in similar patterns. But in my opinion and experience they lack the stability when it comes to the issues that originated from chaos and randomness of large scale or high throughput systems. For example droping tcp connections or app fully crashing on higher load or unplanned network latency that makes tasks to run out of sync and enter into a crashloop. Erlang/OTP is built exactly for handling those chaotic scenarios and be highly available and massively scalable. Python may never achieve that level of scalability, but trying to borrow that super power from erlang/OTP is a endeavour worth taking.

This current implementation (release/dev branch, currently default branch, may change in feature) is the very minimum basic proof of concept implementation of the previously discussed concept. This currently has WSGI and ASGI support (support that is enough to run a app). I tested this mainly with flask and worked okay. Please refer the below guide to installation and usage.

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
- Omnicorn should build now, and you may build this inside your projects venv for ease, I haven't test other scenarios much.

## How to run a server with this
- This currently offer a minimal config system using a yaml file, please refer following format. You may add this inside your project root.
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
```
- Run the app with following command, omnicorn.yaml is your yaml config file
```bash
omnicorn --config omnicorn.yaml
```
---
