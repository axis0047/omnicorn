import os
import yaml
import sys
import multiprocessing

DEFAULTS = {
    "server": {
        "host": "127.0.0.1",
        "port": 8080,
        "socket": "127.0.0.1:8080"
    },
    "workers": {
        "count": 0,
        "timeout": 5000,
        "max_restarts": 1000,
        "restart_period": 60
    },
    "upstream": {
        "app_path": "main:app",
        "mode": "auto" # 'auto', 'asgi', or 'wsgi'
    }
}

class ConfigLoader:
    @staticmethod
    def load(config_path=None):
        config = DEFAULTS.copy()

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                try:
                    user_conf = yaml.safe_load(f)
                    ConfigLoader._merge(config, user_conf)
                except yaml.YAMLError as e:
                    print(f"❌ Error parsing config file: {e}")
                    sys.exit(1)

        if config['workers']['count'] == 0:
            config['workers']['count'] = (multiprocessing.cpu_count() * 2) + 1

        return config

    @staticmethod
    def _merge(default, user):
        for k, v in user.items():
            if isinstance(v, dict) and k in default:
                ConfigLoader._merge(default[k], v)
            else:
                default[k] = v
