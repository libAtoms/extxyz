# https://mesonbuild.com/
project(
    'extxyz', # Project name
    'c',
    # Use 'python' which works cross-platform inside cibuildwheel
    version: run_command('python', 'discover_version.py', check: true).stdout().strip(), # Project version
)

# https://mesonbuild.com/Python-module.html
pymod = import('python')
# Don't specify 'python3' - let Meson find the Python used to run itself
python = pymod.find_installation(
    required: true,
    pure: false
)

host_system = host_machine.system()
cc = meson.get_compiler('c')

# Determine MSVC runtime library (for PCRE2 library name)
vs_crt = 'release'
vs_crt_opt = get_option('b_vscrt')
if vs_crt_opt in ['mdd', 'mtd']
  vs_crt = 'debug'
elif vs_crt_opt == 'from_buildtype'
  if get_option('buildtype') == 'debug'
    vs_crt = 'debug'
  endif
endif

# adapted from https://gitlab.gnome.org/GNOME/glib/-/blob/cd9a5c173a154e326a3ebaa28cfe41a7444625c5/meson.build#L2020-L2052
pcre2 = dependency('libpcre2-8', version: '>= 10.23', required : false)
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
  elif host_system == 'windows'
    # MinGW/GCC on Windows: Try to find the library directly
    pcre2 = cc.find_library('pcre2-8', required : false)
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