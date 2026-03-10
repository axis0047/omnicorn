import os
import subprocess
import sys

import click

from .config import ConfigLoader


@click.command()
@click.argument("app_path", required=False)
@click.option("--config", "-c", help="Path to config file (.yaml, .ini, .py)")
def main(app_path, config):
    conf = ConfigLoader.load(config)
    if app_path:
        conf["upstream"]["app_path"] = app_path

    if not conf["upstream"]["app_path"]:
        print("❌ Error: No application specified.")
        sys.exit(1)

    env = os.environ.copy()
    env.update(
        {
            "OMNICORN_APP": conf["upstream"]["app_path"],
            "OMNICORN_MODE": conf["upstream"]["mode"],
            "OMNICORN_PORT": str(conf["server"]["port"]),
            "OMNICORN_WORKERS": str(conf["workers"]["count"]),
            "OMNICORN_TIMEOUT": str(conf["workers"]["timeout"]),
            "OMNICORN_SOCK": str(conf["server"]["socket"]),
            "PYTHONPATH": os.getcwd() + os.pathsep + env.get("PYTHONPATH", ""),
        }
    )

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    erl_src_dir = os.path.join(pkg_dir, "erl_src")
    release_bin = os.path.join(
        erl_src_dir, "_build", "default", "rel", "omnicorn", "bin", "omnicorn"
    )

    print(f"\n🦄 Omnicorn v2.0.0 (unstable)")
    print(f"-----------------------------------")
    print(f"🐍 App:       {conf['upstream']['app_path']} [{conf['upstream']['mode']}]")
    print(f"🚀 Workers:   {conf['workers']['count']}")
    print(f"-----------------------------------")

    cmd = (
        [release_bin, "foreground"]
        if os.path.exists(release_bin)
        else ["rebar3", "shell"]
    )
    try:
        subprocess.run(cmd, env=env, cwd=erl_src_dir)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully.")
