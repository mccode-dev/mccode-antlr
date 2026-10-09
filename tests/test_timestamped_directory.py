"""Default output directories get a number appended if they already exist."""
from mccode_antlr.run.runner import timestamped_directory


def test_existing_directories_are_not_reused(tmp_path):
    first = timestamped_directory(tmp_path, 'instr')
    assert first.parent == tmp_path and first.name.startswith('instr')
    first.mkdir()
    second = timestamped_directory(tmp_path, 'instr')
    if second.name.startswith(first.name):  # (else the second has passed)
        assert second.name == first.name + '_1'
    second.mkdir()
    assert timestamped_directory(tmp_path, 'instr') not in (first, second)
