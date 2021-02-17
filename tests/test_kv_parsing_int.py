def integer_strings():
    ints = []
    for sign in ['', '+', '-']:
        for num in [ '2', '12' ]:
            ints.append((int(sign+num), sign+num))

    return ints


def test_integer_values(tmp_path, helpers):
    helpers.do_test_scalar(tmp_path, integer_strings())
