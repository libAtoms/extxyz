import sys
import sysconfig
import pathlib
import os
import subprocess
from setuptools import setup, Extension
# as per https://stackoverflow.com/questions/19569557/pip-not-picking-up-a-custom-install-cmdclass
from setuptools.command.install import install as setuptools__install
from setuptools.command.develop import develop as setuptools__develop
from setuptools.command.egg_info import egg_info as setuptools__egg_info
from setuptools.command.build_ext import build_ext as setuptools__build_ext

def build_grammar():
    # check if we need to run the grammar definition to regenerate .c and .h
    py_grammar_file = pathlib.Path('./grammar/extxyz_kv_grammar.py')
    c_grammar_file = pathlib.Path('./c/extxyz_kv_grammar.c')

    if not c_grammar_file.exists() or (py_grammar_file.stat().st_mtime > c_grammar_file.stat().st_mtime):
        sys.path.insert(0, './python/extxyz')
        import extxyz_kv_grammar
        del sys.path[0]
        extxyz_kv_grammar.write_grammar('./c')
    
def build_libcleri():
    with open('libcleri/Release/makefile', 'r') as f_in, open('libcleri/Release/makefile.extxyz', 'w') as f_out:
        contents = f_in.read()
        contents += """

libcleri.a: $(OBJS) $(USER_OBJS)
\tar rcs libcleri.a $(OBJS) $(USER_OBJS)
"""
        f_out.write(contents)
    subprocess.call(['make', '-C', 'libcleri/Release', '-f', 'makefile.extxyz', 'libcleri.a'])

class install(setuptools__install):
    def run(self):
        build_libcleri()
        setuptools__install.run(self)


class develop(setuptools__develop):
    def run(self):
        build_libcleri()
        setuptools__develop.run(self)


class egg_info(setuptools__egg_info):
    def run(self):
        build_libcleri()
        setuptools__egg_info.run(self)

# https://stackoverflow.com/questions/60284403/change-output-filename-in-setup-py-distutils-extension
class NoSuffixBuilder(setuptools__build_ext):
    def get_ext_filename(self, ext_name):
        filename = super().get_ext_filename(ext_name)
        suffix = sysconfig.get_config_var('EXT_SUFFIX')
        ext = os.path.splitext(filename)[1]
        return filename.replace(suffix, "") + ext

pcre2_cflags = subprocess.run(['pcre2-config', '--cflags'], capture_output=True).stdout.decode('utf-8').strip().split()
pcre2_include_dirs = [i.replace('-I', '', 1) for i in pcre2_cflags if i.startswith('-I')]
# should we also capture other flags to pass to extra_compile_flags?

pcre2_libs = subprocess.run(['pcre2-config', '--libs8'], capture_output=True).stdout.decode('utf-8').strip().split()
pcre2_library_dirs = [l.replace('-L', '', 1) for l in pcre2_libs if l.startswith('-L')]
pcre2_libraries = [l.replace('-l', '', 1) for l in pcre2_libs if l.startswith('-l')]

_extxyz_ext = Extension('extxyz._extxyz', sources=['c/extxyz_kv_grammar.c', 'c/extxyz.c'],
                        include_dirs=['libcleri/inc', 'extxyz'] + pcre2_include_dirs,
                        library_dirs=pcre2_library_dirs, libraries=pcre2_libraries,
                        extra_compile_args=['-fPIC'], extra_objects=['libcleri/Release/libcleri.a'])

build_grammar()

setup(
    name='extxyz',
    version='0.0.1b',
    author='various',
    packages=['extxyz'],
    package_dir={'': 'python'},
    cmdclass={'install': install, 'develop': develop, 'egg_info': egg_info, 'build_ext': NoSuffixBuilder},
    include_package_data=True,
    ext_modules=[_extxyz_ext],
)

