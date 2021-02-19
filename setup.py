import subprocess
from setuptools import setup
from distutils.command.install import install as _install


class install(_install):
    def run(self):
        subprocess.call(['make', 'clean', '-C', 'extxyz'])
        subprocess.call(['make', '-C', 'extxyz'])
        _install.run(self)

setup(
    name='extxyz',
    version='0.0.1b',
    author='various',
    packages=['extxyz'],
    package_data={'extxyz': ['_extxyz.so']},
    cmdclass={'install': install},
)

