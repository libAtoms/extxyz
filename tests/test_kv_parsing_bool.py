def bool_strings():
    bools = []
    for b in ['T', 'true', 'True', 'TRUE', 'F', 'false', 'False', 'FALSE']:
        bools.append((b.lower().startswith('t'), b))

    return bools

def test_bool_scalars(tmp_path, helpers):
    helpers.do_test_scalar(tmp_path, bool_strings())

def test_bool_arrays(tmp_path, helpers):
    helpers.do_test_one_d_array(tmp_path, bool_strings())
