import subprocess
from setuptools import setup
from distutils.command.build_clib import build_clib as _build_clib


class build_clib(_build_clib):
    def run(self):
        subprocess.call(['make', 'clean', '-C', 'extxyz'])
        subprocess.call(['make', '-C', 'extxyz'])
        _build_clib.run(self)

setup(
    name='extxyz',
    version='0.0.1b',
    author='various',
    packages=['extxyz'],
    package_data={'extxyz': ['_extxyz.so']},
    cmdclass={'build_clib': build_clib},
)

