import multiprocessing
import os

from .gunicorn_adapter import load_gunicorn
from .uwsgi_adapter import load_uwsgi
from .yaml_adapter import load_yaml

DEFAULTS = {
    "server": {"port": 8080, "socket": "127.0.0.1:8080"},
    "workers": {"count": 0, "timeout": 5000},
    "upstream": {"app_path": "main:app", "mode": "auto"},
}


class ConfigLoader:
    @staticmethod
    def load(path=None):
        config = DEFAULTS.copy()
        if path and os.path.exists(path):
            if path.endswith(".yaml"):
                config = load_yaml(path, config)
            elif path.endswith(".ini"):
                config = load_uwsgi(path, config)
            elif path.endswith(".py"):
                config = load_gunicorn(path, config)

        if config["workers"]["count"] == 0:
            config["workers"]["count"] = (multiprocessing.cpu_count() * 2) + 1

        return config
