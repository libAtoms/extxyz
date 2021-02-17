def float_strings(minimal=False):
    floats = []

    if minimal:
        signs = ['', '-', '+']
    else:
        signs = ['', '-']

    for init_sign in signs:
        for num in [ '1.0', '1.', '1', '12.0', '12', '0.12', '0.012', '.012']:
            f_str = float(init_sign+num)
            floats.append((f_str, init_sign+num))

            for exp_lett in ['e', 'E', 'd', 'D']:
                for exp_sign in ['+', '-', '']:
                    for exp_num in ['0', '2', '02', '12']:
                        f_str = init_sign+num+exp_lett+exp_sign+exp_num
                        f_val = float(f_str.replace('d','e').replace('D','e'))
                        floats.append((f_val, f_str))
                        if minimal:
                            break
                    else:
                        continue
                    break
                else:
                    continue
                break


    return floats


def test_float_scalars(tmp_path, helpers):
    helpers.do_test_scalar(tmp_path, float_strings())

def test_float_one_darrays(tmp_path, helpers):
    helpers.do_test_one_d_array(tmp_path, float_strings(minimal=True))

def test_float_two_darrays(tmp_path, helpers):
    helpers.do_test_two_d_array(tmp_path, float_strings(minimal=True))
