import os
import subprocess
import sys

import click

from .config import ConfigLoader


@click.command()
@click.argument("app_path", required=False)
@click.option("--config", "-c", help="Path to config file (.yaml, .ini, .py)")
@click.option("--host", "-h", default=None, help="Host to bind (overrides config)")
@click.option("--port", "-p", default=None, help="Port to bind (overrides config)")
@click.option("--workers", "-w", default=None, help="Number of workers (overrides config)")
def main(app_path, config, host, port, workers):
    """
    Omnicorn - Erlang/OTP Distributed Application Server
    
    Run a WSGI/ASGI application with Omnicorn.
    
    Examples:
    
        omnicorn myapp:app
        omnicorn myapp:app --config omnicorn.yaml
        omnicorn myapp:app --workers 4 --port 8000
    """
    conf = ConfigLoader.load(config)
    
    # Override config with command line options
    if app_path:
        conf["upstream"]["app_path"] = app_path
    if host:
        conf["server"]["socket"] = f"{host}:{conf['server']['port']}"
    if port:
        conf["server"]["port"] = int(port)
        conf["server"]["socket"] = f"127.0.0.1:{port}"
    if workers:
        conf["workers"]["count"] = int(workers)

    if not conf["upstream"]["app_path"]:
        click.echo("❌ Error: No application specified.")
        click.echo("Usage: omnicorn APP_PATH [OPTIONS]")
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

    click.echo(f"\n🦄 Omnicorn v{__version__}")
    click.echo(f"{'='*50}")
    click.echo(f"🐍 App:       {conf['upstream']['app_path']} [{conf['upstream']['mode']}]")
    click.echo(f"🚀 Workers:   {conf['workers']['count']}")
    click.echo(f"🌐 Port:      {conf['server']['port']}")
    click.echo(f"{'='*50}\n")

    cmd = (
        [release_bin, "foreground"]
        if os.path.exists(release_bin)
        else ["rebar3", "shell"]
    )
    
    try:
        subprocess.run(cmd, env=env, cwd=erl_src_dir)
    except KeyboardInterrupt:
        click.echo("\n🛑 Shutting down gracefully.")
    except FileNotFoundError:
        click.echo("❌ Error: Omnicorn Erlang backend not found.")
        click.echo("   Run './scripts/build.sh' to build.")
        sys.exit(1)


if __name__ == "__main__":
    main()
