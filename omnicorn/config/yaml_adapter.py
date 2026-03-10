import yaml


def load_yaml(path, config):
    with open(path, "r") as f:
        user = yaml.safe_load(f)
        for k, v in user.items():
            if isinstance(v, dict) and k in config:
                config[k].update(v)
            else:
                config[k] = v
    return config
