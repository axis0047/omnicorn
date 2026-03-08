import os
import subprocess
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.build_py import build_py

def compile_erlang():
    """Compiles the Erlang OTP release using Rebar3."""
    cwd = os.path.dirname(os.path.abspath(__file__))
    # CORRECTED PATH: Inside omnicorn package
    erl_src = os.path.join(cwd, 'omnicorn', 'erl_src')

    print(f"🚀 Omnicorn: Compiling Erlang backend in {erl_src}...")

    try:
        subprocess.check_call(['rebar3', '--version'], stdout=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        print("❌ Error: 'rebar3' is not installed or not in PATH.")
        raise RuntimeError("rebar3 missing")

    try:
        # Clean and Release
        subprocess.check_call(['rebar3', 'clean'], cwd=erl_src)
        subprocess.check_call(['rebar3', 'release'], cwd=erl_src)
        print("✅ Erlang backend compiled successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error compiling Erlang backend: {e}")
        raise

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
    name='omnicorn',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    cmdclass={
        'build_py': CustomBuildPy,
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
    },
)
