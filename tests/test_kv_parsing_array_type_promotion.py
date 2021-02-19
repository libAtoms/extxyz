def test_array_one_d_type_promotion(tmp_path, helpers):
    # int + float to float
    v_str = [ '1', '2', '3.0', '+4.0e0' ]
    v = [1.0, 2.0, 3.0, 4.0]
    helpers.do_one_d_variants(tmp_path, False, 4, v, v_str) 

    # int + barestring to string
    v_str = [ '1', '2', 'abc', 'd']
    v = ['1', '2', 'abc', 'd']
    helpers.do_one_d_variants(tmp_path, True, 4, v, v_str) 

    # bool + barestring to string
    v_str = [ 'T', 'False', 'abc', 'd']
    v = ['T', 'False', 'abc', 'd']
    helpers.do_one_d_variants(tmp_path, True, 4, v, v_str) 

    # bool + quotedstring to string
    v_str = [ 'T', 'False', '"abc"', 'd']
    v = ['T', 'False', 'abc', 'd']
    helpers.do_one_d_variants(tmp_path, True, 4, v, v_str) 

    # bool + int to string
    v_str = [ 'T', 'False', '12', '345' ]
    v = ['T', 'False', '12', '345']
    helpers.do_one_d_variants(tmp_path, True, 4, v, v_str) 


def test_array_two_d_type_promotion(tmp_path, helpers):
    # int + float to float
    v_str = [ '1', '2', '3.0', '+4.0e0' ]
    v = [1.0, 2.0, 3.0, 4.0]
    helpers.do_two_d_variants(tmp_path, 2, 2, v, v_str) 

    # int + barestring to string
    v_str = [ '1', '2', 'abc', 'd']
    v = ['1', '2', 'abc', 'd']
    helpers.do_two_d_variants(tmp_path, 2, 2, v, v_str) 

    # bool + barestring to string
    v_str = [ 'T', 'False', 'abc', 'd']
    v = ['T', 'False', 'abc', 'd']
    helpers.do_two_d_variants(tmp_path, 2, 2, v, v_str) 

    # bool + quotedstring to string
    v_str = [ 'T', 'False', '"abc"', 'd']
    v = ['T', 'False', 'abc', 'd']
    helpers.do_two_d_variants(tmp_path, 2, 2, v, v_str) 

    # bool + int to string
    v_str = [ 'T', 'False', '12', '345' ]
    v = ['T', 'False', '12', '345']
    helpers.do_two_d_variants(tmp_path, 2, 2, v, v_str) 
