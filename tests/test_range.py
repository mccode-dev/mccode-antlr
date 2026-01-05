import pytest
from mccode_antlr.run.range import MRange, EList, Singular, parse_scan_parameters


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
