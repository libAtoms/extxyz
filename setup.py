import subprocess
from setuptools import setup
# as per https://stackoverflow.com/questions/19569557/pip-not-picking-up-a-custom-install-cmdclass
from setuptools.command.install import install as setuptools__install
from setuptools.command.develop import develop as setuptools__develop
from setuptools.command.egg_info import egg_info as setuptools__egg_info


class install(setuptools__install):
    def run(self):
        subprocess.call(['make', '-C', 'extxyz', 'clean'])
        subprocess.call(['make', '-C', 'extxyz', 'LIBCLERI_PATH=${PWD}/libcleri/Release'])
        setuptools__install.run(self)


class develop(setuptools__develop):
    def run(self):
        subprocess.call(['make', '-C', 'extxyz', 'clean'])
        subprocess.call(['make', '-C', 'extxyz', 'LIBCLERI_PATH=${PWD}/libcleri/Release'])
        setuptools__develop.run(self)


class egg_info(setuptools__egg_info):
    def run(self):
        subprocess.call(['make', '-C', 'extxyz', 'clean'])
        subprocess.call(['make', '-C', 'extxyz', 'LIBCLERI_PATH=${PWD}/libcleri/Release'])
        setuptools__egg_info.run(self)


setup(
    name='extxyz',
    version='0.0.1b',
    author='various',
    packages=['extxyz'],
    package_data={'extxyz': ['_extxyz.so']},
    cmdclass={'install': install, 'develop': develop, 'egg_info': egg_info},
)

