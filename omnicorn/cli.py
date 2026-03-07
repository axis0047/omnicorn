import click
import os
import sys
import subprocess
from .config import ConfigLoader

@click.command()
@click.argument('app_path', required=False)
@click.option('--config', '-c', help='Path to config.yaml')
@click.option('--workers', '-w', help='Override worker count')
@click.option('--port', '-p', help='Override port')
def main(app_path, config, workers, port):
    """
    Omnicorn: The Erlang-Powered Python Application Server.
    """

    # 1. Load Configuration
    conf = ConfigLoader.load(config)

    # 2. CLI Overrides (Highest Priority)
    if app_path: conf['upstream']['app_path'] = app_path
    if workers:  conf['workers']['count'] = int(workers)
    if port:     conf['server']['port'] = int(port)

    if not conf['upstream']['app_path']:
        print("❌ Error: No application specified (app:path) in CLI or Config.")
        sys.exit(1)

    # 3. Prepare Environment for Erlang
    # We pass flattened config as ENV vars to the Erlang VM
    env = os.environ.copy()
    env.update({
        'OMNICORN_APP': conf['upstream']['app_path'],
        'OMNICORN_PORT': str(conf['server']['port']),
        'OMNICORN_WORKERS': str(conf['workers']['count']),
        'OMNICORN_TIMEOUT': str(conf['workers']['timeout']),
        'PYTHONPATH': os.getcwd() + os.pathsep + env.get('PYTHONPATH', '')
    })

    # 4. Release Bin Location
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    erl_src_dir = os.path.join(pkg_dir, 'erl_src')
    release_bin = os.path.join(erl_src_dir, '_build', 'default', 'rel', 'omnicorn', 'bin', 'omnicorn')

    print(f"\n🦄 Omnicorn v1.0.0 (General Purpose)")
    print(f"-----------------------------------")
    print(f"🔧 Configuration:   {config or 'Internal Defaults'}")
    print(f"🐍 App Target:      {conf['upstream']['app_path']}")
    print(f"🌍 HTTP Listener:   {conf['server']['host']}:{conf['server']['port']}")
    print(f"🛡️  Supervision:     {conf['workers']['count']} Workers (Timeout: {conf['workers']['timeout']}ms)")
    print(f"-----------------------------------")

    if os.path.exists(release_bin):
        cmd = [release_bin, "foreground"]
        cwd = erl_src_dir
    else:
        print("⚠️  Dev Mode: Using rebar3 shell")
        cmd = ["rebar3", "shell"]
        cwd = erl_src_dir

    try:
        subprocess.run(cmd, env=env, cwd=cwd)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down.")

if __name__ == '__main__':
    main()
