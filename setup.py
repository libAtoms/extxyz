import subprocess
from setuptools import setup
from distutils.command.install import install as DistutilsInstall



class MyInstall(DistutilsInstall):
    def run(self):
        subprocess.call(['make', '-C', 'extxyz', 'clean'])
        subprocess.call(['make', '-C', 'extxyz', 'LIBCLERI_PATH=${PWD}/libcleri/Release'])
        DistutilsInstall.run(self)

setup(
    name='extxyz',
    version='0.0.1b',
    author='various',
    packages=['extxyz'],
    package_data={'extxyz': ['_extxyz.so']},
    cmdclass={'install': MyInstall},
)

