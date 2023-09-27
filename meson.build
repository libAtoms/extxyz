# https://mesonbuild.com/
project(
    'extxyz', # Project name
    'c',
    version: run_command('python3', 'discover_version.py', check: true).stdout().strip(), # Project version
)

# https://mesonbuild.com/Python-module.html
pymod = import('python')
python = pymod.find_installation('python3',
    required: true,
    pure: false
)

host_system = host_machine.system()

# adapted from https://gitlab.gnome.org/GNOME/glib/-/blob/cd9a5c173a154e326a3ebaa28cfe41a7444625c5/meson.build#L2020-L2052
pcre2 = dependency('libpcre2-8', version: '>= 10.32', required : false)
if not pcre2.found()
  if cc.get_id() == 'msvc' or cc.get_id() == 'clang-cl'
  # MSVC: Search for the PCRE2 library by the configuration, which corresponds
  # to the output of CMake builds of PCRE2.  Note that debugoptimized
  # is really a Release build with .PDB files.
    if vs_crt == 'debug'
      pcre2 = cc.find_library('pcre2d-8', required : false)
    else
      pcre2 = cc.find_library('pcre2-8', required : false)
    endif
  endif
endif

# Try again with the fallback
if not pcre2.found()
  pcre2 = dependency('libpcre2-8', required : true, fallback : ['pcre2', 'libpcre2_8'])
  use_pcre2_static_flag = true
elif host_system == 'windows'
  pcre2_static = cc.links('''#define PCRE2_STATIC
                             #define PCRE2_CODE_UNIT_WIDTH 8
                             #include <pcre2.h>
                             int main() {
                               void *p = NULL;
                               pcre2_code_free(p);
                               return 0;
                             }''',
                         dependencies: pcre2,
                         name : 'Windows system PCRE2 is a static build')
  use_pcre2_static_flag = pcre2_static
else
  use_pcre2_static_flag = false
endif

subdir('libcleri')
subdir('libextxyz')
subdir('python/extxyz')