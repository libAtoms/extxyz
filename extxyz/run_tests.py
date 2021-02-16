#!/usr/bin/env python3

import sys
import re

from extxyz import read

cextxyz = False
for f in sys.argv[1:]:
    print('test', f)
    if 'fail' in f:
        success = False
        try:
            configs = read(f, verbose=0, use_regex=True, create_calc=False, use_cextxyz=cextxyz)
            success = True
        except:
            pass

        print(not success)
    else:
        configs = read(f, verbose=0, use_regex=True, create_calc=False, use_cextxyz=cextxyz)
        m = re.search('tests_([^_]+)(?:_(.+))?.xyz', f)
        data_type = m.group(1)
        val = m.group(2)
        print('type', data_type, 'val', val)

        for config in configs:
            print("config info", config.info)
            assert len(config.info) == 1
            info_k = list(config.info.keys())[0]
            info_v = config.info[info_k]
            if data_type == 'bool':
                assert info_v == (val.startswith('t') or val.startswith('T'))
            elif data_type == 'int':
                assert info_v == int(val)
            elif data_type == 'float':
                assert info_v == float(val)
            elif data_type == 'barestring' or data_type == 'quoted_string':
                assert val is None or info_v == val
            else:
                raise RuntimeError(f'unsupported datatype {data_type}')
