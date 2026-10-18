"""A component's CATEGORY may be a bare name or a quoted string."""
import pytest

from mccode_antlr.comp import Comp


@pytest.mark.parametrize('category', ['samples', '"samples"'])
def test_category_is_read_either_way(category):
    source = f'DEFINE COMPONENT T\nSETTING PARAMETERS ()\nCATEGORY {category}\nEND\n'
    assert Comp.from_source(None, None, source).category == 'samples'
