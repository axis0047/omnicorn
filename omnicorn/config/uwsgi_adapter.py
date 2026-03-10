import configparser


def load_uwsgi(path, config):
    parser = configparser.ConfigParser()
    parser.read(path)
    if "uwsgi" in parser:
        u = parser["uwsgi"]
        if "processes" in u:
            config["workers"]["count"] = int(u["processes"])
        if "module" in u:
            config["upstream"]["app_path"] = u["module"]
        if "http" in u:
            config["server"]["port"] = int(u["http"].split(":")[-1])
    return config
