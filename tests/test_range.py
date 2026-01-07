import pytest
from mccode_antlr.run.range import MRange, EList, Singular, parse_scan_parameters, parameters_to_scan


class TestParseScanParameters:
    def test_empty_list(self):
        """Test parsing an empty list returns an empty dictionary."""
        result = parse_scan_parameters([])
        assert result == {}

    def test_single_range_with_equals(self):
        """Test parsing a single range parameter with equals sign."""
        result = parse_scan_parameters(['param=1:0.5:3'])
        assert 'param' in result
        assert isinstance(result['param'], MRange)
        assert result['param'].start == 1
        assert result['param'].stop == 3
        assert result['param'].step == 0.5

    def test_single_range_without_step(self):
        """Test parsing a range without step (defaults to 1)."""
        result = parse_scan_parameters(['param=1:5'])
        assert 'param' in result
        assert isinstance(result['param'], MRange)
        assert result['param'].start == 1
        assert result['param'].stop == 5
        assert result['param'].step == 1

    def test_single_singular_with_equals(self):
        """Test parsing a single singular parameter with equals sign."""
        result = parse_scan_parameters(['param=42'])
        assert 'param' in result
        assert isinstance(result['param'], Singular)
        assert result['param'].value == 42
        assert result['param'].maximum == 1  # max_length is 1 for single singular

    def test_single_singular_space_separated(self):
        """Test parsing a single singular parameter with space separation."""
        result = parse_scan_parameters(['param', '42'])
        assert 'param' in result
        assert isinstance(result['param'], Singular)
        assert result['param'].value == 42

    def test_single_range_space_separated(self):
        """Test parsing a single range parameter with space separation."""
        result = parse_scan_parameters(['param', '1:0.5:3'])
        assert 'param' in result
        assert isinstance(result['param'], MRange)
        assert result['param'].start == 1
        assert result['param'].stop == 3
        assert result['param'].step == 0.5

    def test_multiple_ranges(self):
        """Test parsing multiple range parameters."""
        result = parse_scan_parameters(['a=1:5', 'b=2:0.5:4'])
        assert len(result) == 2
        assert isinstance(result['a'], MRange)
        assert isinstance(result['b'], MRange)
        assert result['a'].start == 1
        assert result['a'].stop == 5
        assert result['b'].start == 2
        assert result['b'].stop == 4
        assert result['b'].step == 0.5

    def test_singular_with_range_updates_maximum(self):
        """Test that Singular maximum is updated to match range length."""
        result = parse_scan_parameters(['a=1:5', 'b=10'])
        assert isinstance(result['a'], MRange)
        assert isinstance(result['b'], Singular)
        # The range a=1:5 has 5 elements (1, 2, 3, 4, 5)
        expected_max = len(result['a'])
        assert result['b'].maximum == expected_max

    def test_mixed_parameters(self):
        """Test parsing a mix of ranges and singular values."""
        result = parse_scan_parameters(['x=0:10', 'y', '5', 'z=1:2:9'])
        assert len(result) == 3
        assert 'x' in result
        assert 'y' in result
        assert 'z' in result

    def test_float_values(self):
        """Test parsing float values."""
        result = parse_scan_parameters(['param=1.5:0.25:3.5'])
        assert result['param'].start == 1.5
        assert result['param'].stop == 3.5
        assert result['param'].step == 0.25

    def test_negative_values(self):
        """Test parsing negative values in ranges."""
        result = parse_scan_parameters(['param=-5:1:5'])
        assert result['param'].start == -5
        assert result['param'].stop == 5
        assert result['param'].step == 1

    def test_singular_string_value(self):
        """Test parsing a singular parameter with a string value."""
        result = parse_scan_parameters(['param=myfile'])
        assert isinstance(result['param'], Singular)
        assert result['param'].value == 'myfile'

    def test_invalid_parameter_raises_error(self):
        """Test that an invalid parameter format raises ValueError."""
        with pytest.raises(ValueError, match='Invalid parameter'):
            parse_scan_parameters(['invalid'])

    def test_preserves_parameter_case(self):
        """Test that parameter names preserve case."""
        result = parse_scan_parameters(['MyParam=10', 'UPPERCASE=20'])
        assert 'MyParam' in result
        assert 'UPPERCASE' in result

    def test_multiple_singulars_all_get_maximum_one(self):
        """Test that multiple singulars without ranges get maximum 1."""
        result = parse_scan_parameters(['a=10', 'b=20'])
        assert isinstance(result['a'], Singular)
        assert isinstance(result['b'], Singular)
        assert result['a'].maximum == 1
        assert result['b'].maximum == 1

    def test_singular_maximum_matches_longest_range(self):
        """Test that singulars get maximum from the longest range."""
        # a has 5 elements (1,2,3,4,5), b has 3 elements (1,3,5)
        result = parse_scan_parameters(['a=1:5', 'b=1:2:5', 'c=42'])
        assert isinstance(result['c'], Singular)
        max_len = max(len(result['a']), len(result['b']))
        assert result['c'].maximum == max_len


class TestSingular:
    def test_singular_getitem(self):
        s = Singular(5)
        assert s[0] == 5
        assert s[1000000000] == 5
        s = Singular(10, 1)
        assert s[0] == 10
        with pytest.raises(IndexError):
            s1000 = s[1000]


class TestEList:
    """Tests for explicit list (EList) parsing functionality."""

    def test_elist_from_str_integers(self):
        """Test EList.from_str with integer values."""
        result = EList.from_str('1,2,3,4,5')
        assert result.values == [1, 2, 3, 4, 5]
        assert all(isinstance(v, int) for v in result.values)

    def test_elist_from_str_floats(self):
        """Test EList.from_str with float values."""
        result = EList.from_str('1.5,2.5,3.5')
        assert result.values == [1.5, 2.5, 3.5]
        assert all(isinstance(v, float) for v in result.values)

    def test_elist_from_str_mixed_int_float(self):
        """Test EList.from_str with mixed integer and float values."""
        result = EList.from_str('1,2.5,3,4.5')
        assert result.values == [1, 2.5, 3, 4.5]
        assert isinstance(result.values[0], int)
        assert isinstance(result.values[1], float)

    def test_elist_from_str_single_value(self):
        """Test EList.from_str with a single value."""
        result = EList.from_str('42')
        assert result.values == [42]
        assert len(result) == 1

    def test_elist_from_str_negative_values(self):
        """Test EList.from_str with negative values."""
        result = EList.from_str('-1,-2.5,3,-4')
        assert result.values == [-1, -2.5, 3, -4]

    def test_elist_len(self):
        """Test EList __len__ method."""
        result = EList.from_str('1,2,3')
        assert len(result) == 3

    def test_elist_iter(self):
        """Test EList __iter__ method."""
        result = EList.from_str('10,20,30')
        values = list(result)
        assert values == [10, 20, 30]

    def test_elist_getitem(self):
        """Test EList __getitem__ method."""
        result = EList.from_str('10,20,30')
        assert result[0] == 10
        assert result[1] == 20
        assert result[2] == 30

    def test_elist_getitem_out_of_range(self):
        """Test EList __getitem__ raises IndexError for out-of-range index."""
        result = EList.from_str('1,2,3')
        with pytest.raises(IndexError, match='Index 5 out of range'):
            _ = result[5]

    def test_elist_getitem_negative_index(self):
        """Test EList __getitem__ raises IndexError for negative index."""
        result = EList.from_str('1,2,3')
        with pytest.raises(IndexError, match='Index -1 out of range'):
            _ = result[-1]

    def test_elist_str(self):
        """Test EList __str__ method."""
        result = EList.from_str('1,2,3')
        assert str(result) == '1,2,3'

    def test_elist_repr(self):
        """Test EList __repr__ method."""
        result = EList.from_str('1,2,3')
        assert repr(result) == 'EList(1,2,3)'

    def test_elist_equality(self):
        """Test EList __eq__ method."""
        list1 = EList.from_str('1,2,3')
        list2 = EList.from_str('1,2,3')
        list3 = EList.from_str('1,2,4')
        assert list1 == list2
        assert not (list1 == list3)

    def test_elist_in_parse_scan_parameters(self):
        """Test EList parsing via parse_scan_parameters."""
        result = parse_scan_parameters(['values=1,2,3,4'])
        assert 'values' in result
        assert isinstance(result['values'], EList)
        assert result['values'].values == [1, 2, 3, 4]

    def test_elist_space_separated_parsing(self):
        """Test EList parsing with space separation."""
        result = parse_scan_parameters(['values', '1,2,3'])
        assert 'values' in result
        assert isinstance(result['values'], EList)
        assert result['values'].values == [1, 2, 3]

    def test_elist_with_range_maximum_not_updated(self):
        """Test that EList values are not affected by range maximum."""
        result = parse_scan_parameters(['a=1:10', 'b=5,10,15'])
        assert isinstance(result['a'], MRange)
        assert isinstance(result['b'], EList)
        # EList values should remain unchanged
        assert result['b'].values == [5, 10, 15]
        assert len(result['b']) == 3

    def test_multiple_elists(self):
        """Test parsing multiple EList parameters."""
        result = parse_scan_parameters(['x=1,2,3', 'y=4,5,6'])
        assert isinstance(result['x'], EList)
        assert isinstance(result['y'], EList)
        assert result['x'].values == [1, 2, 3]
        assert result['y'].values == [4, 5, 6]

    def test_elist_with_large_precision_floats(self):
        """Test EList with high precision float values."""
        result = EList.from_str('0.123456789,0.987654321')
        assert result.values[0] == 0.123456789
        assert result.values[1] == 0.987654321

    def test_elist_scientific_notation(self):
        """Test EList with scientific notation values."""
        result = EList.from_str('1e-3,2.5e2,3e10')
        assert result.values == [1e-3, 2.5e2, 3e10]

    def test_elist_preserves_zero(self):
        """Test EList correctly handles zero values."""
        result = EList.from_str('0,1,0,2')
        assert result.values == [0, 1, 0, 2]
        assert result.values[0] == 0
        assert result.values[2] == 0

    def test_elist_with_singular_and_range(self):
        """Test combining EList with Singular and MRange."""
        result = parse_scan_parameters(['a=1:3', 'b=10', 'c=1.1,2.2,3.3'])
        assert isinstance(result['a'], MRange)
        assert isinstance(result['b'], Singular)
        assert isinstance(result['c'], EList)
        assert len(result['a']) == 3
        assert result['b'].value == 10
        assert result['c'].values == [1.1, 2.2, 3.3]

    def test_elist_direct_constructor(self):
        """Test EList direct construction with a list."""
        result = EList([1, 2, 3])
        assert result.values == [1, 2, 3]
        assert len(result) == 3

    def test_elist_direct_constructor_empty(self):
        """Test EList direct construction with an empty list."""
        result = EList([])
        assert result.values == []
        assert len(result) == 0

    def test_elist_long_list(self):
        """Test EList with a long list of values."""
        values_str = ','.join(str(i) for i in range(100))
        result = EList.from_str(values_str)
        assert len(result) == 100
        assert result.values == list(range(100))

    def test_elist_very_small_floats(self):
        """Test EList with very small float values."""
        result = EList.from_str('1e-10,1e-20,1e-30')
        assert result.values == [1e-10, 1e-20, 1e-30]

    def test_elist_very_large_floats(self):
        """Test EList with very large float values."""
        result = EList.from_str('1e10,1e20,1e30')
        assert result.values == [1e10, 1e20, 1e30]

    def test_elist_positive_explicit_sign(self):
        """Test EList with explicit positive signs."""
        result = EList.from_str('+1,+2.5,+3')
        assert result.values == [1, 2.5, 3]

    def test_elist_mixed_signs(self):
        """Test EList with mixed positive and negative values."""
        result = EList.from_str('-1,+2,-3.5,+4.5')
        assert result.values == [-1, 2, -3.5, 4.5]

    def test_elist_equality_different_lengths(self):
        """Test EList equality with different lengths raises error."""
        list1 = EList.from_str('1,2,3')
        list2 = EList.from_str('1,2')
        with pytest.raises(ValueError):
            _ = list1 == list2

    def test_elist_iteration_multiple_times(self):
        """Test that EList can be iterated multiple times."""
        result = EList.from_str('1,2,3')
        first_pass = list(result)
        second_pass = list(result)
        assert first_pass == second_pass == [1, 2, 3]

    def test_elist_sum_of_values(self):
        """Test that EList works with built-in sum function."""
        result = EList.from_str('1,2,3,4,5')
        assert sum(result) == 15

    def test_elist_in_list_comprehension(self):
        """Test EList in list comprehension."""
        result = EList.from_str('1,2,3')
        doubled = [v * 2 for v in result]
        assert doubled == [2, 4, 6]

    def test_elist_float_str_roundtrip(self):
        """Test that float values survive str conversion roundtrip."""
        original = EList.from_str('1.5,2.5,3.5')
        roundtrip = EList.from_str(str(original))
        assert original == roundtrip

    def test_elist_int_str_roundtrip(self):
        """Test that integer values survive str conversion roundtrip."""
        original = EList.from_str('1,2,3')
        roundtrip = EList.from_str(str(original))
        assert original == roundtrip

    def test_elist_two_values(self):
        """Test EList with exactly two values."""
        result = EList.from_str('10,20')
        assert result.values == [10, 20]
        assert len(result) == 2

    def test_elist_getitem_last_element(self):
        """Test EList __getitem__ with index of last element."""
        result = EList.from_str('10,20,30')
        assert result[2] == 30

    def test_elist_negative_scientific_notation(self):
        """Test EList with negative values in scientific notation."""
        result = EList.from_str('-1e-3,-2.5e2,-3e10')
        assert result.values == [-1e-3, -2.5e2, -3e10]


class TestRangeProperties:
    def test_mrange_properties(self):
        r = MRange.from_str('1:0.1:10')
        assert r.min == 1
        assert r.max == 10

        r = MRange.from_str('10:-0.5:1')
        assert r.min == 10
        assert r.max == 1

    def test_singular_properties(self):
        r = Singular.from_str('100')
        assert r.min == 100
        assert r.max == 100

    def test_elist_properties(self):
        r = EList.from_str('1,2,3')
        assert r.min == 1
        assert r.max == 3


class TestParametersToScan:
    """Tests for the parameters_to_scan function."""

    def test_empty_parameters(self):
        """Test parameters_to_scan with empty dictionary."""
        n_pts, names, values = parameters_to_scan({})
        assert n_pts == 0
        assert names == []
        assert list(values) == []

    def test_single_mrange_linear(self):
        """Test parameters_to_scan with a single MRange in linear mode."""
        params = {'a': MRange(1, 5, 1)}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 5
        assert names == ['a']
        values_list = list(values)
        assert values_list == [(1,), (2,), (3,), (4,), (5,)]

    def test_single_elist_linear(self):
        """Test parameters_to_scan with a single EList in linear mode."""
        params = {'a': EList([10, 20, 30])}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        assert names == ['a']
        values_list = list(values)
        assert values_list == [(10,), (20,), (30,)]

    def test_single_singular_linear(self):
        """Test parameters_to_scan with a single Singular in linear mode."""
        params = {'a': Singular(42, 3)}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        assert names == ['a']
        values_list = list(values)
        assert values_list == [(42,), (42,), (42,)]

    def test_multiple_mranges_linear_same_length(self):
        """Test parameters_to_scan with multiple MRanges of same length in linear mode."""
        params = {'a': MRange(1, 3, 1), 'b': MRange(10, 30, 10)}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        assert 'a' in names
        assert 'b' in names
        values_list = list(values)
        assert len(values_list) == 3
        assert values_list == [(1, 10), (2, 20), (3, 30)]

    def test_mrange_and_elist_linear_same_length(self):
        """Test parameters_to_scan with MRange and EList of same length."""
        params = {'a': MRange(1, 3, 1), 'b': EList([10, 200, 3000])}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        values_list = list(values)
        assert len(values_list) == 3
        assert values_list == [(1, 10), (2, 200), (3, 3000)]

    def test_mrange_with_singular_linear(self):
        """Test parameters_to_scan with MRange and Singular in linear mode."""
        params = {'a': MRange(1, 5, 1), 'b': Singular(99, 5)}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 5
        values_list = list(values)
        assert len(values_list) == 5
        # All b values should be 99
        a_idx = names.index('a')
        b_idx = names.index('b')
        for v in values_list:
            assert v[b_idx] == 99

    def test_elist_with_singular_linear(self):
        """Test parameters_to_scan with EList and Singular in linear mode."""
        params = {'a': EList([1, 2, 3]), 'b': Singular(42, 3)}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        values_list = list(values)
        a_idx = names.index('a')
        b_idx = names.index('b')
        assert [v[a_idx] for v in values_list] == [1, 2, 3]
        assert [v[b_idx] for v in values_list] == [42, 42, 42]

    def test_mismatched_lengths_raises_error(self):
        """Test that mismatched lengths raise ValueError."""
        params = {'a': MRange(1, 5, 1), 'b': MRange(1, 3, 1)}
        with pytest.raises(ValueError, match='has 3 values'):
            parameters_to_scan(params)

    def test_elist_mrange_mismatched_lengths_raises_error(self):
        """Test that mismatched EList and MRange lengths raise ValueError."""
        params = {'a': MRange(1, 5, 1), 'b': EList([10, 20])}
        with pytest.raises(ValueError, match='has 2 values'):
            parameters_to_scan(params)

    def test_grid_mode_single_mrange(self):
        """Test parameters_to_scan with single MRange in grid mode."""
        params = {'a': MRange(1, 3, 1)}
        n_pts, names, values = parameters_to_scan(params, grid=True)
        assert n_pts == 3
        assert names == ['a']
        values_list = list(values)
        assert values_list == [(1,), (2,), (3,)]

    def test_grid_mode_single_elist(self):
        """Test parameters_to_scan with single EList in grid mode."""
        params = {'a': EList([10, 20, 30])}
        n_pts, names, values = parameters_to_scan(params, grid=True)
        assert n_pts == 3
        values_list = list(values)
        assert values_list == [(10,), (20,), (30,)]

    def test_grid_mode_multiple_mranges(self):
        """Test parameters_to_scan with multiple MRanges in grid mode."""
        params = {'a': MRange(1, 2, 1), 'b': MRange(10, 20, 10)}
        n_pts, names, values = parameters_to_scan(params, grid=True)
        # 2 * 2 = 4 grid points
        assert n_pts == 4
        values_list = list(values)
        assert len(values_list) == 4

    def test_grid_mode_mrange_and_elist(self):
        """Test parameters_to_scan with MRange and EList in grid mode."""
        params = {'a': MRange(1, 2, 1), 'b': EList([100, 200])}
        n_pts, names, values = parameters_to_scan(params, grid=True)
        # 2 * 2 = 4 grid points
        assert n_pts == 4
        values_list = list(values)
        assert len(values_list) == 4

    def test_grid_mode_with_singular(self):
        """Test parameters_to_scan with Singular in grid mode."""
        params = {'a': MRange(1, 2, 1), 'b': Singular(99)}
        n_pts, names, values = parameters_to_scan(params, grid=True)
        # 2 * 1 = 2 grid points (singular has maximum=1 in grid mode)
        assert n_pts == 2
        values_list = list(values)
        assert len(values_list) == 2

    def test_names_are_lowercased(self):
        """Test that parameter names are lowercased."""
        params = {'MyParam': MRange(1, 3, 1), 'ANOTHER': EList([1, 2, 3])}
        n_pts, names, values = parameters_to_scan(params)
        assert 'myparam' in names
        assert 'another' in names

    def test_list_input_as_parameter(self):
        """Test parameters_to_scan with plain list as parameter value."""
        params = {'a': [1, 2, 3]}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        values_list = list(values)
        assert len(values_list) == 3

    def test_grid_mode_three_parameters(self):
        """Test grid mode with three parameters."""
        params = {'a': MRange(1, 2, 1), 'b': MRange(10, 20, 10), 'c': EList([100, 200])}
        n_pts, names, values = parameters_to_scan(params, grid=True)
        # 2 * 2 * 2 = 8 grid points
        assert n_pts == 8
        values_list = list(values)
        assert len(values_list) == 8

    def test_linear_mode_preserves_order(self):
        """Test that linear mode preserves iteration order."""
        params = {'a': MRange(1, 3, 1), 'b': EList([10, 20, 30])}
        n_pts, names, values = parameters_to_scan(params)
        values_list = list(values)
        a_idx = names.index('a')
        b_idx = names.index('b')
        assert [v[a_idx] for v in values_list] == [1, 2, 3]
        assert [v[b_idx] for v in values_list] == [10, 20, 30]

    def test_elist_only_parameters_linear(self):
        """Test parameters_to_scan with only EList parameters in linear mode."""
        params = {'x': EList([1, 2, 3]), 'y': EList([10, 20, 30])}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        values_list = list(values)
        assert len(values_list) == 3

    def test_elist_only_parameters_grid(self):
        """Test parameters_to_scan with only EList parameters in grid mode."""
        params = {'x': EList([1, 2]), 'y': EList([10, 20, 30])}
        n_pts, names, values = parameters_to_scan(params, grid=True)
        # 2 * 3 = 6 grid points
        assert n_pts == 6
        values_list = list(values)
        assert len(values_list) == 6

    def test_float_values_in_elist(self):
        """Test parameters_to_scan with float values in EList."""
        params = {'a': EList([1.5, 2.5, 3.5])}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        values_list = list(values)
        assert values_list == [(1.5,), (2.5,), (3.5,)]

    def test_mixed_int_float_in_elist(self):
        """Test parameters_to_scan with mixed int and float in EList."""
        params = {'a': EList([1, 2.5, 3])}
        n_pts, names, values = parameters_to_scan(params)
        assert n_pts == 3
        values_list = list(values)
        assert values_list == [(1,), (2.5,), (3,)]

    def test_singular_infinite_range(self):
        params = {'a': Singular(1), 'b': EList([10, 20, 30])}
        n_pts, names, values = parameters_to_scan(params)
        values_list = list(values)
        a_idx = names.index('a')
        b_idx = names.index('b')
        assert [v[a_idx] for v in values_list] == [1, 1, 1]
        assert [v[b_idx] for v in values_list] == [10, 20, 30]