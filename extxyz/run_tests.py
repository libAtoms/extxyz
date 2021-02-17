#!/usr/bin/env python3

import sys
import re
import numpy as np
import numbers

from ase.atoms import Atoms

from extxyz import read

for cextxyz in [False, True]:
    if cextxyz:
        print ("C+python")
    else:
        print ("pure python")
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
            if isinstance(configs, Atoms):
                configs = [configs]

            m = re.search('tests_([^_]+)(?:_(.+))?.xyz', f)
            data_type = m.group(1)
            val = m.group(2)
            print('type', data_type, 'val', val)

            for config in configs:
                if 'Properties' in config.info:
                    sys.stderr.write("WARNING: got Properties in info\n");
                    del config.info['Properties']
                print("config info", config.info)
                assert len(config.info) == 1
                info_k = list(config.info.keys())[0]
                info_v = config.info[info_k]
                print("info k-v", info_k, info_v)
                if data_type == 'bool':
                    assert info_v == (val.startswith('t') or val.startswith('T'))
                elif data_type == 'integer':
                    assert info_v == int(val)
                elif data_type == 'float':
                    assert info_v == float(val)
                elif data_type == 'barestring' or data_type == 'quotedstring':
                    assert val is None or info_v == val
                elif data_type.endswith('darray'):
                    if val == 'integer':
                        assert issubclass(info_v.dtype.type, numbers.Integral)
                    elif val == 'float':
                        assert issubclass(info_v.dtype.type, numbers.Real)
                    elif val == 'bool':
                        assert info_v.dtype == bool or info_v.dtype == np.bool
                    elif val == 'string':
                        assert info_v.dtype.type is np.str_ or info_v.dtype.type is np.string_
                    else:
                        raise RuntimeError(f'unsupported array datatype {data_type}')
                else:
                    raise RuntimeError(f'unsupported datatype {data_type}')
