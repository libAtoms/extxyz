def test_one_elem_scalar(tmp_path, helpers):
    helpers.do_test_kv_pair(tmp_path, 'i', 1, 'i="1"')
    helpers.do_test_kv_pair(tmp_path, 'i', 1, 'i={1}')

def test_new_non_sym_3_by_3(tmp_path, helpers):
    helpers.do_test_kv_pair(tmp_path, 'lat', [[1,2,3],[4,5,6],[7,8,9]], 'lat=[[1, 2, 3], [4, 5, 6], [7, 8, 9]]')

def test_nine_elem_3_by_3(tmp_path, helpers):
    helpers.do_test_kv_pair(tmp_path, 'lat', [[1,2,3],[4,5,6],[7,8,9]], 'lat="1 2 3  4 5 6  7 8 9"')
    helpers.do_test_kv_pair(tmp_path, 'lat', [[1,2,3],[4,5,6],[7,8,9]], 'lat={1 2 3  4 5 6  7 8 9}')
