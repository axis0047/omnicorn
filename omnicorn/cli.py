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
    # 1. Load Config
    conf = ConfigLoader.load(config)

    # 2. Overrides
    if app_path: conf['upstream']['app_path'] = app_path
    if workers:  conf['workers']['count'] = int(workers)
    if port:     conf['server']['port'] = int(port)

    if not conf['upstream']['app_path']:
        print("❌ Error: No application specified.")
        sys.exit(1)

    # 3. Pass Config to Erlang via ENV
    env = os.environ.copy()
    env.update({
        'OMNICORN_APP': conf['upstream']['app_path'],
        'OMNICORN_MODE': conf['upstream']['mode'], # Pass mode to Python worker
        'OMNICORN_PORT': str(conf['server']['port']),
        'OMNICORN_WORKERS': str(conf['workers']['count']),
        'OMNICORN_TIMEOUT': str(conf['workers']['timeout']),
        'OMNICORN_MAX_RESTARTS': str(conf['workers']['max_restarts']),
        'OMNICORN_RESTART_PERIOD': str(conf['workers']['restart_period']),
        'OMNICORN_SOCK': str(conf['server']["socket"]),
        'PYTHONPATH': os.getcwd() + os.pathsep + env.get('PYTHONPATH', '')
    })

    # ... (Rest of the file remains the same: locating release_bin and subprocess.run)
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    erl_src_dir = os.path.join(pkg_dir, 'erl_src')
    release_bin = os.path.join(erl_src_dir, '_build', 'default', 'rel', 'omnicorn', 'bin', 'omnicorn')

    print(f"\n🦄 Omnicorn v1.2.0 (Resilient)")
    print(f"-----------------------------------")
    print(f"🐍 App:         {conf['upstream']['app_path']}")
    print(f"🛡️  Tolerance:   {conf['workers']['max_restarts']} crashes / {conf['workers']['restart_period']}s")
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
