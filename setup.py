import os
import subprocess

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py
from setuptools.command.develop import develop
from setuptools.command.install import install


def compile_erlang():
    """Compile the Erlang backend using rebar3."""
    cwd = os.path.dirname(os.path.abspath(__file__))
    erl_src = os.path.join(cwd, "omnicorn", "erl_src")
    
    if not os.path.exists(erl_src):
        print("⚠️  Erlang source not found, skipping compilation.")
        return
    
    print(f"🚀 Omnicorn: Compiling Erlang backend in {erl_src}...")
    
    # Check if rebar3 is available
    try:
        subprocess.check_call(["rebar3", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  rebar3 not found. Please install rebar3 from https://www.rebar3.org/")
        print("   Skipping Erlang compilation.")
        return
    
    try:
        subprocess.check_call(["rebar3", "clean"], cwd=erl_src)
        subprocess.check_call(["rebar3", "compile"], cwd=erl_src)
        subprocess.check_call(["rebar3", "release"], cwd=erl_src)
        print("✅ Erlang backend compiled successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error compiling Erlang backend: {e}")
        print("   You can still use Omnicorn in development mode with: rebar3 shell")
        # Don't fail the build, just warn


class CustomBuildPy(build_py):
    def run(self):
        compile_erlang()
        super().run()


class PostInstallCommand(install):
    def run(self):
        compile_erlang()
        super().run()


class PostDevelopCommand(develop):
    def run(self):
        compile_erlang()
        super().run()


setup(
    name="omnicorn",
    version="1.0.0.dev0",
    packages=find_packages(),
    include_package_data=True,
    cmdclass={
        "build_py": CustomBuildPy,
        "install": PostInstallCommand,
        "develop": PostDevelopCommand,
    },
)
