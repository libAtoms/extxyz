from extxyz.extxyz import read

# assuming SyntaxError is how reads _should_ fail

def reading_failed_correctly(filename):
    failed = True

    for use_cextxyz in [True]: # [False, True]:
        this_failed_correctly = False
        try:
            ats = read(filename, use_cextxyz = use_cextxyz)
        except SyntaxError:
            this_failed_correctly = True

        if not this_failed_correctly:
            return False

    return True


def test_lattice_shape(tmp_path):
    with open(tmp_path / 'bad_lattice_shape.xyz', 'w') as fout:
        fout.write("\n".join(["1","Lattice=\"1 1 0    0 1 0   0 0\"","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_lattice_shape.xyz')


def test_lattice_type_scalar(tmp_path):
    with open(tmp_path / 'bad_lattice_type_scalar.xyz', 'w') as fout:
        fout.write("\n".join(["1","Lattice=bob","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_lattice_type_scalar.xyz')


def test_lattice_dtype(tmp_path):
    with open(tmp_path / 'bad_lattice_dtype.xyz', 'w') as fout:
        fout.write("\n".join(["1","Lattice=\"T F F   F T F   F F T\"","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_lattice_dtype.xyz')


def test_properties_shape(tmp_path):
    with open(tmp_path / 'bad_properties_shape.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=\"1 1\"","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_properties_shape.xyz')


def test_properties_type_scalar(tmp_path):
    with open(tmp_path / 'bad_properties_type_scalar.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=5","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_properties_type_scalar.xyz')


def test_properties_format_dtype(tmp_path):
    with open(tmp_path / 'bad_properties_format_dtype.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=species:S:1:pos:D:3","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_properties_format_dtype.xyz')


def test_properties_format_trunc(tmp_path):
    with open(tmp_path / 'bad_properties_format_trunc.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=species:S:1:pos:R:","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_properties_format_trunc.xyz')


def test_per_atom_wrong_type(tmp_path):
    with open(tmp_path / 'bad_per_atom_data_type.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=species:S:1:pos:R:3","Si 0.0 0.0 T"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_per_atom_data_type.xyz')


def test_per_atom_missing_col(tmp_path):
    with open(tmp_path / 'bad_per_atom_missing_col.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=species:S:1:pos:R:3","Si 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_per_atom_missing_col.xyz')


def test_per_atom_extra_col(tmp_path):
    with open(tmp_path / 'bad_per_atom_extra_col.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=species:S:1:pos:R:3","Si 0.0 0.0 0.0  T"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_per_atom_extra_col.xyz')


def test_missing_atom_lines(tmp_path):
    with open(tmp_path / 'bad_missing_atom_lines.xyz', 'w') as fout:
        fout.write("\n".join(["2","Properties=species:S:1:pos:R:3","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_missing_atom_lines.xyz')


def test_extra_atom_lines(tmp_path):
    with open(tmp_path / 'bad_extra_atom_lines.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=species:S:1:pos:R:3","Si 0.0 0.0 0.0","Si 1.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_extra_atom_lines.xyz')


def test_extra_comment_line(tmp_path):
    with open(tmp_path / 'bad_extra_comment_line.xyz', 'w') as fout:
        fout.write("\n".join(["1","Properties=species:S:1:pos:R:3","extra_comment_bool=T","Si 0.0 0.0 0.0"])+"\n")

    assert reading_failed_correctly(tmp_path / 'bad_extra_comment_line.xyz')
