import sys
import tempfile
import atexit
import shutil
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
    c_grammar_file = pathlib.Path('./libext/extxyz_kv_grammar.c')

    if not c_grammar_file.exists() or (py_grammar_file.stat().st_mtime > c_grammar_file.stat().st_mtime):
        sys.path.insert(0, './python/extxyz')
        import extxyz_kv_grammar
        del sys.path[0]
        extxyz_kv_grammar.write_grammar('./libextxyz')

def which(program):
    import os

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def build_pcre2():
    pcre2_config = which('pcre2-config')
    print(f'which(pcre2-config) = {pcre2_config}')
    if pcre2_config is None:
        pcre2_version = '10.37'
        print(f'pcre2-config not found so downloading and installing PCRE2-{pcre2_version}')

        tempdir = tempfile.mkdtemp()
        atexit.register(lambda: shutil.rmtree(tempdir)) # cleanup tempdir when Python exits
        build_dir = os.path.abspath(f"{tempdir}/pcre2-{pcre2_version}/build")
        pcre2_config = os.path.join(build_dir, 'bin', 'pcre2-config')

        orig_dir = os.getcwd()
        os.chdir(tempdir)
        try:
            subprocess.call(["curl", f"https://ftp.pcre.org/pub/pcre/pcre2-{pcre2_version}.tar.gz", "-o", "pcre2.tar.gz"])
            subprocess.call(["tar", "xvzf", "pcre2.tar.gz"])
            subprocess.call(["./configure", f"--prefix={build_dir}"], cwd=f"pcre2-{pcre2_version}")
            subprocess.call("make", cwd=f"pcre2-{pcre2_version}")
            subprocess.call(["make", "install"], cwd=f"pcre2-{pcre2_version}")
        finally:
            os.chdir(orig_dir)

    pcre2_cflags = subprocess.check_output([f'{pcre2_config}', '--cflags'], encoding='utf-8').strip().split()
    pcre2_include_dirs = [i.replace('-I', '', 1) for i in pcre2_cflags if i.startswith('-I')]
    # should we also capture other flags to pass to extra_compile_flags?

    pcre2_libs = subprocess.check_output([f'{pcre2_config}', '--libs8'], encoding='utf-8').strip().split()
    pcre2_library_dirs = [l.replace('-L', '', 1) for l in pcre2_libs if l.startswith('-L')]
    pcre2_libraries = [l.replace('-l', '', 1) for l in pcre2_libs if l.startswith('-l')]

    return pcre2_cflags, pcre2_include_dirs, pcre2_library_dirs, pcre2_libraries

    
def build_libcleri(pcre2_cflags):
    with open('libcleri/Release/makefile', 'r') as f_in, open('libcleri/Release/makefile.extxyz', 'w') as f_out:
        contents = f_in.read()
        contents += """

libcleri.a: $(OBJS) $(USER_OBJS)
\tar rcs libcleri.a $(OBJS) $(USER_OBJS)
"""
        f_out.write(contents)
    env = os.environ.copy()
    env['CFLAGS'] = ' '.join(pcre2_cflags)
    subprocess.call(['make', '-C', 'libcleri/Release', '-f', 'makefile.extxyz', 'libcleri.a'], env=env)

class install(setuptools__install):
    def run(self):
        build_libcleri(pcre2_cflags)
        setuptools__install.run(self)


class develop(setuptools__develop):
    def run(self):
        build_libcleri(pcre2_cflags)
        setuptools__develop.run(self)


class egg_info(setuptools__egg_info):
    def run(self):
        build_libcleri(pcre2_cflags)
        setuptools__egg_info.run(self)

# https://stackoverflow.com/questions/60284403/change-output-filename-in-setup-py-distutils-extension
class NoSuffixBuilder(setuptools__build_ext):
    def get_ext_filename(self, ext_name):
        filename = super().get_ext_filename(ext_name)
        suffix = sysconfig.get_config_var('EXT_SUFFIX')
        ext = os.path.splitext(filename)[1]
        return filename.replace(suffix, "") + ext

pcre2_cflags, pcre2_include_dirs, pcre2_library_dirs, pcre2_libraries = build_pcre2()        

_extxyz_ext = Extension('extxyz._extxyz', sources=['libextxyz/extxyz_kv_grammar.c', 'libextxyz/extxyz.c'],
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
    install_requires=['numpy>=1.13', 'pyleri>=1.3.3', 'ase>=3.17'],
    ext_modules=[_extxyz_ext],
    entry_points={'console_scripts': ['extxyz=extxyz.cli:main']}
)

