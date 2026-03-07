import os
import yaml # Requires PyYAML
import sys

# Default Configuration "Best Practices"
DEFAULTS = {
    "server": {
        "host": "127.0.0.1",
        "port": 8080,
        "backlog": 1024,
        "nodelay": True
    },
    "workers": {
        "count": 0, # 0 = Auto-detect based on CPU cores
        "max_restarts": 10,
        "restart_period": 60,
        "timeout": 5000, # ms
    },
    "supervisor": {
        "strategy": "one_for_one",
        "shutdown_delay": 2000
    },
    "upstream": {
        "app_path": "main:app",
        "protocol": "http" # http | websocket | tcp
    }
}

class ConfigLoader:
    @staticmethod
    def load(config_path=None):
        config = DEFAULTS.copy()

        # 1. Load from File
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                try:
                    user_conf = yaml.safe_load(f)
                    ConfigLoader._merge(config, user_conf)
                except yaml.YAMLError as e:
                    print(f"❌ Error parsing config file: {e}")
                    sys.exit(1)

        # 2. Override with ENV vars (OMNI_SERVER_PORT=9000)
        ConfigLoader._apply_env(config)

        # 3. Calculate Auto-defaults
        if config['workers']['count'] == 0:
            import multiprocessing
            # Recommended for I/O bound: 2x Cores + 1
            config['workers']['count'] = (multiprocessing.cpu_count() * 2) + 1

        return config

    @staticmethod
    def _merge(default, user):
        """Recursive merge of dicts"""
        for k, v in user.items():
            if isinstance(v, dict) and k in default:
                ConfigLoader._merge(default[k], v)
            else:
                default[k] = v

    @staticmethod
    def _apply_env(config, prefix="OMNI"):
        """Maps OMNI_SECTION_KEY to config dict"""
        for env_k, env_v in os.environ.items():
            if not env_k.startswith(prefix + "_"):
                continue

            parts = env_k.lower().split("_")[1:] # [server, port]
            if len(parts) < 2: continue

            section = parts[0]
            key = "_".join(parts[1:])

            if section in config:
                if key in config[section]:
                    # Type casting based on default value type
                    default_type = type(config[section][key])
                    try:
                        if default_type == bool:
                            config[section][key] = env_v.lower() in ('true', '1', 'yes')
                        else:
                            config[section][key] = default_type(env_v)
                    except ValueError:
                        pass
