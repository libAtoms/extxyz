import os
import subprocess
from setuptools import setup, Extension
# as per https://stackoverflow.com/questions/19569557/pip-not-picking-up-a-custom-install-cmdclass
from setuptools.command.install import install as setuptools__install
from setuptools.command.develop import develop as setuptools__develop
from setuptools.command.egg_info import egg_info as setuptools__egg_info


class install(setuptools__install):
    def run(self):
        # subprocess.call(['make', '-C', 'extxyz', 'clean'])
        subprocess.call(['make', '-C', 'extxyz', 'LIBCLERI_PATH=${PWD}/libcleri/Release', 'libcleri'])
        setuptools__install.run(self)


class develop(setuptools__develop):
    def run(self):
        # subprocess.call(['make', '-C', 'extxyz', 'clean'])
        subprocess.call(['make', '-C', 'extxyz', 'LIBCLERI_PATH=${PWD}/libcleri/Release', 'libcleri'])
        setuptools__develop.run(self)


class egg_info(setuptools__egg_info):
    def run(self):
        # subprocess.call(['make', '-C', 'extxyz', 'clean'])
        subprocess.call(['make', '-C', 'extxyz', 'LIBCLERI_PATH=${PWD}/libcleri/Release', 'libcleri'])
        setuptools__egg_info.run(self)


pcre2_prefix = subprocess.run(['pcre2-config', '--prefix'], capture_output=True).stdout.decode('utf-8').strip()
pcre2_libs = subprocess.run(['pcre2-config', '--libs8'], capture_output=True).stdout.decode('utf-8').strip().split()
pcre2_library_dirs = [l.replace('-L', '', 1) for l in pcre2_libs if l.startswith('-L')]
pcre2_libraries = [l.replace('-l', '', 1) for l in pcre2_libs if l.startswith('-l')]

_extxyz_ext = Extension('extxyz._extxyz', sources=['extxyz/extxyz_kv_grammar.c', 'extxyz/extxyz.c'],
                        include_dirs=['libcleri/inc', 'extxyz', pcre2_prefix+'/include'], 
                        library_dirs=pcre2_library_dirs, libraries=pcre2_libraries,
                        extra_compile_args=['-fPIC'], extra_objects=['libcleri/Release/libcleri.a'])


setup(
    name='extxyz',
    version='0.0.1b',
    author='various',
    packages=['extxyz'],
    cmdclass={'install': install, 'develop': develop, 'egg_info': egg_info},
    include_package_data=True,
    ext_modules=[_extxyz_ext],
)

