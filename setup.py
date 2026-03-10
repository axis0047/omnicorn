import os
import subprocess

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py
from setuptools.command.develop import develop
from setuptools.command.install import install


def compile_erlang():
    cwd = os.path.dirname(os.path.abspath(__file__))
    erl_src = os.path.join(cwd, "omnicorn", "erl_src")
    print(f"🚀 Omnicorn: Compiling Erlang backend in {erl_src}...")
    try:
        subprocess.check_call(["rebar3", "clean"], cwd=erl_src)
        subprocess.check_call(["rebar3", "release"], cwd=erl_src)
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
    name="omnicorn",
    version="2.0.0",
    packages=find_packages(),
    include_package_data=True,
    cmdclass={
        "build_py": CustomBuildPy,
        "install": PostInstallCommand,
        "develop": PostDevelopCommand,
    },
)
