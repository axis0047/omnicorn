import click
import os
import sys
import subprocess

@click.command()
@click.argument('app_path')
@click.option('--workers', default=4, help='Number of Python worker processes')
@click.option('--port', default=8080, help='Port to listen on')
def main(app_path, workers, port):
    """
    Omnicorn: Erlang/OTP Supervisor for Python.

    APP_PATH: The python application (e.g., 'main:app')
    """

    # 1. Locate the Erlang Release relative to this file (cli.py)
    # cli.py is in .../site-packages/omnicorn/
    # erl_src is in .../site-packages/omnicorn/erl_src/
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    erl_src_dir = os.path.join(pkg_dir, 'erl_src')
    release_bin = os.path.join(erl_src_dir, '_build', 'default', 'rel', 'omnicorn', 'bin', 'omnicorn')

    # 2. Configure Environment
    env = os.environ.copy()
    env['OMNICORN_APP'] = app_path
    env['OMNICORN_WORKERS'] = str(workers)
    env['OMNICORN_PORT'] = str(port)
    env['PYTHONPATH'] = os.getcwd() + os.pathsep + env.get('PYTHONPATH', '')

    print(f"\n🦄 Omnicorn v1.0.0 starting...")
    print(f"👉 App: {app_path}")
    print(f"🔧 Workers: {workers}")
    print(f"🌍 Port: {port}")
    print(f"📂 Release Bin: {release_bin}")

    # 3. Execution Strategy
    if os.path.exists(release_bin):
        # Production: Run compiled binary
        cmd = [release_bin, "foreground"]
        cwd = erl_src_dir
    else:
        # Fallback/Dev: Use rebar3 shell if binary is missing
        print("⚠️  Warning: Release binary not found. Attempting to use rebar3 shell.")
        # We point cwd to erl_src so rebar3 finds rebar.config
        cmd = ["rebar3", "shell"]
        cwd = erl_src_dir

    try:
        if not os.path.exists(cwd):
             print(f"❌ Fatal Error: Directory not found: {cwd}")
             print("   Installation might be corrupt. Try 'pip install . --force-reinstall'")
             sys.exit(1)

        subprocess.run(cmd, env=env, cwd=cwd)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down Omnicorn.")
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
