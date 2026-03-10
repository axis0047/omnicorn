import sys


def load_gunicorn(path, config):
    """Parses a legacy gunicorn.conf.py file and translates it to Omnicorn."""
    ctx = {}
    try:
        with open(path, "r") as f:
            # Safely execute the gunicorn conf file into the ctx dictionary
            exec(f.read(), ctx)
    except Exception as e:
        sys.stderr.write(f"⚠️ Failed to parse Gunicorn config {path}: {e}\n")
        return config

    if "workers" in ctx:
        config["workers"]["count"] = int(ctx["workers"])

    if "bind" in ctx:
        binds = ctx["bind"]
        if isinstance(binds, str):
            binds = [binds]
        if binds:
            host_port = binds[0].split(":")
            if len(host_port) == 2:
                config["server"]["port"] = int(host_port[1])

    if "timeout" in ctx:
        # Gunicorn uses seconds, Omnicorn uses milliseconds
        config["workers"]["timeout"] = int(ctx["timeout"]) * 1000

    return config
