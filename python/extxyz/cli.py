import os
import time
import argparse
import cProfile
from pprint import pprint

from ase.atoms import Atoms

from .extxyz import read, write

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    parser.add_argument('-v', '--verbose', action='count',  default=0)
    parser.add_argument('-r', '--regex', action='store_true')
    parser.add_argument('-c', '--create-calc', action='store_true')
    parser.add_argument('-p', '--calc-prefix', action='store', default='')
    parser.add_argument('-w', '--write', action='store_true')
    parser.add_argument('-R', '--round-trip', action='store_true')
    parser.add_argument('-P', '--profile', action='store_true')
    parser.add_argument('-C', '--cextxyz', action='store_true')
    args = parser.parse_args()
    if args.round_trip:
        args.write = True # -R implies -w too

    print(f'Reading from {args.file}')
    if args.profile:
        cProfile.run("""configs = read(args.file,
            verbose=args.verbose,
            use_regex=args.regex,
            create_calc=args.create_calc,
            calc_prefix=args.calc_prefix,
            use_cextxyz=args.cextxyz)""", "readstats")
    t0 = time.time()
    configs = read(args.file,
                    verbose=args.verbose,
                    use_regex=args.regex,
                    create_calc=args.create_calc,
                    calc_prefix=args.calc_prefix,
                    use_cextxyz=args.cextxyz)
    tr = time.time() - t0
    if args.verbose:
        print("main output of read()")
        if isinstance(configs, Atoms):
            configs = [configs]
        for atoms in configs:
            pprint(atoms.info)
            pprint(atoms.arrays)

    print('TIMER read', tr)

    if args.write:
        t0 = time.time()
        out_file = os.path.splitext(args.file)[0] + '.out.xyz'

        if args.profile:
            cProfile.run("""write(out_file, configs,
                verbose=args.verbose,
                write_calc=args.create_calc,
                calc_prefix=args.calc_prefix)""", "writestats")
        else:
            write(out_file, configs,
                  verbose=args.verbose,
                  write_calc=args.create_calc,
                  calc_prefix=args.calc_prefix,
                  use_cextxyz=args.cextxyz)

        tw = time.time() - t0
        print('TIMER write', tw)

    if args.round_trip:
        print(f'Re-reading from {out_file}')
        new_configs = read(out_file,
                            verbose=args.verbose,
                            use_regex=args.regex,
                            create_calc=args.create_calc,
                            calc_prefix=args.calc_prefix,
                            use_cextxyz=args.cextxyz)

        assert configs == new_configs
        print('All configs match!')
