inc_dir = include_directories('inc')

libcleri = static_library('cleri',
  'src/children.c',
  'src/choice.c',
  'src/dup.c',
  'src/expecting.c',
  'src/grammar.c',
  'src/keyword.c',
  'src/kwcache.c',
  'src/list.c',
  'src/node.c',
  'src/cleri.c',
  'src/olist.c',
  'src/optional.c',
  'src/parse.c',
  'src/prio.c',
  'src/ref.c',
  'src/regex.c',
  'src/repeat.c',
  'src/rule.c',
  'src/sequence.c',
  'src/this.c',
  'src/token.c',
  'src/tokens.c', 
  'src/version.c', 
  dependencies: pcre2, 
  include_directories: inc_dir)

cleri = declare_dependency(
  link_with: libcleri,
  include_directories: inc_dir)