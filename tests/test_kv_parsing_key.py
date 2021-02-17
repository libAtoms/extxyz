def test_key(tmp_path, helpers):
    for sp0 in ['', ' ']:
        for sp1 in ['', ' ']:
            helpers.do_test_config(tmp_path, 'bob', 2, kv_str='bob'+sp0+'='+sp1+'2')
            helpers.do_test_config(tmp_path, 'bob#joe', 2, kv_str='bob#joe'+sp0+'='+sp1+'2')
            helpers.do_test_config(tmp_path, 'bob', 2, kv_str='"bob"'+sp0+'='+sp1+'2')
            helpers.do_test_config(tmp_path, 'bob"joe', 2, kv_str='"bob\\"joe"'+sp0+'='+sp1+'2')
            helpers.do_test_config(tmp_path, 'bob joe', 2, kv_str='"bob joe"'+sp0+'='+sp1+'2')
            helpers.do_test_config(tmp_path, 'bob\\joe', 2, kv_str='"bob\\\\joe"'+sp0+'='+sp1+'2')
